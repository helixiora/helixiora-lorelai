"""Contains the ContextRetriever class, responsible for retrieving context for a question.

The ContextRetriever class manages the
integration with Pinecone and OpenAI services, facilitating the retrieval of relevant document
contexts for specified questions. It leverages Pinecone's vector search capabilities alongside
OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
"""

from langchain_core.documents import Document

from lorelai.utils import load_config

from lorelai.pinecone import PineconeHelper

import importlib
import logging


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
        if not ContextRetriever._allowed:
            raise ValueError("ContextRetriever is not allowed to be instantiated directly.")

        self.pinecone_creds = load_config("pinecone")
        if not self.pinecone_creds or len(self.pinecone_creds) == 0:
            raise ValueError("Pinecone credentials not found.")

        self.__pinecone_helper = PineconeHelper()

        self.openai_creds = load_config("openai")
        if not self.openai_creds or len(self.openai_creds) == 0:
            raise ValueError("OpenAI credentials not found.")

        self.lorelai_creds = load_config("lorelai")
        if not self.lorelai_creds or len(self.lorelai_creds) == 0:
            raise ValueError("Lorelai credentials not found.")

        self.org_name: str = org_name
        self.user: str = user_email

    @staticmethod
    def create(retriever_type: str, org_name: str, user: str):
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
        try:
            module = importlib.import_module(f"lorelai.context_retrievers.{retriever_type.lower()}")
            class_ = getattr(module, retriever_type)
            if not issubclass(class_, ContextRetriever):
                raise ValueError(f"Unsupported context retriever type: {retriever_type}, {class_}")
            logging.debug(f"Creating {retriever_type} instance")
            # Set _allowed to True for the specific class being instantiated
            ContextRetriever._allowed = True
            instance = class_(org_name=org_name, user_email=user)
            logging.debug(f"Created {retriever_type} instance")
            ContextRetriever._allowed = False
            return instance
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"Exception in creating context retriever type: {retriever_type}, {class_}: {exc}"
            ) from exc

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

    def get_pinecone(self):
        """
        Get the PineconeHelper instance.

        Returns
        -------
        PineconeHelper
            The PineconeHelper instance.
        """
        return self.__pinecone_helper
