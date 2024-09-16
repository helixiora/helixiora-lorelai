"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackOAuth: Handles OAuth authentication with Slack.
    SlackIndexer: Retrieves, processes, and loads Slack messages into Pinecone.
"""

import logging
import requests
from flask import redirect, request, session, url_for

from app.helpers.database import get_db_connection
from app.helpers.datasources import get_datasource_id_by_name
from lorelai.utils import load_config


class SlackOAuth:
    """Handles OAuth authentication with Slack."""

    AUTH_URL = "https://slack.com/oauth/v2/authorize"
    TOKEN_URL = "https://slack.com/api/oauth.v2.access"
    SCOPES = "channels:history,channels:read,chat:write"

    def __init__(self):
        """Initialize the SlackOAuth class with configuration settings."""
        self.config = load_config("slack")
        self.client_id = self.config["client_id"]
        self.client_secret = self.config["client_secret"]
        self.redirect_uri = self.config["redirect_uri"]

    def get_auth_url(self):
        """
        Generate and return the Slack OAuth authorization URL.

        Returns
        -------
            str: The authorization URL.
        """
        params = {
            "client_id": self.client_id,
            "scope": self.SCOPES,
            "redirect_uri": self.redirect_uri,
        }
        request_url = requests.Request("GET", self.AUTH_URL, params=params).prepare().url
        return request_url

    def get_access_token(self, code):
        """
        Exchange the authorization code for an access token.

        Args:
            code (str): The authorization code received from Slack.

        Returns
        -------
            str or None: The access token if successful, otherwise None.
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        response = requests.post(self.TOKEN_URL, data=payload)
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    def auth_callback(self):
        """
        Handle the OAuth callback, exchange code for token.

        and update the user's Slack token in the database.

        Returns
        -------
            Response: A redirect response to the index page or an error message.
        """
        code = request.args.get("code")
        access_token = self.get_access_token(code)
        if access_token:
            session["slack_access_token"] = access_token
            datasource_id = get_datasource_id_by_name("Slack")
            with get_db_connection() as conn:
                cursor = conn.cursor()
                query = """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            auth_key = VALUES(auth_key),
                            auth_value = VALUES(auth_value),
                            auth_type = VALUES(auth_type);
                        """  # noqa: E501
                data = (session["user_id"], datasource_id, "access_token", access_token, "oauth")
                cursor.execute(query, data)
                conn.commit()
                logging.debug(access_token)
                return redirect(url_for("chat.index"))
        return "Error", 400
