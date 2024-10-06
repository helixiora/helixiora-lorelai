"""Contains the tasks that are executed asynchronously."""

import logging
import os
import time

from rq import get_current_job

from app.helpers.chat import insert_message, insert_thread_ignore
from app.helpers.notifications import add_notification

# import the indexer
from lorelai.indexer import Indexer
from lorelai.llm import Llm
from lorelai.indexers.slackindexer import SlackIndexer

logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)


def get_answer_from_rag(
    thread_id: str,
    chat_message: str,
    user_id,
    user: str,
    organisation: str,
    model_type: str = "OpenAILlm",
    datasource: str = None,
) -> dict:
    """Execute the RAG+LLM model.

    Arguments
    ---------
    chat_message : str
        The chat message.
    user : str
        The user email.
    organisation : str
        The organisation name.
    model_type : str, optional
        The model type to use (OpenAI, Llama3, etc). Default is "OpenAILlm".

    Returns
    -------
    dict
        The answer and source of the answer.

    Raises
    ------
    ValueError
        If the user or organisation is None.
    """
    start_time = time.time()
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")
    logging.info("Task ID: %s, Message: %s", chat_message, job.id)
    logging.info("Session: %s, %s, %s", user_id, user, organisation)

    try:
        # create model
        logging.info("User email: %s, Org name: %s", user, organisation)

        if user is None or organisation is None:
            raise ValueError("User and organisation cannot be None.")

        # insert chat thread
        insert_thread_ignore(
            thread_id=str(thread_id), user_id=user_id, thread_name=chat_message[:20]
        )

        # insert message
        insert_message(thread_id=str(thread_id), sender="user", message_content=chat_message)

        llm = Llm.create(model_type=model_type, user=user, organization=organisation)
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
    finally:
        end_time = time.time()
        logging.info(f"Worker Exec time: {end_time - start_time}")

    return json_data


def run_indexer(
    org_row: list[any],
    user_rows: list[any],
    user_auth_rows: list[any],
    user_data_rows: list[any],
    started_by_user_id: int,
):
    """
    Run the indexer. Should be called from an rq job.

    Arguments
    ---------
    org_row (List[any]): Organization data.
    user_rows (List[any]): List of user data.
    user_auth_rows (List[any]): List of user authentication data.

    Returns
    -------
    dict: A dictionary containing the progress and result of the job.
    """
    # Get the current job instance
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")

    logging.debug(f"Task ID -> Run Indexer: {job.id} for {org_row}")

    # Initialize indexer
    indexer = Indexer.create("GoogleDriveIndexer")

    # Initialize job meta with logs
    job.meta["progress"] = {"current": 0, "total": 100, "status": "Initializing indexing..."}
    job.meta["logs"] = []
    job.save_meta()

    try:
        logging.debug("Starting indexing...")
        job.meta["status"] = "Indexing"
        job.meta["logs"].append("Starting indexing...")
        job.save_meta()
        logging.debug(f"{org_row},{user_rows},{user_auth_rows},{job},")

        # Perform indexing
        results = indexer.index_org(
            user_rows=user_rows,
            user_auth_rows=user_auth_rows,
            user_data_rows=user_data_rows,
            org_row=org_row,
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
            message=f"Indexing completed for {org_row['name']}",
        )

        logging.debug("Indexing completed!")
    except Exception as e:
        logging.error(f"Error in run_indexer task: {str(e)}", exc_info=True)
        job.meta["logs"].append(f"Error in run_indexer task: {str(e)}")
        job.meta["progress"] = {
            "current": 100,
            "total": 100,
            "status": f"Task failed! {e}",
            "result": 0,
        }
        job.save_meta()
        job.set_status("failed")

        return job.meta["progress"]


def run_slack_indexer(user_email: str, org_name: str):
    """
    Run the Slack indexer for a given user and organization.

    This function retrieves the current job, logs task information, and initializes
    the indexing progress. It then creates a SlackIndexer instance for the specified
    user and organization, and starts processing Slack messages.

    Args:
        user_email (str): The email of the user running the indexer.
        org_name (str): The name of the organization for which the Slack data is being indexed.
    """
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")

    logging.info(f"Task ID -> Run Slack Indexer: {job.id} for {org_name}")

    # Initialize job meta with logs
    job.meta["progress"] = {"current": 0, "total": 100, "status": "Initializing indexing..."}
    job.meta["logs"] = []
    job.save_meta()

    indexer = SlackIndexer(user_email, org_name)

    # this should be a generic function that can be called for any indexer
    indexer.process_slack_message()

    logging.info(f"Slack Indexer Completed for {org_name}")
