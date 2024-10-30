"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackIndexer: Handles Slack message indexing using Pinecone and OpenAI.
"""

import logging
import os
import requests
import uuid
from datetime import datetime
import copy
import openai

from flask import current_app

from lorelai.indexer import Indexer
from lorelai.pinecone import PineconeHelper
from lorelai.utils import get_size, clean_text_for_vector

from app.schemas import UserSchema, OrganisationSchema, UserAuthSchema
from rq import job

from app.helpers.datasources import DATASOURCE_SLACK
from app.helpers.slack import SlackHelper


class SlackIndexer(Indexer):
    """Retrieves, processes, and loads Slack messages into Pinecone."""

    def __init__(self, email: str, org_name: str) -> None:
        """
        Initialize the SlackIndexer class with required parameters and API keys.

        Args:
            email (str): The user's email.
            org_name (str): The organisation name.
        """
        # load API keys
        os.environ["OPENAI_API_KEY"] = current_app.config["OPENAI_API_KEY"]

        # setup pinecone helper
        self.pinecone_helper = PineconeHelper()
        self.slack_helper = SlackHelper()

        # init class with required parameters
        self.email = email
        self.org_name = org_name

        # Config for slack api
        self.access_token = self.retrieve_access_token(email=email)
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        self.test_slack_token()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        # setup embedding model
        self.embedding_model_name = current_app.config["EMBEDDINGS_MODEL"]
        self.embedding_model_dimension = current_app.config["EMBEDDINGS_DIMENSION"]
        if self.embedding_model_dimension == -1:
            raise ValueError(
                f"Could not find embedding dimension for model '{self.embedding_model_name}'"
            )

        self.userid_name_dict = self.get_userid_name()

        logging.debug(f"Slack Access Token: {self.access_token}")

    def get_messages_from_channel(self, channel_id: str, channel_name: str) -> list[dict]:
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
            data = self.slack_api_call(url, params=params)
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

                            # get the permalink for the message
                            msg_link = self.get_message_permalink(channel_id, msg_ts)

                            # convert the timestamp to a date
                            msg_datetime = self.timestamp_to_date(msg_ts)

                            # Slack uses user_id not names
                            thread_text = self.replace_userid_with_name(thread_text)
                            # add datetime
                            thread_text = f"{str(msg_datetime)} : {thread_text}"
                            thread_text = clean_text_for_vector(thread_text)
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
            data = self.slack_api_call(url, params=params)

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

    def get_accessible_channels(self) -> dict[str, str]:
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
            data = self.slack_helper.slack_api_call(url, params=params)
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
        self, embedding_model_name: str, messages_dict_list: list[dict]
    ) -> list[dict]:
        """
        Add embeddings to the dict_list using the specified embedding model.

        Args:
            embedding_model_name (str): The embedding model name.
            messages_dict_list (list): list of messages dict without vector.

        Returns
        -------
            list: The chat history with embeddings added.

        Raises
        ------
            Exception: If there is an error during embedding.
            ValueError: If the length of embeddings and dict_list do not match.
        """
        new_messages_dict_list = copy.deepcopy(messages_dict_list)
        try:
            text = [chat["metadata"]["text"] for chat in messages_dict_list]
        except Exception as e:
            raise e

        response = openai.embeddings.create(input=text, model=embedding_model_name)
        response_data = response.data
        embeds = [i.embedding for i in response_data]  # list of vector

        if len(new_messages_dict_list) != len(embeds):
            raise ValueError("Embeds length and document length mismatch")

        for i in range(len(embeds)):
            new_messages_dict_list[i]["values"] = embeds[i]
        return new_messages_dict_list

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
            datasource=DATASOURCE_SLACK,
            environment=current_app.config["LORELAI_ENVIRONMENT"],
            env_name=current_app.config["LORELAI_ENVIRONMENT_SLUG"],
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
        up to `word_limit` words. Additionally, the function ensures there is an overlap of
        `word_overlap` words between consecutive chunks.


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

        while start < len(lst):
            chunk = []
            word_count = len(overlap_words)  # Start with overlap word count

            # Collect items into a chunk until the word limit is reached
            while start < len(lst) and word_count < word_limit:
                item = lst[start]
                chunk.append(item)

                # Count words in the current item's metadata['text']
                word_count += len(item["metadata"]["text"].split())

                start += 1

            # Initialize merged metadata fields
            merged_text = " ".join(overlap_words) + " " if overlap_words else ""

            # Merge the metadata from all items in the chunk
            for item in chunk:
                logging.debug(f'length of chunk {len(item["metadata"]["text"])}')
                logging.debug(f'words in chunk {len(item["metadata"]["text"].split())}')
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

            logging.debug(f"how many message added: {len(chunk)}")
            logging.debug(f"length of merged text: {len(merged_text)}")
            # Calculate overlap for the next chunk based on word_overlap
            if word_overlap > 0:
                words_in_current_chunk = merged_text.split()
                overlap_words = words_in_current_chunk[
                    -word_overlap:
                ]  # Get the last 'word_overlap' words

        return result

    def index_user(
        self,
        user: UserSchema,
        organisation: OrganisationSchema,
        user_auths: list[UserAuthSchema],
        job: job.Job,
    ) -> bool | None:
        """
        Process Slack messages, generate embeddings, and load them into Pinecone.

        Args:
            channel_id (str, optional): The ID of a specific Slack channel to process.
            Defaults to None.
        """
        try:
            # get the list of channels
            channel_ids_dict = self.get_accessible_channels()

            # Process each channel
            for channel_id, channel_name in channel_ids_dict.items():
                logging.info(f"Processing channel {channel_id} {channel_name}")

                # 1. get all messages from the channel
                channel_chat_history = self.get_messages_from_channel(
                    channel_id=channel_id, channel_name=channel_name
                )
                #
                if not channel_chat_history:
                    logging.info(f"No messages found for channel {channel_id} {channel_name}")
                    continue

                # 2. divide the messages into chunks with overlap
                # TODO: check the size in bytes of the channel_chat_history
                messages = self.chunk_and_merge_metadata(
                    lst=channel_chat_history,
                    word_limit=3000,
                    word_overlap=1000,
                    channel_id=channel_id,
                    channel_name=channel_name,
                )

                # 3. Process in Batch to adhere to pinecone and OpenAI api size limit
                total_items = len(messages)
                # Process in Batch
                batch_size = 1
                total_items = len(messages)
                logging.info(
                    f"Getting Embeds and Inserting to DB for {total_items} \
                            messages in batches batch_size: {batch_size}, total messages: {total_items}"  # noqa: E501
                )

                # now doing without size as just batch with 1 element
                # TODO find accurate size then do size
                for start_idx in range(0, total_items, batch_size):
                    end_idx = min(start_idx + batch_size, total_items)
                    batch = messages[start_idx:end_idx]

                    if batch:  # Only process if the batch is not empty
                        logging.info(f"processing batch {start_idx} to {end_idx} of {total_items} ")
                        logging.info("Creating embeds for batch for current batch")

                        # TODO: parameters ??!!
                        batch = self.add_embedding(self.embedding_model_name, batch)

                        logging.debug(f"size of metadata: {get_size(batch[0]['metadata'])}")
                        logging.debug(
                            f"size of metadata text: {get_size(batch[0]['metadata']['text'])}"
                        )
                        logging.debug(
                            f"size of metadata text length: {len(batch[0]['metadata']['text'])}"
                        )

                        logging.debug(
                            f"number of words in text: {len(batch[0]['metadata']['text'].split())}"
                        )
                        logging.debug(
                            f"size of metadata: msg_ts {get_size(batch[0]['metadata']['msg_ts'])}"
                        )
                        logging.debug(
                            f"size of metadata source: {get_size(batch[0]['metadata']['source'])}"
                        )
                        logging.debug(
                            f"size of metadata channel_name: {get_size(batch[0]['metadata']['channel_name'])}"  # noqa: E501
                        )
                        logging.debug(
                            f"size of metadata users: {get_size(batch[0]['metadata']['users'])}"
                        )

                        logging.info("Loading to pinecone for current batch")
                        try:
                            self.load_to_pinecone(batch)
                        except Exception as e:
                            logging.critical("failed to load to pinecone for current batch", e)

                        logging.info(f"Completed batch {start_idx} to {end_idx} of {total_items}")
                logging.info(
                    f"Completed indexing for channel {channel_name} with channel_id {channel_id}"
                )
            logging.info(
                f"Slack Indexer ran successfully for org {self.org_name}, by user {self.email}"
            )
            return True
        except Exception as e:
            raise e
