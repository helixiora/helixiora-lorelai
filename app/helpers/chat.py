"""Chat related helper functions."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, desc
from app.helpers.users import is_admin
from app.models import db, ChatThread, ChatMessage, UserPlan, Plan
from flask import current_app


def get_chat_template_requirements(thread_id: str, user_id: int) -> dict:
    """
    Retrieve the chat template requirements for a given thread.

    Args:
        thread_id (str): The ID of the thread whose chat template requirements are to be retrieved.
        user_id (int): The ID of the user whose chat template requirements are to be retrieved.

    Returns
    -------
        dict: A dictionary containing the chat template requirements.
    """
    recent_conversations = get_recent_threads(user_id)

    is_admin_status = is_admin(user_id)

    return {
        "recent_conversations": recent_conversations,
        "is_admin_status": is_admin_status,
    }


def get_msg_count_last_24hr(user_id: int) -> int:
    """
    Retrieve the count of chat messages for a specified user from the last 24 hours.

    Args:
        user_id (int): The ID of the user whose messages are to be counted.

    Returns
    -------
        int: The number of chat messages sent by the specified user in the last 24 hours.

    Raises
    ------
        Exception: If there is an error executing the query.
    """
    try:
        past_24_hours_time = datetime.now() - timedelta(days=1)
        count = (
            db.session.query(func.count(ChatMessage.message_id))
            .join(ChatThread)
            .filter(
                ChatThread.user_id == user_id,
                ChatMessage.sender == "bot",
                ChatMessage.created_at >= past_24_hours_time,
            )
            .scalar()
        )
        return count or 0
    except Exception as e:
        logging.error(e)
        raise e


def insert_thread_ignore(thread_id: str, user_id: int, thread_name: str = None) -> bool:
    """
    Insert a new chat thread into the chat_threads table, ignoring the insertion if a duplicate.

    Args:
        thread_id (str): The unique identifier for the chat thread.
        user_id (int): The ID of the user who owns the thread.
        thread_name (str, optional): The name of the chat thread. Defaults to None.

    Returns
    -------
        bool: True if the insertion was successful or ignored, False otherwise.
    """
    logging.info("Inserting thread: %s, %s, %s", thread_id, user_id, thread_name)

    try:
        with current_app.app_context():
            existing_thread = db.session.query(ChatThread).filter_by(thread_id=thread_id).first()
            if existing_thread:
                logging.info("Thread already exists, ignore insertion")
                return True  # Thread already exists, ignore insertion

            thread = ChatThread(thread_id=thread_id, user_id=user_id, thread_name=thread_name)
            db.session.add(thread)
            db.session.commit()
            return True
    except Exception as e:
        current_app.logger.error(f"Error inserting thread: {e}")
        db.session.rollback()
        return False


def insert_message(thread_id: str, sender: str, message_content: str, sources: str = None) -> bool:
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
        message = ChatMessage(
            thread_id=thread_id, sender=sender, message_content=message_content, sources=sources
        )
        db.session.add(message)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logging.error(e)
        raise e


def list_all_user_threads(user_id: int) -> list:
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
        threads = ChatThread.query.filter_by(user_id=user_id, marked_deleted=False).all()
        return [thread.thread_id for thread in threads]
    except Exception as e:
        logging.error(e)
        raise e


def get_all_thread_messages(thread_id: str) -> list:
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
        messages = (
            ChatMessage.query.filter_by(thread_id=thread_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return [
            {
                "sender": message.sender,
                "message_content": message.message_content,
                "created_at": message.created_at,
                "sources": message.sources,
            }
            for message in messages
        ]
    except Exception as e:
        logging.error(e)
        raise e


def get_recent_threads(user_id: int) -> list:
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
        recent_threads = (
            db.session.query(
                ChatThread.thread_id,
                ChatThread.thread_name,
                ChatThread.created_at,
                func.max(ChatMessage.created_at).label("last_messages_created_at"),
            )
            .join(ChatMessage, ChatThread.thread_id == ChatMessage.thread_id, isouter=True)
            .filter(
                ChatThread.user_id == user_id,
                ChatThread.marked_deleted.is_(False),
                ChatMessage.sender != "bot",
            )
            .group_by(ChatThread.thread_id, ChatThread.thread_name, ChatThread.created_at)
            .order_by(desc("last_messages_created_at"))
            .limit(10)
            .all()
        )

        return [
            {
                "thread_id": thread.thread_id,
                "thread_name": thread.thread_name,
                "created_at": thread.created_at,
                "last_messages_created_at": thread.last_messages_created_at,
            }
            for thread in recent_threads
        ]
    except Exception as e:
        logging.error(e)
        raise e


def delete_thread(thread_id: str) -> bool:
    """
    Mark a thread as deleted by setting marked_deleted to TRUE.

    Args:
        thread_id (str): The ID of the thread to be marked as deleted.

    Returns
    -------
        bool: True if the operation was successful, False otherwise.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        thread = ChatThread.query.filter_by(thread_id=thread_id).first()
        if thread:
            thread.marked_deleted = True
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error marking thread {thread_id} as deleted: {e}")
        raise e


def get_daily_message_limit(user_id: int) -> int:
    """
    Retrieve the daily message limit for an active plan of a given user.

    Args:
        user_id (int): The ID of the user.

    Returns
    -------
        int : The daily message limit if an active plan is found, otherwise 0.
    """
    try:
        """active_plan = (
            db.session.query(Plan.message_limit_daily)
            .join(UserPlan)
            .filter(
                UserPlan.user_id == user_id,
                UserPlan.is_active,
                UserPlan.start_date <= func.curdate(),
                UserPlan.end_date >= func.curdate(),
            )
            .first()
        )"""

        user_plan = (
            db.session.query(Plan.message_limit_daily)
            .join(UserPlan, UserPlan.plan_id == Plan.plan_id)
            .filter(
                UserPlan.user_id == user_id,
                UserPlan.is_active,
                UserPlan.start_date <= func.curdate(),
                UserPlan.end_date >= func.curdate(),
            )
            .first()
        )

        print(user_id, user_plan)

        return user_plan.message_limit_daily if user_plan else 0
    except Exception as e:
        logging.error(f"Error getting daily msg limit for userid {user_id}: {e}")
        raise e


def can_send_message(user_id: int) -> bool:
    """
    Check if a user can send a message based on their daily limit and extra messages.

    Args:
        user_id (int): The ID of the user.

    Returns
    -------
        bool: True if the user can send a message, otherwise False.
    """
    daily_limit = get_daily_message_limit(user_id)
    logging.info(f"Daily Message Limit for {user_id}: {daily_limit}")
    message_usages = get_msg_count_last_24hr(user_id)
    logging.info(f"Daily Message Used for {user_id}: {message_usages}")
    return message_usages < daily_limit
