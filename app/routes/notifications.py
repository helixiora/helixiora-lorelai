"""Notifications routes for the application."""

from flask import render_template, flash, Blueprint
from flask_login import login_required, current_user
import logging

from app.helpers.notifications import get_notifications

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications")
@login_required
def notifications():
    """Return the notifications page."""
    try:
        # Get all notifications for the page
        result = get_notifications(user_id=current_user.id)
        notifications = result["notifications"]
        notification_types = sorted(set(n.type for n in notifications))
        return render_template(
            "notifications.html",
            notifications=notifications,
            notification_types=notification_types,
            counts=result["counts"],
        )
    except Exception as e:
        logging.error(f"Error fetching notifications: {e}")
        flash("Failed to retrieve notifications.", "error")
        return render_template(
            "notifications.html",
            notifications=[],
            notification_types=[],
            counts={"total": 0, "unread_active": 0, "read_active": 0, "dismissed": 0},
        )
