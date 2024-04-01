"""
This module contains the ContextRetriever class, which is responsible for retrieving context
for a given question from Pinecone.

The ContextRetriever class manages the
integration with Pinecone and OpenAI services, facilitating the retrieval of relevant document
contexts for specified questions. It leverages Pinecone's vector search capabilities alongside
OpenAI's embeddings and language models to generate responses based on the retrieved contexts.
"""
from typing import Tuple, List, Dict, Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from pinecone.models.index_list import IndexList
from lorelai.utils import pinecone_index_name, load_creds

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
        self.pinecone_creds = load_creds('pinecone')
        self.openai_creds = load_creds('openai')

        self.org_name: str = org_name
        self.user: str = user

    # pylint: disable=R0914
    def retrieve_context(self, question: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Retrieves context for a given question using Pinecone and OpenAI.

        Parameters:
            question (str): The question for which context is being retrieved.

        Returns:
            tuple: A tuple containing the retrieval result and a list of sources for the context.
        """
        prompt_template = """
        Answer the following question solely based on the context provided below. Translate Dutch
        to English if needed.:
        {context}

        Question: {question}
        """
        prompt = PromptTemplate.from_template(prompt_template)
        model = ChatOpenAI(model="gpt-3.5-turbo")
        output_parser = StrOutputParser()

        index_name = pinecone_index_name(self.org_name, "googledrive")
        vec_store = PineconeVectorStore.from_existing_index(index_name=index_name,
                                                               embedding=OpenAIEmbeddings())

        # Assuming similarity_search_with_relevance_scores returns List[Tuple[Document, float]]
        results: List[Tuple[Document, float]] = vec_store.similarity_search_with_relevance_scores(
            question, k=3)

        docs: List[Document] = []
        sources: List[Dict[str, Any]] = []

        for doc, score in results:
            # Append the whole document object if needed
            docs.append(doc)
            # Create a source entry with title, source, and score (converted to percentage and
            # stringified)
            source_entry = {
                "title": doc.metadata['title'],
                "source": doc.metadata['source'],
                "score": f"{score*100:.2f}%"
            }
            sources.append(source_entry)

        chain = prompt | model | output_parser
        result = chain.invoke({"context": docs, "question": question})

        return result, sources

    def get_all_indexes(self) -> IndexList:
        """
        Retrieves all indexes in Pinecone along with their metadata.

        Returns:
            list: A list of dictionaries containing the metadata for each index.
        """
        pinecone = Pinecone(api_key=self.pinecone_creds['api-key'])

        return pinecone.list_indexes()

    def get_index_details(self, index_host: str) -> List[Dict[str, Any]]:
        """
        Retrieves details for a specified index in Pinecone.

        Parameters:
            index_host (str): The host of the index for which to retrieve details.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing metadata for vectors in 
            the specified index.
        """
        pinecone = Pinecone(api_key=self.pinecone_creds['api-key'])
        index = pinecone.Index(host=index_host)

        if index is None:
            raise ValueError(f"Index '{index_host}' not found in Pinecone")

        result = []

        try:
            # If index.list() yields individual ids directly
            # pylint: disable=R1721
            ids = [ident for ident in index.list()]  # Assuming this gathers IDs as strings
            if ids:
                vectors = index.fetch(ids)  # This assumes fetch can accept multiple ids directly
                for ident in ids:
                    if ident in vectors.vectors:
                        vector = vectors.vectors[ident]
                        metadata = vector.metadata
                        result.append({
                            "id": ident,
                            "title": metadata.get('title', ''),
                            "source": metadata.get('source', ''),
                            "user": metadata.get('users', ''),
                            "when": metadata.get('when', '')
                        })
        except Exception as e:
            raise ValueError(f"Failed to fetch index details: {e}") from e

        return result
