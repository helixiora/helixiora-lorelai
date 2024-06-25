import requests
from flask import request, redirect, url_for, session
from lorelai.utils import load_config, get_embedding_dimension, pinecone_index_name
from app.utils import get_db_connection
from pprint import pprint
import logging
import os
from langchain_openai import OpenAIEmbeddings
import pinecone
import uuid


class SlackOAuth:
    AUTH_URL = "https://slack.com/oauth/v2/authorize"
    TOKEN_URL = "https://slack.com/api/oauth.v2.access"
    SCOPES = "channels:history,channels:read,chat:write"

    def __init__(self):
        self.config = load_config("slack")
        self.client_id = self.config["client_id"]
        self.client_secret = self.config["client_secret"]
        self.redirect_uri = self.config["redirect_uri"]

    def get_auth_url(self):
        params = {
            "client_id": self.client_id,
            "scope": self.SCOPES,
            "redirect_uri": self.redirect_uri,
        }
        request_url = (
            requests.Request("GET", self.AUTH_URL, params=params).prepare().url
        )
        return request_url

    def get_access_token(self, code):
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
                print(access_token)
                return redirect(url_for("index"))
        return "Error", 400


class slack_indexer:

    def __init__(self, email, org_name) -> None:

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

        print(self.access_token)

    def retrive_access_token(self, email):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            sql_query = "SELECT slack_token FROM users WHERE email = %s;"
            cursor.execute(sql_query, (email,))
            result = cursor.fetchone()
            if result:
                slack_token = result[0]
                print("Slack Token:", slack_token)
                return slack_token

            print("No Slack token found for the specified email.")
            return None

    def get_userid_name(self):
        url = "https://slack.com/api/users.list"
        response = requests.get(url, headers=self.headers)
        if response.ok:
            users = response.json()["members"]
            users_dict = {}
            for i in users:
                users_dict[i["id"]] = i["name"]

            print(f"Loaded user_dict {users_dict}")
            return users_dict
        else:
            print(f"Failed to list users. Error: {response.text}")
            return None

    def replace_userid_with_name(self, thread_text):
        for user_id, user_name in self.userid_name_dict.items():
            thread_text = thread_text.replace(user_id, user_name)
        return thread_text

    def get_messages(self, channel_id, channel_name):

        url = "https://slack.com/api/conversations.history"
        """channel_id="C06FBKAN70A"
        channel_id="C06C64XTP2R"
        channel_name='engineering"""
        print(f"Getting Messages for Channel:{channel_name}")
        params = {"channel": channel_id}
        channel_chat_history = []
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            if response.ok:
                history = response.json()
                # print(history)
                # pprint(history['messages'][5])
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
                            print(metadata)
                            print("--------------------")

                        except Exception as e:
                            logging.fatal(msg)
                            raise (e)

                if history.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = history["response_metadata"]["next_cursor"]
                    print(f"Next Page cursor: {params['cursor']}")
                else:
                    break

            else:
                print("Failed to retrieve channel history. Error:", response.text)
        print("--------------")
        print(f"Total Messages in {channel_name}-{len(channel_chat_history)}")
        return channel_chat_history

    def get_thread(self, thread_id, channel_id):
        url = "https://slack.com/api/conversations.replies"
        params = {"channel": channel_id, "ts": thread_id, "limit": 200}
        print(f"Getting message of thread: {thread_id}")
        complete_thread = ""
        while True:
            response = requests.get(url, headers=self.headers, params=params)

            if response.ok:
                history = response.json()
                # pprint(history)
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
        this function extract msg body and text body of bot message
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
        url = "https://slack.com/api/chat.getPermalink"

        params = {"channel": channel_id, "message_ts": message_ts}
        response = requests.get(url, headers=self.headers, params=params)
        if response.ok:
            data = response.json()
            if data["ok"]:
                return data["permalink"]
            else:
                print("Error in response:", data["error"])
                return None
        else:
            print("Failed to get permalink. Error:", response.text)
            return None

    def dict_channel_ids(self):
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
                    print("Error in response:", data["error"])
                    return None
            else:
                print("Failed to list channels. Error:", response.text)
                return None
        return channels_dict

    def add_embedding(self, embedding_model, complete_chat_history):

        try:
            text = [chat["metadata"]["text"] for chat in complete_chat_history]
        except Exception as e:
            raise e

        embeds = embedding_model.embed_documents(text)
        if len(complete_chat_history) != len(embeds):
            raise ValueError("Embeds length and document length mismatch")

        # will delete one, 2 method does same thing
        for i in range(len(embeds)):
            complete_chat_history[i]["values"] = embeds[i]

        """for idx,chat in enumerate(complete_chat_history):
            chat['values']=embeds[idx]"""

        return complete_chat_history

    def load_to_pinecone(self, embedding_dimension, complete_chat_history):
        index_name = pinecone_index_name(
            org=self.org_name,
            datasource="slack",
            environment=self.lorelai_settings["environment"],
            env_name=self.lorelai_settings["environment_slug"],
            version="v1",
        )

        pc = pinecone.Pinecone(api_key=self.pinecone_settings["api_key"])

        if index_name not in pc.list_indexes().names():
            # Create a new index
            pc.create_index(
                name=index_name,
                dimension=embedding_dimension,
                metric="cosine",
                spec=pinecone.ServerlessSpec(
                    cloud="aws", region=self.pinecone_settings["region"]
                ),
            )
        pc_index = pc.Index(index_name)
        pc_index.upsert(complete_chat_history)
        return len(complete_chat_history)

    def process_slack_message(self, channel_id=None):
        channel_ids_dict = self.dict_channel_ids()
        complete_chat_history = []
        if channel_id is not None:
            if channel_id in channel_ids_dict:
                channel_ids_dict = {channel_id: channel_ids_dict[channel_id]}
            else:
                print(f"{channel_id} not in slack")
                return None

        for channel_id, channel_name in channel_ids_dict.items():
            print(f"Processing {channel_id} {channel_name}")
            complete_chat_history.extend(self.get_messages(channel_id, channel_name))
            #

        embedding_model_name = "text-embedding-ada-002"
        embedding_model = OpenAIEmbeddings(model=embedding_model_name)
        embedding_dimension = get_embedding_dimension(embedding_model_name)
        if embedding_dimension == -1:
            raise ValueError(
                f"Could not find embedding dimension for model '{embedding_model}'"
            )

        # Process in Batch
        batch_size = 200
        total_items = len(complete_chat_history)
        logging.info(
            f"Getting Embeds and Inserting to DB for {total_items} messages in batches of {batch_size}"
        )
        for start_idx in range(0, total_items, batch_size):
            end_idx = min(start_idx + batch_size, total_items)
            batch = complete_chat_history[start_idx:end_idx]
            batch = self.add_embedding(embedding_model, batch)
            self.load_to_pinecone(embedding_dimension, batch)


# 1715850407.699219
