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
        # Get notifications, excluding dismissed ones by default
        notifications = get_notifications(user_id=current_user.id, show_dismissed=False)
        notification_types = sorted(set(n.type for n in notifications))
        return render_template(
            "notifications.html", notifications=notifications, notification_types=notification_types
        )
    except Exception as e:
        logging.error(f"Error fetching notifications: {e}")
        flash("Failed to retrieve notifications.", "error")
        return render_template("notifications.html", notifications=[], notification_types=[])
