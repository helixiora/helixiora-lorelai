"""
Module provides classes for integrating and processing Slack messages with Pinecone and OpenAI.

It includes OAuth handling, message retrieval, embedding generation, and loading data into Pinecone.

Note: filename is tied to the name of the class.

Classes:
    SlackContextRetriever: Handles Slack message retrieval using Pinecone and OpenAI.
"""

import logging

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.document_compressors import FlashrankRerank
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

    def __init__(self, org_name: str, user_email: str):
        """
        Initialize the SlackContextRetriever instance.

        Parameters
        ----------
        org_name : str
            The organization name, used for Pinecone index naming.
        user_email : str
            The user email, potentially used for logging or customization.
        """
        super().__init__(org_name=org_name, user_email=user_email)

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
            f"[SlackContextRetriever] Retrieving context for q: {question} and user: {self.user}"
        )

        index_name = PineconeHelper.get_index_name(
            org=self.org_name,
            datasource=DATASOURCE_SLACK,
            environment=self.lorelai_creds["environment"],
            env_name=self.lorelai_creds["environment_slug"],
            version="v1",
        )
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
            search_kwargs={"k": 10, "filter": {"users": {"$eq": self.user}}},
        )

        compressor = FlashrankRerank(top_n=3, model=self.lorelai_creds["reranker"])
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        results = compression_retriever.invoke(input=question)

        context_response = []
        for result in results:
            context_document = LorelaiContextDocument(
                title=f"Thread in {result.metadata['channel_name']} on {result.metadata['msg_ts']}",
                content=result.page_content,
                link=result.metadata["source"],
                when=result.metadata["msg_ts"],
                relevance_score=result.metadata["relevance_score"],
                raw_langchain_document=result,
            )
            context_response.append(context_document)

        return LorelaiContextRetrievalResponse(
            datasource_name=DATASOURCE_SLACK,
            context=context_response,
        )
