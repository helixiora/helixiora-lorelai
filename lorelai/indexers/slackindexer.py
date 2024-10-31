"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    SlackIndexer: Handles Slack message indexing using Pinecone and OpenAI.
"""

import logging
import os
import copy
import openai

from flask import current_app

from lorelai.indexer import Indexer
from lorelai.pinecone import PineconeHelper
from lorelai.utils import get_size

from app.schemas import UserSchema, OrganisationSchema, UserAuthSchema
from rq import job

from app.helpers.datasources import DATASOURCE_SLACK
from app.helpers.slack import SlackHelper


class SlackIndexer(Indexer):
    """Retrieves, processes, and loads Slack messages into Pinecone."""

    def __init__(self) -> None:
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

        # setup embedding model
        self.embedding_model_name = current_app.config["EMBEDDINGS_MODEL"]
        self.embedding_model_dimension = current_app.config["EMBEDDINGS_DIMENSION"]
        if self.embedding_model_dimension == -1:
            raise ValueError(
                f"Could not find embedding dimension for model '{self.embedding_model_name}'"
            )

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

    def load_to_pinecone(
        self, complete_chat_history: list[dict], user: UserSchema, organisation: OrganisationSchema
    ) -> int:
        """
        Load the complete chat history with embeddings into Pinecone.

        Args:
            embedding_dimension (int): The dimension of the embeddings.
            complete_chat_history (list): The complete chat history with embeddings.
            user (UserSchema): The user to associate with the chat history.
            organisation (OrganisationSchema): The organisation to associate with the chat history.

        Returns
        -------
            int: The number of records loaded into Pinecone.
        """
        index, name = self.pinecone_helper.get_index(
            org_name=organisation.name,
            datasource=DATASOURCE_SLACK,
            environment=current_app.config["LORELAI_ENVIRONMENT"],
            env_name=current_app.config["LORELAI_ENVIRONMENT_SLUG"],
            version="v1",
            create_if_not_exists=True,
        )

        index.upsert(vectors=complete_chat_history)

        return len(complete_chat_history)

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
        slack = SlackHelper(user, organisation, user_auths)

        try:
            # get the list of channels
            channel_ids_dict = slack.get_accessible_channels()

            # Process each channel
            for channel_id, channel_name in channel_ids_dict.items():
                logging.info(f"Processing channel {channel_id} {channel_name}")

                # 1. get all messages from the channel
                channel_chat_history = slack.get_messages_from_channel(
                    channel_id=channel_id, channel_name=channel_name, user_email=user.email
                )

                if not channel_chat_history:
                    logging.info(f"No messages found for channel {channel_id} {channel_name}")
                    continue

                # 2. divide the messages into chunks with overlap
                # TODO: check the size in bytes of the channel_chat_history
                messages = slack.chunk_and_merge_metadata(
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
messages in batches batch_size: {batch_size}, total messages: {total_items}"
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
                            self.load_to_pinecone(batch, user, organisation)
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
