"""Module for interacting with the OpenAI LLM.

Note: the filename has to be openaillm.py to match the class lowercase name.
"""

import logging
import os
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

from lorelai.utils import load_config
from lorelai.llm import Llm


class OpenAILlm(Llm):
    """Class to interact with the OpenAI LLM for answering context-based questions."""

    def __init__(self, user: str, organization: str) -> None:
        super().__init__(user, organization)
        self.openai_creds = load_config("openai")
        os.environ["OPENAI_API_KEY"] = self.openai_creds["api_key"]
        self.model = self.openai_creds["model"]

    def __ask_llm(self: None, question: str, context: list[Document]) -> str:
        """Get an answer specifically from the OpenAI models."""
        context_doc_text = ""
        for context_doc in context:
            if isinstance(context_doc, Document):
                context_doc_text += context_doc.page_content

        logging.debug("[OpenAILlm.get_answer] Prompt template: %s", self._prompt_template)
        logging.debug("[OpenAILlm.get_answer] Question: %s", question)
        logging.debug("[OpenAILlm.get_answer] Context_doc_text: %s", context_doc_text)

        prompt = PromptTemplate.from_template(
            template=self.prompt_template, template_format="f-string"
        )
        prompt.input_variables = ["context_doc_text", "question"]
        logging.debug("[OpenAILlm.get_answer] Prompt: %s", prompt)

        model = ChatOpenAI(model=self.model)
        output_parser = StrOutputParser()
        result = (prompt | model | output_parser).invoke(
            {"context_doc_text": context_doc_text, "question": question}
        )
        return result
