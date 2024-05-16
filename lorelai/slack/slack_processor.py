import requests
from flask import request, redirect, url_for, session
from lorelai.utils import load_config

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
            print(access_token,"FOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUNDFOUND")
            session['slack_access_token'] = access_token
            return redirect(url_for('index'))
        return "Error", 400