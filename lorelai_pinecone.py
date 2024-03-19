"""this file creates a class to process google drive documents using the google drive api, chunk
them using langchain and then index them in pinecone"""

import os

# langchain_community.vectorstores.pinecone.Pinecone is deprecated
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders.googledrive import GoogleDriveLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATABASE = './userdb.sqlite'

class GoogleDriveProcessor:
    """This class is used to process the Google Drive documents and index them in Pinecone
    """


    def __init__(self, pinecone_api_key, pinecone_environment, pinecone_index_name, openai_api_key):
        self.pinecone_api_key = pinecone_api_key
        self.openai_api_key = openai_api_key
        # set env variable with openai api key
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        os.environ["PINECONE_API_KEY"] = self.pinecone_api_key

        self.pinecone_environment = pinecone_environment
        self.pinecone_index_name = pinecone_index_name
        self.embeddings = OpenAIEmbeddings()
        self.pinecone = PineconeVectorStore(pinecone_api_key=self.pinecone_api_key,
                                            index_name=self.pinecone_index_name,
                                            embedding=self.embeddings)

    def process_drive(self):
        """process the Google Drive documents and index them in Pinecone
        """

        #TODO: update to crawl drive
        drive_loader = GoogleDriveLoader(
            document_ids=['1GxEfHnCeHHF94FPWWV3C94MizzVPtnJtOebxiMJUJvE'])
        splitter = RecursiveCharacterTextSplitter(chunk_size=4000)

        docs = drive_loader.load()

        # Iterate over documents and split each document's text into chunks
        # for doc_id, document_content in documents.items():
        #     print(f"Processing document: {doc_id}")
        documents = splitter.split_documents(docs)

        #TODO: subsequent runs should update, not add/duplicate
        db = self.pinecone.from_documents(documents,
                                          self.embeddings,
                                          index_name=self.pinecone_index_name)

        return db

        # vectorized_chunks = [(str(i), self.vectorizer(chunk), {}) for i, chunk in
        # enumerate(chunks)]
        # self.pinecone_index.upsert(items=vectorized_chunks, vectors=vectorized_chunks)
