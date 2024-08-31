"""Notification related helper functions."""

import logging

from app.helpers.database import get_db_connection


def add_notification(
    user_id: int, type: str, title: str, message: str, data: dict = None, url: str = None
) -> bool:
    """Add a notification to the database."""
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = """
            INSERT INTO notifications (user_id, type, title, message, data, url)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (user_id, type, title, message, data, url))
            db.commit()
        return True
    except Exception as e:
        logging.error(f"Failed to add notification: {e}")
        return False
    finally:
        cursor.close()
        db.close()


def get_notifications(user_id: int) -> list[dict]:
    """Get the notifications for a user."""
    try:
        with get_db_connection() as db:
            cursor = db.cursor(dictionary=True)
            query = "SELECT * FROM notifications WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            notifications = cursor.fetchall()
            return notifications

    except Exception as e:
        logging.error(f"Failed to get notifications: {e}")
        return []
    finally:
        cursor.close()
        db.close()


def get_unread_notifications(user_id: int) -> list[dict]:
    """Get the unread notifications for a user."""
    notifications = get_notifications(user_id)
    return [notification for notification in notifications if not notification["read"]]


def mark_notification_as_read(notification_id: int) -> bool:
    """Mark a notification as read."""
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = "UPDATE notifications SET read = TRUE WHERE id = %s"
            cursor.execute(query, (notification_id,))
            db.commit()
            return True
    except Exception as e:
        logging.error(f"Failed to mark notification as read: {e}")
        return False
    finally:
        cursor.close()
        db.close()


def mark_notification_as_dismissed(notification_id: int) -> bool:
    """Mark a notification as dismissed."""
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = "UPDATE notifications SET dismissed = TRUE WHERE id = %s"
            cursor.execute(query, (notification_id,))
            db.commit()
            return True
    except Exception as e:
        logging.error(f"Failed to mark notification as dismissed: {e}")
        return False
    finally:
        cursor.close()
        db.close()
