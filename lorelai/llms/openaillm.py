"""Module for interacting with the OpenAI LLM.

Note: the filename has to be openaillm.py to match the class lowercase name.
"""

import logging
import os
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from lorelai.utils import load_config
from lorelai.llm import Llm, LorelaiContextRetrievalResponse


class OpenAILlm(Llm):
    """Class to interact with the OpenAI LLM for answering context-based questions."""

    def __init__(self, user: str, organization: str) -> None:
        super().__init__(user, organization)
        self.openai_creds = load_config("openai")
        os.environ["OPENAI_API_KEY"] = self.openai_creds["api_key"]
        self.model = self.openai_creds["model"]

    def _ask_llm(self, question: str, context: list[LorelaiContextRetrievalResponse]) -> str:
        """Get an answer specifically from the OpenAI models."""
        logging.info(f"[OpenAILlm.get_answer] Question: {question}")

        # concatenate all the context from the sources
        context_doc_text = ""
        for source in context:
            logging.info("[OpenAILlm.get_answer] Source type: %s", type(source))
            for document in source.context:
                logging.info("[OpenAILlm.get_answer] Document type: %s", type(document))
                if isinstance(document, str):
                    context_doc_text += document
                elif hasattr(document, "page_content"):
                    context_doc_text += document.page_content
                else:
                    logging.warning(f"Unexpected document type: {type(document)}")

        logging.info("[OpenAILlm.get_answer] Prompt template: %s", self._prompt_template)
        logging.info("[OpenAILlm.get_answer] Context_doc_text: %s", context_doc_text)

        prompt = PromptTemplate.from_template(
            template=self.prompt_template, template_format="f-string"
        )
        prompt.input_variables = ["context_doc_text", "question"]
        logging.info("[OpenAILlm.get_answer] Prompt: %s", prompt)

        model = ChatOpenAI(model=self.model)
        output_parser = StrOutputParser()
        result = (prompt | model | output_parser).invoke(
            {"context_doc_text": context_doc_text, "question": question}
        )
        logging.info("[OpenAILlm.get_answer] Result: %s", result)
        return result
