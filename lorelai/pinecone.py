"""Pinecone utilities for Lorelai."""

import pinecone
import logging
import os
import lorelai.utils


class PineconeHelper:
    """Pinecone helper class."""

    def __init__(self):
        """Initialize the PineconeHelper class."""
        self.pinecone_settings = lorelai.utils.load_config("pinecone")
        os.environ["PINECONE_API_KEY"] = self.pinecone_settings["api_key"]

        self.pinecone_client = pinecone.Pinecone()

    def get_index(
        self,
        org: str,
        datasource: str,
        environment: str = "dev",
        env_name: str = "lorelai",
        version: str = "v1",
        create_if_not_exists: bool = True,
    ) -> pinecone.Index:
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

        found = False
        try:
            index = self.pinecone_client.Index(name)
            found = True
        except pinecone.NotFoundException:
            logging.debug(f"Index {name} not found")

        if create_if_not_exists and not found:
            # todo get spec
            index = self.create_index(
                name, self.pinecone_settings["dimension"], self.pinecone_settings["metric"], spec={}
            )

        return index

    def create_index(
        self, index_name: str, dimension: int, metric: str = "cosine", spec: dict = None
    ) -> pinecone.Index:
        """Create a new index in Pinecone.

        Arguments:
        ---------
            index_name (str): The name of the index to create.
            dimension (int): The dimension of the index.
            metric (str): The metric of the index.
            spec (dict): The spec of the index.

        Returns
        -------
            pinecone.Index: The pinecone index.

        """
        self.pinecone_client.create_index(index_name, dimension, metric, spec)
        return self.pinecone_client.Index(index_name)

    def get_index_stats(self, index_name: str) -> pinecone.DescribeIndexStatsResponse | None:
        """Retrieve the details for a specified index in Pinecone.

        :param index_name: the name of the index for which to retrieve details

        :return: a list of dictionaries containing the metadata for the specified index
        """
        try:
            index = pinecone.Index(index_name)
        except pinecone.NotFoundException:
            logging.debug(f"Index {index_name} not found")
            return None

        if index:
            index_stats = index.describe_index_stats()
        logging.debug(f"Index description: ${index_stats}")

        if index_stats:
            return index_stats
        return None

    def print_index_stats_diff(self, index_stats_before, index_stats_after) -> None:
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
