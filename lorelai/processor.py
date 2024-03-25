"""This module contains the Processor class that processes documents and indexes them in Pinecone
"""
import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials

from langchain_community.document_loaders.googledrive import GoogleDriveLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from langchain_pinecone import PineconeVectorStore

class Processor:
    """This class is used to process the Google Drive documents and index them in Pinecone
    """
    # load openai creds from file
    @staticmethod
    def load_openai_creds():
        """loads the openai creds from the settings.json file
        """
        with open('settings.json', encoding='utf-8') as f:
            return json.load(f)['openai']

    # load pinecone creds from file
    @staticmethod
    def load_pinecone_creds():
        """loads the pinecone creds from the settings.json file
        """
        with open('settings.json', encoding='utf-8') as f:
            return json.load(f)['pinecone']


    def __init__(self):
        self.pinecone_creds = self.load_pinecone_creds()
        self.openai_creds = self.load_openai_creds()

        self.pinecone_api_key = self.pinecone_creds['api-key']
        self.openai_api_key = self.openai_creds['api-key']
        # set env variable with openai api key
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["PINECONE_API_KEY"] = self.pinecone_api_key

        self.pinecone_environment = self.pinecone_creds['environment']
        self.pinecone_index_name = self.pinecone_creds['index-name']


    def process(self, docs):
        """process the documents and index them in Pinecone
        """
        splitter = RecursiveCharacterTextSplitter(chunk_size=4000)
        # Iterate over documents and split each document's text into chunks
        # for doc_id, document_content in documents.items():
        #     print(f"Processing document: {doc_id}")
        documents = splitter.split_documents(docs)

        embeddings = OpenAIEmbeddings()
        pinecone = PineconeVectorStore(pinecone_api_key=self.pinecone_api_key,
                                            index_name=self.pinecone_index_name,
                                            embedding=embeddings)

        #TODO: subsequent runs should update, not add/duplicate # pylint: disable=fixme
        db = pinecone.from_documents(documents,
                                            embeddings,
                                            index_name=self.pinecone_index_name)

        return db

    def save_google_creds_to_tempfile(self, refresh_token, token_uri, client_id, client_secret):
        """loads the google creds to a tempfile. This is needed because the GoogleDriveLoader uses
        the Credentials.from_authorized_user_file method to load the credentials
        """
        # create a file: Path.home() / ".credentials" / "token.json" to store the credentials so
        # they can be loaded by GoogleDriveLoader's auth process (this uses
        # Credentials.from_authorized_user_file)
        if not os.path.exists(Path.home() / ".credentials"):
            os.makedirs(Path.home() / ".credentials")

        with open(Path.home() / ".credentials" / "token.json", 'w', encoding='utf-8') as f:
            f.write(json.dumps({
                "refresh_token": refresh_token,
                "token_uri": token_uri,
                "client_id": client_id,
                "client_secret": client_secret
            }))
            f.close()

    def process_google_doc(self, document_id: str, credentials: Credentials):
        """process the Google Drive documents and index them in Pinecone
        """
        # save the google creds to a tempfile as they are needed by the langchain google drive
        # loader until this issue is fixed: https://github.com/langchain-ai/langchain/issues/15058
        self.save_google_creds_to_tempfile(credentials.refresh_token,
                                           "https://oauth2.googleapis.com/token",
                                           credentials.client_id,
                                           credentials.client_secret)

        drive_loader = GoogleDriveLoader(
            document_ids=[document_id])

        docs = drive_loader.load()

        self.process(docs)
        