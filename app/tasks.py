"""Contains the tasks that are executed asynchronously."""

import logging
import os
import time

from rq import get_current_job

from app.helpers.chat import insert_message, insert_thread_ignore
from app.helpers.notifications import add_notification

# import the indexer
from lorelai.indexer import Indexer
from lorelai.indexers.googledriveindexer import GoogleDriveIndexer
from lorelai.indexers.slackindexer import SlackIndexer
from lorelai.llm import Llm

from app.schemas import OrganisationSchema, UserSchema, UserAuthSchema

logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)


def get_answer_from_rag(
    thread_id: str,
    chat_message: str,
    user_id: int,
    user_email: str,
    organisation_name: str,
    model_type: str = "OpenAILlm",
) -> dict:
    """Execute the RAG+LLM model."""
    from app.factory import create_app

    app = create_app()  # Create the Flask app
    with app.app_context():  # Set up the application context
        start_time = time.time()
        job = get_current_job()
        if job is None:
            raise ValueError("Could not get the current job.")
        logging.info("Task ID: %s, Message: %s", chat_message, job.id)
        logging.info("Session: %s, %s, %s", user_id, user_email, organisation_name)

        try:
            # create model
            logging.info("User email: %s, Org name: %s", user_email, organisation_name)

            if user_email is None or organisation_name is None:
                raise ValueError("User and organisation cannot be None.")

            thread_inserted = insert_thread_ignore(
                thread_id=str(thread_id), user_id=user_id, thread_name=chat_message[:20]
            )

            if not thread_inserted:
                logging.error(f"Failed to insert thread for user {user_id}")
                return {
                    "answer": "An error occurred while processing your request. Please try again.",
                    "status": "error",
                    "thread_id": thread_id,
                }

            # insert message
            insert_message(thread_id=str(thread_id), sender="user", message_content=chat_message)

            llm = Llm.create(
                model_type=model_type, user_email=user_email, org_name=organisation_name
            )
            response = llm.get_answer(question=chat_message)
            status = "success"

            logging.info(f"Get Answer time {time.time()-start_time}")

            logging.info("Answer: %s", response)
            insert_message(thread_id=str(thread_id), sender="bot", message_content=response)

            json_data = {
                "answer": response,
                "status": status,
                "thread_id": thread_id,
            }
        except Exception as e:
            logging.error(f"Error in get_answer_from_rag: {str(e)}")
            return {
                "answer": "An error occurred while processing your request. Please try again.",
                "status": "error",
                "thread_id": thread_id,
            }

        finally:
            end_time = time.time()
            logging.info(f"Worker Exec time: {end_time - start_time}")

        return json_data


def run_indexer(
    organisation: OrganisationSchema,
    users: list[UserSchema],
    user_auths: list[UserAuthSchema],
    started_by_user_id: int,
    indexer_class: type[Indexer] = None,
):
    """
    Run the indexer. Should be called from an rq job.

    Arguments
    ---------
    organisation: OrganisationSchema
        Organisation data.
    users: List[UserSchema]
        List of user data.
    user_auths: List[UserAuthSchema]
        List of user authentication data.
    indexer_class: type[Indexer]
        The indexer class to use.

    Returns
    -------
    dict: A dictionary containing the progress and result of the job.
    """
    from app.factory import create_app

    app = create_app()  # Create the Flask app
    with app.app_context():  # Set up the application context
        # Get the current job instance
        job = get_current_job()
        if job is None:
            raise ValueError("Could not get the current job.")

        logging.debug(f"Task ID -> Run Indexer: {job.id} for {organisation.name}")

        if indexer_class is None:
            indexers = [GoogleDriveIndexer, SlackIndexer]
        else:
            indexers = [indexer_class]

        for indexer_class in indexers:
            # Initialize indexer
            indexer = Indexer.create(indexer_class)

            # Initialize job meta with logs
            try:
                logging.debug(f"Starting indexing {indexer_class.__name__}...")
                job.meta["status"] = "Indexing"
                job.meta["logs"].append("Starting indexing...")
                job.save_meta()
                logging.debug(f"{organisation},{users},{user_auths},{job},")

                # Perform indexing
                results = indexer.index_org(
                    organisation=organisation,
                    users=users,
                    user_auths=user_auths,
                    job=job,
                )

                for result in results:
                    logging.debug(result)
                    job.meta["logs"].append(result)
                    job.save_meta()

                add_notification(
                    user_id=started_by_user_id,
                    title="Indexing completed",
                    type="success",
                    message=f"Indexing completed for {organisation.name}",
                )

                logging.debug("Indexing completed!")
            except Exception as e:
                logging.error(f"Error in run_indexer task: {str(e)}", exc_info=True)
                job.meta["logs"].append(f"Error in run_indexer task: {str(e)}")
                job.save_meta()
                job.set_status("failed")

                return job.meta["progress"]
