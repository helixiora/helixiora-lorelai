"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackOAuth: Handles OAuth authentication with Slack.
    SlackIndexer: Retrieves, processes, and loads Slack messages into Pinecone.
"""

import logging
import os
import uuid

import pinecone
import requests
from flask import redirect, request, session, url_for
from langchain_openai import OpenAIEmbeddings

from app.helpers.database import get_db_connection
from lorelai.utils import get_embedding_dimension, load_config
from lorelai.pinecone import index_name


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
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """UPDATE users
                SET slack_token = %s
                WHERE email = %s""",
                    (session["slack_access_token"], session["email"]),
                )
                conn.commit()
                logging.debug(access_token)
                return redirect(url_for("index"))
        return "Error", 400


class SlackIndexer:
    """Retrieves, processes, and loads Slack messages into Pinecone."""

    def __init__(self, email, org_name) -> None:
        """
        Initialize the SlackIndexer class with required parameters and API keys.

        Args:
            email (str): The user's email.
            org_name (str): The organization name.
        """
        # load API keys
        self.pinecone_settings = load_config("pinecone")
        self.openai_creds = load_config("openai")
        self.lorelai_settings = load_config("lorelai")
        os.environ["PINECONE_API_KEY"] = self.pinecone_settings["api_key"]
        os.environ["OPENAI_API_KEY"] = self.openai_creds["api_key"]

        # init class with required parameters
        self.email = email
        self.org_name = org_name
        self.access_token = self.retrive_access_token(email)
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        self.userid_name_dict = self.get_userid_name()

        logging.debug(self.access_token)

    def retrive_access_token(self, email):
        """
        Retrieve the Slack access token from the database for the given email.

        Args:
            email (str): The user's email.

        Returns
        -------
            str or None: The Slack access token if found, otherwise None.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            sql_query = "SELECT slack_token FROM users WHERE email = %s;"
            cursor.execute(sql_query, (email,))
            result = cursor.fetchone()
            if result:
                slack_token = result[0]
                logging.debug("Slack Token:", slack_token)
                return slack_token

            logging.debug("No Slack token found for the specified email.")
            return None

    def get_userid_name(self):
        """
        Retrieve and return a dictionary mapping user IDs to user names from Slack.

        Returns
        -------
            dict: A dictionary mapping user IDs to user names.
        """
        url = "https://slack.com/api/users.list"
        response = requests.get(url, headers=self.headers)
        if response.ok:
            users = response.json()["members"]
            users_dict = {}
            for i in users:
                users_dict[i["id"]] = i["name"]

            logging.debug(f"Loaded user_dict {users_dict}")
            return users_dict
        else:
            logging.debug(f"Failed to list users. Error: {response.text}")
            return None

    def replace_userid_with_name(self, thread_text):
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

    def get_messages(self, channel_id, channel_name):
        """
        Retrieve messages from a Slack channel and return them as a list of chat history records.

        Args:
            channel_id (str): The ID of the Slack channel.
            channel_name (str): The name of the Slack channel.

        Returns
        -------
            list: A list of chat history records.
        """
        url = "https://slack.com/api/conversations.history"
        logging.debug(f"Getting Messages for Channel: {channel_name}")
        params = {"channel": channel_id}
        channel_chat_history = []
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            if response.ok:
                history = response.json()
                if "error" in history:
                    logging.warning(
                        f"Error: {history['error']} - Channel: {channel_name} id: {channel_id} "
                    )

                if "messages" in history:
                    for msg in history["messages"]:
                        try:
                            msg_ts = ""
                            thread_text = ""
                            metadata = {}

                            # if msg has no thread
                            if msg.get("reply_count") is None:
                                thread_text = self.extract_message_text(msg)
                                msg_ts = msg["ts"]

                            # get all thread msg
                            elif "reply_count" in msg:
                                thread_text = self.get_thread(msg["ts"], channel_id)
                                msg_ts = msg["ts"]  # thread_ts

                            msg_link = self.get_message_permalink(channel_id, msg_ts)
                            thread_text = self.replace_userid_with_name(thread_text)
                            metadata = {
                                "text": thread_text,
                                "source": msg_link,
                                "msg_ts": msg_ts,
                                "channel_name": channel_name,
                                "users": [self.email],
                            }
                            channel_chat_history.append(
                                {
                                    "id": str(uuid.uuid4()),
                                    "values": [],
                                    "metadata": metadata,
                                }
                            )
                            logging.debug(metadata)
                            logging.debug("--------------------")

                        except Exception as e:
                            logging.fatal(msg)
                            raise (e)

                if history.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = history["response_metadata"]["next_cursor"]
                    logging.debug(f"Next Page cursor: {params['cursor']}")
                else:
                    break

            else:
                logging.debug("Failed to retrieve channel history. Error:", response.text)
        logging.debug("--------------")
        logging.debug(f"Total Messages in {channel_name}-{len(channel_chat_history)}")
        return channel_chat_history

    def get_thread(self, thread_id, channel_id):
        """
        Retrieve and return the complete thread of messages from Slack.

        Args:
            thread_id (str): The ID of the thread.
            channel_id (str): The ID of the Slack channel.

        Returns
        -------
            str: The complete thread of messages as a single string.
        """
        url = "https://slack.com/api/conversations.replies"
        params = {"channel": channel_id, "ts": thread_id, "limit": 200}
        logging.debug(f"Getting message of thread: {thread_id}")
        complete_thread = ""
        while True:
            response = requests.get(url, headers=self.headers, params=params)

            if response.ok:
                history = response.json()
                # plogging.debug(history)
                if "messages" in history:
                    for msg in history["messages"]:
                        msg_text = self.extract_message_text(msg)
                        complete_thread += msg_text + "\n"

                if history.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = history["response_metadata"]["next_cursor"]
                else:
                    break
        return complete_thread

    def extract_message_text(self, message):
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
            message_text = f"{user}:  {message['text']}"

        if "attachments" in message and message.get("subtype") == "bot_message":
            for i in message["attachments"]:
                message_text += "\n" + i["fallback"]
        return message_text

    def get_message_permalink(self, channel_id, message_ts):
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
        response = requests.get(url, headers=self.headers, params=params)
        if response.ok:
            data = response.json()
            if data["ok"]:
                return data["permalink"]
            else:
                logging.debug("Error in response:", data["error"])
                return None
        else:
            logging.debug("Failed to get permalink. Error:", response.text)
            return None

    def dict_channel_ids(self):
        """
        Retrieve and return a dictionary mapping channel IDs to channel names from Slack.

        Returns
        -------
            dict: A dictionary mapping channel IDs to channel names.
        """
        url = "https://slack.com/api/conversations.list"

        params = {
            "types": "public_channel,private_channel",
            "limit": 1000,  # Adjust the limit if needed
        }

        channels_dict = {}

        while True:
            response = requests.get(url, headers=self.headers, params=params)
            if response.ok:
                data = response.json()
                if data["ok"]:
                    for channel in data["channels"]:
                        channels_dict[channel["id"]] = channel["name"]
                    if data.get("response_metadata", {}).get("next_cursor"):
                        params["cursor"] = data["response_metadata"]["next_cursor"]
                    else:
                        break
                else:
                    logging.debug("Error in response:", data["error"])
                    return None
            else:
                logging.debug("Failed to list channels. Error:", response.text)
                return None
        return channels_dict

    def add_embedding(self, embedding_model, chat_history):
        """
        Add embeddings to the complete chat history using the specified embedding model.

        Args:
            embedding_model (OpenAIEmbeddings): The embedding model to use.
            chat_history (list): chat history.

        Returns
        -------
            list: The chat history with embeddings added.

        Raises
        ------
            Exception: If there is an error during embedding.
            ValueError: If the length of embeddings and chat history do not match.
        """
        try:
            text = [chat["metadata"]["text"] for chat in chat_history]
        except Exception as e:
            raise e

        embeds = embedding_model.embed_documents(text)
        if len(chat_history) != len(embeds):
            raise ValueError("Embeds length and document length mismatch")

        # will delete one, 2 method does same thing
        for i in range(len(embeds)):
            chat_history[i]["values"] = embeds[i]

        return chat_history

    def load_to_pinecone(self, embedding_dimension, complete_chat_history):
        """
        Load the complete chat history with embeddings into Pinecone.

        Args:
            embedding_dimension (int): The dimension of the embeddings.
            complete_chat_history (list): The complete chat history with embeddings.

        Returns
        -------
            int: The number of records loaded into Pinecone.
        """
        index = index_name(
            org=self.org_name,
            datasource="slack",
            environment=self.lorelai_settings["environment"],
            env_name=self.lorelai_settings["environment_slug"],
            version="v1",
        )

        pc = pinecone.Pinecone(api_key=self.pinecone_settings["api_key"])

        if index not in pc.list_indexes().names():
            # Create a new index
            pc.create_index(
                name=index,
                dimension=embedding_dimension,
                metric="cosine",
                spec=pinecone.ServerlessSpec(cloud="aws", region=self.pinecone_settings["region"]),
            )
        pc_index = pc.Index(index)
        pc_index.upsert(complete_chat_history)
        return len(complete_chat_history)

    def process_slack_message(self, channel_id=None):
        """
        Process Slack messages, generate embeddings, and load them into Pinecone.

        Args:
            channel_id (str, optional): The ID of a specific Slack channel to process.
            Defaults to None.
        """
        channel_ids_dict = self.dict_channel_ids()
        complete_chat_history = []
        if channel_id is not None:
            if channel_id in channel_ids_dict:
                channel_ids_dict = {channel_id: channel_ids_dict[channel_id]}
            else:
                logging.debug(f"{channel_id} not in slack")
                return None

        for channel_id, channel_name in channel_ids_dict.items():
            logging.debug(f"Processing {channel_id} {channel_name}")
            complete_chat_history.extend(self.get_messages(channel_id, channel_name))
            #

        embedding_model_name = "text-embedding-ada-002"
        embedding_model = OpenAIEmbeddings(model=embedding_model_name)
        embedding_dimension = get_embedding_dimension(embedding_model_name)
        if embedding_dimension == -1:
            raise ValueError(f"Could not find embedding dimension for model '{embedding_model}'")

        # Process in Batch
        batch_size = 200
        total_items = len(complete_chat_history)
        logging.info(
            f"Getting Embeds and Inserting to DB for {total_items} \
                messages in batches of {batch_size}"
        )
        for start_idx in range(0, total_items, batch_size):
            end_idx = min(start_idx + batch_size, total_items)
            batch = complete_chat_history[start_idx:end_idx]
            batch = self.add_embedding(embedding_model, batch)
            self.load_to_pinecone(embedding_dimension, batch)


# 1715850407.699219
