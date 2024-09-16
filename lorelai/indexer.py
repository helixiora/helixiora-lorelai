"""Creates a class to process Google Drive documents using the Google Drive API.

Chunk them using Langchain, and then index them in Pinecone.
"""

import logging
import os
from rq import job

import lorelai.utils

# The scopes needed to read documents in Google Drive
# (see: https://developers.google.com/drive/api/guides/api-specific-auth)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class Indexer:
    """Used to process a datasource's documents and index them in Pinecone."""

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
        user_data_rows: list[dict[str, any]],
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
            logging.info("Task ID: %s, Message: %s", job.id, job.meta["status"])
            logging.info("Indexing %s: %s", self.get_indexer_name(), job.id)
            job.meta["logs"].append(f"Task ID: {job.id}, Message: {job.meta['status']}")
            job.meta["logs"].append(f"Indexing {self.get_indexer_name()}: {job.id}")

        result = []
        for user_row in user_rows:
            if job:
                job.meta["logs"].append(
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
            success = self.index_user(
                user_row=user_row,
                org_row=org_row,
                user_auth_rows=user_auth_rows_filtered,
                user_data_rows=user_data_rows,
                job=job,
            )

            message = f"User {user_row['email']} indexing {'succeeded' if success else 'failed'}"
            logging.info(message)

            if job:
                job.meta[
                    "logs"
                ].append(f"Indexing {self.get_indexer_name()} for user {user_row['email']}: \
                        {'succeeded' if success else 'failed'}")
                job.meta["org"] = org_row["name"]
                job.meta["user"] = user_row["email"]
                job.save_meta()

            result.append(
                {
                    "job_id": job.id if job else "",
                    "user_id": user_row["user_id"],
                    "success": success,
                    "message": message,
                }
            )

        logging.debug(f"Indexing complete for org: {org_row['name']}. Results: {result}")
        return result

    def index_user(
        self,
        user_row: dict[str, any],
        org_row: dict[str, any],
        user_auth_rows: list[dict[str, any]],
        user_data_rows: list[dict[str, any]],
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
