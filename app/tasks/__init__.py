"""Contains the tasks that are executed asynchronously."""

import json
import logging
import os
import time

from rq import get_current_job

from app.helpers.datasources import get_datasources_name
from app.helpers.chat import insert_message, insert_thread_ignore

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
    datasource : str, optional
        The datasource to use (Slack, Google Drive, Direct, etc). Default is None.

    Returns
    -------
    dict
        The answer and source of the answer.

    Raises
    ------
    ValueError
        If the user or organisation is None.
    """
    execute_rag_llm_start_time = time.time()
    job = get_current_job()
    if job is None:
        raise ValueError("Could not get the current job.")
    logging.info("Task ID: %s, Message: %s", chat_message, job.id)
    logging.info("Session: %s, %s, %s", user_id, user, organisation)
    logging.debug("Datasource %s", datasource)

    db_datasource_list = get_datasources_name()
    if datasource not in db_datasource_list:
        raise ValueError(f"Invalid datasource provided. Received: {datasource}")

    try:
        # create model
        logging.info("User email: %s, Org name: %s", user, organisation)

        if user is None or organisation is None:
            raise ValueError("User and organisation cannot be None.")

        llm = Llm.create(model_type=model_type)

        # insert chat thread
        insert_thread_ignore(
            thread_id=str(thread_id), user_id=user_id, thread_name=chat_message[:20]
        )

        # insert message
        insert_message(thread_id=str(thread_id), sender="user", message_content=chat_message)

        # Get the context for the question
        if datasource == "Direct":
            answer = llm.get_answer_direct(question=chat_message)
            source = None
            status = "Success"
        else:
            # have to change Retriever type based on data source.
            enriched_context = ContextRetriever.create(
                retriever_type="GoogleDriveContextRetriever",
                org_name=organisation,
                user=user,
            )
            try:
                start_time = time.time()
                context, source = enriched_context.retrieve_context(chat_message)
                logging.debug(f"Source: {source}")

                # remove any sources with less than 0.5 score, they are irrelevant
                source = [
                    source_item for source_item in source if float(source_item["score"]) >= 0.5
                ]
                logging.debug(f"Filtered Source: {source}")
                logging.info(f"Context Retriever time {time.time()-start_time}")
                if source is None or len(source) == 0:
                    no_relevant_source = True
                else:
                    no_relevant_source = False

                if context is None:
                    raise ValueError("Failed to retrieve context for the provided chat message.")
            except ValueError as e:
                logging.error("(ValueError): Error in retrieving context: %s", str(e))
                if "Index not found: " in str(e):
                    raise ValueError("Index not found. Please index something first.") from e
                raise  # Re-raise the ValueError to be caught by the outer except block
            except Exception as e:
                logging.error(f"Error in retrieving context: {str(e)}")
                raise Exception("Something went wrong") from e

            start_time = time.time()
            if no_relevant_source:
                answer = ""
                status = "No Relevant Source"
            else:
                answer = llm.get_answer(question=chat_message, context=context)
                status = "Success"
            logging.info(f"Get Answer time {time.time()-start_time}")

        logging.info("Answer: %s", answer)
        logging.info("Source: %s", source)
        logging.debug(f"Source Type: {type(source)}")

        json_data = {
            "answer": answer,
            "source": source,
            "status": status,
            "datasource": datasource,
        }

    except ValueError as e:
        logging.error("ValueError in execute_rag_llm task: %s", str(e))
        json_data = {"error": str(e), "status": "Failed"}
        return json_data
    except Exception as e:
        logging.error("Error in execute_rag_llm task: %s", str(e))
        json_data = {"error": str(e), "status": "Failed"}
        return json_data
    finally:
        end_time = time.time()
        logging.info(f"Worker Exec time: {end_time - execute_rag_llm_start_time}")

    insert_message(
        thread_id=str(thread_id),
        sender="bot",
        message_content=answer if answer else "No Response",
        sources=json.dumps(source),
    )
    return json_data


def run_indexer(
    org_row: list[any],
    user_rows: list[any],
    user_auth_rows: list[any],
    user_data_rows: list[any],
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
        logging.info(f"{org_row},{user_rows},{user_auth_rows},{job},")
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
