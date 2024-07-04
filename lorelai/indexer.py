"""Creates a class to process Google Drive documents using the Google Drive API.

Chunk them using Langchain, and then index them in Pinecone.
"""

import logging
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from rq import job

import lorelai.utils
from lorelai.processor import Processor

# The scopes needed to read documents in Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]


class Indexer:
    """Used to process the Google Drive documents and index them in Pinecone."""

    _allowed = False  # Flag to control constructor access

    @staticmethod
    def create(datasource: str = "GoogleDriveIndexer") -> "Indexer":
        """Create instances of derived classes based on the class name.

        Arguments
        ---------
        datasource: str
            The name of the derived class to instantiate.

        Returns
        -------
        Indexer
            An instance of the derived class.
        """
        Indexer._allowed = True
        class_ = globals().get(datasource)
        if class_ is None or not issubclass(class_, Indexer):
            Indexer._allowed = False
            raise ValueError(f"Unsupported model type: {datasource}")
        instance = class_()
        Indexer._allowed = False
        return instance

    def __init__(self):
        if not self._allowed:
            raise Exception("This class should be instantiated through a create() factory method.")

        self.pinecone_creds = lorelai.utils.load_config("pinecone")
        self.settings = lorelai.utils.load_config("lorelai")

        os.environ["PINECONE_API_KEY"] = self.pinecone_creds["api_key"]

    def get_indexer_name(self) -> str:
        """Retrieve the name of the indexer."""
        return self.__class__.__name__

    def index_org(
        self,
        org_row: dict[str, any],
        user_rows: list[dict[str, any]],
        user_auth_rows: list[dict[str, any]],
        job: job.Job | None = None,
    ) -> list[dict[str, any]]:
        """Process the organisation, indexing all its users.

        Arguments
        ---------
        org_row: dict[str, any]
            The organisation to process, a dictionary of org details (org_id, name).
        user_rows: list[dict[str, any]]
            The users to process, a list of user details (user_id, name, email, token,
            refresh_token).
        user_auth_rows: list[dict[str, any]]
            The user auth rows for all users, a list of user auth details (user_id, auth_key,
            auth_value).
        job: job.Job | None
            The job object for the current task.

        Returns
        -------
        list[dict[str, any]]
            A list of dictionaries containing the results of indexing each user.
        """
        logging.debug(f"Indexing org: {org_row}")
        logging.debug(f"Users: {user_rows}")
        logging.debug(f"User auths: {user_auth_rows}")

        if job:
            job.meta["status"] = "Indexing " + self.get_indexer_name()
            job.save_meta()

            logging.info("Task ID: %s, Message: %s", job.id, job.meta["status"])
            logging.info("Indexing %s: %s", self.get_indexer_name(), job.id)

        result = []
        for user_row in user_rows:
            if job:
                job.meta["status"] = (
                    f"Indexing {self.get_indexer_name()} for user {user_row['email']}"
                )
                job.meta["org"] = org_row["name"]
                job.meta["user"] = user_row["email"]
                job.save_meta()

            # get the user auth rows for this user (there will be many user's auth rows in the
            # original list)
            user_auth_rows_filtered = [
                user_auth_row
                for user_auth_row in user_auth_rows
                if user_auth_row["user_id"] == user_row["user_id"]
            ]

            # index the user
            success, message = self.index_user(
                user_row=user_row, org_row=org_row, user_auth_rows=user_auth_rows_filtered, job=job
            )

            logging.info(
                f"User {user_row['email']} indexing {'succeeded' if success else 'failed'}: \
                    {message}"
            )

            if job:
                job.meta[
                    "status"
                ] = f"Indexing {self.get_indexer_name()} for user {user_row['email']}: \
                        {'succeeded' if success else 'failed'}"
                job.meta["org"] = org_row["name"]
                job.meta["user"] = user_row["email"]
                job.save_meta()

            result.append(
                {
                    "job_id": job.id if job else "",
                    "user_id": user_row["user_id"],
                    "success": success,
                    "message": "User indexed successfully"
                    if success
                    else f"User indexing failed: {message}",
                }
            )

        logging.debug(f"Indexing complete for org: {org_row['name']}. Results: {result}")
        return result

    def index_user(
        self,
        user_row: dict[str, any],
        org_row: dict[str, any],
        user_auth_rows: list[dict[str, any]],
        job: job.Job | None,
    ) -> tuple[bool, str]:
        """Process the Google Drive documents for a user and index them in Pinecone.

        Arguments
        ---------
        user_row: dict[str, any]
            The user to process, a dictionary of user details (user_id, name, email, token,
            refresh_token).
        org_row: dict[str, any]
            The organisation to process, a dictionary of org details (org_id, name).
        user_auth_rows: list[dict[str, any]]
            The user auth rows for the user, a list of user auth details (user_id, auth_key,
            auth_value).
        job: job.Job | None
            The job object for the current task.

        Returns
        -------
        Tuple[bool, str]
            A tuple containing a success flag and a message.
        """
        raise NotImplementedError


class GoogleDriveIndexer(Indexer):
    """Used to process the Google Drive documents and index them in Pinecone."""

    def __init__(self):
        super().__init__()
        self.google_creds = lorelai.utils.load_config("google")

    def index_user(
        self,
        user_row: dict[str, any],
        org_row: dict[str, any],
        user_auth_rows: list[dict[str, any]],
        job: job.Job | None,
        folder_id: str = "",
    ) -> bool:
        """Process the Google Drive documents for a user and index them in Pinecone.

        Arguments
        ---------
        user_row: dict[str, any]
            The user to process, a dictionary of user details (user_id, name, email, token,
            efresh_token).
        org_row: dict[str, any]
            The organisation to process, a dictionary of org details (org_id, name).
        user_auth_rows: list[dict[str, any]]
            The user auth rows for the user, a list of user auth details (user_id, auth_key,
            auth_value).
        job: job.Job | None
            The job object for the current task.
        folder_id: str
            The folder ID to process.

        Returns
        -------
        bool
            True if indexing was successful, False otherwise.
        """
        if user_row:
            logging.debug(f"Processing user: {user_row['email']} from org: {org_row['name']}")
            if folder_id:
                logging.debug(f"Processing folder: {folder_id}")
            else:
                logging.debug("Processing all folders")

            refresh_token = next(
                (
                    user_auth_row["auth_value"]
                    for user_auth_row in user_auth_rows
                    if user_auth_row["auth_key"] == "refresh_token"
                ),
                None,
            )

            if not refresh_token:
                msg = f"User {user_row['email']} does not have a refresh token"
                logging.error(msg)
                return False, msg

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
        document_ids = self.__get_google_docs_ids(credentials, folder_id)

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

    def __get_google_docs_ids(self, credentials: Credentials, folder_id: str = "") -> list[str]:
        """Retrieve all Google Docs document IDs from the user's Google Drive or a specific folder.

        Note: This only includes Google Docs documents, not text files or PDFs.

        Arguments
        ---------
        credentials: Credentials
            Google-auth credentials object for the user.
        folder_id: str
            Optional Google Drive folder ID to restrict the search.

        Returns
        -------
        list[str]
            list of document IDs.
        """
        # Build the Drive v3 API service object
        service = build("drive", "v3", credentials=credentials)

        # List to store all document IDs
        document_ids = []
        query = (
            f"mimeType='application/vnd.google-apps.document' and '{folder_id}' in parents"
            if folder_id
            else "mimeType='application/vnd.google-apps.document'"
        )

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
                logging.debug(f"Found file: {item['name']} with ID: {item['id']}")
                document_ids.append(item["id"])

            # Check if there are more pages
            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return document_ids
