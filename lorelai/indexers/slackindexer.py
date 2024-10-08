"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackIndexer: Handles Slack message indexing using Pinecone and OpenAI.
"""

import logging
import os
import sys
import requests
import uuid
import time
from datetime import datetime
from langchain_openai import OpenAIEmbeddings

import lorelai.utils
from lorelai.indexer import Indexer
from lorelai.pinecone import PineconeHelper
from lorelai.utils import get_embedding_dimension

from app.helpers.datasources import get_datasource_id_by_name
from app.helpers.users import get_user_id_by_email


class SlackIndexer(Indexer):
    """Retrieves, processes, and loads Slack messages into Pinecone."""

    def __init__(self, email: str, org_name: str) -> None:
        """
        Initialize the SlackIndexer class with required parameters and API keys.

        Args:
            email (str): The user's email.
            org_name (str): The organization name.
        """
        # load API keys

        self.openai_creds = lorelai.utils.load_config("openai")
        self.lorelai_settings = lorelai.utils.load_config("lorelai")
        os.environ["OPENAI_API_KEY"] = self.openai_creds["api_key"]

        self.pinecone_helper = PineconeHelper()

        # init class with required parameters
        self.email = email
        self.org_name = org_name
        self.access_token = self.retrieve_access_token(email=email)
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        self.userid_name_dict = self.get_userid_name()

        logging.debug(f"Slack Access Token: {self.access_token}")

    def slack_api_call(
        self, url: str, headers: dict, params: dict, max_retries: int = 3
    ) -> dict | None:
        """
        Make a Slack API call and handle the response, including rate limiting.

        Args
        ----
            :param url (str): The URL to make the API call to.
            :param headers (dict): The headers to include in the API call.
            :param params (dict): The parameters to include in the API call.
            :param max_retries (int): Maximum number of retries for rate limiting.

        Returns
        -------
            dict: The response from the Slack API call.
        """
        for attempt in range(max_retries):
            if attempt > 0:
                logging.debug(f"Making Slack API call to {url} with params: {params}\
(Attempt {attempt + 1}/{max_retries})")
            response = requests.get(url, headers=headers, params=params)

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

    def retrieve_access_token(self, email: str) -> str | None:
        """
        Retrieve the Slack access token from the database for the given email.

        Args:
            email (str): The user's email.

        Returns
        -------
            str or None: The Slack access token if found, otherwise None.
        """
        datasource_id = get_datasource_id_by_name("Slack")
        user_id = get_user_id_by_email(email)
        conn = None
        cursor = None
        try:
            conn = lorelai.utils.get_db_connection()
            cursor = conn.cursor()
            sql_query = (
                "SELECT auth_value FROM user_auth WHERE datasource_id = %s AND user_id = %s;"
            )
            cursor.execute(sql_query, (datasource_id, user_id))
            result = cursor.fetchone()
            if result:
                slack_token = result[0]
                logging.debug(f"Slack Token: {slack_token}")
                return slack_token

            logging.debug("No Slack token found for the specified user_id.")
            return None
        except Exception as e:
            logging.error(f"Error retrieving access token: {e}")
            return None
        finally:
            if cursor:
                cursor.close()  # Close the cursor
            if conn:
                conn.close()  # Close the connection

    def get_userid_name(self) -> dict[str, str]:
        """
        Retrieve and return a dictionary mapping user IDs to user names from Slack.

        Returns
        -------
            dict: A dictionary mapping user IDs to user names.
        """
        data = self.slack_api_call("https://slack.com/api/users.list", self.headers, {})

        if data and "ok" in data and data["ok"] and "members" in data:
            users = data["members"]
            users_dict = {}
            for i in users:
                users_dict[i["id"]] = i["name"]
            return users_dict
        else:
            logging.debug(f"Failed to list users. Error: {data.error}")
            return None

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

    def get_messages(self, channel_id: str, channel_name: str) -> list[dict]:
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
            data = self.slack_api_call(url, headers=self.headers, params=params)
            if data:
                if "error" in data:
                    # see https://api.slack.com/methods/conversations.history#errors
                    logging.error(
                        f"Error: {data['error']} - Channel: {channel_name} Channel ID: {channel_id}\
: see https://api.slack.com/methods/conversations.history#errors for more information"
                    )
                    return False

                if "messages" in data:
                    logging.info(f"Processing messages for channel: {channel_name} Start: \
{data['messages'][0]['ts']} End: {data['messages'][-1]['ts']}. First msg: \
{data['messages'][0]['text']}")
                    for msg in data["messages"]:
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

                            msg_datetime = self.timestamp_to_date(msg_ts)
                            # Slack uses user_id not names
                            thread_text = self.replace_userid_with_name(thread_text)
                            thread_text = f"{str(msg_datetime)} : {thread_text}"
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

    def get_thread(self, thread_id: str, channel_id: str) -> str:
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
        complete_thread = ""
        while True:
            data = self.slack_api_call(url, headers=self.headers, params=params)

            if data:
                if "messages" in data:
                    for msg in data["messages"]:
                        msg_text = self.extract_message_text(msg)
                        complete_thread += msg_text + "\n"

                if data.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = data["response_metadata"]["next_cursor"]
                else:
                    break
        return complete_thread

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
            message_text = f"{user}:  {message['text']}"

        if "attachments" in message and message.get("subtype") == "bot_message":
            for i in message["attachments"]:
                message_text += "\n" + i["fallback"]
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
        data = self.slack_api_call(url, headers=self.headers, params=params)
        if data:
            if data.get("ok"):
                return data["permalink"]
            else:
                logging.error(f"Error in response: {data['error']}")
                return None
        else:
            logging.error(f"Failed to get permalink. Error: {data.text}")
            return None

    def dict_channel_ids(self) -> dict[str, str]:
        """
        Retrieve and return a dictionary mapping channel IDs to channel names from Slack.

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
            data = self.slack_api_call(url, headers=self.headers, params=params)
            if data:
                if data.get("ok"):
                    for channel in data["channels"]:
                        channels_dict[channel["id"]] = channel["name"]
                    if data.get("response_metadata", {}).get("next_cursor"):
                        params["cursor"] = data["response_metadata"]["next_cursor"]
                    else:
                        break
                else:
                    logging.error(f"Error in response: {data['error']}")
                    return None
            else:
                logging.error(f"Failed to list channels. Error: {data.text}")
                return None
        return channels_dict

    def add_embedding(
        self, embedding_model: OpenAIEmbeddings, chat_history: list[dict]
    ) -> list[dict]:
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

    def load_to_pinecone(self, complete_chat_history: list[dict]) -> int:
        """
        Load the complete chat history with embeddings into Pinecone.

        Args:
            embedding_dimension (int): The dimension of the embeddings.
            complete_chat_history (list): The complete chat history with embeddings.

        Returns
        -------
            int: The number of records loaded into Pinecone.
        """
        index, name = self.pinecone_helper.get_index(
            org=self.org_name,
            datasource="slack",
            environment=self.lorelai_settings["environment"],
            env_name=self.lorelai_settings["environment_slug"],
            version="v1",
            create_if_not_exists=True,
        )

        index.upsert(vectors=complete_chat_history)

        return len(complete_chat_history)

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
        members_data = self.slack_api_call(
            url="https://slack.com/api/conversations.members",
            headers=self.headers,
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
            logging.error(f"Failed to retrieve members for channel {channel_id}. \
                Error: {members_data['error'] if members_data else 'Unknown error'}")
            return []

        emails = []

        # Step 2: Loop through each user ID and get their email using users.info
        for user_id in user_ids:
            user_data = self.slack_api_call(
                url="https://slack.com/api/users.info",
                headers=self.headers,
                params={"user": user_id},
            )

            if user_data and "ok" in user_data and user_data["ok"] and "user" in user_data:
                user_info = user_data["user"]
                # Check if the user has an email field and add it to the list
                if "profile" in user_info and "email" in user_info["profile"]:
                    emails.append(user_info["profile"]["email"])
            else:
                logging.warning(f"Failed to retrieve user info for user ID {user_id}. \
                    Error: {user_data['error'] if user_data else 'Unknown error'}")

        return emails

    def chunk_and_merge_metadata(
        self, lst: list[dict], size: int, overlap_size: int, channel_id: str
    ) -> list[dict]:
        """
        Chunks a list of dictionaries and merges their metadata.

        Args:
            lst (list of dict): List of dictionaries, each containing 'id', 'values',
                                and 'metadata' fields. 'metadata' includes:
                                - text (str): A string to concatenate
                                - source (str): A source URL
                                - msg_ts (str): A timestamp
                                - channel_name (str): A channel name
                                - users (list): A list of users
            size (int): Number of items in each chunk.
            overlap_size (int): Number of overlapping items between chunks.
            channel_id (str): channel id, to get the members email for vector storage

        Returns
        -------
            list of dict: A list of new dictionaries with merged metadata:
                        - text: Concatenated text from the chunk
                        - source, msg_ts: Taken from the last item in the chunk
                        - channel_name, users: Unique sets converted to lists.

        Example:
            merged_chunks = chunk_and_merge_metadata(lst, size=2, overlap_size=1)
        """
        user_emails = self.get_channel_member_emails(channel_id)
        result = []
        start = 0

        while start < len(lst):
            end = start + size
            chunk = lst[start:end]

            # Initialize merged metadata fields
            merged_text = ""
            merged_channel_names = set()

            # Merge the metadata from all items in the chunk
            for item in chunk:
                merged_text += item["metadata"]["text"] + " "
                merged_channel_names.add(item["metadata"]["channel_name"])

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
                    "channel_name": list(merged_channel_names),  # Convert set to list
                    "users": list(user_emails),
                },
            }

            result.append(merged_dict)
            print("Metadata size:", sys.getsizeof(merged_dict["metadata"]))
            # Move the start index for the next chunk
            start += size - overlap_size

        return result

    def process_slack_message(self, channel_id: str | None = None) -> bool | None:
        """
        Process Slack messages, generate embeddings, and load them into Pinecone.

        Args:
            channel_id (str, optional): The ID of a specific Slack channel to process.
            Defaults to None.
        """
        try:
            # Setup embedding config:
            embedding_model_name = "text-embedding-ada-002"
            embedding_model = OpenAIEmbeddings(model=embedding_model_name)
            embedding_dimension = get_embedding_dimension(embedding_model_name)
            if embedding_dimension == -1:
                raise ValueError(
                    f"Could not find embedding dimension for model '{embedding_model}'"
                )

            # get the list of channels
            channel_ids_dict = self.dict_channel_ids()

            # this logic allows to process a single channel if passed as args
            if channel_id is not None:
                if channel_id in channel_ids_dict:
                    channel_ids_dict = {channel_id: channel_ids_dict[channel_id]}
                else:
                    logging.info(f"{channel_id} not in slack")
                    return None

            # Process each channel
            for channel_id, channel_name in channel_ids_dict.items():
                logging.info(f"Processing channel {channel_id} {channel_name}")

                # 1. get all messages from the channel
                channel_chat_history = self.get_messages(
                    channel_id=channel_id, channel_name=channel_name
                )
                #
                if not channel_chat_history:
                    logging.info(f"No messages found for channel {channel_id} {channel_name}")
                    continue

                # 2. divide the messages into chunks with overlap
                # TODO: check the size in bytes of the channel_chat_history
                messages = self.chunk_and_merge_metadata(
                    lst=channel_chat_history, size=5, overlap_size=2, channel_id=channel_id
                )

                # 3. Process in Batch to adhere to pinecone and OpenAI api size limit
                total_items = len(messages)
                logging.info(
                    f"Getting Embeds and Inserting to DB for {total_items} \
messages in batches"
                )

                for start_idx in range(0, total_items):
                    batch = []
                    batch_size_in_bytes = 0

                    # Create a batch while respecting the 40KB limit
                    while start_idx < total_items:
                        message = messages[start_idx]
                        message_size = sys.getsizeof(message)

                        # Check if the message itself exceeds the limit
                        if message_size > 10 * 1024:
                            logging.warning(f"Message {start_idx} >= 40KB and will be skipped.")
                            start_idx += 1
                            continue

                        # Check if adding this message exceeds the limit
                        if batch_size_in_bytes + message_size > 10 * 1024:  # 40KB limit
                            break

                        batch.append(message)
                        batch_size_in_bytes += message_size
                        start_idx += 1

                    logging.info(f"Batch size: {batch_size_in_bytes} bytes")

                    if batch:  # Only process if the batch is not empty
                        print("Batch Len: ", len(batch))
                        print("Size byte: ", sys.getsizeof(batch))
                        logging.info(f"Creating embds for {channel_id} {channel_name}")
                        # TODO: parameters ??!!
                        batch = self.add_embedding(embedding_model, batch)

                        logging.info(f"Loading to pinecone for channel {channel_id} {channel_name}")
                        try:
                            self.load_to_pinecone(batch)
                        except Exception as e:
                            print("failed to load to pinecone", e)
                            print(batch)

                        logging.info(f"Completed for channel {channel_id} {channel_name}")

            logging.info(
                f"Slack Indexer ran successfully for org {self.org_name}, by user {self.email}"
            )
            return True
        except Exception as e:
            raise e
