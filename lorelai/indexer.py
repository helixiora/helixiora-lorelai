"""this file creates a class to process google drive documents using the google drive api, chunk
them using langchain and then index them in pinecone"""

import json
import sqlite3

# langchain_community.vectorstores.pinecone.Pinecone is deprecated
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from lorelai.processor import Processor

# The scopes needed to read documents in Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
DATABASE = './userdb.sqlite'

class Indexer:
    """This class is used to process the Google Drive documents and index them in Pinecone
    """
    def __init__(self):
        self.google_creds = self.load_google_creds()

    @staticmethod
    def load_google_creds():
        """loads the google creds from the settings.json file
        """
        with open('settings.json', encoding='utf-8') as f:
            return json.load(f)['google']

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

        # 2. Get the Google Drive document IDs
        document_ids = self.get_google_docs_ids(credentials)
        for document_id in document_ids:

            print(f"Processing document: {document_id}")

            processor = Processor()
            processor.process_google_doc(document_id, credentials)

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
        page_token = None
        while True:
            results = service.files().list( # pylint: disable=no-member
                q="mimeType='application/vnd.google-apps.document'",
                pageSize=100, fields="nextPageToken, files(id, name, parents, spaces)",
                pageToken=page_token).execute()

            # Extract the files from the results
            items = results.get('files', [])

            # Iterate through the files and add their IDs to the document_ids list
            if not items:
                print('No files found.')
                break
            else:
                print(f"Found {len(items)} files")
                for item in items:
                    print(f"Found file: {item['name']} with ID: {item['id']} ")
                    document_ids.append(item['id'])

            # Check if there are more pages
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        return document_ids
    