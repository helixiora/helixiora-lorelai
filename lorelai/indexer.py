"""this file creates a class to process google drive documents using the google drive api, chunk
them using langchain and then index them in pinecone"""

import logging
import os
import sys
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# langchain_community.vectorstores.pinecone.Pinecone is deprecated
from googleapiclient.discovery import build
from rq import get_current_job, job

import lorelai.utils
from lorelai.processor import Processor

# The scopes needed to read documents in Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]


class Indexer:
    """Used to process the Google Drive documents and index them in Pinecone."""

    def __init__(self: None):
        self.google_creds = lorelai.utils.load_config("google")
        self.pinecone_creds = lorelai.utils.load_config("pinecone")
        self.settings = lorelai.utils.load_config("lorelai")

        os.environ["PINECONE_API_KEY"] = self.pinecone_creds["api_key"]

    def index_org_drive(self: None, org: dict[Any], users: dict[Any]) -> bool:
        """Process the Google Drive documents for an organisation.

        :param org: the organisation to process, a list of org details (org_id, name)
        :param users: the users to process, a list of user details (user_id, name, email, token,
            refresh_token)

        :return: None
        """
        # see if we're running from an rq job
        job = get_current_job()
        if job:
            job.meta["status"] = "Indexing Google Drive"
            job.meta["org"] = org

            logging.info("Task ID: %s, Message: %s", "Indexing Google Drive", job.id)

        # 1. Load the Google Drive credentials
        # build a credentials object from the google creds
        for user in users:
            if job:
                job.meta["status"] = f"Indexing Google Drive for user {user['email']}"
                job.meta["org"] = org
                job.meta["user"] = user["email"]
            self.index_user_drive(user, org, job)
            return True

        # if we haven't returned True by now, something went wrong
        return False

    def index_user_drive(
        self: None, user: dict[Any], org: dict[Any], job: Optional["job"]
    ) -> bool:
        """Process the Google Drive documents for a user and index them in Pinecone.

        :param user: the user to process, a list of user details (user_id, name, email, token,
            refresh_token)
        :param org: the organisation to process, a list of org details (org_id, name)

        :return: bool
        """
        # 1. Load the Google Drive credentials
        if user:
            logging.debug(f"Processing user: {user} from org: {org}")
            refresh_token = user["refresh_token"]
            credentials = Credentials.from_authorized_user_info(
                {
                    "refresh_token": refresh_token,
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": self.google_creds["client_id"],
                    "client_secret": self.google_creds["client_secret"],
                },
            )

            # see if the credentials work and refresh if expired
            if not credentials.valid:
                credentials.refresh(Request())
                logging.debug("Refreshed credentials")

        # 2. Get the Google Drive document IDs
        logging.debug(f"Getting Google Drive document IDs for user: {user['email']}")
        document_ids = self.get_google_docs_ids(credentials)

        # 3. Generate the index name we will use in Pinecone
        index_name = lorelai.utils.pinecone_index_name(
            org=org["name"],
            datasource="googledrive",
            environment=self.settings["environment"],
            env_name=self.settings["environment_slug"],
            version="v1",
        )
        # 3.1 Pinecone only allows max 45 chars index names
        if len(index_name) > 45:
            sys.exit(f"{index_name} is longer than maximum allowed chars (45)")
        # 4. Get index statistics before starting the indexing process
        index_stats_before = lorelai.utils.get_index_stats(index_name)

        # 5. Process the Google Drive documents and index them in Pinecone
        logging.info(
            f"Processing {len(document_ids)} Google documents for user: {user['name']}"
        )
        pinecone_processor = Processor()
        pinecone_processor.google_docs_to_pinecone_docs(
            document_ids=document_ids,
            credentials=credentials,
            org_name=org["name"],
            user_email=user["email"],
        )

        # 6. Get index statistics after the indexing process
        logging.debug(f"Indexing complete for user: {user['name']}")
        index_stats_after = lorelai.utils.get_index_stats(index_name)

        # 7. Print the index statistics
        logging.debug("Index statistics before indexing vs after indexing:")
        lorelai.utils.print_index_stats_diff(index_stats_before, index_stats_after)

    def get_google_docs_ids(self: None, credentials) -> list[str]:
        """Retrieve all Google Docs document IDs from the user's Google Drive.

        :param credentials: Google-auth credentials object for the user
        :return: List of document IDs
        """
        # Build the Drive v3 API service object
        service = build("drive", "v3", credentials=credentials)

        # List to store all document IDs
        document_ids = []

        # Call the Drive v3 API to get the list of files. We don't use GoogleDriveLoader because
        # we only need the document IDs here.
        page_token = None
        while True:
            results = (
                service.files()
                .list(  # pylint: disable=no-member
                    q="mimeType='application/vnd.google-apps.document'",
                    pageSize=100,
                    fields="nextPageToken, files(id, name, parents, spaces)",
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                )
                .execute()
            )

            # Extract the files from the results
            items = results.get("files", [])

            # Iterate through the files and add their IDs to the document_ids list
            if not items:
                logging.debug("No files found.")
                break

            logging.debug(f"Found {len(items)} files")
            for item in items:
                logging.debug(f"Found file: {item['name']} with ID: {item['id']} ")
                document_ids.append(item["id"])

            # Check if there are more pages
            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return document_ids
