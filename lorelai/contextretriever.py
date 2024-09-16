"""Contains the ContextRetriever class, responsible for retrieving context for a question.

The ContextRetriever class manages the
integration with Pinecone and OpenAI services, facilitating the retrieval of relevant document
contexts for specified questions. It leverages Pinecone's vector search capabilities alongside
OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
"""

from langchain_core.documents import Document
from pinecone import Pinecone
from pinecone.models.index_list import IndexList

from lorelai.utils import load_config


class ContextRetriever:
    """
    Manage the integration with Pinecone and OpenAI services to retrieve relevant document contexts.

    or specified questions.

    The ContextRetriever class leverages Pinecone's vector search capabilities alongside
    OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
    """

    _allowed = False  # Flag to control constructor access

    def __init__(self, org_name: str, user_email: str):
        """
        Initialize the ContextRetriever instance.

        Parameters
        ----------
            org_name (str): The organization name, used for Pinecone index naming.
            user (str): The user name, potentially used for logging or customization.
        """
        if not self._allowed:
            raise Exception("This class should be instantiated through a create() factory method.")

        self.pinecone_creds = load_config("pinecone")
        if not self.pinecone_creds or len(self.pinecone_creds) == 0:
            raise ValueError("Pinecone credentials not found.")

        self.openai_creds = load_config("openai")
        if not self.openai_creds or len(self.openai_creds) == 0:
            raise ValueError("OpenAI credentials not found.")

        self.lorelai_creds = load_config("lorelai")
        if not self.lorelai_creds or len(self.lorelai_creds) == 0:
            raise ValueError("Lorelai credentials not found.")

        self.org_name: str = org_name
        self.user: str = user_email

    @staticmethod
    def create(retriever_type="GoogleDriveContextRetriever", org_name="", user=""):
        """
        Create instance of derived class based on the class name.

        Parameters
        ----------
        retriever_type : str
            The type of the Retriever, used to instantiate the appropriate subclass.
        org_name : str
            The organization name, used for Pinecone index naming.
        user : str
            The user name, potentially used for logging or customization.

        Returns
        -------
        ContextRetriever
            An instance of the specified ContextRetriever subclass.
        """
        ContextRetriever._allowed = True
        class_ = globals().get(retriever_type)
        if class_ is None or not issubclass(class_, ContextRetriever):
            ContextRetriever._allowed = False
            raise ValueError(f"Unsupported model type: {retriever_type}")
        instance = class_(org_name, user)
        ContextRetriever._allowed = False
        return instance

    def list_subclasses():
        """List all subclasses of ContextRetriever."""
        return ContextRetriever.__subclasses__()

    def retrieve_context(self, question: str) -> tuple[list[Document], list[dict[str, any]]]:
        """
        Retrieve context for a given question using Pinecone and OpenAI.

        Parameters
        ----------
            question (str): The question for which context is being retrieved.

        Returns
        -------
            tuple: A tuple containing the retrieval result and a list of sources for the context.
        """
        raise NotImplementedError

    def get_all_indexes(self) -> IndexList:
        """
        Retrieve all indexes in Pinecone along with their metadata.

        Returns
        -------
            list: A list of dictionaries containing the metadata for each index.
        """
        pinecone = Pinecone(api_key=self.pinecone_creds["api_key"])

        if pinecone is None:
            raise ValueError("Failed to connect to Pinecone.")

        return pinecone.list_indexes()

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
        pinecone = Pinecone(api_key=self.pinecone_creds["api_key"])

        if pinecone is None:
            raise ValueError("Failed to connect to Pinecone.")

        index = pinecone.Index(host=index_host)
        if index is None:
            raise ValueError(f"Index {index_host} not found.")

        result = []

        try:
            for ident in index.list():
                vectors: FetchResponse = index.fetch(ids=ident)  # noqa: F821

                for vector_id, vector_data in vectors.vectors.items():
                    if isinstance(vector_data.metadata, dict):
                        metadata = vector_data.metadata
                        result.append(
                            {
                                "id": vector_id,
                                "title": metadata["title"] if "title" in metadata else "No Title",
                                "source": metadata["source"]
                                if "source" in metadata
                                else "No Source",
                                "user": metadata["users"] if "users" in metadata else "No Users",
                                "when": metadata["when"] if "when" in metadata else "No When",
                            }
                        )
        except Exception as e:
            raise ValueError(f"Failed to fetch index details: {e}") from e

        return result
