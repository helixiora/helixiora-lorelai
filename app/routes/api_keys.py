"""Routes for API keys."""

import logging
import secrets
from flask import Blueprint, request, redirect, url_for, flash
from app.models import UserAPIKey, db
from flask_login import current_user, login_required
import bleach
from datetime import datetime


api_keys_bp = Blueprint("api_keys", __name__)


def generate_api_key() -> str:
    """Generate a random API key."""
    return secrets.token_hex(16)


@api_keys_bp.route("/api-keys/create", methods=["POST"])
@login_required
def create_api_key():
    """Create a new API key for the user.

    Returns
    -------
        Response: Redirects to profile page on success, with flash message
    """
    try:
        # Validate user is authenticated
        if not current_user.is_authenticated:
            logging.warning("Unauthenticated user attempted to create API key")
            flash("You must be logged in to create an API key", "error")
            return redirect(url_for("auth.login"))

        # Get and sanitize expires_at
        raw_expires_at = request.form.get("expires_at")
        if raw_expires_at:
            try:
                # Clean the input and validate date format
                cleaned_expires_at = bleach.clean(raw_expires_at, tags=[], strip=True)
                expires_at = datetime.strptime(cleaned_expires_at, "%Y-%m-%d").date()

                # Validate date is in the future
                if expires_at <= datetime.now().date():
                    flash("Expiry date must be in the future", "error")
                    return redirect(url_for("profile.index"))
            except ValueError:
                logging.warning(f"Invalid expiry date format submitted: {raw_expires_at}")
                flash("Invalid expiry date format. Please use YYYY-MM-DD", "error")
                return redirect(url_for("auth.profile"))
        else:
            expires_at = None

        # Create new API key
        api_key = UserAPIKey(
            expires_at=expires_at,
            user_id=current_user.id,
            api_key=generate_api_key(),
        )

        db.session.add(api_key)
        db.session.commit()

        logging.info(f"API key created successfully for user {current_user.id}")
        flash("API key created successfully", "success")

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating API key: {str(e)}")
        flash("Error creating API key. Please try again.", "error")

    return redirect(url_for("auth.profile"))
