"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackOAuth: Handles OAuth authentication with Slack.
    SlackIndexer: Retrieves, processes, and loads Slack messages into Pinecone.
"""

import logging
import requests
from flask import request, session, current_app

from app.helpers.datasources import DATASOURCE_SLACK
from app.models import db, UserAuth, Datasource
from sqlalchemy.exc import SQLAlchemyError


class SlackOAuth:
    """Handles OAuth authentication with Slack."""

    def __init__(self):
        """Initialize the SlackOAuth class with configuration settings."""
        self.authorization_url = current_app.config["SLACK_AUTHORIZATION_URL"]
        self.token_url = current_app.config["SLACK_TOKEN_URL"]
        self.scopes = current_app.config["SLACK_SCOPES"]
        self.client_id = current_app.config["SLACK_CLIENT_ID"]
        self.client_secret = current_app.config["SLACK_CLIENT_SECRET"]
        self.redirect_uri = current_app.config["SLACK_REDIRECT_URI"]
        self.datasource = Datasource.query.filter_by(name=DATASOURCE_SLACK).first()
        if not self.datasource:
            raise ValueError(f"{DATASOURCE_SLACK} is missing from datasource table in db")

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

                user_auth = UserAuth.query.filter_by(
                    user_id=session["id"],
                    datasource_id=self.datasource.datasource_id,
                    auth_key="access_token",
                ).first()

                if user_auth:
                    user_auth.auth_value = access_token
                else:
                    new_auth = UserAuth(
                        user_id=session["id"],
                        datasource_id=self.datasource.datasource_id,
                        auth_key="access_token",
                        auth_value=access_token,
                        auth_type="oauth",
                    )
                    db.session.add(new_auth)

                db.session.commit()
                logging.debug(access_token)
                return True  # Successful callback
            else:
                logging.error("No access token received from Slack, removing from user_auth table")
                # remove slack access token from user_auth table
                UserAuth.query.filter_by(
                    user_id=session["id"],
                    datasource_id=self.datasource.datasource_id,
                    auth_type="oauth",
                ).delete()
                db.session.commit()
                return False

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Database error handling callback: {e}")
            return False  # Callback failed
        except Exception as e:
            logging.error(f"Error handling callback: {e}")
            return False  # Callback failed
