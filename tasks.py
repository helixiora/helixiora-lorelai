"""
This file contains the rq jobs that are executed asynchronously.
"""

import logging
from typing import Any

from rq import get_current_job


# import the indexer
from lorelai.contextretriever import ContextRetriever
from lorelai.indexer import Indexer
from lorelai.llm import Llm


def execute_rag_llm(chat_message, user, organisation):
    """
    An rq job to execute the RAG+LLM model.
    """
    job = get_current_job()
    logger = logging.getLogger(__name__)

    logger.info(f"Task ID: {job.id}, Message: {chat_message}")
    logger.info(f"Session: {user}, {organisation}")

    try:
        # Get the context for the question
        enriched_context = ContextRetriever(org_name=organisation, user=user)
        context, source = enriched_context.retrieve_context(chat_message)

        if context is None:
            raise ValueError("Failed to retrieve context for the provided chat message.")

        llm = Llm(model="gpt-3.5-turbo")
        answer = llm.get_answer(question=chat_message, context=context)

        logger.info(f"Answer: {answer}")
        logger.info(f"Source: {source}")

        json_data = {"answer": answer, "source": source, "status": "Success"}

    except Exception as e:
        logger.error(f"Error in execute_rag_llm task: {str(e)}")
        json_data = {"error": str(e), "status": "Failed"}
        # Optionally, re-raise the exception if you want the task to be marked as failed
        raise e

    return json_data


# TODO: this won't fly if we're running in containers, the sqlite db will be in a different location
# to fix we need to pass the needed info as parameters from the main app
def run_indexer(org_row: list[Any], user_rows: list[list[Any]]):
    """Run the indexer job to index the Google Drive documents in Pinecone."""
    job = get_current_job()

    print(f"Task ID -> Run Indexer: {job.id}")

    try:
        # Initialize indexer and perform indexing
        indexer = Indexer()
        indexer.index_org_drive(org_row, user_rows)

        print("Indexing completed!")
        return {"current": 100, "total": 100, "status": "Task completed!", "result": 42}
    except Exception as e:
        # Handle any exceptions that occur during the indexing process
        print(f"An error occurred: {str(e)}")
        return {"current": 0, "total": 100, "status": "Failed", "result": 0}
    finally:
        # Ensure the database connection is closed
        conn.close()
