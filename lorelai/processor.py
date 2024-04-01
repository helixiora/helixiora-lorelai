"""This module contains the Processor class that processes documents and indexes them in Pinecone
"""
import json
import os
from pathlib import Path

from typing import Any
from google.oauth2.credentials import Credentials

from langchain_community.document_loaders.googledrive import GoogleDriveLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from langchain_pinecone import PineconeVectorStore
import pinecone
from pinecone import ServerlessSpec

import lorelai.utils

class Processor:
    """This class is used to process the Google Drive documents and index them in Pinecone
    """
    
    def __init__(self):
        """initializes the Processor class
        """

        self.pinecone_creds = lorelai.utils.load_creds('pinecone')
        self.openai_creds = lorelai.utils.load_creds('openai')

        self.pinecone_api_key = self.pinecone_creds['api-key']
        self.openai_api_key = self.openai_creds['api-key']
        # set env variable with openai api key
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["PINECONE_API_KEY"] = self.pinecone_api_key
        
        self.pinecone_environment = self.pinecone_creds['environment']
        self.pinecone_index_name = self.pinecone_creds['index-name']


    def process(self, docs, organisation: str, datasource: str, user: str):
        """process the documents and index them in Pinecone
        """
        splitter = RecursiveCharacterTextSplitter(chunk_size=4000)
        # Iterate over documents and split each document's text into chunks
        # for doc_id, document_content in documents.items():
        #     print(f"Processing document: {doc_id}")
        documents = splitter.split_documents(docs)

        # use text-embedding-ada-002
        embedding_model = 'text-embedding-ada-002'
        embeddings = OpenAIEmbeddings(model=embedding_model)
        embedding_dimension = lorelai.utils.get_embedding_dimension(embedding_model)
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

        vector_store = PineconeVectorStore(pinecone_api_key=self.pinecone_api_key,
                                           index_name=index_name, embedding=embeddings)

        #TODO: subsequent runs should update, not add/duplicate # pylint: disable=fixme
        db = vector_store.from_documents(documents,
                                            embeddings,
                                            index_name=index_name,)

        return db


    def process_google_doc(self, document_id: str, credentials: Credentials, org: str, user: list[Any]):
        """process the Google Drive documents and index them in Pinecone
        """
        # save the google creds to a tempfile as they are needed by the langchain google drive
        # loader until this issue is fixed: https://github.com/langchain-ai/langchain/issues/15058
        lorelai.utils.save_google_creds_to_tempfile(refresh_token=credentials.refresh_token,
                                           token_uri="https://oauth2.googleapis.com/token",
                                           client_id=credentials.client_id,
                                           client_secret=credentials.client_secret)

        drive_loader = GoogleDriveLoader(
            document_ids=[document_id])

        print(f"Processing document: {document_id} for user: {user[2]}")
        docs = drive_loader.load()

        # go through all docs and add the user as metadata
        for doc in docs:
            doc.metadata['user'] += user[2]
        #indexname must consist of lower case alphanumeric characters or '-'"
        index_name = lorelai.utils.pinecone_index_name(org=org_name, datasource='googledrive')


        self.store_docs_in_pinecone(docs, index_name=index_name)
