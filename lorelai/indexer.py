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

    _allowed = False  # Flag to control constructor access

    @staticmethod
    def create(datasource="GoogleDriveIndexer"):
        """Factory method to create instances of derived classes based on the class name."""
        Indexer._allowed = True
        class_ = globals().get(datasource)
        if class_ is None or not issubclass(class_, Indexer):
            Indexer._allowed = False
            raise ValueError(f"Unsupported model type: {datasource}")
        instance = class_()
        Indexer._allowed = False
        return instance

    def __init__(self: None):
        if not self._allowed:
            raise Exception("This class should be instantiated through a create() factory method.")

        self.pinecone_creds = lorelai.utils.load_config("pinecone")
        self.settings = lorelai.utils.load_config("lorelai")

        os.environ["PINECONE_API_KEY"] = self.pinecone_creds["api_key"]

    def get_indexer_name(self: None) -> str:
        """Retrieve the name of the indexer."""
        return self.__class__.__name__

    def index_org(
        self: None, org_row: dict[Any], user_rows: dict[Any], user_auth_rows: dict[Any]
    ) -> list[dict]:
        """Process the organisation, indexing all it's users

        :param org: the organisation to process, a list of org details (org_id, name)
        :param users: the users to process, a list of user details (user_id, name, email, token,
            refresh_token)

        :return: None
        """
        # see if we're running from an rq job
        job = get_current_job()
        if job:
            job.meta["status"] = "Indexing " + self.get_indexer_name()
            job.meta["org"] = org_row["name"]

            logging.info("Task ID: %s, Message: %s", job.id, job.meta["status"])
            logging.info("Indexing %s: %s", self.get_indexer_name, job.id)

        result = []
        for user_row in user_rows:
            if job:
                job.meta["status"] = (
                    f"Indexing {self.get_indexer_name} for user {user_row['email']}"
                )
                job.meta["org"] = org_row["name"]
                job.meta["user"] = user_row["email"]

            # get the user auth rows for this user (there will be many user's auth rows in the
            # original list)
            user_auth_rows_filtered = [
                user_auth_row
                for user_auth_row in user_auth_rows
                if user_auth_row["user_id"] == user_row["user_id"]
            ]

            # index the user
            success = self.index_user(
                user_row=user_row, org_row=org_row, user_auth_rows=user_auth_rows_filtered, job=job
            )

            logging.info(
                f"User {user_row['email']} indexing {'succeeded' if success else 'failed'}"
            )

            result.append(
                {
                    "user_id": user_row["user_id"],
                    "success": success,
                    "message": "User indexed successfully" if success else "User indexing failed",
                }
            )

        logging.debug(f"Indexing complete for org: {org_row['name']}. Results: {result}")
        return result

    def index_user(
        self: None,
        user_row: dict[Any],
        org_row: dict[Any],
        user_auth_rows: dict[Any],
        job: Optional["job"],
    ) -> bool:
        """Process the Google Drive documents for a user and index them in Pinecone.

        :param user: the user to process, a list of user details (user_id, name, email, token,
            refresh_token)
        :param org: the organisation to process, a list of org details (org_id, name)

        :return: bool
        """
        raise NotImplementedError


class GoogleDriveIndexer(Indexer):
    """Used to process the Google Drive documents and index them in Pinecone."""

    def __init__(self: None):
        super().__init__()
        self.google_creds = lorelai.utils.load_config("google")

    def index_user(
        self: None,
        user_row: dict[Any],
        org_row: dict[Any],
        user_auth_rows: dict[Any],
        job: Optional["job"],
        folder_id: str = "",
    ) -> bool:
        """Process the Google Drive documents for a user and index them in Pinecone.

        :param user: the user to process, a list of user details (user_id, name, email, token,
            refresh_token)
        :param org: the organisation to process, a list of org details (org_id, name)

        :return: bool
        """
        # 1. Load the Google Drive credentials
        if user_row:
            logging.debug(f"Processing user: {user_row['email']} from org: {org_row['name']}")
            if folder_id:
                logging.debug(f"Processing folder: {folder_id}")
            else:
                logging.debug("Processing all folders")

            # get the user's refresh token by searhcing through the user_auth_rows where
            # key = 'refresh_token' and user_id = user_row['user_id']
            refresh_token = None
            for user_auth_row in user_auth_rows:
                if user_auth_row["key"] == "refresh_token":
                    refresh_token = user_auth_row["value"]
                    break

            if not refresh_token:
                logging.error(f"User {user_row['email']} does not have a refresh token")
                return False

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
        logging.debug(f"Getting Google Drive document IDs for user: {user_row['email']}")
        document_ids = self.get_google_docs_ids(credentials, folder_id)

        # 3. Generate the index name we will use in Pinecone
        index_name = lorelai.utils.pinecone_index_name(
            org=org_row["name"],
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
            f"Processing {len(document_ids)} Google documents for user: {user_row['email']}"
        )
        pinecone_processor = Processor()
        pinecone_processor.google_docs_to_pinecone_docs(
            document_ids=document_ids,
            credentials=credentials,
            org_name=org_row["name"],
            user_email=user_row["email"],
        )

        # 6. Get index statistics after the indexing process
        logging.debug(f"Indexing complete for user: {user_row['email']}")
        index_stats_after = lorelai.utils.get_index_stats(index_name)

        # 7. Print the index statistics
        logging.debug("Index statistics before indexing vs after indexing:")
        lorelai.utils.print_index_stats_diff(index_stats_before, index_stats_after)

    def __get_google_docs_ids(self, credentials, folder_id: str = "") -> list[str]:
        """Retrieve all Google Docs document IDs from the user's Google Drive or a specific folder.

        Note: this only includes Google Docs documents, not text files or pdfs.

        :param credentials: Google-auth credentials object for the user
        :param folder_id: Optional Google Drive folder ID to restrict the search
        :return: List of document IDs
        """
        # Build the Drive v3 API service object
        service = build("drive", "v3", credentials=credentials)

        # List to store all document IDs
        document_ids = []

        # Construct the query to filter files by mimeType and optional folder_id
        if folder_id != "":
            logging.debug(f"Getting Google Docs from folder: {folder_id}")
            query = f"mimeType='application/vnd.google-apps.document' and '{folder_id}' in parents"
        else:
            logging.debug("Getting all Google Docs")
            query = "mimeType='application/vnd.google-apps.document'"

        # Call the Drive v3 API to get the list of files. We don't use GoogleDriveLoader because
        # we only need the document IDs here.
        page_token = None
        while True:
            results = (
                service.files()
                .list(  # pylint: disable=no-member
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, parents, spaces)",
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    corpora="allDrives",
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
