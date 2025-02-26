"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Note: filename is tied to the name of the class.

Classes:
    SlackContextRetriever: Handles Slack message retrieval using Pinecone and OpenAI.
"""

import logging
import time

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from rerankers import Reranker
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever

from lorelai.context_retriever import (
    ContextRetriever,
    LorelaiContextRetrievalResponse,
    LorelaiContextDocument,
)
from app.helpers.datasources import DATASOURCE_SLACK
from lorelai.pinecone import PineconeHelper


class SlackContextRetriever(ContextRetriever):
    """Context retriever which retrieves context ie vectors stored in Slack index."""

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
        Retrieve context for a given question from Slack using Pinecone and OpenAI.

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
            f"[SlackContextRetriever] Retrieving context for q: {question} and u: {self.user_email}"
        )
        start_time = time.time()
        try:
            index_name = PineconeHelper.get_index_name(
                org_name=self.org_name,
                datasource=DATASOURCE_SLACK,
                environment=self.environment,
                environment_slug=self.environment_slug,
                version="v1",
            )
        except Exception as e:
            logging.error(f"[SlackContextRetriever] Failed to get Pinecone index name: {e}")
            raise e
        logging.info(f"[SlackContextRetriever] Using Pinecone index: {index_name}")

        try:
            vec_store = PineconeVectorStore(index_name=index_name, embedding=OpenAIEmbeddings())
        except ValueError as e:
            logging.error(f"[SlackContextRetriever] Failed to connect to Pinecone: {e}")
            if "not found in your Pinecone project. Did you mean one of the following" in str(e):
                raise ValueError("Index not found. Please index something first.") from e
            raise ValueError("Failed to retrieve context for the provided chat message.") from e

        retriever = vec_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "filter": {"users": {"$eq": self.user_email}}},
        )

        ranker = Reranker(model_name=self.reranker, model_type="flashrank", verbose=1)

        compressor = ranker.as_langchain_compressor(k=3)
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        results = compression_retriever.invoke(input=question)

        context_response = []
        for result in results:
            context_document = LorelaiContextDocument(
                title=f"Conversation in {result.metadata['channel_name']} on \
{result.metadata['msg_ts']}",
                content=result.page_content,
                link=result.metadata["source"],
                when=result.metadata["msg_ts"],
                relevance_score=result.metadata["relevance_score"],
                raw_langchain_document=result,
            )
            context_response.append(context_document)
        end_time = time.time()
        logging.info(f"SlackContextRetriever took: {end_time - start_time}")
        logging.info(f"Found {len(context_response)} context from Slack")
        return LorelaiContextRetrievalResponse(
            datasource_name=DATASOURCE_SLACK,
            context=context_response,
        )
