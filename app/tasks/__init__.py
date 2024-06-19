"""Contains the tasks that are executed asynchronously."""

import logging
import os
from datetime import time

from rq import get_current_job

# import the indexer
from lorelai.contextretriever import ContextRetriever
from lorelai.indexer import Indexer
from lorelai.llm import Llm

logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)


def execute_rag_llm(
    chat_message: str, user: str, organisation: str, model_type: str = "OpenAILlm"
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
        The model type to use. Default is "OpenAILlm".

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
    logging.info("User email: %s, Org name: %s", user, organisation)

    if user is None or organisation is None:
        raise ValueError("User and organisation cannot be None.")

    try:
        # Get the context for the question
        enriched_context = ContextRetriever(org_name=organisation, user_email=user)
        context, source = enriched_context.retrieve_context(chat_message)

        if context is None:
            raise ValueError("Failed to retrieve context for the provided chat message.")

        llm = Llm.create(model_type=model_type)
        logging.info(f"LLM Status: {llm.get_llm_status()}")
        answer = llm.get_answer(question=chat_message, context=context)

        logging.info("Answer: %s", answer)
        logging.info("Source: %s", source)

        json_data = {"answer": answer, "source": source, "status": "Success"}

    except Exception as e:
        logging.error("Error in execute_rag_llm task: %s", str(e))
        json_data = {"error": str(e), "status": "Failed"}
        # Optionally, re-raise the exception if you want the task to be marked as failed
        raise e
    end_time = time.time()
    logging.info(f"Worker Exec time: {end_time-start_time}")
    return json_data


def run_indexer(
    org_row: list[any],
    user_rows: list[any],
    user_auth_rows: list[any],
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
        job.meta["logs"].append("Starting indexing...")
        job.save_meta()

        # Perform indexing
        results = indexer.index_org(org_row, user_rows, user_auth_rows, job)

        for result in results:
            logging.debug(result)
            job.meta["logs"].append(result)
            job.save_meta()

        logging.debug("Indexing completed!")
    except Exception as e:
        logging.error(f"Error in run_indexer task: {str(e)}")
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
