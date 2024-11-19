"""Module for interacting with the OpenAI LLM.

Note: the filename has to be openaillm.py to match the class lowercase name.
"""

import logging
import os
import time

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from flask import current_app
from lorelai.llm import Llm, LorelaiContextRetrievalResponse


class OpenAILlm(Llm):
    """Class to interact with the OpenAI LLM for answering context-based questions."""

    def __init__(self, user_email: str, organisation: str) -> None:
        super().__init__(user_email, organisation)
        os.environ["OPENAI_API_KEY"] = current_app.config["OPENAI_API_KEY"]
        self.model = current_app.config["OPENAI_MODEL"]

    def _ask_llm(self, question: str, context_list: list[LorelaiContextRetrievalResponse]) -> str:
        """Get an answer specifically from the OpenAI models."""
        logging.info(f"[OpenAILlm.get_answer] Question: {question}")

        # concatenate all the context from the sources
        context_doc_text = ""
        for context_retrieval_response in context_list:
            for document in context_retrieval_response.context:
                context_doc_text += (
                    f"Datasource: {context_retrieval_response.datasource_name} \n"
                    + f"Title: {document.title} \n"
                    + f"Relevance score: {document.relevance_score} \n"
                    + f"Link: {document.link} \n"
                    + f"When: {document.when} \n"
                    + "Content: <<<START_CONTENT>>>\n"
                    + document.content
                    + "\n<<END_CONTENT>>>\n\n"
                )

        prompt = PromptTemplate.from_template(
            template=self.prompt_template, template_format="f-string"
        )
        prompt.input_variables = ["context_doc_text", "question"]

        model = ChatOpenAI(model=self.model)
        output_parser_time = time.time()
        output_parser = StrOutputParser()
        result = (prompt | model | output_parser).invoke(
            {"context_doc_text": context_doc_text, "question": question}
        )
        logging.info(f"StrOutputParser took: {time.time()-output_parser_time}")
        return result
