"""API routes for notifications operations."""

from flask import session, request
from flask_restx import Namespace, Resource
from decimal import Decimal
import logging
from typing import Any
import bleach

from app.helpers.notifications import (
    get_notifications,
    mark_notification_as_read,
    mark_notification_as_dismissed,
)

notifications_ns = Namespace("notifications", description="Notifications operations")


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


@notifications_ns.route("/")
class GetNotificationsResource(Resource):
    """Resource to get notifications for the current user."""

    def get(self):
        """Get notifications for the current user."""
        try:
            user_id = session.get("user.id")
            if not user_id:
                return {"error": "Unauthorized"}, 401

            # Get all notifications first
            notifications = get_notifications(user_id=user_id)

            # Then filter based on parameters
            show_read = parse_boolean_param(request.args.get("show_read"), default=True)
            show_unread = parse_boolean_param(request.args.get("show_unread"), default=True)
            show_dismissed = parse_boolean_param(request.args.get("show_dismissed"), default=False)

            # Apply filters
            filtered_notifications = [
                n
                for n in notifications
                if ((n.read_at is not None and show_read) or (n.read_at is None and show_unread))
                and (
                    (n.dismissed_at is not None and show_dismissed)
                    or (n.dismissed_at is None and not show_dismissed)
                )
            ]

            # Convert and sanitize notifications
            serialized_notifications = [
                sanitize_notification(
                    {
                        "id": notification.id,
                        "user_id": notification.user_id,
                        "message": notification.message,
                        "created_at": notification.created_at.isoformat(),
                        "read_at": notification.read_at.isoformat()
                        if notification.read_at
                        else None,
                        "dismissed_at": notification.dismissed_at.isoformat()
                        if notification.dismissed_at
                        else None,
                        "type": notification.type,
                        "title": getattr(notification, "title", ""),
                        "url": getattr(notification, "url", None),
                    }
                )
                for notification in filtered_notifications
            ]

            # Calculate counts based on filtered notifications
            read_count = sum(1 for n in filtered_notifications if n.read_at is not None)
            unread_count = sum(1 for n in filtered_notifications if n.read_at is None)
            dismissed_count = sum(1 for n in filtered_notifications if n.dismissed_at is not None)

            response_data = {
                "notifications": serialized_notifications,
                "counts": {
                    "read": read_count,
                    "unread": unread_count,
                    "dismissed": dismissed_count,
                    "total": len(filtered_notifications),
                },
            }

            # Serialize the response data to handle Decimal objects
            return serialize_notification_response(response_data), 200

        except Exception as e:
            logging.error(f"Error fetching notifications: {str(e)}")
            return {"error": "Unable to fetch notifications"}, 500


@notifications_ns.route("/<int:notification_id>/read")
class MarkNotificationAsReadResource(Resource):
    """Resource to mark a notification as read."""

    def post(self, notification_id):
        """Mark a notification as read."""
        try:
            user_id = session.get("user.id")
            if not user_id:
                return {"error": "Unauthorized"}, 401

            logging.info(f"Marking notification {notification_id} as read for user {user_id}")
            result = mark_notification_as_read(notification_id, user_id)

            if isinstance(result, dict) and result.get("success", False):
                # Serialize the response to handle any Decimal values
                return serialize_notification_response(result), 200
            return {"status": "error", "message": "Failed to mark notification as read"}, 400

        except Exception as e:
            logging.error(f"Error marking notification as read: {str(e)}")
            return {"error": "Unable to mark notification as read"}, 500


@notifications_ns.route("/<int:notification_id>/dismiss")
class MarkNotificationAsDismissedResource(Resource):
    """Resource to mark a notification as dismissed."""

    def post(self, notification_id):
        """Mark a notification as dismissed."""
        try:
            user_id = session.get("user.id")
            if not user_id:
                return {"error": "Unauthorized"}, 401

            logging.info(f"Marking notification {notification_id} as dismissed for user {user_id}")
            result = mark_notification_as_dismissed(notification_id, user_id)

            if isinstance(result, dict) and result.get("success", False):
                # Serialize the response to handle any Decimal values
                return serialize_notification_response(result), 200
            return {"status": "error", "message": "Failed to dismiss notification"}, 400

        except Exception as e:
            logging.error(f"Error dismissing notification: {str(e)}")
            return {"error": "Unable to dismiss notification"}, 500
