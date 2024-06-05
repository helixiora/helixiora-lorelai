"""
This module contains the ContextRetriever class, which is responsible for retrieving context
for a given question from Pinecone.

The ContextRetriever class manages the
integration with Pinecone and OpenAI services, facilitating the retrieval of relevant document
contexts for specified questions. It leverages Pinecone's vector search capabilities alongside
OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
"""

import logging
from typing import Any, Dict, List, Tuple

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from pinecone.models.index_list import IndexList

from lorelai.utils import load_config, pinecone_index_name

class ContextRetriever:
    _allowed = False  # Flag to control constructor access

    def __init__(self, org_name: str, user: str):
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
        self.user: str = user

    @staticmethod
    def create(model_type="GoogleDriveContextRetriever", org_name="", user=""):
        """Factory method to create instances of derived classes based on the class name."""
        ContextRetriever._allowed = True
        class_ = globals().get(model_type)
        if class_ is None or not issubclass(class_, ContextRetriever):
            ContextRetriever._allowed = False
            raise ValueError(f"Unsupported model type: {model_type}")
        instance = class_(org_name, user)
        ContextRetriever._allowed = False
        return instance
    
    def list_subclasses():
        """List all subclasses of ContextRetriever."""
        return ContextRetriever.__subclasses__()

    def retrieve_context(self, question: str) -> Tuple[List[Document], List[Dict[str, Any]]]:
        raise NotImplementedError
    
    def get_index_details(self, index_host: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_all_indexes(self) -> IndexList:
        """
        Retrieves all indexes in Pinecone along with their metadata.

        Returns:
            list: A list of dictionaries containing the metadata for each index.
        """
        pinecone = Pinecone(api_key=self.pinecone_creds["api_key"])

        if pinecone is None:
            raise ValueError("Failed to connect to Pinecone.")

        return pinecone.list_indexes()

    def get_index_details(self, index_host: str) -> List[Dict[str, Any]]:
        pinecone = Pinecone(api_key=self.pinecone_creds["api_key"])

        if pinecone is None:
            raise ValueError("Failed to connect to Pinecone.")

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
class GoogleDriveContextRetriever(ContextRetriever):
    def __init__(self, org_name: str, user: str):
        super().__init__(org_name, user)

    def retrieve_context(self, question: str) -> Tuple[List[Document], List[Dict[str, Any]]]:
        logging.info(f"Retrieving context for question: {question} and user: {self.user}")

        index_name = pinecone_index_name(
            org=self.org_name,
            datasource="googledrive",
            environment=self.lorelai_creds["environment"],
            env_name=self.lorelai_creds["environment_slug"],
            version="v1",
        )
        logging.info(f"Using Pinecone index: {index_name}")
        vec_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=OpenAIEmbeddings()
        )

        if vec_store is None:
            raise ValueError(f"Index {index_name} not found.")

        retriever = vec_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "filter": {"users": {"$eq": self.user}}},
        )

        compressor = FlashrankRerank(top_n=3, model="ms-marco-MiniLM-L-12-v2")
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        results = compression_retriever.invoke(question)
        logging.info(
            f"Retrieved {len(results)} documents from index {index_name} for question: {question}"
        )

        docs: List[Document] = []
        sources: List[Dict[str, Any]] = []
        for doc in results:
            docs.append(doc)
            score = doc.metadata["relevance_score"] * 100
            source_entry = {
                "title": doc.metadata["title"],
                "source": doc.metadata["source"],
                "score": "{:.2f}".format(score),
            }
            sources.append(source_entry)
        logging.debug(f"Context: {docs} Sources: {sources}")
        return docs, sources

class SlackContextRetriever(ContextRetriever):
    def __init__(self, org_name: str, user: str):
        super().__init__(org_name, user)

    def retrieve_context(self, question: str) -> Tuple[List[Document], List[Dict[str, Any]]]:
        logging.info(f"Retrieving context for question: {question} and user: {self.user}")

        index_name = pinecone_index_name(
            org=self.org_name,
            datasource="slack",
            environment=self.lorelai_creds["environment"],
            env_name=self.lorelai_creds["environment_slug"],
            version="v1",
        )
        logging.info(f"Using Pinecone index: {index_name}")
        vec_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=OpenAIEmbeddings()
        )

        if vec_store is None:
            raise ValueError(f"Index {index_name} not found.")

        retriever = vec_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "filter": {"users": {"$eq": self.user}}},
        )

        compressor = FlashrankRerank(top_n=3, model="ms-marco-MiniLM-L-12-v2")
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=retriever
        )

        results = compression_retriever.invoke(question)
        logging.info(
            f"Retrieved {len(results)} documents from index {index_name} for question: {question}"
        )

        docs: List[Document] = []
        sources: List[Dict[str, Any]] = []
        for doc in results:
            docs.append(doc)
            score = doc.metadata["relevance_score"] * 100
            source_entry = {
                "title": doc.metadata["channel_name"],
                "source": doc.metadata["source"],
                "score": "{:.2f}".format(score),
            }
            sources.append(source_entry)
        logging.debug(f"Context: {docs} Sources: {sources}")
        return docs, sources

