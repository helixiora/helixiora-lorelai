"""Notification related helper functions."""

import logging
from datetime import datetime

from app.models import db
from app.models.notification import Notification
from app.schemas import NotificationSchema
from sqlalchemy.exc import SQLAlchemyError
import bleach
from typing import Any
from decimal import Decimal


def serialize_notification_response(data):
    """Serialize helper function for notification response data."""
    if isinstance(data, dict):
        return {k: serialize_notification_response(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_notification_response(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data


def add_notification(
    user_id: int, type: str, title: str, message: str, data: dict = None, url: str = None
) -> bool:
    """Add a notification to the database."""
    try:
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=str(data) if data else None,
            url=url,
        )
        db.session.add(notification)
        db.session.commit()
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Failed to add notification: {e}")
        return False


def get_notifications(
    user_id: int,
    show_read: bool | None = None,
    show_dismissed: bool | None = None,
    limit: int | None = None,
) -> list[NotificationSchema]:
    """Get the notifications for a user.

    Parameters
    ----------
    user_id : int
        The ID of the user to get notifications for
    show_read : Optional[bool]
        If True, include read notifications. If False, exclude them.
        If None, include both read and unread notifications.
    show_dismissed : Optional[bool]
        If True, include dismissed notifications. If False, exclude them.
        If None, include both dismissed and undismissed notifications.
    limit : Optional[int]
        Maximum number of notifications to return

    Returns
    -------
    List[NotificationSchema]
        List of notifications matching the criteria
    """
    try:
        # Base query for all notifications for this user
        base_query = Notification.query.filter_by(user_id=user_id)

        # Get total counts for different states
        counts = (
            db.session.query(
                db.func.count().label("total"),
                db.func.sum(
                    db.case((~Notification.dismissed & ~Notification.read, 1), else_=0)
                ).label("unread_active"),
                db.func.sum(
                    db.case((~Notification.dismissed & Notification.read, 1), else_=0)
                ).label("read_active"),
                db.func.sum(db.case((Notification.dismissed, 1), else_=0)).label("dismissed"),
            )
            .filter(Notification.user_id == user_id)
            .first()
        )

        # Apply read/unread filter if specified
        if show_read is not None:
            base_query = base_query.filter(Notification.read == show_read)

        # Apply dismissed/undismissed filter if specified
        if show_dismissed is not None:
            base_query = base_query.filter(Notification.dismissed == show_dismissed)

        # Always sort by creation date, newest first
        base_query = base_query.order_by(Notification.created_at.desc())

        # Apply limit if specified
        if limit is not None:
            base_query = base_query.limit(limit)

        notifications = base_query.all()
        notification_schemas = [
            NotificationSchema.from_orm(notification) for notification in notifications
        ]

        # Return both notifications and counts
        return {
            "notifications": notification_schemas,
            "counts": {
                "total": int(counts.total or 0),
                "unread_active": int(counts.unread_active or 0),
                "read_active": int(counts.read_active or 0),
                "dismissed": int(counts.dismissed or 0),
            },
        }

    except SQLAlchemyError as e:
        logging.error(f"Failed to get notifications: {e}")
        return {
            "notifications": [],
            "counts": {"total": 0, "unread_active": 0, "read_active": 0, "dismissed": 0},
        }


def get_unread_notifications(user_id: int) -> list[NotificationSchema]:
    """Get the unread notifications for a user."""
    try:
        notifications = (
            Notification.query.filter_by(user_id=user_id, read=False)
            .order_by(Notification.created_at.desc())
            .all()
        )
        return [NotificationSchema.from_orm(notification) for notification in notifications]
    except SQLAlchemyError as e:
        logging.error(f"Failed to get unread notifications: {e}")
        return []


def mark_notification_as_read(notification_id: int, user_id: int) -> dict:
    """Mark a notification as read and return status information."""
    try:
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if notification:
            notification.read = True
            notification.read_at = datetime.utcnow()
            db.session.commit()

        # Get counts for different notification states
        counts = (
            db.session.query(
                db.func.sum(db.case((Notification.read.is_(False), 1), else_=0)).label(
                    "remaining_unread"
                ),
                db.func.sum(db.case((Notification.read.is_(True), 1), else_=0)).label("read"),
                db.func.sum(db.case((Notification.dismissed.is_(True), 1), else_=0)).label(
                    "dismissed"
                ),
                db.func.sum(db.case((Notification.dismissed.is_(False), 1), else_=0)).label(
                    "undismissed"
                ),
            )
            .filter(Notification.user_id == user_id)
            .first()
        )

        return {
            "success": True,
            "remaining_unread": int(counts.remaining_unread or 0),
            "read": int(counts.read or 0),
            "dismissed": int(counts.dismissed or 0),
            "undismissed": int(counts.undismissed or 0),
        }
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Failed to mark notification as read: {e}")
        return {
            "success": False,
            "error": str(e),
            "remaining_unread": 0,
            "read": 0,
            "dismissed": 0,
            "undismissed": 0,
        }


def mark_notification_as_dismissed(notification_id: int, user_id: int) -> dict:
    """Mark a notification as dismissed and return status information."""
    try:
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if notification:
            notification.dismissed = True
            notification.dismissed_at = datetime.utcnow()
            db.session.commit()
            success = True
        else:
            success = False

        # Get counts for different notification states
        counts = (
            db.session.query(
                db.func.sum(db.case((Notification.read.is_(False), 1), else_=0)).label(
                    "remaining_unread"
                ),
                db.func.sum(db.case((Notification.read.is_(True), 1), else_=0)).label("read"),
                db.func.sum(db.case((Notification.dismissed.is_(True), 1), else_=0)).label(
                    "dismissed"
                ),
                db.func.sum(db.case((Notification.dismissed.is_(False), 1), else_=0)).label(
                    "undismissed"
                ),
            )
            .filter(Notification.user_id == user_id)
            .first()
        )

        return {
            "success": success,
            "remaining_unread": int(counts.remaining_unread or 0),
            "read": int(counts.read or 0),
            "dismissed": int(counts.dismissed or 0),
            "undismissed": int(counts.undismissed or 0),
        }
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Failed to mark notification as dismissed: {e}")
        return {
            "success": False,
            "error": str(e),
            "remaining_unread": 0,
            "read": 0,
            "dismissed": 0,
            "undismissed": 0,
        }


def sanitize_param(param: str | None) -> str:
    """Sanitize a string parameter using bleach.

    Parameters
    ----------
    param : Optional[str]
        The parameter to sanitize

    Returns
    -------
    str
        The sanitized parameter
    """
    if param is None:
        return ""
    return bleach.clean(str(param).strip(), tags=[], strip=True)


def parse_boolean_param(param: str | None, default: bool = True) -> bool:
    """Safely parse a string parameter to boolean.

    Parameters
    ----------
    param : Optional[str]
        The parameter to parse
    default : bool
        Default value if param is None or invalid

    Returns
    -------
    bool
        The parsed boolean value
    """
    if param is None:
        return default

    param = sanitize_param(param)
    if param.lower() in ("true", "1", "yes", "on"):
        return True
    if param.lower() in ("false", "0", "no", "off"):
        return False
    return default


def sanitize_notification(notification: dict[str, Any]) -> dict[str, Any]:
    """Sanitize notification data before sending to client.

    Parameters
    ----------
    notification : Dict[str, Any]
        The notification data to sanitize

    Returns
    -------
    Dict[str, Any]
        The sanitized notification data
    """
    return {
        "id": notification["id"],
        "user_id": notification["user_id"],
        "message": bleach.clean(
            notification["message"], tags=["b", "i", "a"], attributes={"a": ["href"]}
        ),
        "created_at": notification["created_at"],
        "read_at": notification["read_at"],
        "dismissed_at": notification["dismissed_at"],
        "type": bleach.clean(notification["type"], tags=[], strip=True),
        "title": bleach.clean(notification.get("title", ""), tags=[], strip=True),
        "url": bleach.clean(notification.get("url", ""), tags=[], strip=True)
        if notification.get("url")
        else None,
    }


def get_notification(notification_id: int, user_id: int) -> NotificationSchema | None:
    """Get a specific notification by ID.

    Parameters
    ----------
    notification_id : int
        The ID of the notification to retrieve
    user_id : int
        The ID of the user who owns the notification

    Returns
    -------
    Optional[NotificationSchema]
        The notification if found, None otherwise
    """
    try:
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if notification:
            return NotificationSchema.from_orm(notification)
        return None
    except SQLAlchemyError as e:
        logging.error(f"Failed to get notification {notification_id}: {e}")
        return None
