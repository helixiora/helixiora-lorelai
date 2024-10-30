"""Slack authorization routes."""

from flask import Blueprint, redirect, url_for, current_app, request, session, flash
import requests
import logging

from app.helpers.slack import SlackHelper
from app.models import UserAuth, db
from sqlalchemy.exc import SQLAlchemyError

slack_bp = Blueprint("slack_auth", __name__)


@slack_bp.route("/slack/auth")
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
    return request_url


@slack_bp.route("/slack/auth/callback")
def slack_callback():
    """Slack OAuth callback route. Handles the Slack OAuth callback."""
    slack = SlackHelper()

    code = request.args.get("code")
    if not code:
        logging.error("No code received from Slack")
        return False

    try:
        auth_data = slack.get_access_token(code)
        if not auth_data:
            logging.error("Failed to get access token from Slack")
            return False

        access_token = auth_data["access_token"]
        team_name = auth_data["team_name"]
        team_id = auth_data["team_id"]

        logging.info(f"Authorized for Slack workspace: {team_name} (ID: {team_id})")
        session["slack.access_token"] = access_token
        session["slack.team_name"] = team_name
        session["slack.team_id"] = team_id

        user_auth = UserAuth.query.filter_by(
            user_id=session["user.id"],
            datasource_id=slack.datasource.datasource_id,
            auth_key="access_token",
        ).first()

        if user_auth:
            user_auth.auth_value = access_token
            logging.info(f"Updated existing UserAuth for user {session['user.id']}")
        else:
            new_auth = UserAuth(
                user_id=session["user.id"],
                datasource_id=slack.datasource.datasource_id,
                auth_key="access_token",
                auth_value=access_token,
                auth_type="oauth",
            )
            db.session.add(new_auth)
            logging.info(f"Created new UserAuth for slack for user {session['user.id']}")

        # see if there are any pending changes to the database
        logging.info(f"Committing pending changes to database for slack, user {session['user.id']}")
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
