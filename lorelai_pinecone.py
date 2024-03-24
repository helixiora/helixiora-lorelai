"""this file creates a class to process google drive documents using the google drive api, chunk
them using langchain and then index them in pinecone"""

import json
import os
import sqlite3
from pathlib import Path

# langchain_community.vectorstores.pinecone.Pinecone is deprecated
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders.googledrive import GoogleDriveLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# The scopes needed to read documents in Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
DATABASE = './userdb.sqlite'

class GoogleDriveProcessor:
    """This class is used to process the Google Drive documents and index them in Pinecone
    """
    def __init__(self, google_creds, pinecone_creds, openai_creds):
        self.pinecone_api_key = pinecone_creds['api-key']
        self.openai_api_key = openai_creds['api-key']
        # set env variable with openai api key
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["PINECONE_API_KEY"] = self.pinecone_api_key

        self.pinecone_environment = pinecone_creds['environment']
        self.pinecone_index_name = pinecone_creds['index-name']
        self.google_creds = google_creds

    # load tokens from sqlite
    def load_tokens_from_sqlite(self):
        """loads the tokens from the sqlite database
        """
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_tokens where user_id = '115957235300401571807'")
        rows = cur.fetchall()
        conn.close()
        return rows

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

    def process_drive(self):
        """process the Google Drive documents and index them in Pinecone
        """
        # self.save_google_creds_to_tempfile()
        # tokens = self.load_tokens_from_sqlite()

        # 1. Load the Google Drive credentials
        # build a credentials object from the google creds

        tokens = self.load_tokens_from_sqlite()

        if tokens:
            token = tokens[0]
            refresh_token = token[2]

            credentials = Credentials.from_authorized_user_info({
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": self.google_creds['client_id'],
                "client_secret": self.google_creds['client_secret']

            })

        # save the google creds to a tempfile as they are needed by the langchain google drive
        # loader until this issue is fixed: https://github.com/langchain-ai/langchain/issues/15058
        self.save_google_creds_to_tempfile(refresh_token, "https://oauth2.googleapis.com/token",
                                           self.google_creds['client_id'],
                                           self.google_creds['client_secret'])

        # 2. Get the Google Drive document IDs
        document_ids = self.get_google_docs_ids(credentials)
        for document_id in document_ids:
            print(f"Processing document: {document_id}")
            self.process_document(document_id)

    def get_google_docs_ids(self, credentials):
        """
        Retrieves all Google Docs document IDs from the user's Google Drive.

        :param credentials: Google-auth credentials object for the user
        :return: List of document IDs
        """
        # Build the Drive v3 API service object
        service = build('drive', 'v3', credentials=credentials)

        # List to store all document IDs
        document_ids = []

        # Call the Drive v3 API to get the list of files
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.document'",
            pageSize=100, fields="nextPageToken, files(id, name)").execute()

        # Extract the files from the results
        items = results.get('files', [])

        # Iterate through the files and add their IDs to the document_ids list
        if not items:
            print('No files found.')
        else:
            for item in items:
                print(f"Found file: {item['name']} with ID: {item['id']}")
                document_ids.append(item['id'])

        return document_ids



    def process_document(self, document_id):
        """process the Google Drive documents and index them in Pinecone
        """
        drive_loader = GoogleDriveLoader(
            document_ids=[document_id])
        splitter = RecursiveCharacterTextSplitter(chunk_size=4000)

        docs = drive_loader.load()

        # Iterate over documents and split each document's text into chunks
        # for doc_id, document_content in documents.items():
        #     print(f"Processing document: {doc_id}")
        documents = splitter.split_documents(docs)

        embeddings = OpenAIEmbeddings()
        pinecone = PineconeVectorStore(pinecone_api_key=self.pinecone_api_key,
                                            index_name=self.pinecone_index_name,
                                            embedding=embeddings)

        #TODO: subsequent runs should update, not add/duplicate
        db = pinecone.from_documents(documents,
                                          embeddings,
                                          index_name=self.pinecone_index_name)

        return db
