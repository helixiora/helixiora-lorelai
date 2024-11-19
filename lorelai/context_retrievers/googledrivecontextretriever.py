"""
Module provides classes for integrating / processing Google Drive documents with Pinecone & OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Classes:
    GoogleDriveContextRetriever: Handles Google Drive document retrieval using Pinecone and OpenAI.
"""

import logging
import time

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.document_compressors import FlashrankRerank

from langchain.retrievers.contextual_compression import ContextualCompressionRetriever

from lorelai.context_retriever import (
    ContextRetriever,
    LorelaiContextRetrievalResponse,
    LorelaiContextDocument,
)
from lorelai.pinecone import PineconeHelper


class GoogleDriveContextRetriever(ContextRetriever):
    """Context retriever which retrieves context ie vectors stored in Google drive index."""

    def __init__(
        self, org_name: str, user_email: str, environment: str, environment_slug: str, reranker: str
    ):
        # Set attributes before calling super().__init__()
        self.environment = environment
        self.environment_slug = environment_slug
        self.reranker = reranker

        super().__init__(
            org_name=org_name,
            user_email=user_email,
            environment=environment,
            environment_slug=environment_slug,
            reranker=reranker,
        )

    def retrieve_context(self, question: str) -> LorelaiContextRetrievalResponse:
        """
        Retrieve context for a given question from Google Drive using Pinecone and OpenAI.

        Parameters
        ----------
        question : str
            The question for which context is being retrieved.

        Returns
        -------
        tuple[list[Document], list[dict[str, any]]]
            A tuple containing the retrieval result and a list of sources for the context.
        """
        logging.info(
            f"Retrieving Google Drive context for question: {question} and user: {self.user_email}"
        )
        start_time = time.time()
        try:
            name = PineconeHelper.get_index_name(
                org_name=self.org_name,
                datasource="googledrive",
                environment=self.environment,
                env_name=self.environment_slug,
                version="v1",
            )
            logging.info(f"Using Pinecone index for Google Drive: {name}")
        except Exception as e:
            logging.error(f"Failed to get Pinecone index name for Google Drive: {e}")
            raise e
        try:
            vec_store = PineconeVectorStore(index_name=name, embedding=OpenAIEmbeddings())

        except ValueError as e:
            logging.error(f"Failed to connect to Pinecone: {e}")
            if "not found in your Pinecone project. Did you mean one of the following" in str(e):
                raise ValueError("Index not found. Please index something first.") from e
            raise ValueError(
                "Failed to retrieve context from Google Drive for the provided chat message."
            ) from e

        retriever = vec_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "filter": {"users": {"$eq": self.user_email}}},
        )

        # Reranker takes the result from base retriever than reranks those retrieved.
        # flash reranker is used as its standalone, lightweight. and free and open source
        compressor = FlashrankRerank(top_n=3, model=self.reranker)

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        results = compression_retriever.invoke(input=question)

        context_response = []
        for result in results:
            context_document = LorelaiContextDocument(
                title=result.metadata["title"],
                content=result.page_content,
                link=result.metadata["source"],
                when=result.metadata["modifiedTime"],
                relevance_score=result.metadata["relevance_score"],
                raw_langchain_document=result,
            )
            context_response.append(context_document)
        end_time = time.time()
        logging.info(f"GoogleDriveContextRetriever took: {end_time-start_time}")
        logging.info(f"Found {len(context_response)} context from GoogleDrive")
        return LorelaiContextRetrievalResponse(
            datasource_name="googledrive",
            context=context_response,
        )
