"""Contains the tasks that are executed asynchronously."""

import logging
import os
import time

from rq import get_current_job
from sentry_sdk import capture_exception, capture_message, set_tag, start_transaction

from app.helpers.chat import insert_conversation_ignore, insert_message
from app.helpers.notifications import add_notification
from app.schemas import OrganisationSchema, UserAuthSchema, UserSchema

# import the indexer
from lorelai.indexer import Indexer
from lorelai.indexers.googledriveindexer import GoogleDriveIndexer
from lorelai.indexers.slackindexer import SlackIndexer
from lorelai.llm import Llm

logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(module)s - %(pathname)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)


def get_answer_from_rag(
    conversation_id: str,
    chat_message: str,
    user_id: int,
    user_email: str,
    organisation_name: str,
    model_type: str = "OpenAILlm",
) -> dict:
    """Execute the RAG+LLM model."""
    # Initialize Sentry for the worker process

    from app.factory import create_app

    # from flask import current_app
    app = create_app()
    logging.debug("Starting task: get_answer_from_rag")
    with app.app_context():  # Set up the application context
        start_time = time.time()
        job = get_current_job()
        if job is None:
            raise ValueError("Could not get the current job.")
        logging.info("Task ID: %s, Message: %s", chat_message, job.id)
        logging.info("Session: %s, %s, %s", user_id, user_email, organisation_name)
        # Start Sentry transaction
        with start_transaction(name="get_answer_from_rag", op="rq.task"):
            try:
                # Measure time for inserting conversation
                conversation_start_time = time.time()
                capture_message("BULBASUR")
                logging.info("User email: %s, Org name: %s", user_email, organisation_name)

                if user_email is None or organisation_name is None:
                    raise ValueError("User and organisation cannot be None.")

                conversation_inserted = insert_conversation_ignore(
                    conversation_id=str(conversation_id),
                    user_id=user_id,
                    conversation_name=chat_message[:20],
                )

                if not conversation_inserted:
                    logging.error(f"Failed to insert conversation for user {user_id}")
                    return {
                        "answer": "An error occurred while processing your request. Please try again.",  # noqa: E501
                        "status": "error",
                        "conversation_id": conversation_id,
                    }

                # Log time taken for inserting conversation
                conversation_time_taken = time.time() - conversation_start_time
                set_tag("conversation_insertion_time", conversation_time_taken)
                logging.info(f"Conversation insertion took {conversation_time_taken:.2f} seconds.")

                # Measure time for inserting message
                message_start_time = time.time()
                insert_message(
                    conversation_id=str(conversation_id),
                    sender="user",
                    message_content=chat_message,
                )

                message_time_taken = time.time() - message_start_time
                set_tag("message_insertion_time", message_time_taken)
                logging.info(f"Message insertion took {message_time_taken:.2f} seconds.")

                # Measure time for LLM creation and getting answer
                llm = Llm.create(
                    model_type=model_type, user_email=user_email, org_name=organisation_name
                )
                get_answer_time_start = time.time()
                response = llm.get_answer(question=chat_message)
                status = "success"

                # Log time taken for getting the answer
                get_answer_time_taken = time.time() - get_answer_time_start
                set_tag("get_answer_time", get_answer_time_taken)
                logging.info(f"Get Answer took {get_answer_time_taken:.2f} seconds.")

                logging.info("Answer: %s", response)

                # Measure time for inserting the bot's response message
                insert_response_start_time = time.time()
                insert_message(
                    conversation_id=str(conversation_id), sender="bot", message_content=response
                )

                insert_response_time_taken = time.time() - insert_response_start_time
                set_tag("insert_response_time", insert_response_time_taken)
                logging.info(
                    f"Inserting bot response took {insert_response_time_taken:.2f} seconds."
                )

                json_data = {
                    "answer": response,
                    "status": status,
                    "conversation_id": conversation_id,
                }

            except Exception as e:
                # Capture exception with Sentry
                capture_exception(e)
                capture_message("err in exp")
                logging.error(f"Error in get_answer_from_rag: {str(e)}")
                return {
                    "answer": "An error occurred while processing your request. Please try again.",
                    "status": "error",
                    "conversation_id": conversation_id,
                }

            finally:
                end_time = time.time()
                total_time_taken = end_time - start_time
                set_tag("total_execution_time", total_time_taken)
                logging.info(f"Worker Exec time: {total_time_taken:.2f} seconds")

        return json_data


def run_indexer(
    organisation: OrganisationSchema,
    users: list[UserSchema],
    user_auths: list[UserAuthSchema],
    started_by_user_id: int,
    indexer_class: type[Indexer] = None,
) -> None:
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
        The indexer class to use (optional, defaults to all indexers)

    Returns
    -------
    None
    """
    from app.factory import create_app

    app = create_app()  # Create the Flask app
    with app.app_context():  # Set up the application context
        # Get the current job instance
        with start_transaction(name="run_indexer", op="rq.task"):
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
                indexer = Indexer.create(indexer_type=indexer_class.__name__)

                # Initialize job meta with logs
                try:
                    logging.debug(f"Starting indexing {indexer_class.__name__}...")
                    job.meta["status"] = "Indexing"
                    job.save_meta()

                    # Perform indexing
                    indexer.index_org(
                        organisation=organisation,
                        users=users,
                        user_auths=user_auths,
                        job=job,
                    )

                    add_notification(
                        user_id=started_by_user_id,
                        title="Indexing completed",
                        type="success",
                        message=f"Indexing completed for {organisation.name}",
                    )

                    logging.debug("Indexing completed!")
                except Exception as e:
                    logging.error(f"Error in run_indexer task: {str(e)}", exc_info=True)
                    job.set_status("failed")
