#!/usr/bin/env python3

"""
Crawl the Google Drive and index the documents.

It processes the documents using Pinecone and OpenAI API through langchain
"""

import argparse
import logging
import os
import sys

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../.."))
# import the indexer
from app.utils import get_db_connection
from lorelai.indexer import Indexer

# logging settings
logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)


def main(folder_id: str = None) -> None:
    """Implement the main function."""
    # get the orgs from db
    logging.info("indexer_cli started")
    with get_db_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name FROM organisations")
        rows = cur.fetchall()
        if not rows:
            logging.info("No User found in DB")
        # get the user creds for this org from DB
        cur = conn.cursor(dictionary=True)
        for org in rows:
            cur.execute(
                """
                SELECT user_id, name, email, access_token, refresh_token
                FROM users where org_id = %s
                """,
                (org["id"],),
            )

            users = cur.fetchall()

            indexer = Indexer.create("GoogleDriveIndexer")
            logging.debug(f"List of org and user found: {org}, {users}")
            indexer.index_org_drive(org, users, folder_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index Google Drive documents.")
    parser.add_argument(
        "--folder_id", type=str, help="Specify the Google Drive folder ID to index", required=False
    )
    args = parser.parse_args()
    main(folder_id=args.folder_id)
