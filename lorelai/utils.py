"""Contains utility functions for the Lorelai package."""

import json
import logging
import os
from pathlib import Path

import mysql.connector
from pinecone import Pinecone
from pinecone.core.client.exceptions import NotFoundException
from pinecone.core.client.model.describe_index_stats_response import (
    DescribeIndexStatsResponse,
)
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import jwt
import datetime


def pinecone_index_name(
    org: str,
    datasource: str,
    environment: str = "dev",
    env_name: str = "lorelai",
    version: str = "v1",
) -> str:
    """Return the pinecone index name for the org.

    Arguments:
    ---------
        org (str): The name of the organization.
        datasource (str): The name of the datasource.
        environment (str): The environment (e.g. dev, prod).
        env_name (str): The name of the environment (e.g. lorelai, openai).
        version (str): The version of the index (e.g. v1).

    Returns
    -------
        str: The name of the pinecone index.

    """
    parts = [environment, env_name, org, datasource, version]

    name = "-".join(parts)

    name = name.lower().replace(".", "-").replace(" ", "-")

    logging.debug("Index name: %s", name)
    return name


def get_config_from_os(service: str) -> dict[str, str]:
    """Load credentials from OS env vars.

    Arguments
    ---------
    service (str): The name of the service (e.g 'openai', 'pinecone')
        for which to load

    Returns
    -------
        dict: A dictionary containing the creds for the specified service.

    """
    config = {}
    # loop through the env vars
    for k in os.environ:
        # check if the service is in the env var
        # eg. GOOGLE_CLIENT_ID
        if service.upper() in k:
            # remove the service name and convert to lower case
            # eg. GOOGLE_CLIENT_ID -> client_id
            n_k = k.lower().replace(f"{service}_", "")
            if "redirect_uris" in n_k:
                config[n_k] = os.environ[k].split("|")
            else:
                config[n_k] = os.environ[k]

    return config


def load_config(service: str, config_file: str = "./settings.json") -> dict[str, str]:
    """Load credentials for a specified service from settings.json.

    If file is non-existent or has syntax errors will try to pull from
    OS env vars.

    Arguments
    ---------
        service (str): The name of the service (e.g 'openai', 'pinecone')
        for which to load credentials.

        config_file (str): The path to the settings.json file.

    Returns
    -------
        dict: A dictionary containing the creds for the specified service.

    """
    logging.debug(f"loading from full file path: {Path(config_file).absolute()}")
    if Path(config_file).is_file():
        with Path(config_file).open(encoding="utf-8") as f:
            try:
                config = json.load(f).get(service, {})

                if service != "google" or service != "lorelai":
                    os.environ[f"{service.upper()}_API_KEY"] = config.get("api_key", "")

            except ValueError as e:
                logging.debug(f"There was an error in your JSON:\n    {e}")
                logging.debug("Trying to fallbak to env vars...")
                config = get_config_from_os(service)
    else:
        config = get_config_from_os(service)

    # if config is {} we need to fail
    if not config:
        raise ValueError(f"No config found in {config_file} under {service}")

    # if config is {} we need to fail
    if not config:
        raise ValueError(f"No config found in {config_file} or OS env var under {service}")

    return config


def get_db_connection() -> mysql.connector.connection.MySQLConnection:
    """Get a database connection.

    Returns
    -------
        conn: a connection to the database

    """
    try:
        creds = load_config("db")
        conn = mysql.connector.connect(
            host=creds["host"],
            user=creds["user"],
            password=creds["password"],
            database=creds["database"],
        )
        return conn
    except mysql.connector.Error:
        logging.exception("Database connection failed")
        raise


def save_google_creds_to_tempfile(
    refresh_token: str,
    token_uri: str,
    client_id: str,
    client_secret: str,
    tempfile: str = ".credentials/token.json",
) -> None:
    """Load the google creds to a tempfile.

    This is needed because the GoogleDriveLoader uses
    the Credentials.from_authorized_user_file method to load the credentials

    Arguments
    ---------
        refresh_token (str): The refresh token
        token_uri (str): The token uri
        client_id (str): The client id
        client_secret (str): The client secret
        tempfile (str): The path to the tempfile
    """
    tempfile = f"{Path.home()}/{tempfile}"

    # create a file: Path.home() / ".credentials" / "token.json" to store the credentials so
    # they can be loaded by GoogleDriveLoader's auth process (this uses
    # Credentials.from_authorized_user_file)
    if not os.path.exists(tempfile):
        # get the directory
        dir = os.path.dirname(tempfile)
        os.makedirs(dir, exist_ok=True)

    with open(tempfile, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "refresh_token": refresh_token,
                    "token_uri": token_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            )
        )
        f.close()


def get_embedding_dimension(model_name) -> int:
    """
    Return the dimension of embeddings for a given model name.

    This function currently uses a hardcoded mapping based on documentation,
    as there's no API endpoint to retrieve this programmatically.
    See: https://platform.openai.com/docs/models/embeddings

    Arguments
    ---------
        :param model_name: The name of the model to retrieve the embedding dimension for.
    """
    # Mapping of model names to their embedding dimensions
    model_dimensions = {
        "text-embedding-3-large": 3072,
        "text-embedding-3-small": 1536,
        "text-embedding-ada-002": 1536,
        # Add new models and their dimensions here as they become available
    }

    return model_dimensions.get(model_name, -1)  # Return None if model is not found


def get_index_stats(index_name: str) -> DescribeIndexStatsResponse | None:
    """Retrieve the details for a specified index in Pinecone.

    :param index_name: the name of the index for which to retrieve details

    :return: a list of dictionaries containing the metadata for the specified index
    """
    pinecone = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    try:
        index = pinecone.Index(index_name)
    except NotFoundException:
        logging.debug(f"Index {index_name} not found")
        return None

    if index:
        index_stats = index.describe_index_stats()
    logging.debug(f"Index description: ${index_stats}")

    if index_stats:
        return index_stats
    return None


def print_index_stats_diff(index_stats_before, index_stats_after) -> None:
    """Print the difference in the index statistics.

    Arguments
    ---------
        index_stats_before: The index statistics before the operation.
        index_stats_after: The index statistics after the operation.
    """
    if index_stats_before and index_stats_after:
        diff = {
            "num_vectors/documents": index_stats_after.total_vector_count
            - index_stats_before.total_vector_count,
        }
        logging.debug("Index statistics difference:")
        logging.debug(diff)
    else:
        logging.debug("No index statistics to compare")


def create_jwt_token_invite_user(invitee_email, org_admin_email, org_name):
    """
    Create a JWT token for inviting a user to the organization.

    This function performs the following steps:
    1. Loads the LorelAI configuration.
    2. Retrieves the JWT secret key from the configuration.
    3. Creates a JWT token containing the invitee's email, the organization admin's email,
    the organization's name, and an expiration time of 48 hours from the token creation.

    Args:
        invitee_email (str): The email address of the invitee.
        org_admin_email (str): The email address of the organization admin.
        org_name (str): The name of the organization.

    Returns
    -------
        str: A JWT token as a string.
    """
    lorelai_config = load_config("lorelai")

    # Create JWT token
    jwt_secret_key = lorelai_config["jwt_secret_key"]
    token = jwt.encode(
        {
            "invitee_email": invitee_email,
            "org_admin_email": org_admin_email,
            "org_name": org_name,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=48),
        },
        jwt_secret_key,
        algorithm="HS256",
    )
    return token


def send_invite_email(org_admin_email, invitee_email, invite_url):
    """
    Send an invitation email to a user with a registration link.

    This function performs the following steps:
    1. Loads the LorelAI configuration.
    2. Sets up the SMTP server details and email credentials.
    3. Creates the email with the invitee's email, the subject, and the body containing the
    invitation link.
    4. Sends the email via the configured SMTP server.
    5. Logs and returns the status of the email sending process.

    Args:
        org_admin_email (str): The email address of the organization admin sending the invite.
        invitee_email (str): The email address of the invitee.
        invite_url (str): The URL link for the invitee to register.

    Returns
    -------
        bool: True if the email was sent successfully, False otherwise.
    """
    # Email configuration
    lorelai_config = load_config("lorelai")

    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # Port for TLS
    support_email = lorelai_config["support_email"]
    password = lorelai_config[
        "support_email_pass"
    ]  # Use an app password if 2-Step Verification is enabled
    # Create the email
    msg = MIMEMultipart()
    msg["From"] = support_email
    msg["To"] = invitee_email  # Recipient's email address
    msg["Subject"] = "Invite to LorelAI"
    # Body of the email
    body = f"Hello, from {org_admin_email}, follow the link to join LorelAI \n Invite Link:{invite_url}"  # noqa: E501
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Upgrade to a secure connection
            server.login(support_email, password)
            server.send_message(msg)
        logging.info("Email sent successfully!")
        return True
    except Exception as e:
        logging.info(f"Error sending email: {e}")
        return False
