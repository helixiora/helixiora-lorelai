import requests
from flask import request, redirect, url_for, session
from lorelai.utils import load_config
from app.utils import get_db_connection
from pprint import pprint
import logging

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
            "redirect_uri": self.redirect_uri
        }
        request_url = requests.Request('GET', self.AUTH_URL, params=params).prepare().url
        return request_url

    def get_access_token(self, code):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        response = requests.post(self.TOKEN_URL, data=payload)
        if response.status_code == 200:
            return response.json()['access_token']
        return None

    def auth_callback(self):
        code = request.args.get('code')
        access_token = self.get_access_token(code)
        if access_token:
            session['slack_access_token'] = access_token
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""UPDATE users 
                SET slack_token = %s
                WHERE email = %s""",
                (session["slack_access_token"], session["email"]))
                conn.commit()
                print(access_token)
                return redirect(url_for('index'))
        return "Error", 400
    

class slack_indexer:
    
    def __init__(self, email) -> None:
        self.email=email
        self.access_token=self.retrive_access_token(email)
        self.headers={
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        print(self.access_token)
    
    def retrive_access_token(self,email):
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
            users = response.json()['members']
            print(users[3])
            users_dict={}
            for i in users:
                users_dict[i['id']]=i['name']
            print(users_dict)
            return users_dict
        else:
            print("Failed to list users. Error:", response.text)
            return None
        
    def get_messages(self, channel_id,channel_name):
        
        url = "https://slack.com/api/conversations.history"
        channel_id="C06FBKAN70A"
        channel_id="C06C64XTP2R"
        channel_name='engineering'
        print(f"Getting Messages for Channel:{channel_name}")
        params = {
            "channel": channel_id
        }
        channel_chat_history=[]
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            if response.ok:
                history = response.json()
                #print(history)
                #pprint(history['messages'][5])
                if 'error' in history:
                    logging.warning(f"Error: {history['error']} - Channel: {channel_name} id: {channel_id} ")
                
                if 'messages' in history:
                    for msg in history['messages']:
                        try:
                            msg_ts=''
                            thread_text=''
                            metadata={}
                            
                            # if msg has no thread
                            if msg.get('reply_count') is None:
                                thread_text=self.extract_message_text(msg)
                                msg_ts=msg['ts']
                                
                            # get all thread msg 
                            elif 'reply_count' in msg:
                                thread_text=self.get_thread(msg['ts'], channel_id)
                                msg_ts=msg['ts']#thread_ts

                            msg_link=self.get_message_permalink(channel_id,msg_ts)
                            metadata={'text': thread_text, 'source': msg_link, 'msg_ts':msg_ts,'channel_name':channel_name,'users':[self.email]}
                            channel_chat_history.append({'values': [], 'metadata': metadata})
                            print(metadata)
                            print("--------------------")
                    
                        except Exception as e:
                            logging.fatal(msg)
                            raise(e)

                if history.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = history["response_metadata"]["next_cursor"]
                    print(f"Next Page cursor: {params['cursor']}")
                else:
                    break
                
            else:
                print("Failed to retrieve channel history. Error:", response.text)
        print('--------------')
        print(f"Total Messages {len(channel_chat_history)}")
        return channel_chat_history
            
            
    def get_thread(self, thread_id, channel_id):
        url = "https://slack.com/api/conversations.replies"
        params = {
            "channel": channel_id,
            "ts":thread_id,
            'limit':200
        }
        print(f"Getting message of thread: {thread_id}")
        complete_thread=''
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.ok:
                history = response.json()
                #pprint(history)
                if 'messages' in history:
                    for msg in history['messages']:
                        msg_text=self.extract_message_text(msg)
                        complete_thread+=msg_text + '\n'
                    
                if history.get("response_metadata", {}).get("next_cursor"):
                    params["cursor"] = history["response_metadata"]["next_cursor"]
                else:
                    break
        return complete_thread

    def extract_message_text(self, message):
        '''
        this function extract msg body and text body of bot message
        '''
        message_text=''
        user=''
        if 'user' in message:
            user=message['user']
            
        if 'text' in message:
            message_text=f"{user}:  {message['text']}"
            
        if 'attachments' in message and message.get('subtype') == 'bot_message':
            for i in message['attachments']:
                message_text += '\n' + i['fallback']
        return message_text


    def get_message_permalink(self, channel_id, message_ts):
        url = "https://slack.com/api/chat.getPermalink"

        params = {
            "channel": channel_id,
            "message_ts": message_ts
        }
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

    def list_channel_ids(self):
        url = "https://slack.com/api/conversations.list"
    
        params = {
            "types": "public_channel,private_channel",
            "limit": 1000  # Adjust the limit if needed
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
    
    def process_slack_message(self, channel_id=None):
        channel_ids=[]
        org_chat_list=[]
        if channel_id is None:
            channel_ids=self.list_channel_ids()

        else:
            channel_ids.append(channel_id)
        
        
        for channel_id in channel_ids:
            org_chat_list.extend(self.get_messages(channel_id))
            break
        
    
#1715850407.699219