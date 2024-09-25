"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveIndexer: Handles Google Drive document indexing using Pinecone and OpenAI.
"""

import logging

from lorelai.indexer import Indexer
from lorelai.processor import Processor

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
        pinecone_processor = Processor()
        pinecone_processor.google_docs_to_pinecone_docs(
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
