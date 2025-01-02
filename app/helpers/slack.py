"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackHelper: Handles Slack helper functions.
"""

import logging
import requests
import time
import uuid
from datetime import datetime
from flask import current_app

from app.helpers.datasources import DATASOURCE_SLACK
from app.models import db, Datasource, User, UserAuth
from app.schemas import UserSchema, OrganisationSchema, UserAuthSchema


from lorelai.utils import clean_text_for_vector


class SlackHelper:
    """Handles Slack helper functions."""

    def __init__(
        self, user: UserSchema, organisation: OrganisationSchema, user_auths: list[UserAuthSchema]
    ):
        """Initialize the SlackHelper class with configuration settings."""
        self.authorization_url = current_app.config["SLACK_AUTHORIZATION_URL"]
        self.token_url = current_app.config["SLACK_TOKEN_URL"]
        self.scopes = current_app.config["SLACK_SCOPES"]
        self.client_id = current_app.config["SLACK_CLIENT_ID"]
        self.client_secret = current_app.config["SLACK_CLIENT_SECRET"]
        self.redirect_uri = current_app.config["SLACK_REDIRECT_URI"]

        self.datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first()
        if not self.datasource:
            raise ValueError(f"{DATASOURCE_SLACK} is missing from datasource table in db")

        # Config for slack api
        self.access_token = self.retrieve_access_token(email=user.email)
        if not self.access_token:
            raise ValueError(f"No Slack access token found for user {user.email}")

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Scope": self.scopes,
        }

        self.test_slack_token = SlackHelper.test_slack_token(self.access_token)
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.userid_name_dict = self.get_userid_name()

        if not self.datasource:
            raise ValueError(f"{DATASOURCE_SLACK} is missing from datasource table in db")

    def chunk_and_merge_metadata(
        self,
        lst: list[dict],
        word_limit: int,
        word_overlap: int,
        channel_id: str,
        channel_name: str,
    ) -> list[dict]:
        """
        Chunk a list of dictionaries based on word count of 'metadata.text' and merge their metadata.

        This function processes a list of dictionaries, each containing metadata like text, source,
        timestamp, and channel information. It merges these dictionaries into chunks, each containing
        up to word_limit words. Additionally, the function ensures there is an overlap of
        word_overlap words between consecutive chunks.


        Args:
            lst (list of dict): List of dictionaries, each containing 'id', 'values',
                                and 'metadata' fields. 'metadata' includes:
                                - text (str): A string to concatenate
                                - source (str): A source URL
                                - msg_ts (str): A timestamp
                                - channel_name (str): A channel name
                                - users (list): A list of users
            word_limit (int): Maximum number of words in each chunk's concatenated text.
            word_overlap (int): Number of overlapping words between chunks.
            channel_id (str): channel id, to get the members email for vector storage.
            channel_name (str): channel_name id, to store in metadata.

        Returns
        -------
                list of dict: A list of new dictionaries with merged metadata:
                            - text: Concatenated text from the chunk
                            - source, msg_ts: Taken from the last item in the chunk
                            - channel_name, users: Unique sets converted to lists.

        Example:
            merged_chunks = chunk_and_merge_metadata(lst, word_limit=4000, word_overlap=200)
        """  # noqa: E501
        user_emails = self.get_channel_member_emails(channel_id)
        result = []
        start = 0
        overlap_words = []  # List to store the overlapping words from the previous chunk

        # Step 1: Preprocess the list to handle oversized text fields
        processed_lst = []
        single_message_limit = int(word_limit / 2)
        for item in lst:
            words = item["metadata"]["text"].split()
            # Check if the text exceeds the word limit
            if len(words) > single_message_limit:
                # Break the text into smaller chunks
                for i in range(0, len(words), single_message_limit):
                    sub_chunk_text = " ".join(words[i : i + single_message_limit])
                    sub_chunk_item = {
                        "id": item["id"],
                        "values": item["values"],
                        "metadata": {
                            "text": sub_chunk_text,
                            "source": item["metadata"]["source"],
                            "msg_ts": item["metadata"]["msg_ts"],
                            "channel_name": item["metadata"]["channel_name"],
                            "users": item["metadata"]["users"],
                        },
                    }
                    processed_lst.append(sub_chunk_item)
            else:
                processed_lst.append(item)

        # Step 2: Continue with the original chunking and merging process
        while start < len(processed_lst):
            chunk = []
            word_count = len(overlap_words)  # Start with overlap word count

            # Collect items into a chunk until the word limit is reached
            while start < len(processed_lst) and word_count < word_limit:
                item = processed_lst[start]
                chunk.append(item)

                # Count words in the current item's metadata['text']
                word_count += len(item["metadata"]["text"].split())

                start += 1

            # Initialize merged metadata fields
            merged_text = " ".join(overlap_words) + " " if overlap_words else ""

            # Merge the metadata from all items in the chunk
            for item in chunk:
                merged_text += item["metadata"]["text"] + " "

            # Remove trailing space from concatenated text
            merged_text = merged_text.strip()

            # Get the source and msg_ts from the last item in the chunk
            last_item = chunk[-1]

            # Create the new dictionary with merged metadata
            merged_dict = {
                "id": str(uuid.uuid4()),  # Generate a new unique id
                "values": [],  # Assuming values field remains as is
                "metadata": {
                    "text": merged_text,
                    "source": last_item["metadata"]["source"],
                    "msg_ts": last_item["metadata"]["msg_ts"],
                    "channel_name": channel_name,
                    "users": list(user_emails),
                },
            }

            result.append(merged_dict)
            logging.info(
                f"Words in Chunk: {len(merged_text.split())}\nLenght of Chunk: {len(merged_text)}"
            )
            # Calculate overlap for the next chunk based on word_overlap
            if word_overlap > 0:
                words_in_current_chunk = merged_text.split()
                overlap_words = words_in_current_chunk[-word_overlap:]

        return result

    def get_messages_from_channel(
        self, channel_id: str, channel_name: str, user_email: str
    ) -> list[dict]:
        """
        Retrieve messages from a Slack channel and return them as a list of chat history records.

        Args:
            channel_id (str): The ID of the Slack channel.
            channel_name (str): The name of the Slack channel.

        Returns
        -------
            list: A list of chat history records. for that channel.
        """
        url = "https://slack.com/api/conversations.history"
        logging.debug(f"Getting Messages for Channel: {channel_name}")
        params = {"channel": channel_id}
        channel_chat_history = []

        while True:
            data = SlackHelper.slack_api_call(url=url, session=self.session, params=params)
            if data:
                if "error" in data:
                    # see https://api.slack.com/methods/conversations.history#errors
                    logging.error(
                        f"Error: {data['error']} - Channel: {channel_name} Channel ID: {channel_id}\
: see https://api.slack.com/methods/conversations.history#errors for more information"
                    )
                    return False

                if "messages" in data:
                    logging.info(
                        f"Processing messages for channel: {channel_name} Start: \
{data['messages'][0]['ts']} End: {data['messages'][-1]['ts']}. First msg: \
{data['messages'][0]['text']}"
                    )
                    for msg in data["messages"]:
                        try:
                            msg_ts = ""
                            conversation_text = ""
                            metadata = {}

                            # if msg has no conversation
                            if msg.get("reply_count") is None:
                                conversation_text = self.extract_message_text(msg)
                                msg_ts = msg["ts"]
                            # get all conversation msg
                            elif "reply_count" in msg:
                                conversation_text = self.get_conversation(msg["ts"], channel_id)
                                msg_ts = msg["ts"]  # conversation_ts

                            # get the permalink for the message
                            msg_link = self.get_message_permalink(channel_id, msg_ts)

                            # convert the timestamp to a date
                            msg_datetime = self.timestamp_to_date(msg_ts)

                            # Slack uses user_id not names
                            conversation_text = self.replace_userid_with_name(conversation_text)
                            # add datetime
                            conversation_text = f"{str(msg_datetime)} : {conversation_text}"
                            conversation_text = clean_text_for_vector(conversation_text)
                            metadata = {
                                "text": conversation_text,
                                "source": msg_link,
                                "msg_ts": msg_ts,
                                "channel_name": channel_name,
                                "users": [user_email],
                            }
                            channel_chat_history.append(
                                {
                                    "id": str(uuid.uuid4()),
                                    "values": [],
                                    "metadata": metadata,
                                }
                            )

                        except Exception as e:
                            logging.error(f"Error processing message: {msg}")
                            raise (e)

                if data.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = data["response_metadata"]["next_cursor"]
                    logging.debug(f"Next Page cursor: {params['cursor']}")
                else:
                    logging.debug(f"No more pages to retrieve for channel: {channel_name}")
                    break
            else:
                logging.error(f"Failed to retrieve channel history. Error: {data.text}")
                return False
        logging.debug(f"Total Messages in {channel_name}: {len(channel_chat_history)}")
        return channel_chat_history

    def get_conversation(self, conversation_id: str, channel_id: str) -> str:
        """
        Retrieve and return the complete conversation of messages from Slack.

        Args:
            conversation_id (str): The ID of the conversation.
            channel_id (str): The ID of the Slack channel.

        Returns
        -------
            str: The complete conversation of messages as a single string.
        """
        url = "https://slack.com/api/conversations.replies"
        params = {"channel": channel_id, "ts": conversation_id, "limit": 200}
        complete_conversation = ""
        while True:
            data = SlackHelper.slack_api_call(url=url, session=self.session, params=params)

            if data:
                if "messages" in data:
                    for msg in data["messages"]:
                        msg_text = self.extract_message_text(msg)
                        complete_conversation += msg_text + "\n"

                if data.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = data["response_metadata"]["next_cursor"]
                else:
                    break
        return complete_conversation

    def get_accessible_channels(self, only_joined: bool = False) -> dict[str, str]:
        """
        Retrieve and return a dictionary mapping channel IDs to channel names from Slack.

        Args:
            only_joined (bool): If True, only return channels the bot has been invited to.
                              If False, return all visible channels. Defaults to True.

        Returns
        -------
            dict: A dictionary mapping channel IDs to channel names.
        """
        url = "https://slack.com/api/conversations.list"

        params = {
            "types": "public_channel,private_channel",
            "limit": 1000,
        }

        channels_dict = {}
        while True:
            data = SlackHelper.slack_api_call(url=url, session=self.session, params=params)
            if data:
                if data.get("ok"):
                    for channel in data["channels"]:
                        # For joined-only channels, we only include if we're a member
                        if only_joined and not channel.get("is_member", False):
                            continue
                        channels_dict[channel["id"]] = channel["name"]

                    if data.get("response_metadata", {}).get("next_cursor"):
                        params["cursor"] = data["response_metadata"]["next_cursor"]
                    else:
                        break
                else:
                    logging.error(f"Error in response: {data}")
                    return None
            else:
                logging.error(f"Failed to list channels. Error: {data.text}")
                return None

        logging.info(f"Found {len(channels_dict)} accessible channels")
        return channels_dict

    def timestamp_to_date(self, timestamp: str) -> str:
        """
        Convert a string Unix timestamp (with fractional seconds) to a formatted date string.

        Args:
            timestamp_str (str): The Unix timestamp as a string. Can include fractional seconds.

        Returns
        -------
            str: The formatted date string in the format 'YYYY-MM-DD HH:MM:SS'.
        """
        # Convert the floating-point timestamp to a datetime object
        timestamp = float(timestamp)
        dt = datetime.fromtimestamp(timestamp)
        # Format the datetime object as a string in the desired format
        formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        return formatted_date

    def get_channel_member_emails(self, channel_id: str) -> list[str]:
        """
        Retrieve a list of email addresses for all users who have access to a specific Slack channel.

        Args
        ----
            :param channel_id (str): The ID of the Slack channel.

        Returns
        -------
            list: A list of email addresses of the users in the specified channel.
        """  # noqa: E501
        # Step 1: Get all user IDs in the channel using conversations.members
        members_data = SlackHelper.slack_api_call(
            url="https://slack.com/api/conversations.members",
            session=self.session,
            params={"channel": channel_id},
        )

        if (
            members_data
            and "ok" in members_data
            and members_data["ok"]
            and "members" in members_data
        ):  # noqa: E501
            user_ids = members_data["members"]
        else:
            logging.error(
                f"Failed to retrieve members for channel {channel_id}. \
                Error: {members_data['error'] if members_data else 'Unknown error'}"
            )
            return []

        emails = []

        # Step 2: Loop through each user ID and get their email using users.info
        for user_id in user_ids:
            user_data = SlackHelper.slack_api_call(
                url="https://slack.com/api/users.info",
                session=self.session,
                params={"user": user_id},
            )

            if user_data and "ok" in user_data and user_data["ok"] and "user" in user_data:
                user_info = user_data["user"]
                # Check if the user has an email field and add it to the list
                if "profile" in user_info and "email" in user_info["profile"]:
                    emails.append(user_info["profile"]["email"])
            else:
                logging.warning(
                    f"Failed to retrieve user info for user ID {user_id}. \
                    Error: {user_data['error'] if user_data else 'Unknown error'}"
                )

        return emails

    @staticmethod
    def get_access_token(code: str) -> dict | None:
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
            "client_id": current_app.config["SLACK_CLIENT_ID"],
            "client_secret": current_app.config["SLACK_CLIENT_SECRET"],
            "code": code,
            "redirect_uri": current_app.config["SLACK_REDIRECT_URI"],
        }
        response = requests.post(current_app.config["SLACK_TOKEN_URL"], data=payload)
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
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                logging.info("Slack token is valid!")
                return True
            else:
                logging.error(f"Slack token is invalid: {data['error']}")
                return False
        else:
            raise RuntimeError(f"HTTP Error: {response.status_code} - {response.text}")

    def get_userid_name(self) -> dict[str, str]:
        """
        Retrieve and return a dictionary mapping user IDs to user names from Slack.

        Returns
        -------
            dict: A dictionary mapping user IDs to user names.
        """
        data = SlackHelper.slack_api_call(
            url="https://slack.com/api/users.list", session=self.session, params={}
        )

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
        data = SlackHelper.slack_api_call(url=url, session=self.session, params=params)
        if data:
            if data.get("ok"):
                return data["permalink"]
            else:
                logging.error(f"Error in response: {data['error']}")
                return None
        else:
            logging.error(f"Failed to get permalink. Error: {data}")
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
        datasource_id = (
            Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first().datasource_id
        )
        auth_value = (
            db.session.query(UserAuth.auth_value)
            .join(User, User.id == UserAuth.user_id)
            .filter(User.email == email, UserAuth.datasource_id == datasource_id)
            .first()
        )
        if auth_value:
            return auth_value[0]
        else:
            logging.info(f"No Slack Token found for user {email}")
            return None

    def replace_userid_with_name(self, conversation_text: str) -> str:
        """
        Replace user IDs with user names in the given text.

        Args:
            conversation_text (str): The text containing user IDs.

        Returns
        -------
            str: The text with user IDs replaced by user names.
        """
        for user_id, user_name in self.userid_name_dict.items():
            conversation_text = conversation_text.replace(user_id, user_name)
        return conversation_text

    @staticmethod
    def slack_api_call(url: str, session: requests.Session, params: dict) -> dict | None:
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
        max_retries: int = 3

        for attempt in range(max_retries):
            if attempt > 0:
                logging.debug(
                    f"Making Slack API call to {url} with params: {params} \
                                        (Attempt {attempt + 1}/{max_retries})"
                )
            response = session.get(url, params=params or {})

            # response.ok is true if status code is 200
            if response.ok:
                # even if response.ok is true, the response can still contain an error message
                # in the response.json()
                response_json = response.json()
                if "ok" in response_json and not response_json["ok"]:
                    logging.error(
                        f"Slack API call failed to {url} with params: {params} \
                                    Error: {response_json['error']}"
                    )
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
