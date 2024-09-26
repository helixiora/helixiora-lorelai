"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackOAuth: Handles OAuth authentication with Slack.
    SlackIndexer: Retrieves, processes, and loads Slack messages into Pinecone.
"""

import logging
import requests
from flask import request, session

from app.helpers.database import get_db_connection
from app.helpers.datasources import get_datasource_id_by_name
from lorelai.utils import load_config


class SlackOAuth:
    """Handles OAuth authentication with Slack."""

    def __init__(self):
        """Initialize the SlackOAuth class with configuration settings."""
        self.config = load_config("slack")
        self.authorization_url = self.config["authorization_url"]
        self.token_url = self.config["token_url"]
        self.scopes = self.config["scopes"]
        self.client_id = self.config["client_id"]
        self.client_secret = self.config["client_secret"]
        self.redirect_uri = self.config["redirect_uri"]
        self.datasource_id = get_datasource_id_by_name("Slack")

    def get_auth_url(self):
        """
        Generate and return the Slack OAuth authorization URL.

        Returns
        -------
            str: The authorization URL.
        """
        params = {
            "client_id": self.client_id,
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri,
        }
        request_url = requests.Request("GET", self.authorization_url, params=params).prepare().url
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
        response = requests.post(self.token_url, data=payload)
        if response.status_code == 200:
            data = response.json()
            if "ok" in data and data["ok"]:
                if "access_token" in data:
                    return data["access_token"]
            else:
                raise Exception(f"Error retrieving access token (ok == False): {data['error']}")
        else:
            raise Exception(f"Error retrieving access token: {response.text}")

    def handle_callback(self) -> bool:
        """
        Handle the OAuth callback, exchange code for token.

        and update the user's Slack token in the database.

        Returns
        -------
            Bool: True if the callback was successful, False otherwise.
        """
        # get code from request
        code = request.args.get("code")
        access_token = None
        try:
            # get access token from slack code
            access_token = self.get_access_token(code)
            if access_token:
                session["slack_access_token"] = access_token

                if not self.datasource_id:
                    raise ValueError("Slack datasource not found")
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    query = """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                auth_key = VALUES(auth_key),
                                auth_value = VALUES(auth_value),
                                auth_type = VALUES(auth_type);
                            """  # noqa: E501
                    data = (
                        session["user_id"],
                        self.datasource_id,
                        "access_token",
                        access_token,
                        "oauth",
                    )
                    cursor.execute(query, data)
                    conn.commit()
                    logging.debug(access_token)
                    return True  # Successful callback
            else:
                logging.error("No access token received from Slack, removing from user_auth table")
                # remove slack access token from user_auth table
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    query = """DELETE FROM user_auth WHERE user_id = %s AND datasource_id = %s AND auth_type = %s;"""  # noqa: E501
                    data = (session["user_id"], self.datasource_id, "oauth")
                    cursor.execute(query, data)
                    conn.commit()
                return False

        except Exception as e:
            logging.error(f"Error handling callback: {e}")
            return False  # Callback failed
