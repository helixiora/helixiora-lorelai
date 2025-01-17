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

from app.schemas import (
    IndexingRunSchema,
    UserAuthSchema,
)

from app.helpers.datasources import DATASOURCE_SLACK
from app.helpers.slack import SlackHelper
from app.models import db
from app.models.indexing import IndexingRunItem
from app.models.datasource import Datasource


class SlackIndexer(Indexer):
    """Retrieves, processes, and loads Slack messages into Pinecone."""

    def _get_datasource(self) -> Datasource:
        """Get the datasource for this indexer."""
        return Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first()

    def __init__(self) -> None:
        """Initialize the SlackIndexer class."""
        logging.debug("SlackIndexer initialized")
        super().__init__()

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

        # Initialize datasource after base class initialization
        self.datasource = self._get_datasource()

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
        self, complete_chat_history: list[dict], indexing_run: IndexingRunSchema
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
            org_name=indexing_run.organisation.name,
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
        indexing_run: IndexingRunSchema,
        user_auths: list[UserAuthSchema],
    ) -> None:
        """Process Slack messages, generate embeddings, and load them into Pinecone."""
        if not user_auths or len(user_auths) == 0:
            logging.error(f"No Slack user auths found for user {indexing_run.user.email}")
            return

        try:
            slack = SlackHelper(indexing_run.user, indexing_run.organisation, user_auths)
        except ValueError as e:
            logging.error(f"Skipping Slack indexing for user {indexing_run.user.email} - {str(e)}")
            return
        except Exception as e:
            logging.error(f"Unexpected error initializing Slack helper: {str(e)}")
            return

        if not slack.test_slack_token:
            logging.critical("Slack token is invalid")
            raise ValueError("Slack token is invalid")

        # get the list of channels
        channels_dict = slack.get_accessible_channels(only_joined=True)

        if not channels_dict:
            logging.info("No channels found for the user")
            return

        # Process each channel
        for channel_id, channel_info in channels_dict.items():
            indexing_run_item = None  # Initialize outside try block
            try:
                indexing_run_item = IndexingRunItem(
                    indexing_run_id=indexing_run.id,
                    item_id=channel_id,
                    item_type="channel",
                    item_name=channel_info["name"],
                    item_url=channel_info["link"],
                    item_status="pending",
                )
                db.session.add(indexing_run_item)
                db.session.commit()

                # 1. get all messages from the channel
                channel_chat_history = slack.get_messages_from_channel(
                    channel_id=channel_id,
                    channel_name=channel_info["name"],
                    user_email=indexing_run.user.email,
                )

                if not channel_chat_history:
                    logging.info(
                        f"No messages found for channel {channel_id} {channel_info['name']}"
                    )
                    indexing_run_item.item_status = "completed"  # Mark as completed even if empty
                    indexing_run_item.item_error = "No messages found in channel"
                    db.session.commit()
                    continue

                # 2. divide the messages into chunks with overlap
                messages = slack.chunk_and_merge_metadata(
                    lst=channel_chat_history,
                    word_limit=1500,
                    word_overlap=600,
                    channel_id=channel_id,
                    channel_name=channel_info["name"],
                )

                # 3. Process in Batch to adhere to pinecone and OpenAI api size limit
                total_items = len(messages)
                batch_size = 1
                logging.info(
                    f"Getting Embeds and Inserting to DB for {total_items} messages in batches \
batch_size: {batch_size}, total messages: {total_items}"
                )

                # Process each batch
                for start_idx in range(0, total_items, batch_size):
                    end_idx = min(start_idx + batch_size, total_items)
                    batch = messages[start_idx:end_idx]

                    if batch:  # Only process if the batch is not empty
                        logging.info(f"processing batch {start_idx} to {end_idx} of {total_items} ")
                        logging.info("Creating embeds for batch for current batch")
                        batch = self.add_embedding(self.embedding_model_name, batch)

                        logging.info("Loading to pinecone for current batch")
                        try:
                            self.load_to_pinecone(batch, indexing_run)
                        except Exception as e:
                            logging.critical("failed to load to pinecone for current batch", e)

                        logging.info(f"Completed batch {start_idx} to {end_idx} of {total_items}")
                logging.info(
                    f"Completed indexing for channel {channel_info['name']} with channel_id \
{channel_id}"
                )

                # Update status after successful processing of THIS channel
                indexing_run_item.item_status = "completed"
                db.session.commit()

            except Exception as e:
                logging.error(
                    f"Error processing channel \
{channel_info['name'] if channel_info else channel_id}: {str(e)}"
                )
                if indexing_run_item:  # Only update if it was created
                    indexing_run_item.item_status = "failed"
                    indexing_run_item.item_error = str(e)
                    db.session.commit()
                continue  # Continue with next channel instead of raising

        logging.info(
            f"Slack Indexer ran successfully for org {indexing_run.organisation.name}, by user \
{indexing_run.user.email}"
        )
