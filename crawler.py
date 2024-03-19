#!/usr/bin/env python3

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import sqlite3
import json
import os
from pathlib import Path
import lorelai_pinecone
import tempfile

# The scopes needed to read documents in Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
DATABASE = './userdb.sqlite'

# load openai creds from file
def load_openai_creds():
    with open('settings.json') as f:
        return json.load(f)['openai']

# load pinecone creds from file 
def load_pinecone_creds():
    with open('settings.json') as f:
        return json.load(f)['pinecone']

# load tokens from sqlite
def load_tokens_from_sqlite():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_tokens where user_id = '115957235300401571807'")
    rows = cur.fetchall()
    conn.close()
    return rows 

def load_google_creds_to_tempfile():
  
    with open('settings.json') as f:
        secrets = json.load(f)['google']

    tokens = load_tokens_from_sqlite()

    if tokens:
        token = tokens[0]
        refresh_token = token[2]
        token_uri = "https://oauth2.googleapis.com/token"
        client_id = secrets['client_id']
        client_secret = secrets['client_secret']
        
        print(f"Token Info: {token} Refresh Token: {refresh_token} Token URI: {token_uri} Client ID: {client_id} Client Secret: {client_secret}")
        
        # create a file: Path.home() / ".credentials" / "token.json" to store the credentials so they can be loaded by GoogleDriveLoader's auth process (this uses Credentials.from_authorized_user_file)        
        if not os.path.exists(Path.home() / ".credentials"):
            os.makedirs(Path.home() / ".credentials")
            
        with open(Path.home() / ".credentials" / "token.json", 'w') as f:
            f.write(json.dumps({
                "refresh_token": refresh_token,
                "token_uri": token_uri,
                "client_id": client_id,
                "client_secret": client_secret
            }))
            f.close()
    else:
        print("No tokens found in sqlite")

    
def main():
    load_google_creds_to_tempfile()
    
    pinecone_creds = load_pinecone_creds()
    
    openai_creds = load_openai_creds()
        
    # Make sure to replace 'your_pinecone_api_key', 'your_environment', and 'your_index_name'
    # with your actual Pinecone API key, environment, and index name.
    processor = lorelai_pinecone.GoogleDriveProcessor(pinecone_api_key=pinecone_creds['api-key'], 
                                                      pinecone_environment=pinecone_creds['environment'], 
                                                      pinecone_index_name=pinecone_creds['index-name'],
                                                      openai_api_key=openai_creds['api-key'])
    processor.processDrive()

if __name__ == '__main__':
    main()
