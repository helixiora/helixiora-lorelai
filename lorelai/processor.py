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
import pinecone
from pinecone import ServerlessSpec

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
    
    @staticmethod    
    def get_embedding_dimension(model_name):
        """
        Returns the dimension of embeddings for a given model name.
        This function currently uses a hardcoded mapping based on documentation,
        as there's no API endpoint to retrieve this programmatically.
        See: https://platform.openai.com/docs/models/embeddings
        """
        # Mapping of model names to their embedding dimensions
        model_dimensions = {
            'text-embedding-3-large':	3072,
            'text-embedding-3-small':	1536,
            'text-embedding-ada-002':	1536
            # Add new models and their dimensions here as they become available
        }
        
        return model_dimensions.get(model_name, None)  # Return None if model is not found



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


    def process(self, docs, organisation, datasource):
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
        embedding_dimension = self.get_embedding_dimension(embedding_model)

        index_name = f"{organisation[1]}-{datasource}"
        #indexname must consist of lower case alphanumeric characters or '-'"
        index_name = index_name.lower().replace(".", "-")
        print(f"Index name: {index_name}")

        pc = pinecone.Pinecone(api_key=self.pinecone_api_key)

        # somehow the PineconeVectorStore doesn't support creating a new index, so we use pinecone package directly
        # Check if the index already exists
        if index_name not in pc.list_indexes().names():
            # Create a new index
            pc.create_index(name=index_name,
                            dimension=embedding_dimension,
                            metric='cosine',
                            spec=ServerlessSpec(
                                cloud='aws',
                                region='us-west-2'
                            ))
            print(f"Index '{index_name}' created.")
        else:
            print(f"Index '{index_name}' already exists.")

        vector_store = PineconeVectorStore(pinecone_api_key=self.pinecone_api_key, index_name=index_name, embedding=embeddings)

        #TODO: subsequent runs should update, not add/duplicate # pylint: disable=fixme
        db = vector_store.from_documents(documents,
                                            embeddings,
                                            index_name=index_name,)

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

    def process_google_doc(self, document_id: str, credentials: Credentials, org: str):
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

        self.process(docs, org, "googledrive")
