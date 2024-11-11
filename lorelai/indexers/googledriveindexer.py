"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveIndexer: Handles Google Drive document indexing using Pinecone and OpenAI.
"""

import logging
from flask import current_app

# from pathlib import Path
from google.oauth2 import credentials
from googleapiclient.discovery import build
from google.auth.credentials import TokenState
from lorelai.indexer import Indexer
from lorelai.processor import Processor
from langchain_googledrive.document_loaders import GoogleDriveLoader
from langchain_core.documents import Document
from rq import job
from app.models import db, GoogleDriveItem
from sqlalchemy.exc import SQLAlchemyError
from app.schemas import OrganisationSchema, UserSchema, UserAuthSchema, GoogleDriveItemSchema

ALLOWED_ITEM_TYPES = ["document", "folder", "file"]


class GoogleDriveIndexer(Indexer):
    """Used to process the Google Drive documents and index them in Pinecone."""

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
        return access_token, refresh_token, expires_at

    def __init__(self) -> None:
        logging.debug("GoogleDriveIndexer initialized")

    def index_user(
        self,
        user: UserSchema,
        organisation: OrganisationSchema,
        user_auths: list[UserAuthSchema],
        job: job.Job,
    ) -> bool:
        """Process the Google Drive documents for a user and index them in Pinecone.

        Arguments
        ---------
        user: UserSchema
        organisation: OrganisationSchema
            The organisation to process.
        user_auths: list[UserAuthSchema]
            The user auth rows for the user.
        job: job.Job
            The job object for the current task.

        Returns
        -------
        bool
            True if indexing was successful, False otherwise.
        """
        logging.info(f"Indexing user: {user.email} from org: {organisation.name}")

        # 1. Get the Google Drive access token, refresh token, and expiry
        access_token, refresh_token, expires_at = self.__get_token_details(user_auths)

        # 2. Get the Google Drive document IDs
        logging.debug(f"Getting Google Drive document IDs for user: {user.email}")

        drive_items = GoogleDriveItem.query.filter_by(user_id=user.id)
        user_data = [GoogleDriveItemSchema.from_orm(data) for data in drive_items]

        # 3. Check if there are any Google Drive documents for the user
        documents = []
        for drive_item in user_data:
            # extra safety: check if item_type in the user_data_row equals the allowed item types
            if drive_item.item_type not in ALLOWED_ITEM_TYPES:
                logging.error(f"Invalid item type: {drive_item.item_type}")
                continue

            # add information about the document to the list
            documents.append(
                {
                    "user_id": user.id,
                    "google_drive_id": drive_item.google_drive_id,
                    "item_type": drive_item.item_type,
                    "item_name": drive_item.item_name,
                }
            )

        if not documents or len(documents) == 0:
            logging.warn(f"No Google Drive documents found for user: {user.email}")
            return True

        # 5. Process the Google Drive documents and index them in Pinecone
        logging.info(f"Processing {len(documents)} Google documents for user: {user.email}")

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
{user.email}"
                )
            except Exception as e:
                logging.error(f"Failed to validate Google Drive credentials for user: \
{user.email} with a simple API call: {e}")
                return False

        # convert the documents to langchain documents
        langchain_docs = self.google_docs_to_langchain_docs(
            documents=documents,
            credentials_object=credentials_object,
            job=job,
        )

        # add the user for whom were indexing the docs to the documents' metadata
        self.add_user_to_docs_metadata(langchain_docs, user.email)

        pinecone_processor = Processor()

        # store the documents in Pinecone
        pinecone_processor.store_docs_in_pinecone(
            langchain_docs,
            user_email=user.email,
            job=job,
            org_name=organisation.name,
            datasource="googledrive",
        )

        self.update_last_indexed_for_docs(documents, job)
        logging.info(f"Indexing Google Drivecomplete for user: {user.email}")

        return True

    def add_user_to_docs_metadata(
        self: None, langchain_docs: list[Document], user_email: str
    ) -> None:
        """Add the user to the documents.

        :param langchain_docs: the list of langchain documents to add the users to
        :param user_email: the user to add to the documents
        """
        # go through all docs. For each doc, see if the user is already in the metadata. If not,
        # add the user to the metadata
        for loaded_doc in langchain_docs:
            logging.info(f"Checking metadata users for Google doc: {loaded_doc.metadata['title']}")

            # check if the user key is in the metadata
            if "users" not in loaded_doc.metadata:
                loaded_doc.metadata["users"] = []

            # check if the user is in the metadata
            if user_email not in loaded_doc.metadata["users"]:
                logging.info(
                    f"Adding user {user_email} to metadata.users for {loaded_doc.metadata['title']}"
                )
                loaded_doc.metadata["users"].append(user_email)

    def load_google_doc_from_file_id(
        self, doc_google_drive_id: str, credentials_object: credentials.Credentials
    ) -> list[Document]:
        """Load a Google Drive file from a file ID.

        :param doc_google_drive_id: the Google Drive file ID
        :param credentials_object: the credentials object to use for Google Drive API

        :return: the list of documents loaded from Google Drive
        """
        logging.info(f"Loading Google Drive file ID: {doc_google_drive_id}")
        loader = GoogleDriveLoader(file_ids=[doc_google_drive_id], credentials=credentials_object)
        docs_loaded = loader.load()
        logging.info(f"Loaded {len(docs_loaded)} docs from file: {doc_google_drive_id}")
        return docs_loaded

    def load_google_doc_from_document_id(
        self, doc_google_drive_id: str, credentials_object: credentials.Credentials
    ) -> list[Document]:
        """Load a Google Drive document from a document ID.

        :param doc_google_drive_id: the Google Drive document ID
        :param credentials_object: the credentials object to use for Google Drive API

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
        self, doc_google_drive_id: str, credentials_object: credentials.Credentials
    ) -> list[Document]:
        """Load a Google Drive folder from a folder ID.

        :param doc_google_drive_id: the Google Drive folder ID
        :param credentials_object: the credentials object to use for Google Drive API

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
        self, doc_google_drive_id: str, credentials_object: credentials.Credentials
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
        self, doc_google_drive_id: str, credentials_object: credentials.Credentials
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

    def google_docs_to_langchain_docs(
        self: None,
        documents: list[dict[str, any]],
        credentials_object: credentials.Credentials,
        job: job.Job,
    ) -> list[Document]:
        """Process the Google Drive documents and divide them into pinecone compatible chunks.

        :param documents: the list of google documents to process. Each document is a dictionary
            with the following keys: google_drive_id, item_type
        :param credentials_object: the credentials object to use for Google Drive API
        :param job: the job object


        :return: the list of documents loaded from Google Drive
        """
        docs: list[Document] = []
        # documents contain a list of dictionaries with the following keys:
        # user_id, google_drive_id, item_type, item_name
        # loop through the documents and load them from Google Drive
        for doc in documents:
            doc_google_drive_id = doc["google_drive_id"]
            doc_item_type = doc["item_type"]
            doc_mime_type = doc["mime_type"]

            if doc_item_type not in ALLOWED_ITEM_TYPES:
                logging.error(
                    f"Invalid item type: {doc_item_type} for document ID: {doc_google_drive_id}"
                )
                raise ValueError(f"Invalid item type: {doc_item_type}")

            # use langchain google drive loader to load the content of the docs from google drive
            match doc_mime_type:
                case "application/vnd.google-apps.presentation":
                    docs_loaded = self.load_google_doc_from_slides_id(
                        doc_google_drive_id, credentials_object
                    )
                case "application/vnd.google-apps.spreadsheet":
                    docs_loaded = self.load_google_doc_from_sheets_id(
                        doc_google_drive_id, credentials_object
                    )
                case "application/vnd.google-apps.document":
                    docs_loaded = self.load_google_doc_from_document_id(
                        doc_google_drive_id, credentials_object
                    )
                case "application/vnd.google-apps.folder":
                    docs_loaded = self.load_google_doc_from_folder_id(
                        doc_google_drive_id, credentials_object
                    )
                case _:
                    match doc_item_type:
                        case "document":
                            docs_loaded = self.load_google_doc_from_file_id(
                                doc_google_drive_id, credentials_object
                            )
                        case "folder":
                            docs_loaded = self.load_google_doc_from_folder_id(
                                doc_google_drive_id, credentials_object
                            )
                        case "file":
                            docs_loaded = self.load_google_doc_from_file_id(
                                doc_google_drive_id, credentials_object
                            )
                        case _:
                            raise ValueError(f"Invalid item type: {doc_item_type}")

            # if the docs_loaded is not None, add the loaded docs to the docs list
            if docs_loaded:
                docs.extend(docs_loaded)

                for loaded_doc in docs_loaded:
                    logging.info(
                        f"Loaded Google doc: {loaded_doc.metadata['title']} with ID: \
{doc_google_drive_id}"
                    )
            else:
                logging.error(
                    f"No documents loaded from Google Drive {doc_item_type} with ID: \
{doc_google_drive_id}"
                )

        logging.debug(f"Total {len(docs)} Google docs loaded from Google Drive using langchain")

        return docs

    def update_last_indexed_for_docs(self, documents, job: job.Job) -> None:
        """Update the last indexed timestamp for the documents in the database.

        :param documents: the documents to update
        :param job: the job object
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
