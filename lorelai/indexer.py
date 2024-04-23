"""this file creates a class to process google drive documents using the google drive api, chunk
them using langchain and then index them in pinecone"""

import os
import sys
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# langchain_community.vectorstores.pinecone.Pinecone is deprecated
from googleapiclient.discovery import build

import lorelai.utils
from lorelai.processor import Processor

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# The scopes needed to read documents in Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
DATABASE = "./userdb.sqlite"


class Indexer:
    """This class is used to process the Google Drive documents and index them in Pinecone"""

    def __init__(self):
        self.google_creds = lorelai.utils.load_config("google")
        self.pinecone_creds = lorelai.utils.load_config("pinecone")
        self.settings = lorelai.utils.load_config("lorelai")

        os.environ["PINECONE_API_KEY"] = self.pinecone_creds["api_key"]

    def index_org_drive(self, org: list[Any], users: list[list[Any]]) -> None:
        """process the Google Drive documents for an organisation

        :param org: the organisation to process, a list of org details (org_id, name)
        :param users: the users to process, a list of user details (user_id, name, email, token,
            refresh_token)

        :return: None
        """
        # 1. Load the Google Drive credentials
        # build a credentials object from the google creds
        for user in users:
            self.index_user_drive(user, org)

    def index_user_drive(self, user: list[Any], org: list[Any]) -> None:
        """process the Google Drive documents for a user and index them in Pinecone

        :param user: the user to process, a list of user details (user_id, name, email, token,
            refresh_token)
        :param org: the organisation to process, a list of org details (org_id, name)

        :return: None
        """

        # 1. Load the Google Drive credentials
        if user:
            print(f"Processing user: {user} from org: {org}")
            refresh_token = user[4]

            credentials = Credentials.from_authorized_user_info(
                {
                    "refresh_token": refresh_token,
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": self.google_creds["client_id"],
                    "client_secret": self.google_creds["client_secret"],
                }
            )

            # see if the credentials work and refresh if expired
            if not credentials.valid:
                credentials.refresh(Request())
                print("Refreshed credentials")

        # 2. Get the Google Drive document IDs
        print(f"Getting Google Drive document IDs for user: {user[2]}")
        document_ids = self.get_google_docs_ids(credentials)

        # 3. Generate the index name we will use in Pinecone
        index_name = lorelai.utils.pinecone_index_name(
            org=org[1],
            datasource="googledrive",
            environment=self.settings["environment"],
            env_name=self.settings["environment_slug"],
            version="v1",
        )
        # 3.1 Pinecone only allows max 45 chars index names
        if len(index_name) > 45:
            sys.exit(f"{index_name} is longer than maximum allowed chars (45)")
        # 4. Get index statistics before starting the indexing process
        index_stats_before = lorelai.utils.get_index_stats(index_name)

        # 5. Process the Google Drive documents and index them in Pinecone
        print(f"Processing {len(document_ids)} documents for user: {user[2]}")
        pinecone_processor = Processor()
        pinecone_processor.google_docs_to_pinecone_docs(document_ids, credentials, org[1], user[2])

        # 6. Get index statistics after the indexing process
        print(f"Indexing complete for user: {user[2]}")
        index_stats_after = lorelai.utils.get_index_stats(index_name)

        # 7. Print the index statistics
        print("Index statistics before indexing vs after indexing:")
        lorelai.utils.print_index_stats_diff(index_stats_before, index_stats_after)

    def get_google_docs_ids(self, credentials) -> list[str]:
        """
        Retrieves all Google Docs document IDs from the user's Google Drive.

        :param credentials: Google-auth credentials object for the user
        :return: List of document IDs
        """
        # Build the Drive v3 API service object
        service = build("drive", "v3", credentials=credentials)

        # List to store all document IDs
        document_ids = []

        # Call the Drive v3 API to get the list of files. We don't use GoogleDriveLoader because
        # we only need the document IDs here.
        page_token = None
        while True:
            results = (
                service.files()
                .list(  # pylint: disable=no-member
                    q="mimeType='application/vnd.google-apps.document'",
                    pageSize=100,
                    fields="nextPageToken, files(id, name, parents, spaces)",
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                )
                .execute()
            )

            # Extract the files from the results
            items = results.get("files", [])

            # Iterate through the files and add their IDs to the document_ids list
            if not items:
                print("No files found.")
                break

            print(f"Found {len(items)} files")
            for item in items:
                print(f"Found file: {item['name']} with ID: {item['id']} ")
                document_ids.append(item["id"])

            # Go through all docs in pinecone and remove the ones that are not in the google drive
            # anymore
            # TODO: Implement this # pylint: disable=fixme

            # Check if there are more pages
            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return document_ids

class SlackIndexer:
    """This class handles the fetching and processing of Slack messages for indexing"""

    def __init__(self):
        self.slack_creds = lorelai.utils.load_config("slack")
        self.settings = lorelai.utils.load_config("lorelai")
        self.slack_client = WebClient(token=self.slack_creds["slack_token"])

    def fetch_and_index_slack_messages(self, org: list[Any]) -> None:
        """Fetch messages from all Slack channels and index them"""
        try:
            # Fetch all channels in the workspace
            channels_response = self.slack_client.conversations_list()
            all_channels = channels_response["channels"]

            for channel in all_channels:
                print(f"Processing channel: {channel['name']}")

                # Fetch messages from the channel
                messages = self._fetch_messages_from_channel(channel["id"])
                
                # Index messages
                self._index_messages(messages, channel["name"], org[1])

        except SlackApiError as e:
            print(f"Error fetching channels: {e.response['error']}")

    def _fetch_messages_from_channel(self, channel_id: str) -> list:
        """Fetch messages from a specific Slack channel by ID"""
        messages = []
        try:
            response = self.slack_client.conversations_history(channel=channel_id)
            messages.extend(response["messages"])

            while response["has_more"]:
                response = self.slack_client.conversations_history(channel=channel_id, cursor=response["response_metadata"]["next_cursor"])
                messages.extend(response["messages"])

        except SlackApiError as e:
            print(f"Error fetching messages from channel {channel_id}: {e.response['error']}")

        return messages

    def _index_messages(self, messages: list, channel_name: str, org_name: str):
        """Process and index messages in Pinecone or another database"""
        print(f"Indexing {len(messages)} messages from channel: {channel_name}")

        # Create a Pinecone index name
        index_name = lorelai.utils.pinecone_index_name(
            org=org_name,
            datasource="slack",
            environment=self.settings["environment"],
            env_name=self.settings["environment_slug"],
            version="v1",
        )

        # Process and index messages
        pinecone_processor = Processor()
        pinecone_processor.messages_to_pinecone_docs(messages, channel_name, org_name)

        print(f"Completed indexing for channel: {channel_name}")