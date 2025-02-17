#!/usr/bin/env python3

"""Query indexed documents in Pinecone using LangChain and OpenAI in the CLI."""

import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask

from colorama import Fore, Style, init

from lorelai.context_retriever import ContextRetriever
from lorelai.llm import Llm
from app.models.user import User
from app.models.organisation import Organisation
from app.models import db

# Add parent directory to path and load environment variables
sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../.."))
env_path = Path(os.path.join(os.path.dirname(__file__), "../..")) / ".env"
load_dotenv(dotenv_path=env_path)

# logging settings
logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)

# Initialize Flask app and SQLAlchemy
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Add required configuration from .env
app.config["PINECONE_API_KEY"] = os.getenv("PINECONE_API_KEY")
app.config["PINECONE_REGION"] = os.getenv("PINECONE_REGION")
app.config["PINECONE_METRIC"] = os.getenv("PINECONE_METRIC")
app.config["PINECONE_DIMENSION"] = os.getenv("PINECONE_DIMENSION")
app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
app.config["OPENAI_MODEL"] = os.getenv("OPENAI_MODEL")
app.config["LORELAI_ENVIRONMENT"] = os.getenv("LORELAI_ENVIRONMENT", "dev")
app.config["LORELAI_ENVIRONMENT_SLUG"] = os.getenv("LORELAI_ENVIRONMENT_SLUG", "development")
app.config["LORELAI_RERANKER"] = os.getenv("LORELAI_RERANKER", "ms-marco-TinyBERT-L-2-v2")
app.config["FEATURE_SLACK"] = os.getenv("FEATURE_SLACK", "1")
app.config["FEATURE_GOOGLE_DRIVE"] = os.getenv("FEATURE_GOOGLE_DRIVE", "1")

db.init_app(app)
app.app_context().push()  # Make the app context available to the script


def main() -> None:
    """Retrieve the context, ask a question, and display the results."""
    init(autoreset=True)  # Initialize Colorama
    parser = setup_arg_parser()
    args = parser.parse_args()

    question = args.question
    org_id, org_name = get_organisation(args.org_name)
    user_id, user_email = get_user_from_organisation(org_id, args.user_name)

    # Create context retrievers with required parameters
    retrievers = []
    for retriever_type in ["SlackContextRetriever", "GoogleDriveContextRetriever"]:
        enriched_context = ContextRetriever.create(
            retriever_type=retriever_type,
            org_name=org_name,
            user_email=user_email,
            environment=os.getenv("LORELAI_ENVIRONMENT", "dev"),
            environment_slug=os.getenv("LORELAI_ENVIRONMENT_SLUG", "development"),
            reranker=os.getenv("LORELAI_RERANKER", "ms-marco-TinyBERT-L-2-v2"),
        )
        retrievers.append(enriched_context)

    # Get context and format results from all retrievers
    all_context = []
    for retriever in retrievers:
        try:
            context_response = retriever.retrieve_context(question)
            all_context.extend(context_response.context)
            # Debug log to inspect the first document's attributes and content
            if context_response.context:
                doc = context_response.context[0]
                logging.info(f"Document attributes: {dir(doc)}")
                logging.info(f"Document dict: {doc.model_dump()}")
                logging.info(f"Document type: {type(doc)}")
                logging.info(f"Document repr: {repr(doc)}")
        except Exception as e:
            logging.warning(f"Error retrieving context from {retriever.__class__.__name__}: {e}")

    # Create LLM instance and get answer
    llm = Llm.create(model_type=args.model_type, user_email=user_email, org_name=org_name)
    llm_answer = llm.get_answer(question, all_context)

    # Format sources for display with more defensive approach
    sources = []
    for doc in all_context:
        try:
            source_dict = {}
            # Try different possible attribute names for source
            for source_attr in ["datasource", "source", "source_name", "metadata"]:
                if hasattr(doc, source_attr):
                    source_dict["source"] = getattr(doc, source_attr)
                    break
            if "source" not in source_dict:
                source_dict["source"] = "Unknown Source"

            # Try different possible attribute names for title
            for title_attr in ["title", "name", "page_content"]:
                if hasattr(doc, title_attr):
                    source_dict["title"] = getattr(doc, title_attr)
                    if isinstance(source_dict["title"], str):
                        source_dict["title"] = (
                            source_dict["title"][:100] + "..."
                            if len(source_dict["title"]) > 100
                            else source_dict["title"]
                        )
                    break
            if "title" not in source_dict:
                source_dict["title"] = "Untitled"

            # Try different possible attribute names for score
            for score_attr in ["relevance_score", "score", "similarity"]:
                if hasattr(doc, score_attr):
                    score = getattr(doc, score_attr)
                    if isinstance(score, int | float):
                        source_dict["score"] = score
                        break
            if "score" not in source_dict:
                source_dict["score"] = 0.0

            sources.append(source_dict)
        except Exception as e:
            logging.warning(f"Error formatting source: {e}")
            sources.append({"source": "Error", "title": "Error formatting source", "score": 0.0})

    display_results(llm_answer, sources)


def setup_arg_parser() -> argparse.ArgumentParser:
    """Set up argument parser for command-line options."""
    parser = argparse.ArgumentParser(description="Query indexed documents with context.")
    parser.add_argument("question", help="Question to query")
    parser.add_argument("--org-name", help="Name of the organisation", default=None)
    parser.add_argument("--user-name", help="Name of the user", default=None)
    parser.add_argument("--model-type", help="Type of the model to use", default="OpenAILlm")
    return parser


def get_organisation(org_name: str or None) -> tuple:
    """Retrieve or select an organisation."""
    if org_name:
        org = Organisation.query.filter_by(name=org_name).first()
        if org:
            return org.id, org.name
        print(
            f"{Fore.RED}No organisation found with the name '{org_name}'.",
            " Falling back to selection.",
        )

    return select_organisation()


def select_organisation() -> tuple:
    """Interactively select an organisation from a list."""
    organisations = Organisation.query.all()
    print(f"{Fore.CYAN}Select an organisation:")
    for index, org in enumerate(organisations, start=1):
        print(f"{Fore.YELLOW}{index}: {Fore.GREEN}{org.name}")
    choice = input(f"{Fore.MAGENTA}Organisation ({organisations[0].name}): ") or "1"

    selected_org = organisations[int(choice) - 1]
    return selected_org.id, selected_org.name


def get_user_from_organisation(org_id: int, user_name: str or None = None) -> tuple:
    """Retrieve or select a user from a specific organisation."""
    if user_name:
        user = User.query.filter_by(org_id=org_id, user_name=user_name).first()
        if user:
            return user.id, user.email
        print(
            f"{Fore.RED}No user found with name '{user_name}' in the selected organisation.",
            "Falling back to selection.",
        )

    return select_user_from_organisation(org_id)


def select_user_from_organisation(org_id: int) -> tuple:
    """Interactively select a user from a list."""
    users = User.query.filter_by(org_id=org_id).all()
    print(f"{Fore.CYAN}Select a user:")
    for index, user in enumerate(users, start=1):
        print(f"{Fore.YELLOW}{index}: {Fore.GREEN}{user.user_name} ({user.email})")
    choice = input(f"{Fore.MAGENTA}User ({users[0].user_name}): ") or "1"
    selected_user = users[int(choice) - 1]
    return selected_user.id, selected_user.email


def display_results(answer: str, sources: list) -> None:
    """Display the results in a formatted manner."""
    print(f"{Fore.BLUE}Answer: {Style.BRIGHT}{answer}\nSources:")

    for source in sources:
        src = source["source"]
        title = source["title"]
        score = source["score"]
        print(f"- {Fore.YELLOW}{src} {Fore.BLUE}({score}): {Fore.GREEN}{title}")


if __name__ == "__main__":
    main()
