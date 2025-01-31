"""Pinecone utilities for Lorelai."""

import pinecone
import logging
import os
from flask import current_app
from pinecone import ServerlessSpec, FetchResponse


class PineconeHelper:
    """Pinecone helper class."""

    def __init__(self):
        """Initialize the PineconeHelper class."""
        os.environ["PINECONE_API_KEY"] = current_app.config["PINECONE_API_KEY"]
        self.pinecone_client = pinecone.Pinecone()

    @staticmethod
    def get_index_name(
        org_name: str,
        datasource: str,
        environment: str = "dev",
        environment_slug: str = "lorelai",
        version: str = "v1",
    ) -> str:
        """Return the pinecone index name for the org.

        Arguments:
        ---------
            org_name (str): The name of the organisation.
            datasource (str): The name of the datasource.
            environment (str): The environment (e.g. dev, prod).
            environment_slug (str): The environment slug (e.g. lorelai, walter).
            version (str): The version of the index (e.g. v1).

        Returns
        -------
            str: The name of the pinecone index in format:
                {environment}-{environment_slug}-{org_name}-{datasource}-{version}

        """
        parts = [environment, environment_slug, org_name, datasource, version]
        name = "-".join(parts)
        name = name.lower().replace(".", "-").replace(" ", "-")
        return name

    def get_index(
        self,
        org_name: str,
        datasource: str,
        environment: str = "dev",
        environment_slug: str = "lorelai",
        version: str = "v1",
        create_if_not_exists: bool = True,
    ) -> tuple[pinecone.Index, str]:
        """Return the pinecone index for the org.

        Arguments:
        ---------
            org_name (str): The name of the organisation.
            datasource (str): The name of the datasource.
            environment (str): The environment (e.g. dev, prod).
            environment_slug (str): The environment slug (e.g. lorelai, walter).
            version (str): The version of the index (e.g. v1).
            create_if_not_exists (bool): Whether to create the index if it doesn't exist.

        Returns
        -------
            tuple[pinecone.Index, str]: The pinecone index and the name of the pinecone index.

        """
        name = self.get_index_name(
            org_name=org_name,
            datasource=datasource,
            environment=environment,
            environment_slug=environment_slug,
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
        return list(self.pinecone_client.list_indexes())

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
        all_keys = set()

        logging.debug(f"Starting to fetch details for index: {index_host}")

        # First pass: collect all possible metadata keys
        try:
            vector_ids = list(index.list())  # Convert generator to list
            logging.debug(f"Found {len(vector_ids)} vectors in index")

            for ident in vector_ids:
                vectors: FetchResponse = index.fetch(ids=ident)
                logging.debug(f"Fetched vector {ident}, got {len(vectors.vectors)} results")

                for vector_id, vector_data in vectors.vectors.items():
                    if isinstance(vector_data.metadata, dict):
                        metadata = vector_data.metadata
                        if isinstance(metadata, dict):
                            logging.debug(f"Vector {vector_id} metadata keys: {metadata.keys()}")
                            all_keys.update(metadata.keys())
                            all_keys.add("id")  # Ensure id is always included

            logging.debug(f"All metadata keys found: {all_keys}")
        except Exception as e:
            raise ValueError(f"Failed to fetch index details: {e}") from e

        # Second pass: create normalized metadata dictionaries
        try:
            for ident in list(index.list()):  # Convert generator to list
                vectors: FetchResponse = index.fetch(ids=ident)
                for vector_id, vector_data in vectors.vectors.items():
                    if isinstance(vector_data.metadata, dict):
                        metadata = vector_data.metadata
                        if isinstance(metadata, dict):
                            # Create a dictionary with all keys initialized to None
                            normalized_metadata = {key: None for key in all_keys}
                            # Update with actual values from metadata
                            normalized_metadata.update(metadata)
                            # Add the ID
                            normalized_metadata["id"] = vector_id
                            logging.debug(
                                f"Normalized metadata for vector {vector_id}: {normalized_metadata}"
                            )
                            result.append(normalized_metadata)
        except Exception as e:
            raise ValueError(f"Failed to fetch index details: {e}") from e

        logging.debug(f"Total vectors processed: {len(result)}")
        return result

    def delete_user_datasource_vectors(
        self, user_id: int, datasource_name: str, user_email: str, org_name: str
    ) -> None:
        """Delete or update vectors for a specific user and datasource from Pinecone.

        If the user is the only one in the users list, the vector is deleted.
        If there are other users, the user is removed from the users list.

        Args:
            user_id (int): The ID of the user whose vectors should be deleted/updated
            datasource_name (str): Name of the datasource whose vectors should be deleted/updated
            user_email (str): The email address of the user whose vectors should be deleted/updated
            org_name (str): The name of the organization to determine the index name
        """
        try:
            # Get the index using the dynamic index name
            index, _ = self.get_index(
                org_name=org_name,
                datasource=datasource_name,
                environment=current_app.config["LORELAI_ENVIRONMENT"],  # e.g. 'dev'
                environment_slug=current_app.config["LORELAI_ENVIRONMENT_SLUG"],  # e.g. 'walter'
                version="v1",
            )

            # First, find all vectors where this user's email is in the users list
            vector_query = index.query(
                vector=[0.0] * int(current_app.config["PINECONE_DIMENSION"]),
                filter={"users": {"$in": [user_email]}},
                top_k=10000,
                include_metadata=True,
            )

            vectors_to_delete = []
            updated_vectors = 0
            for match in vector_query.matches:
                users = match.metadata.get("users", [])
                if len(users) == 1 and users[0] == user_email:
                    # This is the only user, delete the vector
                    vectors_to_delete.append(match.id)
                else:
                    # Remove the user from the users list
                    users.remove(user_email)
                    index.update(id=match.id, set_metadata={"users": users})
                    updated_vectors += 1

            # Delete vectors where this was the only user
            if vectors_to_delete:
                index.delete(ids=vectors_to_delete)

            logging.info(
                f"Successfully processed vectors for user {user_email} (ID: {user_id}) and "
                f"datasource {datasource_name} in org {org_name}. "
                f"Deleted {len(vectors_to_delete)} vectors and updated users list in "
                f"{updated_vectors} vectors."
            )

        except Exception as e:
            logging.error(
                f"Error processing vectors for user {user_email} (ID: {user_id}) and datasource "
                f"{datasource_name} in org {org_name}: {str(e)}"
            )
            raise


def delete_user_datasource_vectors(
    user_id: int, datasource_name: str, user_email: str, org_name: str
) -> None:
    """Delete all vectors for a specific user and datasource from Pinecone.

    This is a convenience function that creates a PineconeHelper instance and calls
    delete_user_datasource_vectors on it.

    Args:
        user_id (int): The ID of the user whose vectors should be deleted
        datasource_name (str): The name of the datasource whose vectors should be deleted
        user_email (str): The email address of the user whose vectors should be deleted
        org_name (str): The name of the organization to determine the index name
    """
    helper = PineconeHelper()
    helper.delete_user_datasource_vectors(
        user_id=user_id,
        datasource_name=datasource_name,
        user_email=user_email,
        org_name=org_name,
    )
