#!/usr/bin/env python3

"""This script is used to crawl the Google Drive and process the documents using Pinecone and
OpenAI API through langchain
"""
import sqlite3

# import the indexer
from lorelai.indexer import Indexer

DATABASE = './userdb.sqlite'


def main():
    """the main function
    """

    # get the orgs from sqlite
    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()
    cur.execute("SELECT * FROM organisations")
    rows = cur.fetchall()

    # get the user creds for this org from sqlite
    cur = conn.cursor()
    for org in rows:
        cur.execute("SELECT * FROM users where org_id = ?", (org[0],))

        users = cur.fetchall()

        indexer = Indexer()
        indexer.index_org_drive(org, users)

if __name__ == '__main__':
    main()