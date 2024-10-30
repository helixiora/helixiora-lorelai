"""Abstract class for an indexer that indexes data into Pinecone."""

import logging
from rq import job
import importlib
from app.schemas import OrganisationSchema, UserSchema, UserAuthSchema

# The scopes needed to read documents in Google Drive
# (see: https://developers.google.com/drive/api/guides/api-specific-auth)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class Indexer:
    """Used to process a datasource's documents and index them in Pinecone."""

    _allowed = False  # Flag to control constructor access

    @staticmethod
    def create(indexer_type: str = "GoogleDriveIndexer") -> "Indexer":
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
        module = importlib.import_module(f"lorelai.indexers.{indexer_type.lower()}")
        class_ = getattr(module, indexer_type)
        if class_ is None or not issubclass(class_, Indexer):
            Indexer._allowed = False
            raise ValueError(f"Unsupported indexer type: {indexer_type}")
        instance = class_()
        Indexer._allowed = False
        return instance

    def __init__(self):
        if not self._allowed:
            raise Exception("This class should be instantiated through a create() factory method.")

    def get_indexer_name(self) -> str:
        """Retrieve the name of the indexer."""
        return self.__class__.__name__

    def index_org(
        self,
        organisation: OrganisationSchema,
        users: list[UserSchema],
        user_auths: list[UserAuthSchema],
        job: job.Job | None = None,
    ) -> list[dict[str, any]]:
        """Process the organisation, indexing all its users.

        Arguments
        ---------
        org_row: OrganisationSchema
            The organisation to process.
        users: list[UserSchema]
            The users to process.
        user_auths: list[UserAuthSchema]
            The user auth rows for all users.
        job: job.Job | None
            The job object for the current task.

        Returns
        -------
        list[dict[str, any]]
            A list of dictionaries containing the results of indexing each user.
        """
        logging.debug(f"Indexing org: {organisation.name}")
        logging.debug(f"Users: {[user.email for user in users]}")
        logging.debug(f"User auths: {user_auths}")

        if job:
            logging.info("Task ID: %s, Message: %s", job.id, job.meta["status"])
            logging.info("Indexing %s: %s", self.get_indexer_name(), job.id)

        result = []
        for user in users:
            if job:
                job.meta["org"] = organisation.name
                job.meta["user"] = user.email
                job.save_meta()

            # get the user auth rows for this user
            user_auth_rows_filtered = [
                user_auth_row for user_auth_row in user_auths if user_auth_row.user_id == user.id
            ]

            # index the user
            success = self.index_user(
                user=user,
                organisation=organisation,
                user_auths=user_auth_rows_filtered,
                job=job,
            )

            message = f"User {user.email} indexing {'succeeded' if success else 'failed'}"
            logging.info(message)

            if job:
                job.meta["org"] = organisation.name
                job.meta["user"] = user.email
                job.save_meta()

            result.append(
                {
                    "job_id": job.id if job else "",
                    "user_id": user.id,
                    "success": success,
                    "message": message,
                }
            )

        logging.debug(f"Indexing complete for org: {organisation.name}. Results: {result}")
        return result

    def index_user(
        self,
        user: UserSchema,
        organisation: OrganisationSchema,
        user_auths: list[UserAuthSchema],
        job: job.Job | None,
    ) -> tuple[bool, str]:
        """Process the Google Drive documents for a user and index them in Pinecone.

        Arguments
        ---------
        user: UserSchema
            The user to process.
        organisation: OrganisationSchema
            The organisation to process.
        user_auths: list[UserAuthSchema]
            The user auth rows for the user.
        job: job.Job | None
            The job object for the current task.

        Returns
        -------
        Tuple[bool, str]
            A tuple containing a success flag and a message.
        """
        raise NotImplementedError
