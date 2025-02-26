"""Contains the Processor class that processes and indexes them in Pinecone."""

from flask import current_app
import itertools
import logging
import os
import uuid
from collections.abc import Iterable

import numpy as np

import pinecone

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from lorelai.utils import (
    get_embedding_dimension,
    clean_text_for_vector,
    batch_embed_langchain_documents,
)
from lorelai.pinecone import PineconeHelper

from app.schemas import IndexingRunSchema


class Processor:
    """Used to process the langchain documents and index them in Pinecone."""

    def __init__(self):
        """Initialize the Processor class."""
        # needed for the openai embeddings model
        os.environ["OPENAI_API_KEY"] = current_app.config["OPENAI_API_KEY"]
        os.environ["PINECONE_API_KEY"] = current_app.config["PINECONE_API_KEY"]

        # Initialize PineconeHelper
        self.pinecone_helper = PineconeHelper()

    def pinecone_filter_deduplicate_documents_list(
        self,
        formatted_documents: Iterable[Document],
        pc_index: pinecone.Index,
        indexing_run: IndexingRunSchema,
    ) -> list:
        """Process the vectors and removes vector which exist in database.

        Also tag doc metadata with new user

        :param documents: the documents to process
        :param pc_index: pinecone index object

        :return:1. (list of documents deduplicated and filtered , ready to be inserted in pinecone)
                2. (number of documents tagged with current user)
                3. (number of document already exist and tagged by current user)
        """
        # Create a new list from the iterable to avoid modifying it while iterating
        documents = list(formatted_documents)
        logging.info(
            f"Checking {len(documents)} docs for dupes in Pinecone for: {indexing_run.user.email}"
        )
        tagged_existing_doc_with_user = 0
        already_exist_and_tagged = 0
        # Check if docs exist in pinecone.
        # Create a list to store documents to remove to avoid modifying list during iteration
        docs_to_remove = []
        for doc in documents:
            # doc["metadata"]["users"]=["newuser.com"]
            result = pc_index.query(
                vector=doc["values"],
                top_k=1,
                include_metadata=True,
                filter={"source": doc["metadata"]["source"]},
            )
            # Check if we got matches from query result
            if len(result["matches"]) > 0:
                # Check if the vector is already in the database
                if (
                    result["matches"][0]["score"] >= 0.99
                    and result["matches"][0]["metadata"]["source"] == doc["metadata"]["source"]
                ):
                    # Check if doc already tag for this users
                    if indexing_run.user.email in result["matches"][0]["metadata"]["users"]:
                        logging.debug(
                            f"Document {doc['metadata']['title']} already exists in Pinecone and \
tagged by {indexing_run.user.email}, removing from list"
                        )
                        # Mark document for removal
                        docs_to_remove.append(doc)
                        already_exist_and_tagged += 1

                    # if doc is not tagged for user, then we update the meta data
                    # to include this user and we remove the doc.
                    else:
                        users_list = result["matches"][0]["metadata"]["users"] + [
                            indexing_run.user.email
                        ]
                        logging.info(f"Tagging {doc['metadata']['title']} with {users_list}")
                        pc_index.update(
                            id=result["matches"][0]["id"],
                            set_metadata={"users": users_list},
                        )
                        docs_to_remove.append(doc)
                        tagged_existing_doc_with_user += 1

        logging.debug(f"Number of docs to remove because they already exist: {len(docs_to_remove)}")
        # Remove documents after iteration is complete
        for doc in docs_to_remove:
            documents.remove(doc)

        logging.info("Completed Deduplication")
        return documents, tagged_existing_doc_with_user, already_exist_and_tagged

    def pinecone_format_vectors(
        self,
        documents: Iterable[Document],
        embeddings_model: Embeddings,
        indexing_run: IndexingRunSchema,
    ) -> list:
        """Process the documents and format them for pinecone insert.

        :param docs: the documents to process
        :param embeddings_model: embeddings_model object

        :return: list of documents ready to be inserted in pinecone
        """
        logging.info(
            f"Formatting {len(documents)} chunked docs to Pinecone format for user: \
{indexing_run.user.email} indexing run: {indexing_run.id}"
        )
        # Get Text
        text_docs = []
        for doc in documents:
            texts = doc.page_content
            texts = f"Documents Title: {doc.metadata['title']}: {texts}"
            texts = clean_text_for_vector(texts)
            text_docs.append(texts)

        try:
            embeds = batch_embed_langchain_documents(embeddings_model, text_docs, batch_size=100)
        except Exception as e:
            logging.error(f"Failed to generate embeddings for documents: {str(e)}")
            raise ValueError(f"Failed to generate embeddings: {str(e)}") from e

        # prepare pinecone vectors
        formatted_documents = []
        logging.info(
            f" Number documents {len(documents)} == Number embeds {len(embeds)} \
                == {len(embeds) == len(documents)}"
        )
        if len(documents) != len(embeds):
            raise ValueError("Embeds length and document length mismatch")

        for i in range(len(documents)):
            temp_dict = {
                "id": str(uuid.uuid4()),
                "values": embeds[i],
                "metadata": documents[i].metadata,
            }

            temp_dict["metadata"]["text"] = text_docs[i]
            formatted_documents.append(temp_dict)
        if len(formatted_documents) != len(documents):
            logging.error("Formatted Doc not equal documents")
            raise ValueError
        logging.info(f"Formatted {len(formatted_documents)} documents for pinecone index")
        return formatted_documents

    def remove_nolonger_accessed_documents(
        self,
        formatted_documents: list[dict[str, any]],
        pc_index: pinecone.Index,
        embedding_dimension: int,
        indexing_run: IndexingRunSchema,
    ):
        """Delete document which user no longer has access to from Pinecone.

        Arguments
        ---------
            :param formatted_documents: document user currently have access to
            :param pc_index: pinecone index object
            :param embedding_dimension: embedding model dimension

        Returns
        -------
            :return: None

        """
        logging.info("Removing docs which user doesn't have access to.")
        count_updated = 0
        count_deleted = 0
        input_vector = np.random.rand(embedding_dimension).tolist()
        result = pc_index.query(
            vector=input_vector,
            top_k=10000,
            include_metadata=True,
            include_values=False,
            filter={"users": {"$eq": indexing_run.user.email}},
        )

        # This dict contains all doc accessed by this user in db.
        # mapping = {source:{ids:[],users:[]}}
        db_vector_dict = {}
        for i in result["matches"]:
            if i["metadata"]["source"] not in db_vector_dict:
                db_vector_dict[i["metadata"]["source"]] = {
                    "ids": [i["id"]],
                    "users": i["metadata"]["users"],
                    "title": i["metadata"]["title"],
                }
                continue
            # add ids to source key, some source can have many vector because of chunking
            db_vector_dict[i["metadata"]["source"]]["ids"] = db_vector_dict[
                i["metadata"]["source"]
            ]["ids"] + [i["id"]]

        logging.info(
            f"Documents in pinecone {len(db_vector_dict)} for user: {indexing_run.user.email} \
indexing run: {indexing_run.id}"
        )
        # Compare current doc list accessible by user to the doc in the db.
        # only keep which is not accessible by user
        logging.info(f"FORMATTED DOC SIZE {len(formatted_documents)}")
        for doc in formatted_documents:
            if doc["metadata"]["source"] in db_vector_dict:
                logging.debug(
                    f"{doc['metadata']['source']} already in pinecone index for user: \
{indexing_run.user.email} indexing run: {indexing_run.id}"
                )
                logging.debug(f"Size before {len(db_vector_dict)}")
                db_vector_dict.pop(doc["metadata"]["source"])
                logging.debug(f"Size after {len(db_vector_dict)}")
        delete_vector_ids_list = []
        delete_vector_title_list = []
        for key in db_vector_dict:
            logging.info(
                f"{indexing_run.user.email} does not have access to {db_vector_dict[key]['title']}"
            )
            # if document have 2 users in metadata, then remove only 1 user
            if len(db_vector_dict[key]["users"]) >= 2:
                new_user_list = db_vector_dict[key]["users"]
                new_user_list.remove(indexing_run.user.email)
                logging.info("Removing access without deleting docs from Pinecone")
                for id in db_vector_dict[key]["ids"]:
                    pc_index.update(
                        id=id,
                        set_metadata={"users": new_user_list},
                    )
                    count_updated += 1
            # else remove the document it self as no user have access
            else:
                delete_vector_ids_list = delete_vector_ids_list + db_vector_dict[key]["ids"]
                delete_vector_title_list.append(db_vector_dict[key]["title"])

        if delete_vector_ids_list and len(delete_vector_ids_list) > 0:
            logging.info(
                f"Deleting following document from pinecone :\n \
                    {delete_vector_title_list}\n \
                    Size:{len(delete_vector_title_list)}\n \
                    as no users have access to these documents"
            )
            pc_index.delete(ids=delete_vector_ids_list)
            count_deleted = len(delete_vector_ids_list)
        else:
            count_deleted = 0
            logging.info(
                "No document to delete from pinecone for user: {indexing_run.user.email} indexing \
run: {indexing_run.id}"
            )
        # store ids of doc in db to be delete as user does not have access
        return count_updated, count_deleted

    def store_docs_in_pinecone(
        self,
        docs: Iterable[Document],
        indexing_run: IndexingRunSchema,
    ) -> int:
        """Process the documents and index them in Pinecone.

        Arguments
        ---------
            :param docs: the langchain documents to process
            :param indexing_run: the indexing run to store the documents for

        Returns
        -------
            :return: the number of new documents added to Pinecone
        """

        def chunks(iterable, batch_size=100):
            """Break an iterable into chunks of size batch_size."""
            it = iter(iterable)
            chunk = tuple(itertools.islice(it, batch_size))
            while chunk:
                yield chunk
                chunk = tuple(itertools.islice(it, batch_size))

        if not docs:
            logging.warning("No documents to store in Pinecone")
            return 0

        logging.info(f"Storing {len(docs)} documents for user: {indexing_run.user.email}")

        chunk_size = current_app.config["EMBEDDINGS_CHUNK_SIZE"]
        embedding_model_name = current_app.config["EMBEDDINGS_MODEL"]
        logging.debug(f"Using chunk size: {chunk_size} and embedding model: {embedding_model_name}")

        splitter = RecursiveCharacterTextSplitter(chunk_size=int(chunk_size))

        # Iterate over documents and split each document's text into chunks
        document_chunks = splitter.split_documents(docs)
        logging.info(f"Converted {len(docs)} docs into {len(document_chunks)} Chunks")

        embedding_model = OpenAIEmbeddings(model=embedding_model_name)
        embedding_dimension = get_embedding_dimension(embedding_model_name)
        if embedding_dimension == -1:
            raise ValueError(f"Could not find embedding dimension for model '{embedding_model}'")

        # get the pinecone index
        pc_index, index_name = self.pinecone_helper.get_index(
            org_name=indexing_run.organisation.name,
            datasource=indexing_run.datasource.datasource_name,
            environment=current_app.config["LORELAI_ENVIRONMENT"],
            environment_slug=current_app.config["LORELAI_ENVIRONMENT_SLUG"],
            version="v1",
            create_if_not_exists=True,
        )

        logging.info(
            f"Indexing {len(document_chunks)} documents in Pinecone index {index_name} \
using embedding_model:{embedding_model_name}"
        )

        # Format the document for insertion
        formatted_document_chunks = self.pinecone_format_vectors(
            document_chunks, embedding_model, indexing_run
        )
        filtered_document_chunks, tagged_existing_doc_with_user, already_exist_and_tagged = (
            self.pinecone_filter_deduplicate_documents_list(
                formatted_document_chunks, pc_index, indexing_run
            )
        )

        count_removed_access, count_deleted = self.remove_nolonger_accessed_documents(
            formatted_document_chunks, pc_index, embedding_dimension, indexing_run
        )

        # inserting the documents
        if filtered_document_chunks:
            logging.info(
                f"Inserting {len(filtered_document_chunks)} documents in Pinecone {index_name} for \
user: {indexing_run.user.email} indexing run: {indexing_run.id}"
            )
            for chunk in chunks(filtered_document_chunks, 50):
                response = pc_index.upsert(vectors=chunk)
                logging.debug(f"Upsert response: {response}")

        logging.info(f"Total Number of langchain documents {len(docs)}")
        logging.info(f"Total Number of document chunks, ie after chunking {len(document_chunks)}")
        logging.info(
            f"{already_exist_and_tagged} documents already exist / tagged in index {index_name}"
        )
        logging.info(
            f"Added user tag to {tagged_existing_doc_with_user} documents which already exist \
in index {index_name} for user: {indexing_run.user.email} indexing run: {indexing_run.id}"
        )
        logging.info(f"removed user tag to {count_removed_access} documents in index {index_name}")
        logging.info(f"Deleted {count_deleted} documents in Pinecone index {index_name}")
        logging.info(
            f"Added {len(filtered_document_chunks)} new document chunks in index {index_name} for \
user: {indexing_run.user.email} indexing run: {indexing_run.id}"
        )

        return len(filtered_document_chunks)
