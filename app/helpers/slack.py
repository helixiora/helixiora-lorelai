"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackHelper: Handles Slack helper functions.
"""

import logging
import requests
import time
from flask import request, session, current_app

from app.helpers.datasources import DATASOURCE_SLACK
from app.models import db, UserAuth, Datasource, User
from sqlalchemy.exc import SQLAlchemyError


class SlackHelper:
    """Handles Slack helper functions."""

    def __init__(self):
        """Initialize the SlackHelper class with configuration settings."""
        self.authorization_url = current_app.config["SLACK_AUTHORIZATION_URL"]
        self.token_url = current_app.config["SLACK_TOKEN_URL"]
        self.scopes = current_app.config["SLACK_SCOPES"]
        self.client_id = current_app.config["SLACK_CLIENT_ID"]
        self.client_secret = current_app.config["SLACK_CLIENT_SECRET"]
        self.redirect_uri = current_app.config["SLACK_REDIRECT_URI"]
        self.datasource = Datasource.query.filter_by(name=DATASOURCE_SLACK).first()
        if not self.datasource:
            raise ValueError(f"{DATASOURCE_SLACK} is missing from datasource table in db")

    @staticmethod
    def get_auth_url(authorization_url: str, client_id: str, scopes: str, redirect_uri: str) -> str:
        """
        Generate and return the Slack OAuth authorization URL.

        Returns
        -------
            str: The authorization URL.
        """
        params = {
            "client_id": client_id,
            "scope": scopes,
            "redirect_uri": redirect_uri,
        }
        request_url = requests.Request("GET", authorization_url, params=params).prepare().url
        return request_url

    @staticmethod
    def get_access_token(
        token_url: str, client_id: str, client_secret: str, code: str, redirect_uri: str
    ) -> dict | None:
        """
        Exchange the authorization code for an access token.

        Args:
            code (str): The authorization code received from Slack.

        Returns
        -------
            dict or None: Dictionary containing access token and team info if successful,
                         otherwise None.
        """
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        response = requests.post(token_url, data=payload)
        if response.status_code == 200:
            data = response.json()
            if "ok" in data and data["ok"]:
                if "access_token" in data:
                    return {
                        "access_token": data["access_token"],
                        "team_name": data.get("team", {}).get("name"),
                        "team_id": data.get("team", {}).get("id"),
                    }
            else:
                raise Exception(f"Error retrieving access token (ok == False): {data['error']}")
        else:
            raise Exception(f"Error retrieving access token: {response.text}")

    @staticmethod
    def test_slack_token(access_token: str) -> bool:
        """
        Verify if the Slack access token is valid.

        Makes a request to the `auth.test` endpoint. Raises RuntimeError if the token is invalid
        or an HTTP error occurs.

        Raises
        ------
            RuntimeError: If the token is invalid or there's an HTTP error.

        Returns
        -------
            bool: True if the token is valid.
        """
        url = "https://slack.com/api/auth.test"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                logging.info("Slack token is valid!")
                return True
            else:
                raise RuntimeError(f"Slack token test failed: {data.get('error')}")
        else:
            raise RuntimeError(f"HTTP Error: {response.status_code} - {response.text}")

    def get_userid_name(self) -> dict[str, str]:
        """
        Retrieve and return a dictionary mapping user IDs to user names from Slack.

        Returns
        -------
            dict: A dictionary mapping user IDs to user names.
        """
        data = self.slack_api_call("https://slack.com/api/users.list")

        if data and "ok" in data and data["ok"] and "members" in data:
            users = data["members"]
            users_dict = {}
            for i in users:
                users_dict[i["id"]] = i["name"]
            return users_dict
        else:
            logging.error(f"Failed to list users. Error: {data}")
            return None

    def extract_message_text(self, message: dict) -> str:
        """
        Extract the text body content from a Slack message.

        Args:
            message (dict): The Slack message.

        Returns
        -------
            str: The extracted message text.
        """
        message_text = ""
        user = ""
        if "user" in message:
            user = message["user"]

        if "text" in message:
            message_text = f"{user}:  {message['text']}."

        if "attachments" in message and message.get("subtype") == "bot_message":
            for i in message["attachments"]:
                message_text += "\n" + i["fallback"] + "."
        return message_text

    def get_message_permalink(self, channel_id: str, message_ts: str) -> str | None:
        """
        Retrieve and return the permalink for a specific Slack message.

        Args:
            channel_id (str): The ID of the Slack channel.
            message_ts (str): The timestamp of the message.

        Returns
        -------
            str or None: The permalink if successful, otherwise None.
        """
        url = "https://slack.com/api/chat.getPermalink"

        params = {"channel": channel_id, "message_ts": message_ts}
        data = self.slack_api_call(url, params=params)
        if data:
            if data.get("ok"):
                return data["permalink"]
            else:
                logging.error(f"Error in response: {data['error']}")
                return None
        else:
            logging.error(f"Failed to get permalink. Error: {data.text}")
            return None

    def retrieve_access_token(self, email: str) -> str | None:
        """
        Retrieve the Slack access token from the database for the given email.

        Args:
            email (str): The user's email.

        Returns
        -------
            str or None: The Slack access token if found, otherwise None.
        """
        auth_value = (
            db.session.query(UserAuth.auth_value)
            .join(User, User.id == UserAuth.user_id)
            .filter(User.email == email, UserAuth.datasource_id == 3)
            .first()
        )
        if auth_value:
            return auth_value[0]
        else:
            raise ValueError(f"Slack Token not found for user {email}")

    def replace_userid_with_name(self, thread_text: str) -> str:
        """
        Replace user IDs with user names in the given text.

        Args:
            thread_text (str): The text containing user IDs.

        Returns
        -------
            str: The text with user IDs replaced by user names.
        """
        for user_id, user_name in self.userid_name_dict.items():
            thread_text = thread_text.replace(user_id, user_name)
        return thread_text

    def slack_api_call(self, url: str, params: dict = None, max_retries: int = 3) -> dict | None:
        """
        Make a Slack API call and handle the response, including rate limiting.

        Args
        ----
            :param url (str): The URL to make the API call to.
            :param params (dict): The parameters to include in the API call.
            :param max_retries (int): Maximum number of retries for rate limiting.

        Returns
        -------
            dict: The response from the Slack API call.
        """
        for attempt in range(max_retries):
            if attempt > 0:
                logging.debug(f"Making Slack API call to {url} with params: {params} \
                                        (Attempt {attempt + 1}/{max_retries})")
            response = self.session.get(url, params=params or {})

            # response.ok is true if status code is 200
            if response.ok:
                # even if response.ok is true, the response can still contain an error message
                # in the response.json()
                response_json = response.json()
                if "ok" in response_json and not response_json["ok"]:
                    logging.error(f"Slack API call failed to {url} with params: {params} \
                                    Error: {response_json['error']}")
                    return response_json
                return response_json
            elif response.status_code == 429:  # Rate limited
                retry_after = int(response.headers.get("Retry-After", 1)) + 1
                logging.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                logging.error(f"Failed to make Slack API call. Error: {response.text}")
                return None

        logging.error(f"Max retries reached for Slack API call to {url}")
        return None

    def handle_callback(self) -> bool:
        """
        Handle the OAuth callback, exchange code for token.

        and update the user's Slack token in the database.

        Returns
        -------
            Bool: True if the callback was successful, False otherwise.
        """
        code = request.args.get("code")
        if not code:
            logging.error("No code received from Slack")
            return False

        try:
            auth_data = self.get_access_token(
                self.token_url, self.client_id, self.client_secret, code, self.redirect_uri
            )
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
                datasource_id=self.datasource.datasource_id,
                auth_key="access_token",
            ).first()

            if user_auth:
                user_auth.auth_value = access_token
                logging.info(f"Updated existing UserAuth for user {session['user.id']}")
            else:
                new_auth = UserAuth(
                    user_id=session["user.id"],
                    datasource_id=self.datasource.datasource_id,
                    auth_key="access_token",
                    auth_value=access_token,
                    auth_type="oauth",
                )
                db.session.add(new_auth)
                logging.info(f"Created new UserAuth for slack for user {session['user.id']}")

            # see if there are any pending changes to the database
            logging.info(
                f"Committing pending changes to database for slack, user {session['user.id']}"
            )
            db.session.commit()
            logging.info(f"Successfully saved access token for slack for user {session['user.id']}")
            return True

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Database error handling callback: {e}")
            return False
        except Exception as e:
            logging.error(f"Error handling callback: {e}")
            return False
