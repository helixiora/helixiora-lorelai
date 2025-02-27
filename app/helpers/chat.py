"""Chat related helper functions."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, desc
from app.database import db
from app.models.chat import ChatConversation, ChatMessage
from app.models.plan import UserPlan, Plan
from app.models.extra_messages import ExtraMessages
from flask import current_app


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
            .join(ChatConversation)
            .filter(
                ChatConversation.user_id == user_id,
                ChatMessage.sender == "bot",
                ChatMessage.created_at >= past_24_hours_time,
            )
            .scalar()
        )
        return count or 0
    except Exception as e:
        logging.error(e)
        raise e


def insert_conversation_ignore(
    conversation_id: str, user_id: int, conversation_name: str = None
) -> bool:
    """Insert new chat conversation into the chat_conversations table, ignoring the if a duplicate.

    Args:
        conversation_id (str): The unique identifier for the chat conversation.
        user_id (int): The ID of the user who owns the conversation.
        conversation_name (str, optional): The name of the chat conversation. Defaults to None.

    Returns
    -------
        bool: True if the insertion was successful or ignored, False otherwise.
    """
    logging.info(
        "Inserting conversation: %s, %s, %s",
        conversation_id,
        user_id,
        conversation_name,
    )

    try:
        with current_app.app_context():
            existing_conversation = (
                db.session.query(ChatConversation)
                .filter_by(conversation_id=conversation_id)
                .first()
            )
            if existing_conversation:
                logging.info("Conversation already exists, ignore insertion")
                return True  # Conversation already exists, ignore insertion

            conversation = ChatConversation(
                conversation_id=conversation_id,
                user_id=user_id,
                conversation_name=conversation_name,
            )
            db.session.add(conversation)
            db.session.commit()
            return True
    except Exception as e:
        current_app.logger.error(f"Error inserting conversation: {e}")
        db.session.rollback()
        return False


def insert_message(
    conversation_id: str,
    sender: str,
    message_content: str,
    sources: str = None,
    classified_prompt: str = None,
) -> bool:
    """
    Insert a new message into the chat_messages table.

    Args:
        conversation_id (str): The unique identifier for the chat convo the message belongs to.
        sender (str): The sender of the message.
        message_content (str): The content of the message.
        sources (str, optional): Any sources associated with the message. Defaults to None.
        classified_prompt (str, optional): The classified prompt type. Defaults to None.

    Returns
    -------
        bool: True if the insertion was successful, False otherwise.

    Raises
    ------
        Exception: Propagates any exception that occurs during the database operation.
    """
    try:
        message = ChatMessage(
            conversation_id=conversation_id,
            sender=sender,
            message_content=message_content,
            sources=sources,
            classified_prompt=classified_prompt,
        )
        db.session.add(message)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logging.error(e)
        raise e


def list_all_user_conversations(user_id: int) -> list:
    """
    Retrieve all conversation IDs for a given user.

    Args:
        user_id (int): The ID of the user whose conversations are to be listed.

    Returns
    -------
        list: A list of conversation IDs associated with the user. Returns an empty list if no
        conversations are found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        conversations = ChatConversation.query.filter_by(
            user_id=user_id, marked_deleted=False
        ).all()
        return [conversation.conversation_id for conversation in conversations]
    except Exception as e:
        logging.error(e)
        raise e


def get_all_conversation_messages(conversation_id: str) -> list:
    """
    Retrieve all messages for a given conversation, ordered by creation time.

    Args:
        conversation_id (str): The ID of the conversation whose messages are to be retrieved.

    Returns
    -------
        list: A list of messages associated with the conversation. Each message includes sender,
        message_content, created_at, and sources. Returns an empty list if no messages are found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        messages = (
            db.session.query(ChatMessage)
            .join(
                ChatConversation,
                ChatMessage.conversation_id == ChatConversation.conversation_id,
            )
            .filter(
                ChatMessage.conversation_id == conversation_id,
                ChatConversation.marked_deleted == 0,
            )
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


def get_recent_conversations(user_id: int) -> list:
    """
    Retrieve the most recent conversations for a given user.

    Args:
        user_id (int): The ID of the user whose recent conversations are to be retrieved.

    Returns
    -------
        list: A list of recent conversations for the user. Each convo includes conversation_id,
        conversation_name, and created_at. Returns an empty list if no recent conversations are
        found.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        recent_conversations = (
            db.session.query(
                ChatConversation.conversation_id,
                ChatConversation.conversation_name,
                ChatConversation.created_at,
                func.max(ChatMessage.created_at).label("last_messages_created_at"),
            )
            .join(
                ChatMessage,
                ChatConversation.conversation_id == ChatMessage.conversation_id,
                isouter=True,
            )
            .filter(
                ChatConversation.user_id == user_id,
                ChatConversation.marked_deleted.is_(False),
                ChatMessage.sender != "bot",
            )
            .group_by(
                ChatConversation.conversation_id,
                ChatConversation.conversation_name,
                ChatConversation.created_at,
            )
            .order_by(desc("last_messages_created_at"))
            .limit(10)
            .all()
        )

        return [
            {
                "conversation_id": conversation.conversation_id,
                "conversation_name": conversation.conversation_name,
                "created_at": conversation.created_at,
                "last_messages_created_at": conversation.last_messages_created_at,
            }
            for conversation in recent_conversations
        ]
    except Exception as e:
        logging.error(e)
        raise e


def delete_conversation(conversation_id: str) -> bool:
    """
    Mark a conversation as deleted by setting marked_deleted to TRUE.

    Args:
        conversation_id (str): The ID of the conversation to be marked as deleted.

    Returns
    -------
        bool: True if the operation was successful, False otherwise.

    Raises
    ------
        Exception: If there is an error during the database query.
    """
    try:
        conversation = ChatConversation.query.filter_by(conversation_id=conversation_id).first()
        if conversation:
            conversation.marked_deleted = True
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error marking conversation {conversation_id} as deleted: {e}")
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
        # First, log that we're checking the message limit for this user
        logging.info(f"Checking daily message limit for user_id: {user_id}")

        # Query to find all active user plans
        user_plans = (
            db.session.query(UserPlan, Plan.message_limit_daily)
            .join(Plan, UserPlan.plan_id == Plan.plan_id)
            .filter(
                UserPlan.user_id == user_id,
                UserPlan.is_active == True,  # noqa: E712 Explicit comparison for clarity
            )
            .all()
        )

        # Log the number of plans found
        logging.info(f"Found {len(user_plans)} active plans for user_id: {user_id}")

        if not user_plans:
            logging.warning(f"No active plans found for user_id: {user_id}")
            return 0

        # If multiple plans exist, use the one with the highest message limit
        if len(user_plans) > 1:
            logging.warning(
                f"Multiple active plans found for user_id: {user_id}, using highest limit"
            )

        # Find the plan with the highest message limit using max()
        # This avoids direct indexing and is more Pythonic
        selected_plan = max(user_plans, key=lambda x: x[1] or 0)
        user_plan, message_limit = selected_plan

        # Use safe access with or 0 to handle None values
        message_limit = message_limit or 0

        logging.info(
            f"Using plan_id: {user_plan.plan_id} with message_limit: {message_limit} for user_id:\
{user_id}"
        )

        return message_limit
    except Exception as e:
        logging.error(
            f"Error getting daily message limit for user_id {user_id}: {e}", exc_info=True
        )
        return 0  # Return 0 instead of raising to prevent application errors


def deduct_extra_message_if_available(user_id: int):
    """
    Deduct an extra message if available for the user.

    Args:
        user_id (int): The ID of the user.

    Returns
    -------
        bool: True if the deduction was successful, otherwise False.
    """
    try:
        # Check the current quantity of extra messages
        extra_message_entry = (
            db.session.query(ExtraMessages).filter_by(user_id=user_id, is_active=True).first()
        )

        if extra_message_entry is None:
            # No active extra messages for this user
            return False

        if extra_message_entry.quantity <= 0:
            return False

        # Deduct one message
        extra_message_entry.quantity -= 1

        # Commit the changes to the database
        db.session.commit()
        return True

    except Exception as e:
        logging.error(f"Error deducting extra message for user_id {user_id}: {e}")
        db.session.rollback()  # Rollback in case of error
        return False


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
    if message_usages < daily_limit:
        return True

    # In future we have to deduct extra message only if bot has replied. for now its ok.
    status = deduct_extra_message_if_available(user_id=user_id)
    # status True if extra message is available false if not
    return status
