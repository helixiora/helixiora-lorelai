"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveIndexer: Handles Google Drive document indexing using Pinecone and OpenAI.
"""

import io
import logging
from typing import Any
from datetime import datetime

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

from app.schemas import (
    GoogleDriveItemSchema,
    IndexingRunSchema,
    UserAuthSchema,
)
from lorelai.indexer import Indexer
from lorelai.processor import Processor
from lorelai.processors import process_file, ProcessorConfig, ProcessorStatus
from lorelai.processors.errors import ProcessorError, ProcessorErrorCode

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

        # Initialize service as None
        self._service = None

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

    def _handle_google_drive_error(
        self,
        error: Exception,
        doc_google_drive_id: str,
        indexing_run: IndexingRunSchema,
        file_type: str = "file",
    ) -> bool:
        """Handle Google Drive API errors consistently with error codes."""
        error_str = str(error)
        processor_error: ProcessorError | None = None

        if "File not found" in error_str:
            processor_error = ProcessorError(
                code=ProcessorErrorCode.FILE_NOT_FOUND,
                message=f"{file_type.capitalize()} no longer exists or access lost",
                details=error_str,
                item_id=doc_google_drive_id,
            )
        elif "insufficient permissions" in error_str.lower():
            processor_error = ProcessorError(
                code=ProcessorErrorCode.INSUFFICIENT_PERMISSIONS,
                message=f"Insufficient permissions to access {file_type}",
                details=error_str,
                item_id=doc_google_drive_id,
            )

        if processor_error:
            logging.error(str(processor_error))
            # Find and update the indexing run item
            indexing_run_item = IndexingRunItem.query.filter_by(
                indexing_run_id=indexing_run.id, item_id=doc_google_drive_id
            ).first()
            if indexing_run_item:
                self._update_indexing_run_item(
                    indexing_run_item.id,
                    "failed",
                    f"[{processor_error.code.name}] {processor_error.message}",
                )
            return True
        return False

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
        logging.info(f"Loading generic file from Google Drive, ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        langchain_docs = loader.load()
        logging.info(f"Converted Google Drive file into {len(langchain_docs)} Langchain documents")
        return langchain_docs

    def load_google_doc_from_document_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive document from a document ID."""
        logging.info(f"Loading Google Doc (document) from Drive, ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                document_ids=[doc_google_drive_id], credentials=credentials_object
            )
            langchain_docs = loader.load()
            # Update source URLs
            for doc in langchain_docs:
                doc.metadata["source"] = (
                    f"https://docs.google.com/document/d/{doc_google_drive_id}/view"
                )
            logging.info(f"Converted Google Doc into {len(langchain_docs)} Langchain documents")
            return langchain_docs
        except Exception as e:
            if self._handle_google_drive_error(e, doc_google_drive_id, indexing_run, "Google Doc"):
                return []
            raise

    def load_google_doc_from_slides_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Slides presentation from Drive."""
        logging.info(f"Loading Google Slides presentation from Drive, ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                file_ids=[doc_google_drive_id], credentials=credentials_object
            )
            langchain_docs = loader.load_slides_from_id(doc_google_drive_id)
            # Update source URLs
            for doc in langchain_docs:
                doc.metadata["source"] = (
                    f"https://docs.google.com/presentation/d/{doc_google_drive_id}/view"
                )
            logging.info(
                f"Converted Google Slides presentation into {len(langchain_docs)} Langchain \
documents (one per slide)"
            )
            return langchain_docs
        except Exception as e:
            if self._handle_google_drive_error(
                e, doc_google_drive_id, indexing_run, "Google Slides"
            ):
                return []
            raise

    def load_google_doc_from_sheets_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Sheets spreadsheet from Drive."""
        logging.info(f"Loading Google Sheets spreadsheet from Drive, ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                file_ids=[doc_google_drive_id], credentials=credentials_object
            )
            langchain_docs = loader.load_sheets_from_id(doc_google_drive_id)
            # Update source URLs
            for doc in langchain_docs:
                doc.metadata["source"] = (
                    f"https://docs.google.com/spreadsheets/d/{doc_google_drive_id}/view"
                )
            logging.info(
                f"Converted Google Sheets spreadsheet into {len(langchain_docs)} Langchain \
documents (one per sheet)"
            )
            return langchain_docs
        except Exception as e:
            if self._handle_google_drive_error(
                e, doc_google_drive_id, indexing_run, "Google Sheets"
            ):
                return []
            raise

    def load_google_doc_from_pdf_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load a Google Drive PDF from a PDF ID.

        This method:
        1. Fetches the PDF file and metadata from Google Drive
        2. Processes the PDF using the PDFProcessor, which:
           - Extracts text from each PDF page into Langchain documents
           - Splits the text into smaller chunks for better processing
           - Adds metadata to track original pages and chunks
        3. Adds Google Drive specific metadata to each chunk

        Parameters
        ----------
        doc_google_drive_id : str
            The Google Drive PDF ID
        credentials_object : credentials.Credentials
            The credentials object to use for Google Drive API
        indexing_run : IndexingRunSchema
            The indexing run to add the users to

        Returns
        -------
        list[Document]
            List of processed text chunks as Langchain documents
        """
        logging.info(f"Starting PDF processing for file ID: {doc_google_drive_id}")

        try:
            # Get the shared service instance
            service = self._get_service(credentials_object)

            # Get file metadata and content in a single call
            logging.info("Fetching file from Google Drive")
            try:
                # Get both metadata and content
                file_metadata = (
                    service.files()
                    .get(
                        fileId=doc_google_drive_id,
                        fields="id,name,mimeType,createdTime,modifiedTime,owners",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                file_bytes = service.files().get_media(fileId=doc_google_drive_id).execute()
            except Exception as e:
                if "File not found" in str(e):
                    error_msg = f"File {doc_google_drive_id} no longer exists in Google Drive or \
user has lost access"
                    logging.error(error_msg)
                    # Find the indexing run item for this file
                    indexing_run_item = IndexingRunItem.query.filter_by(
                        indexing_run_id=indexing_run.id, item_id=doc_google_drive_id
                    ).first()
                    if indexing_run_item:
                        indexing_run_item.item_status = "failed"
                        indexing_run_item.item_error = error_msg
                        db.session.commit()
                    return []
                raise

            logging.info(
                f"File retrieved: Name='{file_metadata.get('name')}', "
                f"Type='{file_metadata.get('mimeType')}', "
                f"Created='{file_metadata.get('createdTime')}', "
                f"Modified='{file_metadata.get('modifiedTime')}', "
                f"Owner='{file_metadata.get('owners', [{}])[0].get('emailAddress', 'Unknown')}'"
            )

            # Validate downloaded content
            if not file_bytes:
                error_msg = "Downloaded PDF file is empty"
                logging.error(error_msg)
                return []

            file_size = len(file_bytes)
            logging.info(f"Downloaded PDF file size: {file_size:,} bytes")
            if file_size == 0:
                error_msg = "Downloaded PDF file has zero bytes"
                logging.error(error_msg)
                return []

            # Create processor configuration for text extraction and chunking
            logging.info("Creating processor configuration")
            config = ProcessorConfig(
                chunk_size=2000,  # Characters per chunk
                overlap=200,  # Character overlap between chunks
                custom_settings={
                    "start_page": 1,  # First PDF page to process
                    "end_page": None,  # Process all PDF pages
                },
            )
            logging.info(f"ProcessorConfig created: {config.model_dump()}")

            # Process the PDF using the PDFProcessor
            logging.info("Starting PDF text extraction and chunking")
            result = process_file(file_bytes=file_bytes, mime_type="application/pdf", config=config)

            # Log all extraction messages for debugging
            logging.info(f"PDF processing completed with status: {result.status}")
            logging.info(f"Processing stats: {result.processing_stats}")
            for log_message in result.extraction_log:
                logging.info(f"PDF Processing: {log_message}")

            # Check processing status and handle errors
            if result.status != ProcessorStatus.OK:
                errors: list[ProcessorError] = []
                error_details = []

                # First collect all error messages for a complete picture
                for log_message in result.extraction_log:
                    if "error" in log_message.lower() or "failed" in log_message.lower():
                        error_details.append(log_message)

                # Now create structured errors based on the complete context
                if error_details:
                    if any("no content" in msg.lower() for msg in error_details):
                        errors.append(
                            ProcessorError(
                                code=ProcessorErrorCode.NO_CONTENT,
                                message="PDF appears to be empty or contains no extractable text",
                                details="\n".join(error_details),
                                item_id=doc_google_drive_id,
                            )
                        )
                    elif any("validation" in msg.lower() for msg in error_details):
                        errors.append(
                            ProcessorError(
                                code=ProcessorErrorCode.VALIDATION_ERROR,
                                message="PDF content failed validation checks",
                                details="\n".join(error_details),
                                item_id=doc_google_drive_id,
                            )
                        )
                    elif any("extraction" in msg.lower() for msg in error_details):
                        # Only mark as extraction failure if we actually failed to get content
                        if not result.documents:
                            errors.append(
                                ProcessorError(
                                    code=ProcessorErrorCode.EXTRACTION_FAILED,
                                    message="Failed to extract any text from PDF",
                                    details="\n".join(error_details),
                                    item_id=doc_google_drive_id,
                                )
                            )
                    else:
                        errors.append(
                            ProcessorError(
                                code=ProcessorErrorCode.UNKNOWN_ERROR,
                                message="Encountered issues while processing PDF",
                                details="\n".join(error_details),
                                item_id=doc_google_drive_id,
                            )
                        )

                # If we have documents despite errors, log a warning instead of error
                if result.documents:
                    logging.warning(
                        f"PDF processing completed with warnings for {doc_google_drive_id}:"
                    )
                    for error in errors:
                        logging.warning(str(error))
                    # Continue processing since we have documents
                else:
                    # No documents extracted, this is a real error
                    logging.error(
                        f"PDF processing failed to extract any content from {doc_google_drive_id}:"
                    )
                    for error in errors:
                        logging.error(str(error))
                    return []

                # Log full processing details at debug level
                logging.debug(f"Full processing log for {doc_google_drive_id}:")
                for log_message in result.extraction_log:
                    logging.debug(f"  {log_message}")

            # Get the number of original PDF pages from the first document's metadata
            pdf_page_count = (
                result.documents[0].metadata.get("total_pages", 1) if result.documents else 1
            )

            # Add Google Drive specific metadata to each text chunk
            logging.info(
                f"Processing successful - Creating {len(result.documents)} text chunks from \
{pdf_page_count} PDF pages"
            )
            for i, chunk_doc in enumerate(result.documents, 1):
                chunk_doc.metadata.update(
                    {
                        "google_drive_id": doc_google_drive_id,
                        "title": file_metadata.get("name", "Untitled Document"),
                        "google_drive_name": file_metadata.get("name", "Unknown"),
                        "google_drive_created": file_metadata.get("createdTime", "Unknown"),
                        "google_drive_modified": file_metadata.get("modifiedTime", "Unknown"),
                        "google_drive_owner": file_metadata.get(
                            "owners", [{"emailAddress": "Unknown"}]
                        )[0].get("emailAddress", "Unknown"),
                        "source_system": "google_drive",
                        "source": f"https://drive.google.com/file/d/{doc_google_drive_id}/view",
                        "pdf_page_count": pdf_page_count,  # Total pages in original PDF
                        "chunk_number": i,  # Position of this chunk
                        "total_chunks": len(result.documents),  # Total number of chunks
                    }
                )

            logging.info(
                f"Successfully processed PDF {doc_google_drive_id} - "
                f"Original PDF pages: {pdf_page_count}, "
                f"Text chunks created: {len(result.documents)}"
            )
            return result.documents

        except Exception as e:
            logging.error(f"Error loading PDF {doc_google_drive_id}: {str(e)}", exc_info=True)
            return []

    def load_google_doc_from_text_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load text-based files (txt, csv, html, xml, json) from Google Drive.

        Parameters
        ----------
        doc_google_drive_id : str
            The Google Drive file ID
        credentials_object : credentials.Credentials
            The credentials object to use for Google Drive API
        indexing_run : IndexingRunSchema
            The indexing run to add the users to

        Returns
        -------
        list[Document]
            List of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive text file ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                file_ids=[doc_google_drive_id], credentials=credentials_object
            )
            docs_loaded = loader.load()
            logging.info(f"Loaded text content from file: {doc_google_drive_id}")
            return docs_loaded
        except Exception as e:
            if self._handle_google_drive_error(e, doc_google_drive_id, indexing_run, "text file"):
                return []
            raise

    def load_google_doc_from_ms_office_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load Microsoft Office files from Google Drive.

        Parameters
        ----------
        doc_google_drive_id : str
            The Google Drive file ID
        credentials_object : credentials.Credentials
            The credentials object to use for Google Drive API
        indexing_run : IndexingRunSchema
            The indexing run to add the users to

        Returns
        -------
        list[Document]
            List of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive MS Office file ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                file_ids=[doc_google_drive_id], credentials=credentials_object
            )
            docs_loaded = loader.load()
            logging.info(f"Loaded content from MS Office file: {doc_google_drive_id}")
            return docs_loaded
        except Exception as e:
            if self._handle_google_drive_error(
                e, doc_google_drive_id, indexing_run, "Office document"
            ):
                return []
            raise

    def load_google_doc_from_image_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load image files from Google Drive.

        Parameters
        ----------
        doc_google_drive_id : str
            The Google Drive file ID
        credentials_object : credentials.Credentials
            The credentials object to use for Google Drive API
        indexing_run : IndexingRunSchema
            The indexing run to add the users to

        Returns
        -------
        list[Document]
            List of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive image file ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                file_ids=[doc_google_drive_id], credentials=credentials_object
            )
            docs_loaded = loader.load()
            logging.info(f"Loaded content from image file: {doc_google_drive_id}")
            return docs_loaded
        except Exception as e:
            if self._handle_google_drive_error(e, doc_google_drive_id, indexing_run, "image"):
                return []
            raise

    def load_google_doc_from_media_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load media files (audio/video) from Google Drive.

        Parameters
        ----------
        doc_google_drive_id : str
            The Google Drive file ID
        credentials_object : credentials.Credentials
            The credentials object to use for Google Drive API
        indexing_run : IndexingRunSchema
            The indexing run to add the users to

        Returns
        -------
        list[Document]
            List of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive media file ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                file_ids=[doc_google_drive_id], credentials=credentials_object
            )
            docs_loaded = loader.load()
            logging.info(f"Loaded content from media file: {doc_google_drive_id}")
            return docs_loaded
        except Exception as e:
            if self._handle_google_drive_error(e, doc_google_drive_id, indexing_run, "media file"):
                return []
            raise

    def load_google_doc_from_archive_id(
        self,
        doc_google_drive_id: str,
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Load archive files (zip, rar, tar, gz) from Google Drive.

        Parameters
        ----------
        doc_google_drive_id : str
            The Google Drive file ID
        credentials_object : credentials.Credentials
            The credentials object to use for Google Drive API
        indexing_run : IndexingRunSchema
            The indexing run to add the users to

        Returns
        -------
        list[Document]
            List of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive archive file ID: {doc_google_drive_id}")
        try:
            loader = GoogleDriveLoader(
                file_ids=[doc_google_drive_id], credentials=credentials_object
            )
            docs_loaded = loader.load()
            logging.info(f"Loaded content from archive file: {doc_google_drive_id}")
            return docs_loaded
        except Exception as e:
            if self._handle_google_drive_error(e, doc_google_drive_id, indexing_run, "archive"):
                return []
            raise

    def google_docs_to_langchain_docs(
        self: None,
        documents: list[dict[str, any]],
        credentials_object: credentials.Credentials,
        indexing_run: IndexingRunSchema,
    ) -> list[Document]:
        """Convert Google Drive files into Langchain documents for processing.

        Takes Google Drive files and converts them into Langchain Document objects
        that can be processed and stored in Pinecone. Each file may result in
        multiple Langchain documents depending on its type and content length.
        """
        langchain_docs: list[Document] = []
        for doc in documents:
            doc_google_drive_id = doc["google_drive_id"]
            doc_item_type = doc["item_type"]
            doc_mime_type = doc["mime_type"]
            indexing_run_item_id = doc["indexing_run_item_id"]

            try:
                if doc_item_type not in ALLOWED_ITEM_TYPES:
                    error_msg = f"Invalid item type: {doc_item_type}"
                    logging.error(f"{error_msg} for Google Drive file ID: {doc_google_drive_id}")
                    self._update_indexing_run_item(indexing_run_item_id, "failed", error_msg)
                    continue

                # Match on mime type categories
                file_langchain_docs = []  # documents created from this specific file
                match doc_mime_type:
                    case "application/pdf":
                        file_langchain_docs = self.load_google_doc_from_pdf_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case "application/vnd.google-apps.document":
                        file_langchain_docs = self.load_google_doc_from_document_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case "application/vnd.google-apps.spreadsheet":
                        file_langchain_docs = self.load_google_doc_from_sheets_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case "application/vnd.google-apps.presentation":
                        file_langchain_docs = self.load_google_doc_from_slides_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case mime if mime.startswith("text/"):
                        file_langchain_docs = self.load_google_doc_from_text_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case mime if mime in [
                        "application/msword",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "application/vnd.ms-excel",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.ms-powerpoint",
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    ]:
                        file_langchain_docs = self.load_google_doc_from_ms_office_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case mime if mime.startswith("image/"):
                        file_langchain_docs = self.load_google_doc_from_image_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case mime if mime.startswith("video/") or mime.startswith("audio/"):
                        file_langchain_docs = self.load_google_doc_from_media_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case mime if mime in [
                        "application/zip",
                        "application/x-rar-compressed",
                        "application/x-tar",
                        "application/gzip",
                    ]:
                        file_langchain_docs = self.load_google_doc_from_archive_id(
                            doc_google_drive_id, credentials_object, indexing_run
                        )
                    case _:
                        error_msg = f"Unsupported MIME type: {doc_mime_type}"
                        logging.error(
                            f"{error_msg} for Google Drive file ID: {doc_google_drive_id}"
                        )
                        self._update_indexing_run_item(indexing_run_item_id, "failed", error_msg)
                        continue

                if file_langchain_docs:
                    langchain_docs.extend(file_langchain_docs)
                    # Update status to completed after successful processing
                    titles = list(
                        set([doc.metadata.get("title", "Untitled") for doc in file_langchain_docs])
                    )
                    # limit the titles to 20
                    if len(titles) > 20:
                        text = "First 20 titles: " + ", ".join(titles[:20]) + "..."
                    else:
                        text = ", ".join(titles)

                    success_msg = f"Successfully converted Google Drive file into \
{len(file_langchain_docs)} Langchain documents from {len(titles)} files; {text}"
                    self._update_indexing_run_item(
                        indexing_run_item_id,
                        "completed",
                        success_msg,
                        extracted_text="\n\n".join(doc.page_content for doc in file_langchain_docs),
                    )
                else:
                    error_msg = f"No content could be extracted from Google Drive {doc_item_type}"
                    logging.error(f"{error_msg} with ID: {doc_google_drive_id}")
                    self._update_indexing_run_item(indexing_run_item_id, "failed", error_msg)

            except Exception as e:
                error_msg = str(e)
                logging.error(
                    f"Error processing document {doc_google_drive_id}: {error_msg}", exc_info=True
                )
                self._update_indexing_run_item(indexing_run_item_id, "failed", error_msg)

        return langchain_docs

    def _update_indexing_run_item(
        self, item_id: int, status: str, message: str, extracted_text: str | None = None
    ) -> None:
        """Update the status and message of an indexing run item.

        Parameters
        ----------
        item_id : int
            The ID of the indexing run item to update
        status : str
            The new status ('completed', 'failed', etc.)
        message : str
            The message to store with the status
        extracted_text : str | None, optional
            The extracted text to store, by default None
        """
        try:
            indexing_run_item = IndexingRunItem.query.get(item_id)
            if indexing_run_item:
                indexing_run_item.item_status = status
                # Add timestamp to messages for better tracking
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                indexing_run_item.item_error = f"[{timestamp}] {message}"
                if extracted_text:
                    indexing_run_item.item_extractedtext = extracted_text
                    char_count = len(extracted_text)
                    logging.info(
                        f"Storing {char_count:,} characters of extracted text for item {item_id}"
                    )
                db.session.commit()
        except Exception as e:
            logging.error(f"Error updating indexing run item {item_id}: {str(e)}", exc_info=True)
            db.session.rollback()

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

    def _get_service(self, credentials_object: credentials.Credentials) -> Any:
        """Get or create the Google Drive service instance.

        Parameters
        ----------
        credentials_object : credentials.Credentials
            The credentials object to use for Google Drive API

        Returns
        -------
        Any
            The Google Drive service instance
        """
        if self._service is None:
            logging.debug("Creating new Google Drive service instance")
            self._service = build("drive", "v3", credentials=credentials_object)
        return self._service

    def __list_files_in_folder(
        self,
        folder_id: str,
        credentials_object: credentials.Credentials,
        indexing_run_model: IndexingRun,
        indexing_run_item_id: int,
        processed_folders: set[str] = None,
    ) -> list[dict]:
        """Recursively list all files in a Google Drive folder.

        Parameters
        ----------
        folder_id : str
            The ID of the folder to list files from
        credentials_object : credentials.Credentials
            Google Drive credentials
        indexing_run_model : IndexingRun
            The indexing run model instance
        indexing_run_item_id : int
            ID of the indexing run item for the folder
        processed_folders : set[str], optional
            Set of folder IDs that have already been processed (to avoid cycles)

        Returns
        -------
        list[dict]
            List of dictionaries containing file information for all files in the folder
            and its subfolders
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
        logging.info(f"Processing Google Drive folder {folder_id}")

        try:
            # Get the shared service instance
            service = self._get_service(credentials_object)
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
                logging.info(f"Found {len(items)} items in Google Drive folder {folder_id}")
                for item in items:
                    logging.info(
                        f"Found item in folder - Name: {item['name']}, Type: {item['mimeType']}, \
ID: {item['id']}"
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
                f"Completed processing Google Drive folder {folder_id}, total items found: \
{len(results)}"
            )
            return results

        except Exception as e:
            logging.error(f"Error listing files in Google Drive folder {folder_id}: {str(e)}")
            raise
