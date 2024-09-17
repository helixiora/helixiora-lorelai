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
from langchain_core.documents import Document

from lorelai.context_retriever import ContextRetriever


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

    def retrieve_context(self, question: str) -> tuple[list[Document], list[dict[str, any]]]:
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

        index = self.get_pinecone().get_index(
            org=self.org_name,
            datasource="slack",
            environment=self.lorelai_creds["environment"],
            env_name=self.lorelai_creds["environment_slug"],
            version="v1",
        )
        logging.info(f"[SlackContextRetriever] Using Pinecone index: {index}")

        try:
            vec_store = PineconeVectorStore(index=index, embedding=OpenAIEmbeddings())
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

        results = compression_retriever.invoke(question)
        logging.info(
            f"Retrieved {len(results)} documents from index {index} for question: {question}"
        )

        docs: list[Document] = []
        sources: list[dict[str, any]] = []
        for doc in results:
            docs.append(doc)
            score = doc.metadata["relevance_score"] * 100
            source_entry = {
                "title": doc.metadata["channel_name"],
                "source": doc.metadata["source"],
                "score": f"{score:.2f}",
            }
            sources.append(source_entry)
        return docs, sources
