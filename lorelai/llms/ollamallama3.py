"""Module for interacting with the Ollama LLM.

Note: the filename has to be ollamallama3.py to match the class lowercase name.
"""

import logging
import requests
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from ollama import Ollama

from lorelai.utils import load_config
from lorelai.llm import Llm


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
        """Get an answer from local Llama3 7b model."""
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
