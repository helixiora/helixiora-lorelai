"""Contains the ContextRetriever class, responsible for retrieving context for a question.

The ContextRetriever class manages the
integration with Pinecone and OpenAI services, facilitating the retrieval of relevant document
contexts for specified questions. It leverages Pinecone's vector search capabilities alongside
OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
"""

from langchain.schema import Document

from lorelai.pinecone import PineconeHelper

import importlib
import logging

from pydantic import BaseModel


class LorelaiContextDocument(BaseModel):
    """A Pydantic model for context retrieval."""

    title: str
    content: str
    link: str
    when: str
    relevance_score: float
    raw_langchain_document: Document


class LorelaiContextRetrievalResponse(BaseModel):
    """A Pydantic model for context retrieval."""

    datasource_name: str
    context: list[LorelaiContextDocument]


class ContextRetriever:
    """
    Manage the integration with Pinecone and OpenAI services to retrieve relevant document contexts.

    or specified questions.

    The ContextRetriever class leverages Pinecone's vector search capabilities alongside
    OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
    """

    _allowed = False  # Flag to control constructor access

    def __init__(
        self, org_name: str, user_email: str, environment: str, environment_slug: str, reranker: str
    ):
        """
        Initialize the ContextRetriever instance.

        Parameters
        ----------
            org_name (str): The organization name, used for Pinecone index naming.
            user_email (str): The user name, potentially used for logging or customization.
            environment (str): The environment name, used for Pinecone index naming.
            environment_slug (str): The environment slug, used for Pinecone index naming.
            reranker (str): The reranker name, used for reranking the retrieved context.
        """
        if not ContextRetriever._allowed:
            raise ValueError("ContextRetriever is not allowed to be instantiated directly.")

        self.__pinecone_helper = PineconeHelper()

        self.org_name: str = org_name
        self.user: str = user_email

        self.environment: str = environment
        self.environment_slug: str = environment_slug
        self.reranker: str = reranker

    @staticmethod
    def create(
        retriever_type: str,
        org_name: str,
        user: str,
        environment: str,
        environment_slug: str,
        reranker: str,
    ):
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
        environment : str
            The environment name, used for Pinecone index naming.
        environment_slug : str
            The environment slug, used for Pinecone index naming.
        reranker : str
            The reranker name, used for reranking the retrieved context.

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
            instance = class_(
                org_name=org_name,
                user_email=user,
                environment=environment,
                environment_slug=environment_slug,
                reranker=reranker,
            )
            logging.debug(f"Created {retriever_type} instance")
            ContextRetriever._allowed = False
            return instance
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"Exception in creating context retriever type: {retriever_type}: {exc}"
            ) from exc

    def retrieve_context(self, question: str) -> LorelaiContextRetrievalResponse:
        """
        Retrieve context for a given question using Pinecone and OpenAI.

        Parameters
        ----------
            question (str): The question for which context is being retrieved.

        Returns
        -------
            list[Document]: The list of documents retrieved from Pinecone.
        """
        raise NotImplementedError

    def get_pinecone(self) -> PineconeHelper:
        """
        Get the PineconeHelper instance.

        Returns
        -------
        PineconeHelper
            The PineconeHelper instance.
        """
        return self.__pinecone_helper
