"""
This module contains the ContextRetriever class, which is responsible for retrieving context
for a given question from Pinecone.

The ContextRetriever class manages the
integration with Pinecone and OpenAI services, facilitating the retrieval of relevant document
contexts for specified questions. It leverages Pinecone's vector search capabilities alongside
OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
"""

from typing import Any, Dict, List, Tuple

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from pinecone import Pinecone
from pinecone.core.client.model.fetch_response import FetchResponse
from pinecone.models.index_list import IndexList

from lorelai.utils import load_config, pinecone_index_name


class ContextRetriever:
    """
    A class to retrieve context for a given question from Pinecone.

    This class manages the integration with Pinecone and OpenAI services,
    facilitating the retrieval of relevant document contexts for specified questions.
    It leverages Pinecone's vector search capabilities alongside OpenAI's embeddings and
    language models to generate responses based on the retrieved contexts.
    """

    def __init__(self, org_name: str, user: str):
        """
        Initializes the ContextRetriever instance.

        Parameters:
            org_name (str): The organization name, used for Pinecone index naming.
            user (str): The user name, potentially used for logging or customization.
        """
        self.pinecone_creds = load_config("pinecone")
        self.openai_creds = load_config("openai")
        self.lorelai_creds = load_config("lorelai")

        self.org_name: str = org_name
        self.user: str = user

    def retrieve_context(self, question: str) -> Tuple[List[Document], List[Dict[str, Any]]]:
        """
        Retrieves context for a given question using Pinecone and OpenAI.

        Parameters:
            question (str): The question for which context is being retrieved.

        Returns:
            tuple: A tuple containing the retrieval result and a list of sources for the context.
        """

        index_name = pinecone_index_name(
            org=self.org_name,
            datasource="googledrive",
            environment=self.lorelai_creds["environment"],
            env_name=self.lorelai_creds["environment_slug"],
            version="v1",
        )
        vec_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=OpenAIEmbeddings()
        )
        retriever = vec_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "filter": {"users": {"$eq": self.user}}},
        )

        # list of models:https://github.com/PrithivirajDamodaran/FlashRank
        compressor = FlashrankRerank(top_n=3, model="ms-marco-MultiBERT-L-12")
        # Reranker takes the result from base retriever than reranks those retrived.
        # flash reranker is used as its standalone, lighweight. and free and open source
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        results = compression_retriever.get_relevant_documents(question)

        docs: List[Document] = []
        sources: List[Dict[str, Any]] = []
        for doc in results:
            # Append the whole document object if needed
            docs.append(doc)
            # Create a source entry with title, source, and score (converted to percentage and
            # stringified)
            source_entry = {
                "title": doc.metadata["title"],
                "source": doc.metadata["source"],
                "score": "{:.2f}".format(doc.metadata["relevance_score"] * 100),
                # "score": f"{score*100:.2f}%",
            }
            sources.append(source_entry)

        return docs, sources

    def get_all_indexes(self) -> IndexList:
        """
        Retrieves all indexes in Pinecone along with their metadata.

        Returns:
            list: A list of dictionaries containing the metadata for each index.
        """
        pinecone = Pinecone(api_key=self.pinecone_creds["api_key"])

        return pinecone.list_indexes()

    def get_index_details(self, index_host: str) -> List[Dict[str, Any]]:
        """
        Retrieves details for a specified index in Pinecone.

        Parameters:
            index_host (str): The host of the index for which to retrieve details.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing metadata for vectors
            in the specified index.
        """
        pinecone = Pinecone(api_key=self.pinecone_creds["api_key"])
        index = pinecone.Index(host=index_host)
        if index is None:
            raise ValueError(f"Index {index_host} not found.")

        result = []

        try:
            for ident in index.list():
                vectors: FetchResponse = index.fetch(ids=ident)

                for vector_id, vector_data in vectors.vectors.items():
                    if isinstance(vector_data.metadata, dict):
                        metadata = vector_data.metadata
                        result.append(
                            {
                                "id": vector_id,
                                "title": metadata["title"],
                                "source": metadata["source"],
                                "user": metadata["users"],
                                "when": metadata["when"],
                            }
                        )
        except Exception as e:
            raise ValueError(f"Failed to fetch index details: {e}") from e

        return result
