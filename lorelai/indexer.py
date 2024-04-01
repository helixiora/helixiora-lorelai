"""this file creates a class to process google drive documents using the google drive api, chunk
them using langchain and then index them in pinecone"""

import os

from typing import Any

# langchain_community.vectorstores.pinecone.Pinecone is deprecated
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from lorelai.processor import Processor
import lorelai.utils

# The scopes needed to read documents in Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
DATABASE = './userdb.sqlite'

class Indexer:
    """This class is used to process the Google Drive documents and index them in Pinecone
    """
    def __init__(self):
        self.google_creds = lorelai.utils.load_creds('google')
        self.pinecone_creds = lorelai.utils.load_creds('pinecone')

        os.environ["PINECONE_API_KEY"] = self.pinecone_creds['api-key']

    def index_org_drive(self, org: list[Any], users: list[list[Any]]) -> None:
        """process the Google Drive documents for an organisation
        """
        # 1. Load the Google Drive credentials
        # build a credentials object from the google creds
        for user in users:
            self.index_user_drive(user, org)


    def index_user_drive(self, user: list[Any], org: list[Any]) -> None:
        """process the Google Drive documents for a user and index them in Pinecone
        
        :param user: the user to process, a list of user details (user_id, name, email, token, refresh_token)
        """

        if user:
            print(f"Processing user: {user} from org: {org}")
            token = user[3]
            refresh_token = user[4]

            credentials = Credentials.from_authorized_user_info({
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": self.google_creds['client_id'],
                "client_secret": self.google_creds['client_secret']

            })
            
            # see if the credentials work and refresh if expired
            if not credentials.valid:
                credentials.refresh(Request())
                print("Refreshed credentials")

        # 2. Get the Google Drive document IDs
        document_ids = self.get_google_docs_ids(credentials)
        for document_id in document_ids:

            print(f"Processing document: {document_id}")

            if not os.environ.get('DRY_RUN'):
                processor = Processor()
                processor.process_google_doc(document_id, credentials, org, user)

    def get_google_docs_ids(self, credentials) -> list[str]:
        """
        Retrieves all Google Docs document IDs from the user's Google Drive.

        :param credentials: Google-auth credentials object for the user
        :return: List of document IDs
        """
        # Build the Drive v3 API service object
        service = build('drive', 'v3', credentials=credentials)

        # List to store all document IDs
        document_ids = []

        # Call the Drive v3 API to get the list of files. We don't use GoogleDriveLoader because
        # we only need the document IDs here.
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
