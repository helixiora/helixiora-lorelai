"""API routes for notifications operations."""

from flask import session
from flask_restx import Namespace, Resource
from decimal import Decimal
import logging

from app.helpers.notifications import (
    get_notifications,
    mark_notification_as_read,
    mark_notification_as_dismissed,
)

notifications_ns = Namespace("notifications", description="Notifications operations")


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
            # Fetch unread notifications for the current user
            notifications = get_notifications(session.get("user.id"))

            # Convert notifications to a JSON-serializable format
            serialized_notifications = [
                {
                    "id": notification.id,
                    "user_id": notification.user_id,
                    "message": notification.message,
                    "created_at": notification.created_at.isoformat(),
                    "read_at": notification.read_at.isoformat() if notification.read_at else None,
                    "dismissed_at": notification.dismissed_at.isoformat()
                    if notification.dismissed_at
                    else None,
                    "type": notification.type,
                }
                for notification in notifications
            ]

            # Return the serialized list directly instead of wrapping it in jsonify
            return serialized_notifications, 200
        except Exception as e:
            # Log the error (you should set up proper logging)
            logging.error(f"Error fetching notifications: {str(e)}")
            return {"error": "Unable to fetch notifications"}, 500


@notifications_ns.route("/<int:notification_id>/read")
class MarkNotificationAsReadResource(Resource):
    """Resource to mark a notification as read."""

    def post(self, notification_id):
        """Mark a notification as read."""
        logging.info(
            f"Marking notification {notification_id} as read for user {session.get('user.id')}"
        )
        result = mark_notification_as_read(notification_id, session.get("user.id"))
        logging.debug(f"Notification read result: {result}")

        # Serialize the response data
        serialized_result = serialize_notification_response(result)

        if isinstance(result, dict) and result.get("success", False):
            return serialized_result, 200
        return {"status": "error", "message": "Failed to mark notification as read"}, 400


@notifications_ns.route("/<int:notification_id>/dismiss")
class MarkNotificationAsDismissedResource(Resource):
    """Resource to mark a notification as dismissed."""

    def post(self, notification_id):
        """Mark a notification as dismissed."""
        logging.info(
            f"Marking notification {notification_id} as dismissed for user {session.get('user.id')}"
        )
        result = mark_notification_as_dismissed(notification_id, session.get("user.id"))

        # Serialize the response data
        serialized_result = serialize_notification_response(result)

        if isinstance(result, dict) and result.get("success", False):
            return serialized_result, 200
        return {"status": "error", "message": "Failed to dismiss notification"}, 400
