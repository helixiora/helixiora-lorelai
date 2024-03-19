#!/usr/bin/env python3
import json
import os
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings

# a simple test script to ask a question langchain that has been indexed in pinecone

# load openai creds from file and set env variable
def load_openai_creds():
    with open('settings.json') as f:
        creds = json.load(f)['openai']
    os.environ["OPENAI_API_KEY"] = creds['api-key']

def load_pinecone_creds():
    with open('settings.json') as f:
        creds = json.load(f)['pinecone']
    os.environ["PINECONE_API_KEY"] = creds['api-key']
    print(f"Pinecone Creds: {creds}")

load_openai_creds()
load_pinecone_creds()

template = """Beantwoord de volgende vraag alleen gebaseerd op de context hieronder:
{context}

Vraag: {question}
"""
prompt = ChatPromptTemplate.from_template(template)

model = ChatOpenAI(model="gpt-3.5-turbo")
output_parser = StrOutputParser()

vector_store = PineconeVectorStore(index_name="lorelai-index", embedding=OpenAIEmbeddings())

retriever = vector_store.as_retriever()

setup_and_retrieval = RunnableParallel(
    {"context": retriever, "question": RunnablePassthrough()}
)

chain = setup_and_retrieval | prompt | model | output_parser

result = chain.invoke({"question": "Waarop is het onderhoudsplan ingeschat?"})

print(result)