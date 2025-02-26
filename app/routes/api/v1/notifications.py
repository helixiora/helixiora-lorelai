"""API routes for notifications operations."""

import logging

from flask import request, session
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields

from app.helpers.notifications import (
    get_notification,
    get_notifications,
    mark_notification_as_dismissed,
    mark_notification_as_read,
    parse_boolean_param,
    sanitize_notification,
)

notifications_ns = Namespace("notifications", description="Notifications operations")


# Custom datetime field for Flask-RESTX
class DateTimeField(fields.Raw):
    """Custom field for datetime serialization."""

    def format(self, value):
        """Format datetime to ISO format string."""
        if value is None:
            return None
        return value.isoformat()


# Models for request/response documentation
notification_model = notifications_ns.model(
    "Notification",
    {
        "id": fields.Integer(description="Notification ID"),
        "type": fields.String(description="Notification type"),
        "title": fields.String(description="Notification title"),
        "message": fields.String(description="Notification message"),
        "data": fields.Raw(description="Additional notification data"),
        "url": fields.String(description="Related URL"),
        "read": fields.Boolean(description="Whether the notification has been read"),
        "read_at": DateTimeField(description="When the notification was read"),
        "dismissed": fields.Boolean(description="Whether the notification has been dismissed"),
        "dismissed_at": DateTimeField(description="When the notification was dismissed"),
        "created_at": DateTimeField(description="When the notification was created"),
    },
)

bulk_ids_model = notifications_ns.model(
    "BulkIds",
    {"ids": fields.List(fields.Integer, required=True, description="List of notification IDs")},
)


@notifications_ns.route("")
class GetNotificationsResource(Resource):
    """Resource for getting notifications."""

    @notifications_ns.doc(
        security="Bearer Auth",
        params={
            "show_read": "Include read notifications (true/false)",
            "show_unread": "Include unread notifications (true/false)",
            "show_dismissed": "Include dismissed notifications (true/false)",
            "limit": "Maximum number of notifications to return",
        },
    )
    @notifications_ns.response(200, "Notifications retrieved successfully")
    @notifications_ns.response(401, "Unauthorized")
    @notifications_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers", "cookies"])
    def get(self):
        """Get notifications for the current user."""
        try:
            # Get user ID from JWT token instead of session
            user_id = get_jwt_identity()
            if not user_id:
                logging.error("No user ID found in JWT token")
                return {
                    "error": "Unauthorized",
                    "notifications": [],
                    "counts": {"total": 0, "unread_active": 0, "read_active": 0, "dismissed": 0},
                }, 401

            # Get query parameters
            show_read = parse_boolean_param(request.args.get("show_read", None))
            show_unread = parse_boolean_param(request.args.get("show_unread", None))
            # Default to not showing dismissed notifications unless explicitly requested
            show_dismissed = parse_boolean_param(
                request.args.get("show_dismissed", None), default=False
            )
            limit = request.args.get("limit", type=int)

            # If both show_read and show_unread are specified, use their values
            # If neither is specified, show all
            # If only one is specified, use the opposite for the other
            if show_read is not None and show_unread is not None:
                # If both are False, show nothing
                if not show_read and not show_unread:
                    return {
                        "notifications": [],
                        "counts": {
                            "total": 0,
                            "unread_active": 0,
                            "read_active": 0,
                            "dismissed": 0,
                        },
                    }, 200
                # If both are True or only one is True, pass None to show all
                show_read = None if (show_read and show_unread) else show_read
            elif show_read is not None:
                # Only show_read specified, show_unread is opposite
                show_read = show_read
            elif show_unread is not None:
                # Only show_unread specified, show_read is opposite
                show_read = not show_unread
            else:
                # Neither specified, show all
                show_read = None
            # Get notifications with filters
            result = get_notifications(
                user_id=user_id,
                show_read=show_read,
                show_dismissed=show_dismissed,
                limit=limit,
            )

            if not result:
                return {
                    "notifications": [],
                    "counts": {"total": 0, "unread_active": 0, "read_active": 0, "dismissed": 0},
                }, 200

            # Convert Pydantic models to dictionaries and format datetime fields
            filtered_notifications = []
            for n in result["notifications"]:
                try:
                    notification_dict = n.model_dump()

                    # Convert datetime objects to ISO format strings
                    for field in ["created_at", "read_at", "dismissed_at", "updated_at"]:
                        if field in notification_dict and notification_dict[field] is not None:
                            notification_dict[field] = notification_dict[field].isoformat()
                    filtered_notifications.append(sanitize_notification(notification_dict))
                except Exception as e:
                    logging.error(f"Error processing notification: {str(e)}")
                    continue
            response_data = {"notifications": filtered_notifications, "counts": result["counts"]}
            return response_data, 200

        except Exception as e:
            logging.error(f"Error fetching notifications: {str(e)}")
            return {
                "error": "Unable to fetch notifications",
                "notifications": [],
                "counts": {"total": 0, "unread_active": 0, "read_active": 0, "dismissed": 0},
            }, 500


@notifications_ns.route("/<int:notification_id>")
class NotificationResource(Resource):
    """Resource for individual notification operations."""

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.response(200, "Success", notification_model)
    @notifications_ns.response(404, "Notification not found")
    @jwt_required(locations=["headers", "cookies"])
    def get(self, notification_id):
        """Get a specific notification."""
        try:
            notification = get_notification(notification_id, session["user.id"])
            if not notification:
                return {"error": "Notification not found"}, 404

            # Convert the notification to a dictionary and format datetime fields
            notification_dict = notification.model_dump()
            for field in ["created_at", "read_at", "dismissed_at", "updated_at"]:
                if field in notification_dict and notification_dict[field] is not None:
                    notification_dict[field] = notification_dict[field].isoformat()

            return sanitize_notification(notification_dict)
        except Exception as e:
            logging.error(f"Error fetching notification {notification_id}: {str(e)}")
            return {"error": "Unable to fetch notification"}, 500


@notifications_ns.route("/<int:notification_id>/read")
class MarkReadResource(Resource):
    """Resource for marking notifications as read."""

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.response(200, "Notification marked as read")
    @notifications_ns.response(404, "Notification not found")
    @jwt_required(locations=["headers", "cookies"])
    def post(self, notification_id):
        """Mark a notification as read."""
        try:
            success = mark_notification_as_read(notification_id, session["user.id"])
            if not success:
                return {"error": "Notification not found"}, 404
            return {"message": "Notification marked as read"}, 200
        except Exception as e:
            logging.error(f"Error marking notification {notification_id} as read: {str(e)}")
            return {"error": "Unable to mark notification as read"}, 500


@notifications_ns.route("/<int:notification_id>/dismiss")
class DismissResource(Resource):
    """Resource for dismissing notifications."""

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.response(200, "Notification dismissed")
    @notifications_ns.response(404, "Notification not found")
    @jwt_required(locations=["headers", "cookies"])
    def post(self, notification_id):
        """Dismiss a notification."""
        try:
            success = mark_notification_as_dismissed(notification_id, session["user.id"])
            if not success:
                return {"error": "Notification not found"}, 404
            return {"message": "Notification dismissed"}, 200
        except Exception as e:
            logging.error(f"Error dismissing notification {notification_id}: {str(e)}")
            return {"error": "Unable to dismiss notification"}, 500


@notifications_ns.route("/bulk/read")
class BulkMarkReadResource(Resource):
    """Resource for marking multiple notifications as read."""

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.expect(bulk_ids_model)
    @notifications_ns.response(200, "Notifications marked as read")
    @jwt_required(locations=["headers", "cookies"])
    def post(self):
        """Mark multiple notifications as read."""
        try:
            data = request.get_json()
            if not data or "ids" not in data:
                return {"error": "Missing notification IDs", "success": False}, 400

            notification_ids = data["ids"]
            if not isinstance(notification_ids, list):
                return {"error": "Invalid notification IDs format", "success": False}, 400

            # Ensure all IDs are integers
            try:
                notification_ids = [int(id) for id in notification_ids]
            except (ValueError, TypeError):
                return {"error": "Invalid notification ID format", "success": False}, 400

            user_id = get_jwt_identity()
            success_count = 0

            for notification_id in notification_ids:
                try:
                    result = mark_notification_as_read(notification_id, user_id)
                    if result.get("success"):
                        success_count += 1
                except Exception as e:
                    logging.error(f"Error marking notification {notification_id} as read: {str(e)}")
                    continue

            # Get updated counts
            result = get_notifications(user_id=user_id)

            return {
                "message": f"{success_count} notifications marked as read",
                "success": True,
                "counts": result["counts"]
                if result
                else {"total": 0, "unread_active": 0, "read_active": 0, "dismissed": 0},
            }, 200

        except Exception as e:
            logging.error(f"Error marking notifications as read: {str(e)}")
            return {"error": "Unable to mark notifications as read", "success": False}, 500


@notifications_ns.route("/bulk/dismiss")
class BulkDismissResource(Resource):
    """Resource for dismissing multiple notifications."""

    @notifications_ns.doc(security="Bearer Auth")
    @notifications_ns.expect(bulk_ids_model)
    @notifications_ns.response(200, "Notifications dismissed")
    @jwt_required(locations=["headers", "cookies"])
    def post(self):
        """Dismiss multiple notifications."""
        try:
            notification_ids = request.json.get("ids", [])
            success_count = 0
            for notification_id in notification_ids:
                result = mark_notification_as_dismissed(notification_id, session["user.id"])
                if result["success"]:
                    success_count += 1

            # Get updated counts
            result = get_notifications(user_id=session["user.id"])

            return {
                "message": f"{success_count} notifications dismissed",
                "success": True,
                "counts": result["counts"],
            }, 200
        except Exception as e:
            logging.error(f"Error dismissing notifications: {str(e)}")
            return {"error": "Unable to dismiss notifications", "success": False}, 500
