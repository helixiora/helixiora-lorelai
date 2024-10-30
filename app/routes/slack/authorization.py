"""Slack authorization routes."""

from flask import Blueprint, redirect, url_for

from app.helpers.slack import SlackHelper

slack_bp = Blueprint("slack_auth", __name__)


@slack_bp.route("/slack/auth")
def slack_auth():
    """Slack OAuth route. Redirects to the Slack OAuth URL."""
    slack_helper = SlackHelper()
    return redirect(
        slack_helper.get_auth_url(
            authorization_url=slack_helper.authorization_url,
            client_id=slack_helper.client_id,
            scopes=slack_helper.scopes,
            redirect_uri=slack_helper.redirect_uri,
        )
    )


@slack_bp.route("/slack/auth/callback")
def slack_callback():
    """Slack OAuth callback route. Handles the Slack OAuth callback."""
    slack_helper = SlackHelper()

    slack_helper.handle_callback()
    return redirect(url_for("auth.profile"))
