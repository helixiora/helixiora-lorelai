import json
import os
from typing import Tuple, List, Dict, Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from lorelai.utils import pinecone_index_name

class ContextRetriever:
    """
    A class to retrieve context for a given question from Pinecone.

    This class manages the integration with Pinecone and OpenAI services,
    facilitating the retrieval of relevant document contexts for specified questions.
    It leverages Pinecone's vector search capabilities alongside OpenAI's embeddings and
    language models to generate responses based on the retrieved contexts.
    """

    @staticmethod
    def load_creds(service: str) -> Dict[str, str]:
        """
        Loads API credentials for a specified service from settings.json.

        Parameters:
            service (str): The name of the service ('openai' or 'pinecone') for which to load credentials.

        Returns:
            dict: A dictionary containing the API key for the specified service.
        """
        with open('settings.json', 'r', encoding='utf-8') as f:
            creds = json.load(f).get(service, {})
        os.environ[f"{service.upper()}_API_KEY"] = creds.get('api-key', '')
        return creds

    def __init__(self, org_name: str, user: str):
        """
        Initializes the ContextRetriever instance.

        Parameters:
            org_name (str): The organization name, used for Pinecone index naming.
            user (str): The user name, potentially used for logging or customization.
        """
        self.pinecone_creds = self.load_creds('pinecone')
        self.openai_creds = self.load_creds('openai')

        self.org_name: str = org_name
        self.user: str = user

    def retrieve_context(self, question: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Retrieves context for a given question using Pinecone and OpenAI.

        Parameters:
            question (str): The question for which context is being retrieved.

        Returns:
            tuple: A tuple containing the retrieval result and a list of sources for the context.
        """
        prompt_template = """
        Answer the following question solely based on the context provided below. Translate Dutch to English if needed.:
        {context}

        Question: {question}
        """
        prompt = PromptTemplate.from_template(prompt_template)
        model = ChatOpenAI(model="gpt-3.5-turbo")
        output_parser = StrOutputParser()

        index_name = pinecone_index_name(self.org_name, "googledrive")
        vector_store = PineconeVectorStore.from_existing_index(index_name=index_name, embedding=OpenAIEmbeddings())

        # retriever = vector_store.as_retriever(search_kwargs={"filter": {"user": self.user}})
        # docs = retriever.get_relevant_documents(question, k=3)

        # Assuming similarity_search_with_relevance_scores returns List[Tuple[Document, float]]
        results: List[Tuple[Document, float]] = vector_store.similarity_search_with_relevance_scores(question, k=3)

        docs: List[Document] = []
        sources: List[Dict[str, any]] = []

        for doc, score in results:
            # Append the whole document object if needed
            docs.append(doc)
            # Create a source entry with title, source, and score (converted to percentage and stringified)
            source_entry = {
                "title": doc.metadata['title'], 
                "source": doc.metadata['source'], 
                "score": f"{score*100:.2f}%"
            }
            sources.append(source_entry)
            
            

        chain = prompt | model | output_parser
        result = chain.invoke({"context": docs, "question": question})

        return result, sources
