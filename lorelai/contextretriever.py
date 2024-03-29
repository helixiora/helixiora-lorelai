"""This module is used to retrieve the context for a question from pinecone
"""

import json
import os
from pprint import pprint

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from lorelai.utils import pinecone_index_name

class Contextretriever:
    """this class is used to retrieve the context for a question from pinecone
    """
    # load openai creds from file and set env variable
    @staticmethod
    def load_openai_creds():
        """loads the openai creds from the settings.json file
        """
        with open('settings.json', encoding='utf-8') as f:
            creds = json.load(f)['openai']
        os.environ["OPENAI_API_KEY"] = creds['api-key']
        return creds

    @staticmethod
    def load_pinecone_creds():
        """loads the pinecone creds from the settings.json file
        """
        with open('settings.json', encoding='utf-8') as f:
            creds = json.load(f)['pinecone']
        os.environ["PINECONE_API_KEY"] = creds['api-key']
        return creds


    def __init__(self, org_name, user):
        """initializes the class and loads the pinecone and openai creds
        """
        pinecone_creds = self.load_pinecone_creds()
        openai_creds = self.load_openai_creds()

        self.pinecone_creds = pinecone_creds
        self.openai_creds = openai_creds

        self.pinecone_api_key = pinecone_creds['api-key']
        self.openai_api_key = openai_creds['api-key']

        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["PINECONE_API_KEY"] = self.pinecone_api_key

        self.org_name = org_name
        self.user = user

    def retrieve_context(self, question):
        """retrieves the context for the question
        """

        Template = """Answer the following question solely based on the context provided below. Translate Dutch to English if needed.:
        {context}

        Question: {question}
        """
        prompt = PromptTemplate.from_template(Template)

        model = ChatOpenAI(model="gpt-3.5-turbo")
        output_parser = StrOutputParser()

        index_name = pinecone_index_name(self.org_name, "googledrive")
        vector_store = PineconeVectorStore(index_name=index_name, embedding=OpenAIEmbeddings())

        retriever = vector_store.as_retriever()

        docs = retriever.get_relevant_documents(question, k=3)

        #print the source of the document
        source = []
        for doc in docs:
            # add the source to the list of sources
            source.append(doc.metadata['source'])

        chain = prompt | model | output_parser

        result = chain.invoke({"context": docs, "question": question})

        return result, source