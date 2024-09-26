"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveIndexer: Handles Google Drive document indexing using Pinecone and OpenAI.
"""

import logging

from lorelai.indexer import Indexer
from lorelai.processor import Processor
from langchain_google_community.drive import GoogleDriveLoader
from lorelai.utils import load_config, save_google_creds_to_tempfile, get_db_connection
from rq import job


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

            if user_data_row["item_type"] not in ["document", "folder"]:
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
            job.meta["logs"].append(
                f"No Google Drive documents found for user: {user_row['email']}"
            )
            # return True, f"No Google Drive documents found for user: {user_row['email']}"

        # 5. Process the Google Drive documents and index them in Pinecone
        logging.info(f"Processing {len(documents)} Google documents for user: {user_row['email']}")
        job.meta["logs"].append(
            f"Processing {len(documents)} Google documents for user: {user_row['email']}"
        )

        self.google_docs_to_pinecone_docs(
            documents=documents,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            org_name=org_row["name"],
            user_email=user_row["email"],
            job=job,
        )

        logging.info(f"Indexing complete for user: {user_row['email']}")
        job.meta["logs"].append(f"Indexing complete for user: {user_row['email']}")

        return True

    def google_docs_to_pinecone_docs(
        self: None,
        documents: list[str],
        access_token: str,
        refresh_token: str,
        expires_at: int,
        org_name: str,
        user_email: str,
        job: job.Job,
    ) -> None:
        """Process the Google Drive documents and divide them into pinecone compatible chunks.

        :param documents: the list of google document ids to process
        :param access_token: the access token to use for Google Drive API
        :param refresh_token: the refresh token to use for Google Drive API
        :param expires_at: the expiry time of the access token
        :param org_name: the name of the organization
        :param user_email: the user to process
        :param job: the job object

        :return: None
        """
        google_creds = load_config("google")

        # save the google creds to a tempfile as they are needed by the langchain google drive
        # loader until this issue is fixed: https://github.com/langchain-ai/langchain/issues/15058
        save_google_creds_to_tempfile(
            access_token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=google_creds["client_id"],
            client_secret=google_creds["client_secret"],
        )

        docs = []
        # documents contain a list of dictionaries with the following keys:
        # user_id, google_drive_id, item_type, item_name
        # loop through the documents and load them from Google Drive
        for doc in documents:
            doc_user_id = doc["user_id"]
            doc_google_drive_id = doc["google_drive_id"]
            doc_item_type = doc["item_type"]
            doc_item_name = doc["item_name"]

            if doc_item_type not in ["document", "folder"]:
                logging.error(f"Invalid item type: {doc_item_type}")
                raise ValueError(f"Invalid item type: {doc_item_type}")

            logging.info(
                f"Loading {doc_item_type}: {doc_item_name} ({doc_google_drive_id}) \
for user: {doc_user_id}"  # noqa
            )
            if doc_item_type == "document":
                drive_loader = GoogleDriveLoader(document_ids=[doc_google_drive_id])
            elif doc_item_type == "folder":
                drive_loader = GoogleDriveLoader(
                    folder_id=doc_google_drive_id, recursive=True, include_folders=True
                )

            # use langchain google drive loader to load the content of the docs from google drive
            docs_loaded = drive_loader.load()

            # if the docs_loaded is not None, add the loaded docs to the docs list
            if docs_loaded:
                docs.extend(docs_loaded)
                logging.info(f"Loaded {len(docs_loaded)} Google docs from Google Drive \
                    {doc_item_type} {doc_item_name}")
                job.meta["logs"].append(f"Loaded {len(docs_loaded)} Google docs from Google Drive \
                    {doc_item_type} {doc_item_name}")

                # if the doc_item_type is a folder, log the loaded docs
                if doc_item_type == "folder":
                    for loaded_doc in docs_loaded:
                        logging.info(
                            f"Loaded Google doc: {loaded_doc.metadata['title']} \
                                (source: {loaded_doc.metadata['source']})"
                        )
                        job.meta["logs"].append(
                            f"Loaded Google doc: {loaded_doc.metadata['title']} \
                                (source: {loaded_doc.metadata['source']})"
                        )

        logging.debug(f"Loaded {len(docs)} Google docs from Google Drive")

        # go through all docs. For each doc, see if the user is already in the metadata. If not,
        # add the user to the metadata
        for loaded_doc in docs:
            logging.info(f"Checking metadata users for Google doc: {loaded_doc.metadata['title']}")
            # check if the user key is in the metadata
            if "users" not in loaded_doc.metadata:
                loaded_doc.metadata["users"] = []
            # check if the user is in the metadata
            if user_email not in loaded_doc.metadata["users"]:
                logging.info(
                    f"Adding user {user_email} to doc.metadata['users'] for \
 metadata.users ${loaded_doc.metadata['users']}"
                )
                loaded_doc.metadata["users"].append(user_email)

        pinecone_processor = Processor()

        # store the documents in Pinecone
        new_docs_added = pinecone_processor.store_docs_in_pinecone(
            docs, user_email=user_email, job=job, org_name=org_name, datasource="googledrive"
        )

        self.update_last_indexed_for_docs(documents, job)

        logging.info(f"Processed {len(docs)} documents for user: {user_email}")
        job.meta["logs"].append(f"Processed {len(docs)} documents for user: {user_email}")
        return {"new_docs_added": new_docs_added}

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

        job.meta["logs"].append(f"Updated last indexed timestamp for {len(documents)} documents")
