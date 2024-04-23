import os
import tarfile

import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def download_and_extract(url, save_path, extract_to):
    response = requests.get(url)
    with open(save_path, "wb") as f:
        f.write(response.content)
    with tarfile.open(save_path, "r:gz") as tar:
        tar.extractall(path=extract_to)


def google_drive_auth(credentials_path):
    scopes = ["https://www.googleapis.com/auth/drive"]
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
    creds = flow.run_local_server(port=0)
    service = build("drive", "v3", credentials=creds)
    return service


def find_or_create_folder(service, folder_name):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}'"
    response = service.files().list(q=query).execute()
    folders = response.get("files", [])
    if not folders:
        folder_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        folder = service.files().create(body=folder_metadata, fields="id").execute()
        return folder.get("id")
    return folders[0]["id"]


def upload_files(service, folder_id, directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaFileUpload(file_path, mimetype="text/plain")
        service.files().create(body=file_metadata, media_body=media, fields="id").execute()
