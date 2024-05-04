import logging
import os

import requests  # Needed for API requests to local server
from langchain_community.llms import Ollama
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from lorelai.utils import load_config


class Llm:
    """Base class to handle interaction with different language model APIs."""

    _allowed = False  # Flag to control constructor access

    _prompt_template = """
        Answer the following question based on the provided context:
        {context_doc_text}

        Question: {question}
        """

    @staticmethod
    def create(model_type="OpenAILlm"):
        """Factory method to create instances of derived classes based on the class name."""
        Llm._allowed = True
        class_ = globals().get(model_type)
        if class_ is None or not issubclass(class_, Llm):
            Llm._allowed = False
            raise ValueError(f"Unsupported model type: {model_type}")
        instance = class_()
        Llm._allowed = False
        return instance

    def __init__(self):
        if not self._allowed:
            raise Exception("This class should be instantiated through a create() factory method.")

    def get_answer(self, question, context):
        """Retrieve an answer to a given question based on provided context."""
        raise NotImplementedError

    def get_llm_status(self):
        """Retrieve the status of the language model."""
        raise NotImplementedError


class OllamaLlama3(Llm):
    """Class to interact with a local Llama3 7b model for answering context-based questions."""

    def __init__(self):
        super().__init__()
        self.llama_creds = load_config("llama_local")
        self.api_url = self.llama_creds.get(
            "api_url", "http://localhost:8000"
        )  # Default to localhost
        self.model = "llama3-7b"  # Model identifier

    def get_answer(self, question, context):
        """Implementation specific to local Llama3 7b model."""

        context_doc_text = ""
        for context_doc in context:
            if isinstance(context_doc, Document):
                context_doc_text += context_doc.page_content

        logging.debug("[OllamaLlama3.get_answer] Prompt template: %s", self._prompt_template)
        logging.debug("[OllamaLlama3.get_answer] Question: %s", question)
        logging.debug("[OllamaLlama3.get_answer] Context_doc_text: %s", context_doc_text)

        prompt = PromptTemplate.from_template(
            template=self._prompt_template, template_format="f-string"
        )
        prompt.input_variables = ["context_doc_text", "question"]
        logging.debug("[OllamaLlama3.get_answer] Prompt: %s", prompt)

        # prompt.format(context=context, question=question)

        model = Ollama(model="llama3")
        output_parser = StrOutputParser()
        result = (prompt | model | output_parser).invoke(
            {"context_doc_text": context_doc_text, "question": question}
        )
        return result

    def get_llm_status(self):
        """Check the current status of the LLM at the local endpoint."""
        response = requests.get(f"{self.api_url}/models/status/{self.model}")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to retrieve model status: {response.text}")


class OpenAILlm(Llm):
    """Class to interact with the OpenAI LLM for answering context-based questions."""

    def __init__(self):
        super().__init__()
        self.openai_creds = load_config("openai")
        os.environ["OPENAI_API_KEY"] = self.openai_creds["api_key"]
        self.model = "gpt-3.5-turbo"

    def get_answer(self, question, context):
        """Implementation specific to OpenAI models."""

        context_doc_text = ""
        for context_doc in context:
            if isinstance(context_doc, Document):
                context_doc_text += context_doc.page_content

        logging.debug("[OpenAILlm.get_answer] Prompt template: %s", self._prompt_template)
        logging.debug("[OpenAILlm.get_answer] Question: %s", question)
        logging.debug("[OpenAILlm.get_answer] Context_doc_text: %s", context_doc_text)

        prompt = PromptTemplate.from_template(
            template=self._prompt_template, template_format="f-string"
        )
        prompt.input_variables = ["context_doc_text", "question"]
        logging.debug("[OpenAILlm.get_answer] Prompt: %s", prompt)

        # prompt.format(context=context, question=question)

        model = ChatOpenAI(model=self.model)
        output_parser = StrOutputParser()
        result = (prompt | model | output_parser).invoke(
            {"context_doc_text": context_doc_text, "question": question}
        )
        return result

    def get_llm_status(self):
        """Check the current status of the LLM."""
        model = ChatOpenAI(model=self.model)
        return model.get_status()
