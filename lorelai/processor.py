"""This module contains the Processor class that processes documents and indexes them in Pinecone
"""
import os
from typing import Iterable, List

import pinecone
from google.oauth2.credentials import Credentials
from langchain_community.document_loaders.googledrive import GoogleDriveLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import ServerlessSpec

from lorelai.utils import (get_embedding_dimension, load_config, pinecone_index_name,
                           save_google_creds_to_tempfile)


class Processor:
    """This class is used to process the Google Drive documents and index them in Pinecone
    """

    def __init__(self):
        """initializes the Processor class
        """

        self.pinecone_creds = load_config('pinecone')
        self.openai_creds = load_config('openai')
        self.lorelai_settings = load_config('lorelai')

        self.pinecone_api_key = self.pinecone_creds['api-key']
        self.openai_api_key = self.openai_creds['api-key']
        # set env variable with openai api key
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["PINECONE_API_KEY"] = self.pinecone_api_key

    def store_docs_in_pinecone(self, docs: Iterable[Document], index_name) -> None:
        """process the documents and index them in Pinecone

        :param docs: the documents to process
        :param organisation: the organisation to process
        :param datasource: the datasource to process
        :param user: the user to process
        """
        splitter = RecursiveCharacterTextSplitter(chunk_size=4000)
        # Iterate over documents and split each document's text into chunks
        # for doc_id, document_content in documents.items():
        documents = splitter.split_documents(docs)

        # use text-embedding-ada-002
        embedding_model = 'text-embedding-ada-002'
        embeddings = OpenAIEmbeddings(model=embedding_model)
        embedding_dimension = get_embedding_dimension(embedding_model)
        if embedding_dimension == -1:
            raise ValueError(f"Could not find embedding dimension for model '{embedding_model}'")

        pc = pinecone.Pinecone(api_key=self.pinecone_api_key)

        # somehow the PineconeVectorStore doesn't support creating a new index, so we use pinecone
        # package directly. Check if the index already exists
        if index_name not in pc.list_indexes().names():
            # Create a new index
            pc.create_index(name=index_name,
                            dimension=embedding_dimension,
                            metric='cosine',
                            spec=ServerlessSpec(
                                cloud='aws',
                                region='us-west-2'
                            ))
            print(f"Created new Pinecone index {index_name}")
        else:
            print(f"Pinecone index {index_name} already exists")

        print(f"Indexing {len(documents)} documents in Pinecone index {index_name}")

        vector_store = PineconeVectorStore(pinecone_api_key=self.pinecone_api_key,
                                           index_name=index_name, embedding=embeddings)

        #TODO: subsequent runs should update, not add/duplicate # pylint: disable=fixme
        vector_store.from_documents(documents,
                                            embeddings,
                                            index_name=index_name)

        print(f"Indexed {len(documents)} documents in Pinecone index {index_name}")

    def google_docs_to_pinecone_docs(self, document_ids: List[str], credentials: Credentials,
                                     org_name: str, user_email: str):
        """process the Google Drive documents and divide them into pinecone compatible chunks

        :param document_id: the document to process
        :param credentials: the credentials to use to process the document
        :param org: the organisation to process
        :param user: the user to process

        :return: None
        """
        # save the google creds to a tempfile as they are needed by the langchain google drive
        # loader until this issue is fixed: https://github.com/langchain-ai/langchain/issues/15058
        save_google_creds_to_tempfile(refresh_token=credentials.refresh_token,
                                           token_uri="https://oauth2.googleapis.com/token",
                                           client_id=credentials.client_id,
                                           client_secret=credentials.client_secret)

        drive_loader = GoogleDriveLoader(document_ids=document_ids)

        print(f"Processing document: {document_ids} for user: {user_email}")
        docs = drive_loader.load()
        print(f"Loaded {len(docs)} documents from Google Drive")

        # go through all docs. For each doc, see if the user is already in the metadata. If not,
        # add the user to the metadata
        for doc in docs:
            print(f"Processing doc: {doc.metadata['title']}")
            # check if the user key is in the metadata
            if "users" not in doc.metadata:
                doc.metadata["users"] = []
            # check if the user is in the metadata
            if user_email not in doc.metadata["users"]:
                # print(f"Adding user {user_email} to doc.metadata['users'] for metadata.users
                # ${doc.metadata['users']}")
                doc.metadata["users"].append(user_email)

        #indexname must consist of lower case alphanumeric characters or '-'"
        index_name = pinecone_index_name(org=org_name,
                                         datasource='googledrive',
                                         environment=self.lorelai_settings['environment'],
                                         env_name=self.lorelai_settings['environment_slug'],
                                         version="v1")


        self.store_docs_in_pinecone(docs, index_name=index_name)
        print(f"Processed {len(docs)} documents for user: {user_email}")
