"""This module contains utility functions for the Lorelai package."""

import json
import logging
import os
from pathlib import Path

from pinecone import Pinecone
from pinecone.core.client.exceptions import NotFoundException
from pinecone.core.client.model.describe_index_stats_response import DescribeIndexStatsResponse


def pinecone_index_name(
    org: str,
    datasource: str,
    environment: str = "dev",
    env_name: str = "lorelai",
    version: str = "v1",
) -> str:
    """Return the pinecone index name for the org."""
    parts = [environment, env_name, org, datasource, version]

    name = "-".join(parts)

    name = name.lower().replace(".", "-").replace(" ", "-")

    logging.debug("Index name: %s", name)
    return name


def get_creds_from_os(service: str) -> dict[str, str]:
    """Load credentials from OS env vars.

    Arguments:
    ---------
        service (str): The name of the service (e.g 'openai', 'pinecone') for which to load

    Returns:
    -------
        dict: A dictionary containing the creds for the specified service.

    """
    creds = {}
    # Expected creds
    e_creds = [
        "client_id",
        "project_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_secret",
        "redirect_uris",
        "api_key",
        "environment",
        "environment_slug",
    ]

    # loop through the env vars
    for k in os.environ:
        # check if the service is in the env var
        if service.upper() in k:
            # remove the service name and convert to lower case
            n_k = k.lower().replace(f"{service}_", "")
            if "redirect_uris" in n_k:
                creds[n_k] = os.environ[k].split("|")
            else:
                creds[n_k] = os.environ[k]
    if not any(i in creds for i in e_creds):
        missing_creds = ", ".join([ec for ec in e_creds if ec not in creds])
        msg = "Missing required credentials: "
        raise ValueError(msg, missing_creds)

    return creds


def load_config(service: str) -> dict[str, str]:
    """Load credentials for a specified service from settings.json.

    If file is non-existant or has syntax errors will try to pull from OS env vars.

    Arguments:
    ---------
        service (str): The name of the service (e.g 'openai', 'pinecone') for which to load
        credentials.

    Returns:
    -------
        dict: A dictionary containing the creds for the specified service.

    """
    if Path("./settings.json").is_file():
        with Path("./settings.json").open(encoding="utf-8") as f:
            try:
                creds = json.load(f).get(service, {})

                if service != "google" or service != "lorelai":
                    os.environ[f"{service.upper()}_API_KEY"] = creds.get("api_key", "")

            except ValueError as e:
                print(f"There was an error in your JSON:\n    {e}")
                print("Trying to fallbak to env vars...")
                creds = get_creds_from_os(service)
    else:
        creds = get_creds_from_os(service)

    return creds


def save_google_creds_to_tempfile(refresh_token, token_uri, client_id, client_secret):
    """load the google creds to a tempfile.
    This is needed because the GoogleDriveLoader uses
    the Credentials.from_authorized_user_file method to load the credentials

    :param refresh_token: the refresh token
    :param token_uri: the token uri
    :param client_id: the client id
    :param client_secret: the client secret
    """
    # create a file: Path.home() / ".credentials" / "token.json" to store the credentials so
    # they can be loaded by GoogleDriveLoader's auth process (this uses
    # Credentials.from_authorized_user_file)
    if not os.path.exists(Path.home() / ".credentials"):
        os.makedirs(Path.home() / ".credentials")

    with open(Path.home() / ".credentials" / "token.json", "w", encoding="utf-8") as f:
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
    Returns the dimension of embeddings for a given model name.
    This function currently uses a hardcoded mapping based on documentation,
    as there's no API endpoint to retrieve this programmatically.
    See: https://platform.openai.com/docs/models/embeddings

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
        print(f"Index {index_name} not found")
        return None

    if index:
        index_stats = index.describe_index_stats()
    print(f"Index description: ${index_stats}")

    if index_stats:
        return index_stats
    return None


def print_index_stats_diff(index_stats_before, index_stats_after):
    """prints the difference in the index statistics"""
    if index_stats_before and index_stats_after:
        diff = {
            "num_documents": index_stats_after.num_documents - index_stats_before.num_documents,
            "num_vectors": index_stats_after.num_vectors - index_stats_before.num_vectors,
            "num_partitions": index_stats_after.num_partitions - index_stats_before.num_partitions,
            "num_replicas": index_stats_after.num_replicas - index_stats_before.num_replicas,
            "num_shards": index_stats_after.num_shards - index_stats_before.num_shards,
            "num_segments": index_stats_after.num_segments - index_stats_before.num_segments,
            "num_unique_segments": index_stats_after.num_unique_segments
            - index_stats_before.num_unique_segments,
            "num_unique_shards": index_stats_after.num_unique_shards
            - index_stats_before.num_unique_shards,
            "num_unique_replicas": index_stats_after.num_unique_replicas
            - index_stats_before.num_unique_replicas,
            "num_unique_partitions": index_stats_after.num_unique_partitions
            - index_stats_before.num_unique_partitions,
        }
        print("Index statistics difference:")
        print(diff)
    else:
        print("No index statistics to compare")
