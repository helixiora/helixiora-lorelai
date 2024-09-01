"""Chat related helper functions."""

import logging
from datetime import datetime, timedelta

from app.helpers.users import is_admin
from app.helpers.datasources import get_datasources_name
from app.helpers.database import get_db_connection


def get_chat_template_requirements(thread_id: str, user_id: int):
    """
    Retrieve the chat template requirements for a given thread.

    Args:
        thread_id (str): The ID of the thread whose chat template requirements are to be retrieved.
        user_id (int): The ID of the user whose chat template requirements are to be retrieved.

    Returns
    -------
        dict: A dictionary containing the chat template requirements.
    """
    datasources = get_datasources_name()

    recent_conversations = get_recent_threads(user_id)

    is_admin_status = is_admin(user_id)

    return {
        "datasources": datasources,
        "recent_conversations": recent_conversations,
        "is_admin_status": is_admin_status,
    }


def get_msg_count_last_24hr(user_id: int):
    """
    Retrieve the count of chat messages for a specified user from the last 24 hours.

    Args:
        user_id (int): The ID of the user whose messages are to be counted.

    Returns
    -------
        int: The number of chat messages sent by the specified user in the last 24 hours.

    Raises
    ------
        Exception: If there is an error connecting to the database or executing the query.
    """
    try:
        with get_db_connection() as db:
            past_24_hours_time = datetime.now() - timedelta(days=1)
            cursor = db.cursor()
            query = """
                    SELECT t.user_id, COUNT(m.message_id) AS message_count
            FROM chat_threads t
            JOIN chat_messages m ON t.thread_id = m.thread_id
            WHERE t.user_id = %s AND m.sender = 'bot' and m.created_at >= %s
            GROUP BY t.user_id
                """
            cursor.execute(query, (user_id, past_24_hours_time))
            count = cursor.fetchone()
            if count is None:
                return 0
            return count[1]  # (user_id,message_count)
    except Exception as e:
        logging.error(e)
        raise e


def insert_thread_ignore(thread_id: str, user_id, thread_name=None):
    """
    Insert a new chat thread into the chat_threads table, ignoring the insertion if a duplicate.

    # thread_id exists.

    Args:
        thread_id (str): The unique identifier for the chat thread.
        user_id: The ID of the user who owns the thread.
        thread_name (str, optional): The name of the chat thread. Defaults to None.

    Returns
    -------
        bool: True if the insertion was successful or ignored, False otherwise.

    Raises
    ------
        Exception: Propagates any exception that occurs during the database operation.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            INSERT IGNORE INTO chat_threads (thread_id, user_id, thread_name)
            VALUES (%s, %s, %s)
                """
            thread_data = (thread_id, user_id, thread_name)
            cursor.execute(query, thread_data)
            db.commit()
            return True
    except Exception as e:
        logging.error(e)
        raise e


def insert_message(thread_id: str, sender: str, message_content: str, sources: str = None):
    """
    Insert a new message into the chat_messages table.

    Args:
        thread_id (str): The unique identifier for the chat thread the message belongs to.
        sender (str): The sender of the message.
        message_content (str): The content of the message.
        sources (str, optional): Any sources associated with the message. Defaults to None.

    Returns
    -------
        bool: True if the insertion was successful, False otherwise.

    Raises
    ------
        Exception: Propagates any exception that occurs during the database operation.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            INSERT INTO chat_messages (thread_id, sender, message_content, sources)
            VALUES (%s, %s, %s, %s)
                """
            msg_data = (thread_id, sender, message_content, sources)
            cursor.execute(query, msg_data)
            db.commit()
            return True
    except Exception as e:
        logging.error(e)
        raise e


def list_all_user_threads(user_id: int):
    """
    Retrieve all thread IDs for a given user.

    Args:
        user_id (int): The ID of the user whose threads are to be listed.

    Returns
    -------
        list: A list of thread IDs associated with the user. Returns an empty list if no threads are
        found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            SELECT thread_id from chat_threads WHERE user_id = %s;
                """
            cursor.execute(query, (user_id,))
            thread_ids = cursor.fetchall()
            if thread_ids is None:
                return []
            return thread_ids
    except Exception as e:
        logging.error(e)
        raise e


def get_all_thread_messages(thread_id: str):
    """
    Retrieve all messages for a given thread, ordered by creation time.

    Args:
        thread_id (str): The ID of the thread whose messages are to be retrieved.

    Returns
    -------
        list: A list of messages associated with the thread. Each message includes sender,
        message_content, created_at, and sources. Returns an empty list if no messages are found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor(dictionary=True)
            query = """
            SELECT sender, message_content, created_at, sources
                FROM chat_messages
                WHERE thread_id = %s
                ORDER BY created_at ASC;
                """
            cursor.execute(query, (thread_id,))
            messages = cursor.fetchall()
            if messages is None:
                return []
            return messages
    except Exception as e:
        logging.error(e)
        raise e


def get_recent_threads(user_id: int):
    """
    Retrieve the most recent threads for a given user.

    Args:
        user_id (int): The ID of the user whose recent threads are to be retrieved.

    Returns
    -------
        list: A list of recent threads for the user. Each thread includes thread_id, thread_name,
        and created_at. Returns an empty list if no recent threads are found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        with get_db_connection() as db:
            cursor = db.cursor(dictionary=True)
            query = """
            SELECT thread_id, thread_name, created_at
            FROM chat_threads
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10;
            """
            cursor.execute(query, (user_id,))
            recent_threads = cursor.fetchall()
            if recent_threads is None:
                return []
            return recent_threads
    except Exception as e:
        logging.error(e)
        raise e
    finally:
        cursor.close()
        db.close()
