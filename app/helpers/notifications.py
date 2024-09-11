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
            query = "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC"
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


def mark_notification_as_read(notification_id: int, user_id: int) -> dict:
    """Mark a notification as read and return status information."""
    try:
        with get_db_connection() as db:
            cursor = db.cursor(dictionary=True)

            # Mark the notification as read
            update_query = (
                """UPDATE notifications SET `read` = TRUE WHERE `id` = %s AND `user_id` = %s"""
            )
            cursor.execute(update_query, (notification_id, user_id))
            db.commit()

            # Get counts for different notification states
            count_query = """
            SELECT
                SUM(CASE WHEN `read` = FALSE THEN 1 ELSE 0 END) as `remaining_unread`,
                SUM(CASE WHEN `read` = TRUE THEN 1 ELSE 0 END) as `read`,
                SUM(CASE WHEN `dismissed` = TRUE THEN 1 ELSE 0 END) as `dismissed`,
                SUM(CASE WHEN `dismissed` = FALSE THEN 1 ELSE 0 END) as `undismissed`
            FROM `notifications`
            WHERE `user_id` = %s
            """
            cursor.execute(count_query, (user_id,))
            counts = cursor.fetchone()

            return {"success": True, **{k: v or 0 for k, v in counts.items()}}
    except Exception as e:
        logging.error(f"Failed to mark notification as read: {e}")
        return {
            "success": False,
            "error": str(e),
            "remaining_unread": 0,
            "read": 0,
            "dismissed": 0,
            "undismissed": 0,
        }
    finally:
        cursor.close()
        db.close()


def mark_notification_as_dismissed(notification_id: int, user_id: int) -> dict:
    """Mark a notification as dismissed and return status information."""
    try:
        with get_db_connection() as db:
            cursor = db.cursor(dictionary=True)

            # Mark the notification as dismissed
            update_query = """UPDATE `notifications` SET `dismissed` = TRUE WHERE `id` = %s AND
            `user_id` = %s"""
            cursor.execute(update_query, (notification_id, user_id))
            success = cursor.rowcount > 0
            db.commit()

            # Get counts for different notification states
            count_query = """
            SELECT
                SUM(CASE WHEN `read` = FALSE THEN 1 ELSE 0 END) as `remaining_unread`,
                SUM(CASE WHEN `read` = TRUE THEN 1 ELSE 0 END) as `read`,
                SUM(CASE WHEN `dismissed` = TRUE THEN 1 ELSE 0 END) as `dismissed`,
                SUM(CASE WHEN `dismissed` = FALSE THEN 1 ELSE 0 END) as `undismissed`
            FROM `notifications`
            WHERE `user_id` = %s
            """
            cursor.execute(count_query, (user_id,))
            counts = cursor.fetchone()

            return {"success": success, **{k: v or 0 for k, v in counts.items()}}
    except Exception as e:
        logging.error(f"Failed to mark notification as dismissed: {e}")
        return {
            "success": False,
            "error": str(e),
            "remaining_unread": 0,
            "read": 0,
            "dismissed": 0,
            "undismissed": 0,
        }
    finally:
        cursor.close()
        db.close()
