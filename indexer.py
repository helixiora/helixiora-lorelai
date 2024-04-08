#!/usr/bin/env python3

"""This script is used to crawl the Google Drive and process the documents using Pinecone and
OpenAI API through langchain
"""
import sqlite3

# import the indexer
from lorelai.indexer import Indexer
from app.utils import get_db_connection


def main():
    """the main function
    """

    # get the orgs from sqlite
    conn = get_db_connection()

    cur = conn.cursor()
    cur.execute("SELECT id, name FROM organisations")
    rows = cur.fetchall()

    # get the user creds for this org from sqlite
    cur = conn.cursor()
    for org in rows:
        cur.execute("SELECT user_id, name, email, access_token, refresh_token \n"
                    "FROM users where org_id = ?", (org[0],))

        users = cur.fetchall()

        indexer = Indexer()
        indexer.index_org_drive(org, users)

if __name__ == '__main__':
    main()
