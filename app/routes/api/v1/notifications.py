"""API routes for notifications operations."""

from flask import session, request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required
import logging

from app.helpers.notifications import (
    get_notifications,
    mark_notification_as_read,
    mark_notification_as_dismissed,
    serialize_notification_response,
    parse_boolean_param,
    sanitize_notification,
)

notifications_ns = Namespace("notifications", description="Notifications operations")


@notifications_ns.route("/")
class GetNotificationsResource(Resource):
    """Resource to get notifications for the current user."""

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.response(200, "Notifications retrieved successfully")
    @notifications_ns.response(401, "Unauthorized")
    @notifications_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers"])
    def get(self):
        """Get notifications for the current user."""
        logging.info("Getting notifications")

        try:
            user_id = session.get("user.id")
            if not user_id:
                return {"error": "Unauthorized"}, 401

            # Get all notifications first
            notifications = get_notifications(user_id=user_id)
            logging.debug(f"Notification count: {len(notifications)}")

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

            logging.debug(f"Response data: {response_data}")

            # Serialize the response data to handle Decimal objects
            return serialize_notification_response(response_data), 200

        except Exception as e:
            logging.error(f"Error fetching notifications: {str(e)}")
            return {"error": "Unable to fetch notifications"}, 500


@notifications_ns.route("/<int:notification_id>/read")
class MarkNotificationAsReadResource(Resource):
    """Resource to mark a notification as read."""

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.response(200, "Notification marked as read")
    @notifications_ns.response(401, "Unauthorized")
    @notifications_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers"])
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

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.response(200, "Notification marked as dismissed")
    @notifications_ns.response(401, "Unauthorized")
    @notifications_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers"])
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
