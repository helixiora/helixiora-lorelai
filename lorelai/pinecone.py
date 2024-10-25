"""Pinecone utilities for Lorelai."""

import pinecone
import logging
import os
from flask import current_app
from pinecone import ServerlessSpec


class PineconeHelper:
    """Pinecone helper class."""

    def __init__(self):
        """Initialize the PineconeHelper class."""
        os.environ["PINECONE_API_KEY"] = current_app.config["PINECONE_API_KEY"]

        self.pinecone_client = pinecone.Pinecone()

    @staticmethod
    def get_index_name(
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
        return name

    def get_index(
        self,
        org: str,
        datasource: str,
        environment: str = "dev",
        env_name: str = "lorelai",
        version: str = "v1",
        create_if_not_exists: bool = True,
    ) -> tuple[pinecone.Index, str]:
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
        name = self.get_index_name(
            org=org,
            datasource=datasource,
            environment=environment,
            env_name=env_name,
            version=version,
        )

        region = current_app.config["PINECONE_REGION"]

        found = False
        try:
            index = self.pinecone_client.Index(name)
            found = True
        except pinecone.NotFoundException:
            logging.debug(f"Index {name} not found")

        if create_if_not_exists and not found:
            # todo get spec
            index = self.create_index(
                name,
                int(current_app.config["PINECONE_DIMENSION"]),
                current_app.config["PINECONE_METRIC"],
                ServerlessSpec(cloud="aws", region=region),
            )

        return index, name

    def list_indexes(self) -> list[str]:
        """List all indexes in Pinecone.

        Returns
        -------
            list[str]: The list of index names.
        """
        return self.pinecone_client.list_indexes()

    def create_index(
        self, index_name: str, dimension: int, metric: str = "cosine", spec: ServerlessSpec = None
    ) -> pinecone.Index:
        """Create a new index in Pinecone.

        Arguments:
        ---------
            index_name (str): The name of the index to create.
            dimension (int): The dimension of the index.
            metric (str): The metric of the index.
            spec (ServerlessSpec): The spec of the index.

        Returns
        -------
            pinecone.Index: The pinecone index.

        """
        if spec is None:
            spec = ServerlessSpec(
                cloud="aws",
                region=current_app.config["PINECONE_REGION"],
                dimension=int(current_app.config["PINECONE_DIMENSION"]),
            )
        else:
            if not isinstance(spec, ServerlessSpec):
                raise ValueError("spec must be a ServerlessSpec")

        self.pinecone_client.create_index(
            name=index_name, dimension=dimension, metric=metric, spec=spec
        )
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

    def get_index_details(self, index_host: str) -> list[dict[str, any]]:
        """
        Get details of a specific index.

        Parameters
        ----------
        index_host : str
            The host name of the index.

        Returns
        -------
        list[dict[str, any]]
            A list of dictionaries containing the metadata for each vector in the index.
        """
        index = self.pinecone_client.Index(host=index_host)
        if index is None:
            raise ValueError(f"Index {index_host} not found.")

        result = []

        try:
            for ident in index.list():
                vectors: FetchResponse = index.fetch(ids=ident)  # noqa: F821

                for vector_id, vector_data in vectors.vectors.items():
                    if isinstance(vector_data.metadata, dict):
                        metadata = vector_data.metadata
                        if isinstance(metadata, dict):
                            if "title" in metadata:
                                result.append(
                                    {  # google driv
                                        "id": vector_id,
                                        "title": metadata["title"],
                                        "source": metadata["source"],
                                        "users": metadata["users"],
                                        "text": metadata["text"],
                                        "when": metadata["when"],
                                    }
                                )
                            if "msg_ts" in metadata:
                                result.append(
                                    {  # slack
                                        "id": vector_id,
                                        "text": metadata["text"],
                                        "source": metadata["source"],
                                        "msg_ts": metadata["msg_ts"],
                                        "channel_name": metadata["channel_name"],
                                        "users": metadata["users"],
                                    }
                                )
        except Exception as e:
            raise ValueError(f"Failed to fetch index details: {e}") from e

        return result
