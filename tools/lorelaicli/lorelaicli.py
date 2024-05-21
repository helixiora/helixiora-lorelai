#!/usr/bin/env python3

"""Query indexed documents in Pinecone using LangChain and OpenAI in the CLI"""

import argparse
from colorama import Fore, Style, init
import logging
import os
import sys

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../.."))
from lorelai.contextretriever import ContextRetriever
from lorelai.llm import Llm
from lorelai.utils import get_db_connection

# logging settings
logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)


def main() -> None:
    """Retrieve the context, ask a question, and display the results."""
    init(autoreset=True)  # Initialize Colorama
    parser = setup_arg_parser()
    args = parser.parse_args()

    question = args.question
    org_id, org_name = get_organisation(args.org_name)
    user_id = get_user_from_organisation(org_id, args.user_name)
    enriched_context = ContextRetriever(org_name=org_name, user=user_id)
    answer, source = enriched_context.retrieve_context(question)
    llm = Llm.create(model_type=args.model_type)
    llm_answer = llm.get_answer(question, answer)
    display_results(llm_answer, source)


def setup_arg_parser() -> argparse.ArgumentParser:
    """
    Set up argument parser for command-line options.
    Params: none
    Returns: ArgumentParser object
    """
    parser = argparse.ArgumentParser(description="Query indexed documents with context.")
    parser.add_argument("question", help="Question to query")
    parser.add_argument("--org-name", help="Name of the organisation", default=None)
    parser.add_argument("--user-name", help="Name of the user", default=None)
    parser.add_argument("--model-type", help="Type of the model to use", default="OpenAILlm")
    return parser


def get_organisation(org_name: str or None) -> tuple:
    """
    Retrieve or select an organisation.
    Params: org_name: str, name of the organisation
    Returns: tuple with org ID as the 0 object or select_organisation
    function
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        if org_name:
            cur.execute("SELECT id, name FROM organisations WHERE name = %s", (org_name,))
            org = cur.fetchone()
        if org:
            return org
        print(
            f"{Fore.RED}No organisation found with the name '{org_name}'.",
            " Falling back to selection.",
        )

    return select_organisation()


def select_organisation() -> tuple:
    """
    Interactively select an organisation from a list.
    Params: none
    Returns: tuple with the org ID and name
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM organisations")
        organisations = cur.fetchall()
        print(f"{Fore.CYAN}Select an organisation:")
        for index, org in enumerate(organisations, start=1):
            print(f"{Fore.YELLOW}{index}: {Fore.GREEN}{org[1]}")
        choice = (
            input(f"{Fore.MAGENTA}Organisation ({organisations[0][1]}): ") or organisations[0][0]
        )

    return organisations[int(choice) - 1]


def get_user_from_organisation(org_id: int, user_name: str or None = None) -> int:
    """
    Retrieve or select a user from a specific organisation.
    Params:
        org_id, int, the organisation ID
        user_name, str, the user name
    Returns:
        user ID int or
        results from select_user_from_organisation function

    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        if user_name:
            cur.execute(
                """
                SELECT user_id, name, email FROM users WHERE org_id =
                %s AND name = %s
                """,
                (org_id, user_name),
            )
            user = cur.fetchone()
            if user:
                return user[0]
            print(
                f"{Fore.RED}No user found with name '{user_name}' in the selected organisation.",
                "Falling back to selection.",
            )

    return select_user_from_organisation(org_id)


def select_user_from_organisation(org_id: int) -> int:
    """
    Interactively select a user from a list.
    Params:
            org_id: int, the ID of the organisation
    Returns:
            user id: int
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, name, email FROM users WHERE org_id = %s", (org_id,))
        users = cur.fetchall()
        print(f"{Fore.CYAN}Select a user:")
        for index, user in enumerate(users, start=1):
            print(f"{Fore.YELLOW}{index}: {Fore.GREEN}{user[1]} ({user[2]})")
        return input(f"{Fore.MAGENTA}User ({users[0][1]}): ") or users[0][0]


def display_results(answer: str, sources: dict) -> None:
    """Display the results in a formatted manner."""
    print(f"{Fore.BLUE}Answer: {Style.BRIGHT}{answer}\nSources:")

    for source in sources:
        src = source["source"]
        title = source["title"]
        score = source["score"]
        print(f"- {Fore.YELLOW}{src} {Fore.BLUE}({score}): {Fore.GREEN}{title}")


if __name__ == "__main__":
    main()
