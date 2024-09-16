"""Slack authorization routes."""

from flask import Blueprint, redirect, url_for

from lorelai.slack.oauth import SlackOAuth


slack_bp = Blueprint("slack_auth", __name__)


@slack_bp.route("/slack/auth")
def slack_auth():
    """Slack OAuth route. Redirects to the Slack OAuth URL."""
    slack_oauth = SlackOAuth()
    return redirect(slack_oauth.get_auth_url())


@slack_bp.route("/slack/auth/callback")
def slack_callback():
    """Slack OAuth callback route. Handles the Slack OAuth callback."""
    slack = SlackOAuth()

    slack.handle_callback()
    return redirect(url_for("auth.profile"))
