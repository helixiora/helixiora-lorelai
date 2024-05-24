"""Contains the Processor class that processes and indexes them in Pinecone."""

import logging
import os
import uuid
from typing import Iterable

import numpy as np
import pinecone
from google.oauth2.credentials import Credentials
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_google_community.drive import GoogleDriveLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import ServerlessSpec

from lorelai.utils import (
    get_embedding_dimension,
    load_config,
    pinecone_index_name,
    save_google_creds_to_tempfile,
)


class Processor:
    """This class is used to process the Google Drive documents and index them in Pinecone."""

    def __init__(self):
        """Initialize the Processor class."""
        self.pinecone_settings = load_config("pinecone")
        self.openai_creds = load_config("openai")
        self.lorelai_settings = load_config("lorelai")

        self.pinecone_api_key = self.pinecone_settings["api_key"]
        self.openai_api_key = self.openai_creds["api_key"]
        # set env variable with openai api key
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["PINECONE_API_KEY"] = self.pinecone_api_key

    def pinecone_filter_deduplicate_documents_list(
        self, formatted_documents: Iterable[Document], pc_index
    ) -> list:
        """Process the vectors and removes vector which exist in database.

        Also tag doc metadata with new user

        :param documents: the documents to process
        :param pc_index: pinecone index object

        :return:1. (list of documents deduplicated and filtered , ready to be inserted in pinecone)
                2. (number of documents tagged with current user)
                3. (number of document already exist and tagged by current user)
        """
        documents = formatted_documents.copy()
        logging.info(f"Checking {len(documents)} documents for duplicates in Pinecone index")
        tagged_existing_doc_with_user = 0
        already_exist_and_tagged = 0
        # Check if docs exist in pinecone.
        for doc in documents[:]:
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
                    if doc["metadata"]["users"][0] in result["matches"][0]["metadata"]["users"]:
                        logging.info(
                            f"Document {doc['metadata']['title']} already exists in Pinecone and tagged by {doc['metadata']['users'][0]}"
                        )
                        # if so then we remove doc form the document list
                        documents.remove(doc)
                        already_exist_and_tagged += 1

                    # if doc is not tagged for user, then we update the meta data
                    # to include this user and we remove the doc.
                    else:
                        users_list = (
                            result["matches"][0]["metadata"]["users"] + doc["metadata"]["users"]
                        )
                        logging.info(f"Tagging {doc['metadata']['title']} with {users_list}")
                        logging.info(f"Tagging {doc['metadata']['title']} with {users_list}")
                        pc_index.update(
                            id=result["matches"][0]["id"],
                            set_metadata={"users": users_list},
                        )
                        documents.remove(doc)
                        tagged_existing_doc_with_user += 1
        logging.info("Completed Deduplication")
        return documents, tagged_existing_doc_with_user, already_exist_and_tagged

    def pinecone_format_vectors(
        self, documents: Iterable[Document], embeddings_model: Embeddings
    ) -> list:
        """process the documents and format them for pinecone insert.

        :param docs: the documents to process
        :param embeddings_model: embeddings_model object

        :return: list of documents ready to be inserted in pinecone
        """
        logging.info(f"Formating {len(documents)}Chunked docs to Pinecone format")
        # Get Text
        text_docs = []
        for doc in documents:
            texts = doc.page_content.replace("\n", " ").replace("\r", " ")
            text_docs.append(texts)
        embeds = embeddings_model.embed_documents(text_docs)

        # prepare pinecone vectors
        formatted_documents = []
        logging.info(
            f" Number documents {len(documents)} == Number embeds {len(embeds)} == {len(embeds)==len(documents)}"
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
        self, formatted_documents, pc_index, embedding_dimension, user_email
    ):
        """Delete document which user no longer has access to from Pinecone

        :param formatted_documents: document user currently have access to
        :param pc_index: pinecone index object
        :param embedding_dimension: embedding model dimension

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
            filter={"users": {"$eq": user_email}},
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
            # add ids to source key, some source can have many vector becuase of chuncking
            db_vector_dict[i["metadata"]["source"]]["ids"] = db_vector_dict[
                i["metadata"]["source"]
            ]["ids"] + [i["id"]]

        logging.info(f"Google document in pinecone {len(db_vector_dict)}")
        # Compare current doc list accessible by user to the doc in the db.
        # only keep which is not accessible by user
        logging.info(f"FORMATED DOC SIZE {len(formatted_documents)}")
        for doc in formatted_documents:
            if doc["metadata"]["source"] in db_vector_dict:
                logging.debug(f'{doc["metadata"]["source"]} already in pinecone index')
                logging.debug(f"Size before {len(db_vector_dict)}")
                db_vector_dict.pop(doc["metadata"]["source"])
                logging.debug(f"Size after {len(db_vector_dict)}")
        delete_vector_ids_list = []
        delete_vector_title_list = []
        for key in db_vector_dict:
            logging.info(f'{user_email} does not have access to {db_vector_dict[key]["title"]}')
            # if document have 2 users in metadata, then remove only 1 user
            if len(db_vector_dict[key]["users"]) >= 2:
                new_user_list = db_vector_dict[key]["users"]
                new_user_list.remove(user_email)
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

        logging.info(
            f"Deleting following document from pinecone :\n{delete_vector_title_list}\nSize:{len(delete_vector_title_list)}\n as no users have access to these documents"
        )
        if delete_vector_ids_list:
            pc_index.delete(ids=delete_vector_ids_list)
            count_deleted = len(delete_vector_ids_list)
        # store ids of doc in db to be delete as user does not have access
        return count_updated, count_deleted

    def store_docs_in_pinecone(self, docs: Iterable[Document], index_name, user_email) -> None:
        """process the documents and index them in Pinecone

        :param docs: the documents to process
        :param index_name: name of index
        :param user_email: the user to process
        """
        logging.info(f"Processing {len(docs)} Google documents for user: {user_email}")

        splitter = RecursiveCharacterTextSplitter(chunk_size=4000)
        # Iterate over documents and split each document's text into chunks
        # for doc_id, document_content in documents.items():
        documents = splitter.split_documents(docs)
        logging.info(f"Converted {len(docs)}Google Docs into {len(documents)} Chucks")
        # use text-embedding-ada-002
        embedding_model_name = "text-embedding-ada-002"
        embedding_model = OpenAIEmbeddings(model=embedding_model_name)
        embedding_dimension = get_embedding_dimension(embedding_model_name)
        if embedding_dimension == -1:
            raise ValueError(f"Could not find embedding dimension for model '{embedding_model}'")

        pc = pinecone.Pinecone(api_key=self.pinecone_api_key)

        region = self.pinecone_settings["region"]

        # somehow the PineconeVectorStore doesn't support creating a new index, so we use pinecone
        # package directly. Check if the index already exists
        if index_name not in pc.list_indexes().names():
            # Create a new index
            pc.create_index(
                name=index_name,
                dimension=embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=region),
            )
            logging.debug(f"Created new Pinecone index {index_name}")
        else:
            logging.debug(f"Pinecone index {index_name} already exists")

        logging.info(
            f"Indexing {len(documents)} documents in Pinecone index {index_name} using:embedding_model:{embedding_model_name}"
        )

        pc_index = pc.Index(index_name)

        # Format the document for insertion
        formatted_documents = self.pinecone_format_vectors(documents, embedding_model)
        filtered_documents, tagged_existing_doc_with_user, already_exist_and_tagged = (
            self.pinecone_filter_deduplicate_documents_list(formatted_documents, pc_index)
        )

        count_removed_access, count_deleted = self.remove_nolonger_accessed_documents(
            formatted_documents, pc_index, embedding_dimension, user_email
        )

        # inserting  the documents
        if filtered_documents:
            pc_index.upsert(filtered_documents)
        logging.info(f"Total Number of Google Docs {len(docs)}")
        logging.info(f"Total Number of documents, ie after chucking {len(documents)}")
        logging.info(
            f"{already_exist_and_tagged} documents  already exist and tagged in index {index_name}"
        )
        logging.info(
            f"Added user tag to {tagged_existing_doc_with_user} documents which already exist in index {index_name}"
        )
        logging.info(f"removed user tag to {count_removed_access} documents in index {index_name}")
        logging.info(f"Deleted {count_deleted} documents in Pinecone index {index_name}")

        logging.info(f"Added {len(filtered_documents)} new documents in index {index_name}")

    def google_docs_to_pinecone_docs(
        self: None,
        document_ids: list[str],
        credentials: Credentials,
        org_name: str,
        user_email: str,
    ) -> None:
        """Process the Google Drive documents and divide them into pinecone compatible chunks.

        :param document_id: the document to process
        :param credentials: the credentials to use to process the document
        :param org: the organisation to process
        :param user: the user to process

        :return: None
        """
        # save the google creds to a tempfile as they are needed by the langchain google drive
        # loader until this issue is fixed: https://github.com/langchain-ai/langchain/issues/15058
        save_google_creds_to_tempfile(
            refresh_token=credentials.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
        )

        drive_loader = GoogleDriveLoader(document_ids=document_ids)

        logging.info(f"Processing {len(document_ids)} google documents for user: {user_email}")
        docs = drive_loader.load()
        logging.debug(f"Loaded {len(docs)} documents from Google Drive")

        # go through all docs. For each doc, see if the user is already in the metadata. If not,
        # add the user to the metadata
        for doc in docs:
            logging.info(f"Processing doc: {doc.metadata['title']}")
            # check if the user key is in the metadata
            if "users" not in doc.metadata:
                doc.metadata["users"] = []
            # check if the user is in the metadata
            if user_email not in doc.metadata["users"]:
                logging.info(
                    f"Adding user {user_email} to doc.metadata['users'] for \
                    metadata.users ${doc.metadata['users']}"
                )
                doc.metadata["users"].append(user_email)

        # indexname must consist of lower case alphanumeric characters or '-'"
        index_name = pinecone_index_name(
            org=org_name,
            datasource="googledrive",
            environment=self.lorelai_settings["environment"],
            env_name=self.lorelai_settings["environment_slug"],
            version="v1",
        )
        self.store_docs_in_pinecone(docs, index_name=index_name, user_email=user_email)
        logging.info(f"Processed {len(docs)} documents for user: {user_email}")
