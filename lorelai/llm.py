"""
    a class that takes a question and context and sends it to the LLM, then returns the answer
"""
import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from lorelai.utils import load_config


class Llm:
    """A class to interact with the OpenAI language model for answering questions based on context
    """
    def __init__(self, model="gpt-3.5-turbo"):
        creds = load_config('openai')
        self.openai_creds = creds
        os.environ["OPENAI_API_KEY"] = creds['api_key']
        self.model = model

    def get_answer(self, question, context):
        """Get the answer to a question based on the provided context using the OpenAI language
        model.

        parameters:
            question (str): The question to be answered.
            context (str): The context in which the question is asked.
        """

        prompt_template = """
        Answer the following question solely based on the context provided below. Translate Dutch
        to English if needed.:
        {context}

        Question: {question}
        """

        # Create a prompt from the template
        prompt = PromptTemplate.from_template(prompt_template)

        # Create a chain of components to process the prompt
        model = ChatOpenAI(model=self.model)

        # Create an output parser to extract the answer from the model's response
        output_parser = StrOutputParser()

        # Create a chain of components to process the prompt
        chain = prompt | model | output_parser

        # Invoke the chain
        result = chain.invoke({"context": context, "question": question})

        # Return the result
        return result

    def get_llm_status(self):
        """Get the status of the LLM model.
        """
        chat = ChatOpenAI(model=self.model)

        return chat.get_status()
