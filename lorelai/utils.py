"""Contains utility functions for the Lorelai package."""

import logging
import sys
import re

from flask import current_app

import jwt
import datetime
from itertools import chain

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.models import User


def get_user_id_by_email(email: str) -> int:
    """
    Get the user ID by email.

    Parameters
    ----------
    email : str
        The email of the user.

    Returns
    -------
    int
        The user ID.
    """
    user = User.query.filter_by(email=email).first()
    return user.id if user else None


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

    return model_dimensions.get(model_name, -1)  # Return -1 if model is not found


def create_jwt_token_invite_user(invitee_email, org_admin_email, org_name):
    """
    Create a JWT token for inviting a user to the organisation.

    This function performs the following steps:
    1. Loads the LorelAI configuration.
    2. Retrieves the JWT secret key from the configuration.
    3. Creates a JWT token containing the invitee's email, the organisation admin's email,
    the organisation's name, and an expiration time of 48 hours from the token creation.

    Args:
        invitee_email (str): The email address of the invitee.
        org_admin_email (str): The email address of the organisation admin.
        org_name (str): The name of the organisation.

    Returns
    -------
        str: A JWT token as a string.
    """
    # Create JWT token
    jwt_secret_key = current_app.config["JWT_SECRET_KEY"]
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
        org_admin_email (str): The email address of the organisation admin.
        invitee_email (str): The email address of the invitee.
        invite_url (str): The URL to register the invitee.

    Returns
    -------
        bool: True if the email was sent successfully, False otherwise.
    """
    template_id = current_app.config["SENDGRID_INVITE_TEMPLATE_ID"]

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

    sendgridapikey = current_app.config["SENDGRID_API_KEY"]

    try:
        sg = SendGridAPIClient(sendgridapikey)
        response = sg.send(message)
        logging.debug(f"Email sent successfully. Status code: {response.status_code}, \
body: {response.body}, headers: {response.headers}")

        return True
    except Exception as e:
        logging.debug(e.message)
        return False


def get_size(obj, seen=None):
    """
    Recursively calculate the memory size of an object, including its nested elements.

    This function computes the total memory size of an object by traversing its contents. It handles
    common data structures like dictionaries, lists, sets, and custom objects that may contain
    nested elements. To avoid counting the same object multiple times, it tracks processed objects
    using their IDs.

    Args:
        obj: The object whose size is to be calculated.
        seen (set, optional): A set of object IDs that have already been processed. This prevents
                              double-counting in case of circular references. Defaults to None.

    Returns
    -------
        int: The total memory size of the object in bytes.
    """
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(get_size(v, seen) for v in obj.values())
        size += sum(get_size(k, seen) for k in obj.keys())
    elif hasattr(obj, "__dict__"):
        size += get_size(obj.__dict__, seen)
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, bytearray)):  # noqa: UP038
        size += sum(get_size(i, seen) for i in obj)
    return size


def clean_text_for_vector(text):
    """
    Clean a given text string by removing HTML tags, control characters, extra whitespace.

    and repeated punctuation.

    This function is useful for preprocessing text before vectorization or other natural language
    processing tasks. It removes unnecessary elements like HTML tags, newlines, tabs, and repeated
    punctuation, while also ensuring the text is trimmed of excess whitespace.

    Args:
        text (str): The input string to be cleaned.

    Returns
    -------
        str: The cleaned version of the input text.
    """
    # Remove HTML tags
    text = re.sub("<[^<]+?>", "", text)
    # Remove control characters (newline, tab, carriage return)
    text = re.sub(r"[\n\t\r]+", " ", text)
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove repeated punctuation
    text = re.sub(r"([!?.]){2,}", r"\1", text)
    return text


def batch_embed_langchain_documents(embeddings_model, text_docs, batch_size=100):
    """
    Embed documents in batches to avoid memory issues with large lists.

    Args:
        embeddings_model: Model that provides the embed_documents method.
        text_docs (list of str): List of text documents to embed.
        batch_size (int): Number of documents per batch.

    Returns
    -------
        list: List of embedding vectors in the original order.
    """
    # Split text_docs into batches
    batches = [text_docs[i : i + batch_size] for i in range(0, len(text_docs), batch_size)]

    # Embed each batch and collect results
    embeds = [embeddings_model.embed_documents(batch) for batch in batches]

    # Flatten the list of lists into a single list, preserving order
    embeds_flat = list(chain.from_iterable(embeds))

    return embeds_flat
