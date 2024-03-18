#!/usr/bin/env python3

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os.path

# The scopes needed to read documents in Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

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
