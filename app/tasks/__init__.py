"""
This module contains the tasks that are executed asynchronously.
"""

import logging
import os
import time
from typing import List

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
    chat_message: str,
    user: str,
    organisation: str,
    model_type: str = "OpenAILlm",
    datasource: str = None,
) -> dict:
    """
    A task to execute the RAG+LLM model.
    """
    start_time = time.time()
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")

    logging.info("Task ID: %s, Message: %s", chat_message, job.id)
    logging.info("Session: %s, %s", user, organisation)
    print("data sorce", datasource)
    try:
        # create model
        llm = Llm.create(model_type=model_type)

        # Get the context for the question
        if datasource == "direct":
            logging.info(f"LLM Status: {llm.get_llm_status()}")
            answer = llm.get_answer_direct(question=chat_message)
            source = "OpenAI"
        else:
            #enriched_context = ContextRetriever.create()
            enriched_context = ContextRetriever(org_name=organisation, user=user)
            context, source = enriched_context.retrieve_context(chat_message)

            if context is None:
                raise ValueError("Failed to retrieve context for the provided chat message.")

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
    org_row: List[any],
    user_rows: List[any],
):
    """
    An rq job to run the indexer
    """
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")

    logging.debug(f"Task ID -> Run Indexer: {job.id} for {org_row} ")

    # Initialize indexer and perform indexing
    indexer = Indexer()

    success = indexer.index_org_drive(org_row, user_rows)
    if success:
        logging.debug("Indexing completed!")
        return {"current": 100, "total": 100, "status": "Task completed!", "result": 42}
    else:
        logging.error("Indexing failed!")
        return {"current": 100, "total": 100, "status": "Task failed!", "result": 0}
