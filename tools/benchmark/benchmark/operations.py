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
    logging.info(f"Authenticating with Google Drive using credentials file '{credentials_path}'")

    if not os.path.exists(credentials_path):
        logging.error(f"Credentials file not found: {credentials_path}")
        raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
    if not credentials_path.endswith(".json"):
        logging.error("Credentials file must be in JSON format")
        raise ValueError("Credentials file must be in JSON format")

    scopes = ["https://www.googleapis.com/auth/drive"]
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path, scopes, redirect_uri="http://localhost:54364"
        )
        creds = flow.run_local_server(port=54364)
        service = build("drive", "v3", credentials=creds)
        return service
    except Exception as e:
        logging.error(f"Failed to create Google Drive service: {e}")
        raise


def find_or_create_folder(service, folder_name):
    logging.info(f"Finding or creating Google Drive folder '{folder_name}'")
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}'"
    response = service.files().list(q=query).execute()
    folders = response.get("files", [])
    if not folders:
        folder_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        folder = service.files().create(body=folder_metadata, fields="id").execute()
        return folder.get("id")
    logging.info(f"Found Google Drive folder '{folder_name}' with ID '{folders[0]['id']}'")
    return folders[0]["id"]


def file_exists(service, name, folder_id):
    """
    Check if a file or folder already exists in the specified folder on Google Drive.

    Args:
        service: Google Drive service object
        name: Name of the file or folder to check
        folder_id: ID of the folder where to look for the file or folder

    Returns:
        The ID of the existing file or folder if found, otherwise None.
    """
    logging.info(f"Checking if file '{name}' exists in Google Drive folder '{folder_id}'")
    query = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
    response = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    files = response.get("files", [])
    if files:
        return files[0]["id"]
    return None


def upload_files(service, folder_id, directory):
    """
    Recursively upload files from a directory to Google Drive, checking for existing files/folders.

    Args:
        service: Google Drive service object
        folder_id: Google Drive folder ID
        directory: Path to the directory containing files to upload
    """
    logging.info(f"Uploading contents of '{directory}' to Google Drive folder '{folder_id}'")

    for item in os.listdir(directory):
        file_path = os.path.join(directory, item)
        if os.path.isfile(file_path):
            with open(file_path, "r") as f:
                first_line = f.readline().strip()
                first_line = first_line.replace("'", "\\'")
            file_name = first_line if first_line else item
            if not file_exists(service, file_name, folder_id):
                logging.info(f"Uploading file '{file_name}'")
                file_metadata = {"name": file_name, "parents": [folder_id]}
                mime_type = "text/plain"  # Default MIME type for conversion
                media = MediaFileUpload(file_path, mimetype=mime_type)
                service.files().create(
                    body=file_metadata, media_body=media, fields="id", supportsAllDrives=True
                ).execute()
            else:
                logging.info(f"File '{file_name}' already exists in folder '{folder_id}'")

        elif os.path.isdir(file_path):
            if not (folder_id := file_exists(service, item, folder_id)):
                logging.info(f"Creating directory '{item}' in Google Drive")
                folder_metadata = {
                    "name": item,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [folder_id],
                }
                folder = (
                    service.files()
                    .create(body=folder_metadata, fields="id", supportsAllDrives=True)
                    .execute()
                )
                folder_id = folder.get("id")
            upload_files(service, folder_id, file_path)
