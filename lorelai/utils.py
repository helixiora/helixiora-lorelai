"""Contains utility functions for the Lorelai package."""

import json
import logging
import os
from pathlib import Path

import mysql.connector


import jwt
import datetime

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


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
    access_token: str,
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
                    "access_token": access_token,
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
    Send an invitation email to a user.

    This function performs the following steps:
    1. Sends an email to the invitee containing the invitation URL.
    2. Logs and returns the status of the email sending process.

    Args
    ----
        org_admin_email (str): The email address of the organization admin.
        invitee_email (str): The email address of the invitee.
        invite_url (str): The URL to register the invitee.

    Returns
    -------
        bool: True if the email was sent successfully, False otherwise.
    """
    sendgridconfig = load_config("sendgrid")
    template_id = sendgridconfig["invite_template_id"]

    return send_templated_email(
        from_addr=org_admin_email,
        to_addr=invitee_email,
        template_id=template_id,
        template_data={
            "invitee": invitee_email,
            "inviter": org_admin_email,
            "link": invite_url,
        },
    )


def send_templated_email(
    from_addr: str,
    to_addr: str,
    template_id: str,
    template_data: dict,
):
    """
    Send an email.

    This function performs the following steps:
    1. Loads the LorelAI configuration.
    2. Sets up the SMTP server details and email credentials.
    3. Creates the email with the sender's email, the recipient's email, the subject, and the body.
    4. Sends the email via the configured SMTP server.
    5. Logs and returns the status of the email sending process.

    Args:
        from_addr (str): The email address of the sender.
        to_addr (str): The email address of the recipient.
        subject (str): The subject of the email.
        body (str): The body of the email.

    Returns
    -------
        bool: True if the email was sent successfully, False otherwise.
    """
    message = Mail(
        from_email=from_addr,
        to_emails=to_addr,
    )
    message.template_id = template_id
    message.dynamic_template_data = template_data

    sendgridconfig = load_config("sendgrid")
    sendgridapikey = sendgridconfig["api_key"]

    try:
        sg = SendGridAPIClient(sendgridapikey)
        response = sg.send(message)
        logging.debug(f"Email sent successfully. Status code: {response.status_code}, \
body: {response.body}, headers: {response.headers}")

        return True
    except Exception as e:
        logging.debug(e.message)
        return False
