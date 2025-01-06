"""Abstract class for an indexer that indexes data into Pinecone."""

import logging
from rq import job
import importlib
from app.schemas import OrganisationSchema, UserSchema, UserAuthSchema, IndexingRunSchema
from app.models import db
from app.models.indexing import IndexingRun, IndexingRunItem
from app.models.datasource import Datasource

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

    def _get_datasource(self) -> Datasource:
        """Get the datasource for this indexer. Must be implemented by derived classes."""
        raise NotImplementedError

    def index_org(
        self,
        organisation: OrganisationSchema,
        users: list[UserSchema],
        user_auths: list[UserAuthSchema],
        job: job.Job,
    ) -> None:
        """Process the organisation, indexing all its users.

        This method should be called from an rq job. It will create an indexing run and index each
        user. It will return a list of dictionaries containing the results of indexing each user.

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
        None
        """
        logging.debug(f"Indexing org: {organisation.name}")
        logging.debug(f"Users: {[user.email for user in users]}")
        logging.debug(
            f"User auths for datasource {self._get_datasource().datasource_name}: {user_auths}"
        )

        if job:
            logging.info("Task ID: %s, Message: %s", job.id, job.meta["status"])
            logging.info("Indexing %s: %s", self.get_indexer_name(), job.id)

        # Get the datasource ID based on the indexer type
        datasource = self._get_datasource()
        if not datasource:
            logging.error("Could not find datasource for this Indexer class")
            return

        for user in users:
            # create a new indexing run in the database, this is used for logging and tracking
            indexing_run = IndexingRun(
                rq_job_id=job.id,
                status="pending",
                user_id=user.id,
                organisation_id=organisation.id,
                datasource_id=datasource.datasource_id,
            )
            db.session.add(indexing_run)
            db.session.commit()

            try:
                # get the user auth rows for this user and datasource
                user_auth_rows_filtered = [
                    user_auth_row
                    for user_auth_row in user_auths
                    if str(user_auth_row.user_id) == str(user.id)
                    and str(user_auth_row.datasource_id) == str(datasource.datasource_id)
                ]
                if not user_auth_rows_filtered or len(user_auth_rows_filtered) == 0:
                    logging.info(
                        f"No auth rows found for user {user.email} (id: {user.id}) for datasource \
{datasource.datasource_name}"
                    )
                    indexing_run.status = "completed"
                    indexing_run.error = (
                        f"No auth rows found for user for datasource {datasource.datasource_name}"
                    )
                    db.session.commit()
                    continue

                # Refresh to ensure relationships are loaded
                db.session.refresh(indexing_run)

                # Explicitly load the relationships
                _ = indexing_run.user
                _ = indexing_run.organisation
                _ = indexing_run.datasource

                # Convert the model to a schema
                indexing_run_schema = IndexingRunSchema.from_orm(indexing_run)

                # index the user
                self.index_user(
                    indexing_run=indexing_run_schema,
                    user_auths=user_auth_rows_filtered,
                )
            except Exception as e:
                logging.error(f"Error indexing user {user.email}: {e}")
                indexing_run.status = "failed"
                indexing_run.error = str(e)
                db.session.commit()
                continue

            finally:
                total_items = IndexingRunItem.query.filter_by(
                    indexing_run_id=indexing_run.id
                ).count()
                logging.info(
                    f"Total items for indexing run {indexing_run.id} for user {user.email} for \
datasource {datasource.datasource_name}: {total_items}"
                )

                # Update run status based on items
                failed_items = IndexingRunItem.query.filter_by(
                    indexing_run_id=indexing_run.id, item_status="failed"
                ).count()

                if failed_items > 0:
                    indexing_run.status = "completed_with_errors"
                    indexing_run.error = f"Failed items: {failed_items}; Total items: {total_items}"
                else:
                    indexing_run.status = "completed"
                    indexing_run.error = f"No errors; Total items: {total_items}"

                db.session.commit()

        logging.debug(f"Indexing complete for org: {organisation.name}")

    def index_user(
        self,
        indexing_run: IndexingRunSchema,
        user_auths: list[UserAuthSchema],
    ) -> None:
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
        None
        """
        raise NotImplementedError
