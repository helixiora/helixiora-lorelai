"""Slack authorization routes."""

from flask import Blueprint, redirect, url_for, current_app, request, session, flash
import requests
import logging

from app.helpers.slack import SlackHelper
from app.models import db
from app.models.user_auth import UserAuth
from app.models.datasource import Datasource
from sqlalchemy.exc import SQLAlchemyError
from flask_login import login_required, current_user

from app.helpers.datasources import DATASOURCE_SLACK

slack_bp = Blueprint("slack_auth", __name__)


@slack_bp.route("/slack/auth")
@login_required
def slack_auth():
    """Slack OAuth route. Redirects to the Slack OAuth URL."""
    params = {
        "client_id": current_app.config["SLACK_CLIENT_ID"],
        "scope": current_app.config["SLACK_SCOPES"],
        "redirect_uri": current_app.config["SLACK_REDIRECT_URI"],
    }
    request_url = (
        requests.Request("GET", current_app.config["SLACK_AUTHORIZATION_URL"], params=params)
        .prepare()
        .url
    )
    return redirect(request_url)


@slack_bp.route("/slack/auth/callback")
def slack_callback():
    """Slack OAuth callback route. Handles the Slack OAuth callback."""
    slack_datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first()
    if not slack_datasource:
        logging.error("Slack datasource not found")
        flash("Error: Slack integration not configured properly.", "error")
        return redirect(url_for("auth.profile"))

    code = request.args.get("code")
    if not code:
        logging.error("No code received from Slack")
        flash("Error: No authorization code received from Slack.", "error")
        return redirect(url_for("auth.profile"))

    try:
        auth_data = SlackHelper.get_access_token(code)
        if not auth_data:
            logging.error("Failed to get access token from Slack")
            flash("Error: Failed to get authorization from Slack.", "error")
            return redirect(url_for("auth.profile"))

        access_token = auth_data["access_token"]
        logging.info(f"Access token: {len(access_token)} characters")
        team_name = auth_data["team_name"]
        team_id = auth_data["team_id"]

        logging.info(f"Authorized for Slack workspace: {team_name} (ID: {team_id})")
        session["slack.access_token"] = access_token
        session["slack.team_name"] = team_name
        session["slack.team_id"] = team_id

        # First try to find existing auth
        user_auth = UserAuth.query.filter_by(
            user_id=session["user.id"],
            datasource_id=slack_datasource.datasource_id,
            auth_key="access_token",
        ).first()

        if user_auth:
            # Update existing auth
            user_auth.auth_value = access_token
            user_auth.auth_type = "oauth"
        else:
            # Create new auth
            user_auth = UserAuth(
                user_id=session["user.id"],
                datasource_id=slack_datasource.datasource_id,
                auth_key="access_token",
                auth_value=access_token,
                auth_type="oauth",
            )
            db.session.add(user_auth)

        db.session.commit()
        logging.info(f"Successfully saved access token for slack for user {session['user.id']}")
        flash("Slack account authorized successfully.", "success")

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error handling callback: {e}")
        flash("An error occurred while authorizing your Slack account. Please try again.", "error")

    except Exception as e:
        logging.error(f"Error handling callback: {e}")
        flash("An error occurred while authorizing your Slack account. Please try again.", "error")

    return redirect(url_for("auth.profile"))


@slack_bp.route("/slack/revoke", methods=["POST"])
@login_required
def revoke():
    """Revoke Slack access and remove auth records."""
    try:
        slack_datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first()
        if slack_datasource:
            UserAuth.query.filter_by(
                user_id=current_user.id, datasource_id=slack_datasource.datasource_id
            ).delete()
            db.session.commit()
            flash("Slack integration has been revoked.", "success")
        else:
            flash("Slack integration not found.", "error")
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error while revoking Slack access: {e}")
        flash("An error occurred while revoking Slack access.", "error")

    return redirect(url_for("auth.profile"))
