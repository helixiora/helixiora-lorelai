import requests
from flask import request, redirect, url_for, session
from lorelai.utils import load_config
from app.utils import get_db_connection
from pprint import pprint

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
        
    def get_messages(self:None):
        url = "https://slack.com/api/conversations.history"
        channel_id="C06FBKAN70A"
        params = {
            "channel": channel_id
        }
        response = requests.get(url, headers=self.headers, params=params)
        if response.ok:
            history = response.json()
            #print(history)
            print("*************")
            #pprint(history['messages'][1])
            thread_list=[]
            for msg in history['messages']:
                try:
                    if 'thread_ts' in msg and 'reply_count' in msg:
                        thread_chats=self.get_thread(msg['thread_ts'],channel_id)
                        thread_list.append(thread_chats)
                    elif 'text' in msg:
                        thread_list.append(msg['text'])
                except Exception as e:
                    pprint(msg)
                    raise(e)
                    
                
                
            #print( history['messages'])
        
        else:
            print("Failed to retrieve channel history. Error:", response.text)
            
    def get_thread(self, thread_id, channel_id):
        url = "https://slack.com/api/conversations.replies"
        params = {
            "channel": channel_id,
            "ts":thread_id
        }
        response = requests.get(url, headers=self.headers   , params=params)
        if response.ok:
            message_text=''
            history = response.json()
            #pprint(history)
            for i in history['messages']:
                user=''
                text=''
                if 'user' in i:
                    user=i['user']
                if 'text' in i:
                    text=i['text']
                if text=='':
                    continue
                message_text += f"{user}: {text}\n"
                print(f"{user}: {text}")
            return message_text
        return None
        
        

#1715850407.699219