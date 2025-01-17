"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveIndexer: Handles Google Drive document indexing using Pinecone and OpenAI.
"""

import io
import logging

from flask import current_app
from google.auth.credentials import TokenState
from google.oauth2 import credentials
from googleapiclient.discovery import build
from langchain_core.documents import Document
from langchain_googledrive.document_loaders import GoogleDriveLoader
from sqlalchemy.exc import SQLAlchemyError

from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE
from app.helpers.googledrive import get_token_details
from app.models import db
from app.models.datasource import Datasource
from app.models.google_drive import GoogleDriveItem
from app.models.indexing import IndexingRun, IndexingRunItem

# from app.models import Datasource, GoogleDriveItem, IndexingRun, IndexingRunItem, db
from app.schemas import (
    GoogleDriveItemSchema,
    IndexingRunSchema,
    UserAuthSchema,
)
from lorelai.indexer import Indexer
from lorelai.processor import Processor

ALLOWED_ITEM_TYPES = ["document", "folder", "file"]


class GoogleDriveIndexer(Indexer):
    """Used to process the Google Drive documents and index them in Pinecone."""

    def _get_datasource(self) -> Datasource:
        """Get the datasource for this indexer."""
        return Datasource.query.filter_by(datasource_name=DATASOURCE_GOOGLE_DRIVE).first()

    def __init__(self) -> None:
        """Initialize the Google Drive indexer."""
        # Create string IO to capture log messages
        self.log_capture = io.StringIO()

        # Create custom handler that writes to our string buffer
        string_handler = logging.StreamHandler(self.log_capture)
        string_handler.setLevel(logging.INFO)  # Changed to INFO to capture all logs
        # formatter = logging.Formatter('%(levelname)s - %(asctime)s - %(message)s')
        # string_handler.setFormatter(formatter)

        # Capture all logs
        self.logger = logging.getLogger()
        self.logger.addHandler(string_handler)
        self.logger.setLevel(logging.INFO)

        logging.debug("GoogleDriveIndexer initialized")
        super().__init__()
        self.datasource = self._get_datasource()

    def get_captured_logs(self) -> str:
        """Get captured logs and clear the buffer."""
        logs = self.log_capture.getvalue()
        # Clear the buffer
        self.log_capture.truncate(0)
        self.log_capture.seek(0)
        return logs

    def __validate_input(self, indexing_run: IndexingRunSchema) -> IndexingRun:
        """Validate input parameters and get the database model.

        Returns the database model instance for the indexing run.
        """
        if not isinstance(indexing_run, IndexingRunSchema):
            raise TypeError(f"Expected IndexingRunSchema but got {type(indexing_run)}")

        logging.info(
            f"Indexing user: {indexing_run.user.email} from org: {indexing_run.organisation.name}"
        )

        # 2. Get the Google Drive document IDs
        logging.debug(f"Getting Google Drive document IDs for user: {indexing_run.user.email}")

        # Get the actual model instance from the database
        indexing_run_model = IndexingRun.query.get(indexing_run.id)
        if not indexing_run_model:
            raise ValueError(f"Could not find IndexingRun with id {indexing_run.id}")

        return indexing_run_model

    def __create_indexing_item(
        self, indexing_run_id: int, drive_item: GoogleDriveItemSchema
    ) -> IndexingRunItem:
        """Create an indexing run item for a drive item."""
        indexing_run_item = IndexingRunItem(
            indexing_run_id=indexing_run_id,
            item_id=drive_item.google_drive_id,
            item_type=drive_item.item_type,
            item_name=drive_item.item_name,
            item_url=drive_item.item_url if drive_item.item_url else "Original item has no URL",
            item_status="pending",
        )
        db.session.add(indexing_run_item)
        db.session.commit()
        return indexing_run_item

    def __create_credentials(
        self, access_token: str, refresh_token: str
    ) -> credentials.Credentials:
        """Create and validate Google credentials object."""
        credentials_object = credentials.Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=current_app.config["GOOGLE_CLIENT_ID"],
            client_secret=current_app.config["GOOGLE_CLIENT_SECRET"],
        )

        if credentials_object.token_state == TokenState.INVALID:
            raise ValueError("Credentials object is invalid")

        return credentials_object

    def __validate_credentials(
        self, credentials_object: credentials.Credentials, user_email: str
    ) -> None:
        """Test if the credentials are working by making a simple API call."""
        try:
            drive_service = build("drive", "v3", credentials=credentials_object)
            drive_service.files().list(pageSize=1).execute()
            logging.info(f"Google Drive credentials are valid and working for user: {user_email}")
        except Exception as e:
            raise ValueError(f"Failed to validate Google Drive credentials: {str(e)}") from e

    def __process_drive_items(
        self,
        user_id: int,
        indexing_run_model: IndexingRun,
        credentials_object: credentials.Credentials,
    ) -> list[dict]:
        """Process Google Drive items and create indexing run items."""
        # Get root items (directly selected by user)
        drive_items = GoogleDriveItem.query.filter_by(user_id=user_id)
        user_data = [GoogleDriveItemSchema.from_orm(data) for data in drive_items]

        documents = []
        for drive_item in user_data:
            try:
                indexing_run_item = self.__create_indexing_item(indexing_run_model.id, drive_item)
                # This is a root item (directly added by user), so parent_item_id is None
                indexing_run_item.parent_item_id = None
                db.session.commit()

                if drive_item.item_type not in ALLOWED_ITEM_TYPES:
                    indexing_run_item.item_status = "skipped"
                    indexing_run_item.item_error = f"Invalid item type: {drive_item.item_type}"
                    db.session.commit()
                    continue

                if drive_item.item_type == "folder":
                    documents_from_folder = self.__list_files_in_folder(
                        folder_id=drive_item.google_drive_id,
                        credentials_object=credentials_object,
                        indexing_run_model=indexing_run_model,
                        indexing_run_item_id=indexing_run_item.id,
                    )
                    logging.info(
                        f"Found folder {drive_item.item_name}, recursively loaded \
{len(documents_from_folder)} items"
                    )
                    # Add folder itself to documents list
                    documents.append(
                        {
                            "user_id": user_id,
                            "google_drive_id": drive_item.google_drive_id,
                            "item_type": "folder",
                            "item_name": drive_item.item_name,
                            "mime_type": "application/vnd.google-apps.folder",
                            "indexing_run_item_id": indexing_run_item.id,
                        }
                    )
                    # Add all files from folder to documents list
                    documents.extend(documents_from_folder)

                    # Update folder status
                    indexing_run_item.item_status = "completed"
                    indexing_run_item.item_error = (
                        f"Successfully processed folder with {len(documents_from_folder)} items"
                    )
                    db.session.commit()
                else:
                    documents.append(
                        {
                            "user_id": user_id,
                            "google_drive_id": drive_item.google_drive_id,
                            "item_type": drive_item.item_type,
                            "item_name": drive_item.item_name,
                            "mime_type": drive_item.mime_type,
                            "indexing_run_item_id": indexing_run_item.id,
                        }
                    )

            except Exception as e:
                logging.error(f"Error processing item {drive_item.item_name}: {str(e)}")
                if "indexing_run_item" in locals():
                    indexing_run_item.item_status = "failed"
                    indexing_run_item.item_error = str(e)
                    db.session.commit()

        return documents

    def __process_documents(
        self,
        documents: list[dict],
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> None:
        """Process documents and store them in Pinecone."""
        if not documents:
            logging.warn(f"No Google Drive documents found for user: {indexing_run.user.email}")
            return

        logging.info(
            f"Processing {len(documents)} Google documents for user: {indexing_run.user.email}"
        )

        # Convert documents to Langchain format and add metadata
        langchain_docs = self.google_docs_to_langchain_docs(
            documents=documents,
            credentials_object=credentials_object,
            indexing_run=indexing_run,
        )
        self.add_user_to_docs_metadata(langchain_docs, indexing_run)

        # Store in Pinecone
        pinecone_processor = Processor()
        pinecone_processor.store_docs_in_pinecone(langchain_docs, indexing_run=indexing_run)

        # Update indexing timestamps
        self.update_last_indexed_for_docs(documents, indexing_run)
        logging.info(f"Indexing Google Drive complete for user: {indexing_run.user.email}")

        """# Check for any warnings after processing
        warnings = self.get_captured_warnings()
        if warnings:
            # Update the indexing run item with any warnings
            indexing_run_item = IndexingRunItem.query.get(indexing_run_item_id)
            if indexing_run_item:
                indexing_run_item.item_error = warnings
                db.session.commit()"""

    def index_user(
        self,
        indexing_run: IndexingRunSchema,
        user_auths: list[UserAuthSchema],
    ) -> None:
        """Process the Google Drive documents for a user and index them in Pinecone."""
        try:
            # Validate input and get database model
            indexing_run_model = self.__validate_input(indexing_run=indexing_run)

            # Get authentication tokens
            google_drive_tokens = get_token_details(indexing_run.user.id)
            access_token = google_drive_tokens.access_token
            refresh_token = google_drive_tokens.refresh_token

            # Create and validate credentials
            credentials_object = self.__create_credentials(
                access_token=access_token, refresh_token=refresh_token
            )
            self.__validate_credentials(
                credentials_object=credentials_object,
                user_email=indexing_run.user.email,
            )

            # Process drive items
            documents = self.__process_drive_items(
                user_id=indexing_run.user.id,
                indexing_run_model=indexing_run_model,
                credentials_object=credentials_object,
            )

            # Process and store documents
            self.__process_documents(
                documents=documents,
                credentials_object=credentials_object,
                indexing_run=indexing_run,
            )

        except Exception as e:
            logging.error(f"Error processing Google Drive documents: {str(e)}")
            # Also capture any warnings that occurred during the error

            return

    def add_user_to_docs_metadata(
        self: None, langchain_docs: list[Document], indexing_run: IndexingRunSchema
    ) -> None:
        """Add the user to the documents.

        :param langchain_docs: the list of langchain documents to add the users to
        :param indexing_run: the indexing run to add the users to
        """
        if not isinstance(indexing_run, IndexingRunSchema):
            raise TypeError(f"Expected IndexingRunSchema but got {type(indexing_run)}")

        # go through all docs. For each doc, see if the user is already in the metadata. If not,
        # add the user to the metadata
        for loaded_doc in langchain_docs:
            logging.info(f"Checking metadata users for Google doc: {loaded_doc.metadata['title']}")

            # check if the user key is in the metadata
            if "users" not in loaded_doc.metadata:
                loaded_doc.metadata["users"] = []

            # check if the user is in the metadata
            if indexing_run.user.email not in loaded_doc.metadata["users"]:
                logging.info(
                    f"Adding user {indexing_run.user.email} to metadata.users for \
{loaded_doc.metadata['title']}"
                )
                loaded_doc.metadata["users"].append(indexing_run.user.email)

    def load_google_doc_from_file_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive file from a file ID.

        :param doc_google_drive_id: the Google Drive file ID
        :param credentials_object: the credentials object to use for Google Drive API
        :param indexing_run: the indexing run to add the users to

        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive file ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded {len(docs_loaded)} docs from file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_document_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive document from a document ID.

        :param doc_google_drive_id: the Google Drive document ID
        :param credentials_object: the credentials object to use for Google Drive API
        :param indexing_run: the indexing run to add the users to

        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive document ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(
            document_ids=[doc_google_drive_id], credentials=credentials_object
        )
        docs_loaded = loader.load()
        logging.info(f"Loaded {len(docs_loaded)} docs from document: {doc_google_drive_id}")
        return docs_loaded

    def __list_files_in_folder(
        self,
        folder_id: str,
        credentials_object: credentials.Credentials,
        indexing_run_model: IndexingRun,
        indexing_run_item_id: int,
        processed_folders: set[str] = None,
    ) -> list[dict]:
        """Recursively list all files in a Google Drive folder.

        :param folder_id: The ID of the folder to list files from
        :param credentials_object: Google Drive credentials
        :param indexing_run_model: The indexing run model instance
        :param indexing_run_item_id: ID of the indexing run item for the folder
        :param processed_folders: Set of folder IDs that have already been processed (to avoid
                cycles)

        :return: List of dictionaries containing file information
        """
        if processed_folders is None:
            processed_folders = set()
            logging.info(f"Starting recursive folder traversal from root folder: {folder_id}")

        if folder_id in processed_folders:
            logging.warning(
                f"Folder {folder_id} has already been processed, skipping to avoid cycles"
            )
            return []

        processed_folders.add(folder_id)
        logging.info(f"Processing folder {folder_id}")

        try:
            service = build("drive", "v3", credentials=credentials_object)
            results = []
            page_token = None

            while True:
                # List all files and folders in the current folder
                query = f"'{folder_id}' in parents and trashed = false"
                logging.debug(f"Querying Google Drive with: {query}")

                # Now do the regular query for all items
                response = (
                    service.files()
                    .list(
                        q=query,
                        spaces="drive",
                        fields="nextPageToken, files(id, name, mimeType, parents)",
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )

                items = response.get("files", [])
                logging.info(f"Found {len(items)} items in folder {folder_id}")
                logging.info(f"Raw response from Google Drive API: {response}")
                for item in items:
                    logging.info(
                        f"Item details - Name: {item['name']}, Type: {item['mimeType']}, ID: \
{item['id']}"
                    )
                    if item["mimeType"] == "application/vnd.google-apps.folder":
                        logging.info(f"Found subfolder: {item['name']} ({item['id']})")
                        # Create indexing run item for subfolder
                        subfolder_item = IndexingRunItem(
                            indexing_run_id=indexing_run_model.id,
                            item_id=item["id"],
                            item_type="folder",
                            item_name=item["name"],
                            item_url=f"https://drive.google.com/drive/folders/{item['id']}",
                            item_status="pending",
                            parent_item_id=indexing_run_item_id,  # Track parent folder
                        )
                        db.session.add(subfolder_item)
                        db.session.commit()

                        # Add the subfolder itself to results
                        folder = {
                            "user_id": indexing_run_model.user_id,
                            "google_drive_id": item["id"],
                            "item_type": "folder",
                            "item_name": item["name"],
                            "mime_type": item["mimeType"],
                            "indexing_run_item_id": subfolder_item.id,
                        }
                        results.append(folder)

                        # Recursively process subfolders
                        logging.info(
                            f"Starting recursive processing of subfolder: {item['name']} \
({item['id']})"
                        )
                        subfolder_items = self.__list_files_in_folder(
                            folder_id=item["id"],
                            credentials_object=credentials_object,
                            indexing_run_model=indexing_run_model,
                            indexing_run_item_id=subfolder_item.id,
                            processed_folders=processed_folders,
                        )
                        logging.info(
                            f"Finished processing subfolder {item['name']}, found \
{len(subfolder_items)} items"
                        )
                        results.extend(subfolder_items)

                        # Update subfolder status
                        subfolder_item.item_status = "completed"
                        subfolder_item.item_error = (
                            f"Successfully processed subfolder with {len(subfolder_items)} items"
                        )
                        db.session.commit()
                    else:
                        logging.info(f"Found file: {item['name']} ({item['id']})")
                        # Create indexing run item for file
                        file_item = IndexingRunItem(
                            indexing_run_id=indexing_run_model.id,
                            item_id=item["id"],
                            item_type="file",
                            item_name=item["name"],
                            item_url=f"https://drive.google.com/file/d/{item['id']}/view",
                            item_status="pending",
                            parent_item_id=indexing_run_item_id,  # Track parent folder
                        )
                        db.session.add(file_item)
                        db.session.commit()

                        # Add non-folder items to results
                        file = {
                            "user_id": indexing_run_model.user_id,
                            "google_drive_id": item["id"],
                            "item_type": "file",
                            "item_name": item["name"],
                            "mime_type": item["mimeType"],
                            "indexing_run_item_id": file_item.id,
                        }
                        results.append(file)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            logging.info(
                f"Completed processing folder {folder_id}, total items found: {len(results)}"
            )
            return results

        except Exception as e:
            logging.error(f"Error listing files in folder {folder_id}: {str(e)}")
            raise

    def load_google_doc_from_slides_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive slides from a slides ID.

        :param doc_google_drive_id: the Google Drive slides ID
        :param credentials_object: the credentials object to use for Google Drive API

        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive slides ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load_slides_from_id(doc_google_drive_id)
        logging.info(f"Loaded {len(docs_loaded)} slides from file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_sheets_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive sheets from a sheets ID.

        :param doc_google_drive_id: the Google Drive sheets ID
        :param credentials_object: the credentials object to use for Google Drive API

        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive sheets ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load_sheets_from_id(doc_google_drive_id)
        logging.info(f"Loaded {len(docs_loaded)} sheets from file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_pdf_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive PDF from a PDF ID.

        :param doc_google_drive_id: the Google Drive PDF ID
        :param credentials_object: the credentials object to use for Google Drive API

        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive PDF ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded {len(docs_loaded)} pages from PDF: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_text_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load text-based files (txt, csv, html, xml, json) from Google Drive.

        :param doc_google_drive_id: the Google Drive file ID
        :param credentials_object: the credentials object to use for Google Drive API
        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive text file ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded text content from file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_ms_office_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load Microsoft Office files from Google Drive.

        :param doc_google_drive_id: the Google Drive file ID
        :param credentials_object: the credentials object to use for Google Drive API
        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive MS Office file ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded content from MS Office file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_image_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load image files from Google Drive.

        Note: This requires OCR capabilities to extract text from images.

        :param doc_google_drive_id: the Google Drive file ID
        :param credentials_object: the credentials object to use for Google Drive API
        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive image file ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded content from image file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_media_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load media files (audio/video) from Google Drive.

        Note: This requires speech-to-text capabilities for meaningful text extraction.

        :param doc_google_drive_id: the Google Drive file ID
        :param credentials_object: the credentials object to use for Google Drive API
        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive media file ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded content from media file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_archive_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load archive files (zip, rar, tar, gz) from Google Drive.

        Note: This requires archive extraction capabilities.

        :param doc_google_drive_id: the Google Drive file ID
        :param credentials_object: the credentials object to use for Google Drive API
        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive archive file ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded content from archive file: {doc_google_drive_id}")
        return docs_loaded

    def google_docs_to_langchain_docs(
        self: None,
        documents: list[dict[str, any]],
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Process the Google Drive documents and divide them into pinecone compatible chunks."""
        docs: list[Document] = []
        for doc in documents:
            doc_google_drive_id = doc["google_drive_id"]
            doc_item_type = doc["item_type"]
            doc_mime_type = doc["mime_type"]
            indexing_run_item_id = doc["indexing_run_item_id"]

            try:
                if doc_item_type not in ALLOWED_ITEM_TYPES:
                    logging.error(
                        f"Invalid item type: {doc_item_type} for document ID: {doc_google_drive_id}"
                    )
                    raise ValueError(f"Invalid item type: {doc_item_type}")

                # Match on mime type categories
                match doc_mime_type:
                    # Google Workspace files
                    case "application/vnd.google-apps.presentation":
                        docs_loaded = self.load_google_doc_from_slides_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case "application/vnd.google-apps.spreadsheet":
                        docs_loaded = self.load_google_doc_from_sheets_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case "application/vnd.google-apps.document":
                        docs_loaded = self.load_google_doc_from_document_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case "application/vnd.google-apps.folder":
                        # Skip folders as they are already processed by __list_files_in_folder
                        logging.info(
                            f"Skipping folder {doc_google_drive_id} as its contents are already \
                                processed"
                        )
                        docs_loaded = []
                        # Mark the folder item as completed
                        indexing_run_item = IndexingRunItem.query.get(indexing_run_item_id)
                        if indexing_run_item:
                            indexing_run_item.item_status = "completed"
                            indexing_run_item.item_error = "Folder contents already processed"
                            db.session.commit()
                        continue

                    # Microsoft Office files
                    case mime if mime in [
                        "application/msword",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "application/vnd.ms-excel",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.ms-powerpoint",
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    ]:
                        docs_loaded = self.load_google_doc_from_ms_office_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )

                    # Text-based files
                    case mime if mime in [
                        "text/plain",
                        "text/csv",
                        "text/html",
                        "text/xml",
                        "application/json",
                        "application/xml",
                        "application/javascript",
                        "application/x-python-code",
                    ]:
                        docs_loaded = self.load_google_doc_from_text_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )

                    # Image files
                    case mime if mime in [
                        "image/jpeg",
                        "image/png",
                        "image/gif",
                        "image/bmp",
                        "image/svg+xml",
                        "image/tiff",
                    ]:
                        docs_loaded = self.load_google_doc_from_image_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )

                    # Audio/Video files
                    case mime if mime in [
                        "audio/mpeg",
                        "audio/wav",
                        "video/mp4",
                        "video/mpeg",
                        "video/quicktime",
                    ]:
                        docs_loaded = self.load_google_doc_from_media_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )

                    # Archive files
                    case mime if mime in [
                        "application/zip",
                        "application/x-rar-compressed",
                        "application/x-tar",
                        "application/gzip",
                    ]:
                        docs_loaded = self.load_google_doc_from_archive_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )

                    # PDF files
                    case "application/pdf":
                        docs_loaded = self.load_google_doc_from_pdf_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )

                    # Default fallback
                    case _:
                        match doc_item_type:
                            case "document":
                                docs_loaded = self.load_google_doc_from_file_id(
                                    doc_google_drive_id,
                                    credentials_object,
                                    indexing_run,
                                )
                            case "file":
                                docs_loaded = self.load_google_doc_from_file_id(
                                    doc_google_drive_id,
                                    credentials_object,
                                    indexing_run,
                                )
                            case _:
                                raise ValueError(f"Invalid item type: {doc_item_type}")

                if docs_loaded:
                    docs.extend(docs_loaded)
                    for loaded_doc in docs_loaded:
                        logging.info(
                            f"Loaded Google doc: {loaded_doc.metadata['title']} with ID: \
                                    {doc_google_drive_id}"
                        )
                    # Update status to completed after successful processing
                    indexing_run_item = IndexingRunItem.query.get(indexing_run_item_id)
                    if indexing_run_item:
                        indexing_run_item.item_status = "completed"
                        # docs_loaded is a list of langchain documents
                        # each document has a metadata field with a title
                        # we want: the number of langchain documents loaded
                        # plus the unique list of titles of the documents loaded
                        titles = list(
                            set([doc.metadata.get("title", "Untitled") for doc in docs_loaded])
                        )
                        # limit the titles to 20
                        if len(titles) > 20:
                            text = "First 20 titles: " + ", ".join(titles[:20]) + "..."
                        else:
                            text = ", ".join(titles)

                        indexing_run_item.item_error = (
                            f"Successfully loaded {len(titles)} files; {text}"
                        )
                        # Store the extracted text
                        page_contents = [doc.page_content for doc in docs_loaded]
                        indexing_run_item.item_extractedtext = "\n\n".join(page_contents)

                        db.session.commit()
                else:
                    logging.error(
                        f"Unable to load {doc_item_type} with ID: \
                            {doc_google_drive_id}"
                    )
                    # Update status to failed if no documents were loaded
                    indexing_run_item = IndexingRunItem.query.get(indexing_run_item_id)
                    if indexing_run_item:
                        indexing_run_item.item_status = "failed"
                        indexing_run_item.item_error = "[invalid type]: Document not skipped"
                        db.session.commit()

            except Exception as e:
                logging.error(f"Error processing document {doc_google_drive_id}: {str(e)}")
                # Update status to failed on exception
                indexing_run_item = IndexingRunItem.query.get(indexing_run_item_id)
                if indexing_run_item:
                    indexing_run_item.item_status = "failed"
                    indexing_run_item.item_error = str(e)
                    db.session.commit()
            # Add logs
            logs = self.get_captured_logs()
            if logs:
                if indexing_run_item.item_log:
                    indexing_run_item.item_log += "\n" + logs
                else:
                    indexing_run_item.item_log = logs
                db.session.commit()
        logging.debug(f"Total {len(docs)} Google docs loaded from Google Drive using langchain")
        return docs

    def update_last_indexed_for_docs(self, documents, indexing_run: IndexingRunSchema) -> None:
        """Update the last indexed timestamp for the documents in the database.

        :param documents: the documents to update
        """
        for doc in documents:
            doc_id = doc["google_drive_id"]
            logging.info(f"Updating last indexed timestamp for document: {doc_id}")

            try:
                google_drive_item = GoogleDriveItem.query.filter_by(google_drive_id=doc_id).first()
                if google_drive_item:
                    google_drive_item.last_indexed_at = db.func.now()
                    db.session.commit()
                else:
                    logging.warning(f"Document with ID {doc_id} not found in the database")
            except SQLAlchemyError as e:
                db.session.rollback()
                logging.error(f"Error updating last indexed timestamp for document {doc_id}: {e}")
            except Exception as e:
                logging.error(
                    f"Unexpected error updating last indexed timestamp for document {doc_id}: {e}"
                )
