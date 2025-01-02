"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveIndexer: Handles Google Drive document indexing using Pinecone and OpenAI.
"""

import logging
from flask import current_app

from google.oauth2 import credentials
from googleapiclient.discovery import build
from google.auth.credentials import TokenState
from lorelai.indexer import Indexer
from lorelai.processor import Processor
from sqlalchemy.exc import SQLAlchemyError
from langchain_googledrive.document_loaders import GoogleDriveLoader
from langchain_core.documents import Document
from app.models import db, GoogleDriveItem, IndexingRunItem, IndexingRun
from app.schemas import (
    IndexingRunSchema,
    UserAuthSchema,
    GoogleDriveItemSchema,
)
from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE
from app.models import Datasource

ALLOWED_ITEM_TYPES = ["document", "folder", "file"]


class GoogleDriveIndexer(Indexer):
    """Used to process the Google Drive documents and index them in Pinecone."""

    def get_datasource(self) -> Datasource:
        """Get the datasource for this indexer."""
        return Datasource.query.filter_by(datasource_name=DATASOURCE_GOOGLE_DRIVE).first()

    def __get_token_details(self, user_auths: list[UserAuthSchema]) -> tuple[str, str, str]:
        access_token = next(
            (
                user_auth.auth_value
                for user_auth in user_auths
                if user_auth.auth_key == "access_token"
            ),
            None,
        )

        refresh_token = next(
            (
                user_auth.auth_value
                for user_auth in user_auths
                if user_auth.auth_key == "refresh_token"
            ),
            None,
        )

        expires_at = next(
            (
                user_auth.auth_value
                for user_auth in user_auths
                if user_auth.auth_key == "expires_at"
            ),
            None,
        )

        if not access_token or not refresh_token:
            raise ValueError("Missing Google Drive authentication tokens for user")

        return access_token, refresh_token, expires_at

    def __init__(self) -> None:
        logging.debug("GoogleDriveIndexer initialized")

    def index_user(
        self,
        indexing_run: IndexingRunSchema,
        user_auths: list[UserAuthSchema],
    ) -> None:
        """Process the Google Drive documents for a user and index them in Pinecone.

        Arguments
        ---------
        indexing_run: IndexingRunSchema
            The indexing run to process.
        user_auths: list[UserAuthSchema]
            The user auth rows for the user.

        Returns
        -------
        None
        """
        if not isinstance(indexing_run, IndexingRunSchema):
            raise TypeError(f"Expected IndexingRunSchema but got {type(indexing_run)}")

        logging.info(
            f"Indexing user: {indexing_run.user.email} from org: {indexing_run.organisation.name}"
        )

        # 1. Get the Google Drive access token, refresh token, and expiry
        access_token, refresh_token, expires_at = self.__get_token_details(user_auths)

        # 2. Get the Google Drive document IDs
        logging.debug(f"Getting Google Drive document IDs for user: {indexing_run.user.email}")

        # Get the actual model instance from the database
        indexing_run_model = IndexingRun.query.get(indexing_run.id)
        if not indexing_run_model:
            raise ValueError(f"Could not find IndexingRun with id {indexing_run.id}")

        drive_items = GoogleDriveItem.query.filter_by(user_id=indexing_run.user.id)
        user_data = [GoogleDriveItemSchema.from_orm(data) for data in drive_items]

        # 3. Check if there are any Google Drive documents for the user
        documents = []
        for drive_item in user_data:
            indexing_run_item = None
            try:
                # Create indexing run item
                indexing_run_item = IndexingRunItem(
                    indexing_run_id=indexing_run_model.id,
                    item_id=drive_item.google_drive_id,
                    item_type=drive_item.item_type,
                    item_name=drive_item.item_name,
                    item_url=drive_item.item_url
                    if drive_item.item_url
                    else "Original item has no URL",
                    item_status="pending",
                )
                db.session.add(indexing_run_item)
                db.session.commit()

                # Process the item...
                if drive_item.item_type not in ALLOWED_ITEM_TYPES:
                    indexing_run_item.item_status = "skipped"
                    indexing_run_item.item_error = f"Invalid item type: {drive_item.item_type}"
                    db.session.commit()
                    continue

                # Add to documents list for processing
                documents.append(
                    {
                        "user_id": indexing_run.user.id,
                        "google_drive_id": drive_item.google_drive_id,
                        "item_type": drive_item.item_type,
                        "item_name": drive_item.item_name,
                        "mime_type": drive_item.mime_type,
                        "indexing_run_item_id": indexing_run_item.id,
                    }
                )

            except Exception as e:
                if indexing_run_item:
                    indexing_run_item.item_status = "failed"
                    indexing_run_item.item_error = str(e)
                    db.session.commit()
                logging.error(f"Error processing item {drive_item.item_name}: {str(e)}")
                continue

        if not documents or len(documents) == 0:
            logging.warn(f"No Google Drive documents found for user: {indexing_run.user.email}")
            return True

        # 5. Process the Google Drive documents and index them in Pinecone
        logging.info(
            f"Processing {len(documents)} Google documents for user: {indexing_run.user.email}"
        )

        try:
            # create a credentials object
            credentials_object = credentials.Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=current_app.config["GOOGLE_CLIENT_ID"],
                client_secret=current_app.config["GOOGLE_CLIENT_SECRET"],
            )

            # test the credentials object
            if credentials_object.token_state == TokenState.INVALID:
                logging.error("Credentials object is invalid")
                return False
            else:
                logging.info("Credentials object state: %s", credentials_object.token_state)

                # Perform a simple API operation to ensure the credentials are working
                try:
                    drive_service = build("drive", "v3", credentials=credentials_object)
                    drive_service.files().list(pageSize=1).execute()
                    logging.info(
                        f"Google Drive credentials are valid and working for user: \
{indexing_run.user.email}"
                    )
                except Exception as e:
                    logging.error(
                        f"Failed to validate Google Drive credentials for user: \
{indexing_run.user.email} with a simple API call: {e}"
                    )
                    return False

            # convert the documents to langchain documents
            langchain_docs = self.google_docs_to_langchain_docs(
                documents=documents,
                credentials_object=credentials_object,
                indexing_run=indexing_run,
            )

            # add the user for whom were indexing the docs to the documents' metadata
            self.add_user_to_docs_metadata(langchain_docs, indexing_run)

            pinecone_processor = Processor()

            # store the documents in Pinecone
            pinecone_processor.store_docs_in_pinecone(
                langchain_docs,
                indexing_run=indexing_run,
            )

            self.update_last_indexed_for_docs(documents, indexing_run)
            logging.info(f"Indexing Google Drive complete for user: {indexing_run.user.email}")

            return True

        except Exception as e:
            logging.error(f"Error processing Google Drive documents: {str(e)}")
            return

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

    def load_google_doc_from_folder_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive folder from a folder ID.

        :param doc_google_drive_id: the Google Drive folder ID
        :param credentials_object: the credentials object to use for Google Drive API
        :param indexing_run: the indexing run to add the users to

        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive folder ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(
            folder_id=doc_google_drive_id,
            recursive=True,
            include_folders=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
            credentials=credentials_object,
        )
        docs_loaded = loader.load()
        logging.info(f"Loaded {len(docs_loaded)} docs from folder: {doc_google_drive_id}")
        return docs_loaded

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
                        docs_loaded = self.load_google_doc_from_folder_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )

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
                                    doc_google_drive_id, credentials_object, indexing_run
                                )
                            case "folder":
                                docs_loaded = self.load_google_doc_from_folder_id(
                                    doc_google_drive_id, credentials_object, indexing_run
                                )
                            case "file":
                                docs_loaded = self.load_google_doc_from_file_id(
                                    doc_google_drive_id, credentials_object, indexing_run
                                )
                            case _:
                                raise ValueError(f"Invalid item type: {doc_item_type}")

                if docs_loaded and len(docs_loaded) > 0:
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
                        db.session.commit()
                else:
                    logging.error(
                        f"No documents loaded from Google Drive {doc_item_type} with ID: \
{doc_google_drive_id}"
                    )
                    # Update status to failed if no documents were loaded
                    indexing_run_item = IndexingRunItem.query.get(indexing_run_item_id)
                    if indexing_run_item:
                        indexing_run_item.item_status = "failed"
                        indexing_run_item.item_error = "No documents loaded from Google Drive"
                        db.session.commit()

            except Exception as e:
                logging.error(f"Error processing document {doc_google_drive_id}: {str(e)}")
                # Update status to failed on exception
                indexing_run_item = IndexingRunItem.query.get(indexing_run_item_id)
                if indexing_run_item:
                    indexing_run_item.item_status = "failed"
                    indexing_run_item.item_error = str(e)
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
