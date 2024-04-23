import logging
import os

import nltk
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from nltk.corpus import reuters


def download_nltk_reuters(extract_to: str):
    # Check if NLTK Reuters corpus is available, and download if not
    try:
        nltk.data.find("corpora/reuters.zip")
    except LookupError:
        logging.info("NLTK Reuters corpus not found, downloading...")
        nltk.download("reuters")

    # Ensure the target directory exists, create if not
    if not os.path.exists(extract_to):
        os.makedirs(extract_to)
        logging.info(f"Created directory '{extract_to}'")

    try:
        # Go through the Reuters corpus and download all files individually
        for category in reuters.categories():
            # Create category directory
            category_dir = os.path.join(extract_to, category)
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)
                logging.info(f"Created directory '{category_dir}'")

            # Download files
            filecount = len(reuters.fileids([category]))
            logging.info(f"Downloading files for category '{category}': {filecount} files")

            for fileid in reuters.fileids([category]):
                # Parse content
                content = reuters.raw(fileid)

                # Normalize fileid by removing the test/training directory
                normalized_fileid = os.path.join(category_dir, fileid.split("/")[-1])

                # Store data in category directories
                with open(normalized_fileid, "w") as file:
                    file.write(content)

    except Exception as e:
        logging.error(f"Failed to download NLTK Reuters corpus as JSON: {e}")
        return

    logging.info(f"Downloaded NLTK Reuters corpus to '{extract_to}' as JSON files")


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
