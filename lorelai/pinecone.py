"""Pinecone utilities for Lorelai."""

import logging


def index_name(
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
