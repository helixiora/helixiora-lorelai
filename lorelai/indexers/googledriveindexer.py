"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveIndexer: Handles Google Drive document indexing using Pinecone and OpenAI.
"""

import logging

# from pathlib import Path
from google.oauth2 import credentials
from googleapiclient.discovery import build
from google.auth.credentials import TokenState
from lorelai.indexer import Indexer
from lorelai.processor import Processor
from langchain_googledrive.document_loaders import GoogleDriveLoader
from langchain_core.documents import Document
from lorelai.utils import load_config, get_db_connection
from rq import job

ALLOWED_ITEM_TYPES = ["document", "folder", "file"]


class GoogleDriveIndexer(Indexer):
    """Used to process the Google Drive documents and index them in Pinecone."""

    def __get_token_details(self, user_auth_rows: list[dict[str, any]]) -> tuple[str, str, str]:
        access_token = next(
            (
                user_auth_row["auth_value"]
                for user_auth_row in user_auth_rows
                if user_auth_row["auth_key"] == "access_token"
            ),
            None,
        )

        refresh_token = next(
            (
                user_auth_row["auth_value"]
                for user_auth_row in user_auth_rows
                if user_auth_row["auth_key"] == "refresh_token"
            ),
            None,
        )

        expires_at = next(
            (
                user_auth_row["auth_value"]
                for user_auth_row in user_auth_rows
                if user_auth_row["auth_key"] == "expires_at"
            ),
            None,
        )
        return access_token, refresh_token, expires_at

    def index_user(
        self,
        user_row: dict[str, any],
        org_row: dict[str, any],
        user_auth_rows: list[dict[str, any]],
        user_data_rows: list[dict[str, any]],
        job: job.Job,
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
        logging.info(f"Indexing user: {user_row['email']} from org: {org_row['name']}")
        job.meta["logs"].append(f"Indexing user: {user_row['email']} from org: {org_row['name']}")

        # 1. Get the Google Drive access token, refresh token, and expiry
        access_token, refresh_token, expires_at = self.__get_token_details(user_auth_rows)

        # 2. Get the Google Drive document IDs
        logging.debug(f"Getting Google Drive document IDs for user: {user_row['email']}")

        documents = []
        for user_data_row in user_data_rows:
            # extra safety: check if the user_id in the user_data_row matches the user_id
            if user_data_row["user_id"] != user_row["user_id"]:
                continue

            if user_data_row["item_type"] not in ALLOWED_ITEM_TYPES:
                logging.error(f"Invalid item type: {user_data_row['item_type']}")
                continue

            # add information about the document to the list
            documents.append(
                {
                    "user_id": user_data_row["user_id"],
                    "google_drive_id": user_data_row["google_drive_id"],
                    "item_type": user_data_row["item_type"],
                    "item_name": user_data_row["item_name"],
                }
            )

        if not documents or len(documents) == 0:
            logging.warn(f"No Google Drive documents found for user: {user_row['email']}")
            return True

        # 5. Process the Google Drive documents and index them in Pinecone
        logging.info(f"Processing {len(documents)} Google documents for user: {user_row['email']}")

        google_creds = load_config("google")

        # create a credentials object
        credentials_object = credentials.Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=google_creds["client_id"],
            client_secret=google_creds["client_secret"],
        )

        # test the credentials object
        if credentials_object.token_state == TokenState.INVALID:
            logging.error("Credentials object is invalid")
            return False
        else:
            logging.info("Credentials object state: %s", credentials_object.token_state)

            # Perform a simple API operation to ensure the credentials are working
            try:
                drive_service = build("drive", "v3", credentials=credentials_object)
                drive_service.files().list(pageSize=1).execute()
                logging.info("Credentials are valid and working")
            except Exception as e:
                logging.error(f"Failed to validate Google Drive credentials for user: \
{user_row['email']} with a simple API call: {e}")
                return False

        # convert the documents to langchain documents
        langchain_docs = self.google_docs_to_langchain_docs(
            documents=documents,
            credentials_object=credentials_object,
            job=job,
        )

        # add the user for whom were indexing the docs to the documents' metadata
        self.add_user_to_docs_metadata(langchain_docs, user_row["email"])

        pinecone_processor = Processor()

        # store the documents in Pinecone
        pinecone_processor.store_docs_in_pinecone(
            langchain_docs,
            user_email=user_row["email"],
            job=job,
            org_name=org_row["name"],
            datasource="googledrive",
        )

        self.update_last_indexed_for_docs(documents, job)
        logging.info(f"Indexing complete for user: {user_row['email']}")

        return True

    def add_user_to_docs_metadata(
        self: None, langchain_docs: list[Document], user_email: str
    ) -> None:
        """Add the user to the documents.

        :param langchain_docs: the list of langchain documents to add the users to
        :param user_email: the user to add to the documents
        """
        # go through all docs. For each doc, see if the user is already in the metadata. If not,
        # add the user to the metadata
        for loaded_doc in langchain_docs:
            logging.info(f"Checking metadata users for Google doc: {loaded_doc.metadata['title']}")

            # check if the user key is in the metadata
            if "users" not in loaded_doc.metadata:
                loaded_doc.metadata["users"] = []

            # check if the user is in the metadata
            if user_email not in loaded_doc.metadata["users"]:
                logging.info(
                    f"Adding user {user_email} to metadata.users for {loaded_doc.metadata['title']}"
                )
                loaded_doc.metadata["users"].append(user_email)

    def google_docs_to_langchain_docs(
        self: None,
        documents: list[dict[str, any]],
        credentials_object: credentials.Credentials,
        job: job.Job,
    ) -> list[Document]:
        """Process the Google Drive documents and divide them into pinecone compatible chunks.

        :param documents: the list of google documents to process. Each document is a dictionary
            with the following keys: google_drive_id, item_type
        :param credentials_object: the credentials object to use for Google Drive API
        :param job: the job object


        :return: the list of documents loaded from Google Drive
        """
        docs: list[Document] = []
        # documents contain a list of dictionaries with the following keys:
        # user_id, google_drive_id, item_type, item_name
        # loop through the documents and load them from Google Drive
        for doc in documents:
            doc_google_drive_id = doc["google_drive_id"]
            doc_item_type = doc["item_type"]

            if doc_item_type not in ALLOWED_ITEM_TYPES:
                logging.error(
                    f"Invalid item type: {doc_item_type} for document ID: {doc_google_drive_id}"
                )
                raise ValueError(f"Invalid item type: {doc_item_type}")

            logging.info(
                f"Loading Google Drive {doc_item_type}: {doc_google_drive_id} for document ID: \
{doc_google_drive_id}"
            )

            # use langchain google drive loader to load the content of the docs from google drive
            if doc_item_type in ["document", "file"]:
                loader = GoogleDriveLoader(
                    file_ids=[doc_google_drive_id], credentials=credentials_object
                )
            elif doc_item_type == "folder":
                loader = GoogleDriveLoader(
                    folder_id=doc_google_drive_id,
                    recursive=True,
                    include_folders=True,
                    credentials=credentials_object,
                )
            else:
                raise ValueError(f"Invalid item type: {doc_item_type}")

            docs_loaded = loader.load()

            logging.info(
                f"Loaded {len(docs_loaded)} Google docs from Google Drive {doc_item_type} with ID: \
{doc_google_drive_id}"
            )

            # if the docs_loaded is not None, add the loaded docs to the docs list
            if docs_loaded:
                docs.extend(docs_loaded)

                for loaded_doc in docs_loaded:
                    logging.info(
                        f"Loaded Google doc: {loaded_doc.metadata['title']} with ID: \
{doc_google_drive_id}"
                    )

        logging.debug(f"Total {len(docs)} Google docs loaded from Google Drive using langchain")

        return docs

    def update_last_indexed_for_docs(self, documents, job: job.Job) -> None:
        """Update the last indexed timestamp for the documents in the database.

        :param documents: the documents to update
        :param job: the job object
        """
        for doc in documents:
            doc_id = doc["google_drive_id"]
            logging.info(f"Updating last indexed timestamp for document: {doc_id}")

            # update the last indexed timestamp for the document in the database
            db = get_db_connection()
            cursor = db.cursor()
            try:
                cursor.execute(
                    "UPDATE google_drive_items SET last_indexed_at = NOW() \
WHERE google_drive_id = %s",
                    (doc_id,),
                )
                db.commit()
            finally:
                cursor.close()
                db.close()
