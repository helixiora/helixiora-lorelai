#!/usr/bin/env python3

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import sqlite3
import json

# The scopes needed to read documents in Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
DATABASE = './userdb.sqlite'

# sqlite> PRAGMA table_info(user_tokens)
#    ...> ;
# 0|user_id|TEXT|0||1
# 1|access_token|TEXT|0||0
# 2|refresh_token|TEXT|0||0
# 3|expires_in|INTEGER|0||0
# 4|token_type|TEXT|0||0
# 5|scope|TEXT|0||0
# load tokens from sqlite
def load_tokens_from_sqlite():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_tokens where user_id = '115957235300401571807'")
    rows = cur.fetchall()
    conn.close()
    return rows 

def load_client_secrets():
    with open('client_secret.json') as f:
        return json.load(f)
    
def main():
    creds = None
    secrets = load_client_secrets()
    
    tokens = load_tokens_from_sqlite()
    if tokens:
        token = tokens[0]
        creds = Credentials(
            token[1],
            refresh_token=token[2],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=secrets['web']['client_id'],
            client_secret=secrets['web']['client_secret']
        )

    service = build('drive', 'v3', credentials=creds)

    # Call the Drive v3 API to list the documents in the root folder
    results = service.files().list(
        pageSize=10, fields="nextPageToken, files(id, name)", q="'root' in parents and mimeType='application/vnd.google-apps.document'").execute()
    items = results.get('files', [])

    if not items:
        print('No documents found.')
    else:
        print('Documents:')
        for item in items:
            print(u'{0} ({1})'.format(item['name'], item['id']))

if __name__ == '__main__':
    main()
