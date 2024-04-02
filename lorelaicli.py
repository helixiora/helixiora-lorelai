#!/usr/bin/env python3

"""this script is used to query the indexed documents in pinecone using langchain and OpenAI
"""

import sqlite3
import sys

from lorelai.contextretriever import ContextRetriever

# a simple test script to ask a question langchain that has been indexed in pinecone

# the question to ask is supplied as commenad line argument
args = sys.argv
question = args[1]

def select_organisation():
    """ list the organisations in sqlite and ask the user to pick one, defaulting to the first one
    """
    sql = "SELECT id, name FROM organisations"
    conn = sqlite3.connect('userdb.sqlite')
    cur = conn.cursor()
    orgs = cur.execute(sql).fetchall()

    print("Select an organisation:")
    # start numbering at 1
    for i, org in enumerate(orgs):
        print(f"{i+1}: {org[1]}")

    choice = input(f"Organisation ({orgs[0][1]}): ")

    # if no id is given, default to the first one
    if choice:
        org = orgs[int(choice)-1][1]
    else:
        org = orgs[0][1]
        choice = orgs[0][0]

    return org, choice

def select_user_from_organisation(organisation_id):
    """ list the users in sqlite and ask the user to pick one, defaulting to the first one
    """
    sql = f"SELECT user_id, name, email FROM users WHERE org_id = {organisation_id}"
    conn = sqlite3.connect('userdb.sqlite')
    cur = conn.cursor()
    users = cur.execute(sql).fetchall()

    print("Select a user:")
    # start numbering at 1
    for i, user in enumerate(users):
        print(f"{i+1}: {user[1]} ({user[2]})")

    choice = input(f"User ({users[0][1]}): ")

    # if no id is given, default to the first one
    if not choice:
        choice = users[0][0]

    return choice

org_name, org_id = select_organisation()

user_id = select_user_from_organisation(org_id)


# get the context for the question
enriched_context = ContextRetriever(org_name=org_name, user=user_id)

answer, source = enriched_context.retrieve_context(question)

print(f"Answer: {answer}\nSource: {source}")
