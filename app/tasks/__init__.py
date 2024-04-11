"""
This module contains the tasks that are executed asynchronously.
"""

import json
import logging
import sqlite3
import time

from rq import get_current_job

from app.utils import get_db_connection
# import the indexer
from lorelai.contextretriever import ContextRetriever
from lorelai.indexer import Indexer
from lorelai.llm import Llm


def execute_rag_llm(chat_message: str, user: str, organisation: str) -> dict:
    """
    A task to execute the RAG+LLM model.
    """
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")
    logger = logging.getLogger(__name__)

    logger.info("Task ID: %s, Message: %s", chat_message, job.id)
    logger.info("Session: %s, %s", user, organisation)

    try:
        # Get the context for the question
        enriched_context = ContextRetriever(org_name=organisation, user=user)
        context, source = enriched_context.retrieve_context(chat_message)

        if context is None:
            raise ValueError("Failed to retrieve context for the provided chat message.")

        llm = Llm(model="gpt-3.5-turbo")
        answer = llm.get_answer(question=chat_message, context=context)

        logger.info("Answer: %s", answer)
        logger.info("Source: %s", source)

        json_data = {"answer": answer, "source": source, "status": "Success"}

    except Exception as e:
        logger.error("Error in execute_rag_llm task: %s", str(e))
        json_data = {"error": str(e), "status": "Failed"}
        # Optionally, re-raise the exception if you want the task to be marked as failed
        raise e

    return json_data


def run_indexer():
    """
    An rq job to run the indexer
    """
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")

    print(f"Task ID -> Run Indexer: {job.id}")

    conn = get_db_connection()
    try:
        # Connect to SQLite database
        cur = conn.cursor()

        # Fetch organisations
        cur.execute("SELECT id, name FROM organisations")
        org_rows = cur.fetchall()

        for org in org_rows:
            # Fetch user credentials for this org
            cur.execute(
                "SELECT user_id, name, email, access_token, refresh_token FROM users \n"
                "WHERE org_id = ?",
                (org[0],),
            )
            users = cur.fetchall()

            # Initialize indexer and perform indexing
            indexer = Indexer()
            indexer.index_org_drive(org, users)

        print("Indexing completed!")
        return {"current": 100, "total": 100, "status": "Task completed!", "result": 42}
    except Exception as e:  # pylint: disable=broad-except
        # Handle any other exceptions that occur during the indexing process
        print(f"An error occurred: {str(e)}")
        return {"current": 0, "total": 100, "status": "Failed", "result": 0}
    finally:
        # Ensure the database connection is closed
        conn.close()
