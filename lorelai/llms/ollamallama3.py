"""Module for interacting with the Ollama LLM.

Note: the filename has to be ollamallama3.py to match the class lowercase name.
"""

import logging
import time

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.llms import Ollama
from flask import current_app
import requests

from lorelai.llm import Llm, LorelaiContextRetrievalResponse
from app.models.config import Config


class OllamaLlama3(Llm):
    """Class to interact with a local Llama3 7b model for answering context-based questions."""

    def __init__(self, user_email: str, organisation: str) -> None:
        super().__init__(user_email, organisation)
        self.api_url = current_app.config["OLLAMA_API_URL"]  # Default to localhost
        self.model = "llama3-7b"  # Model identifier
        # Get prompt template from config or use default
        self.prompt_template = Config.get_value(
            "ollama_prompt_template",
            default="""You are a helpful AI assistant named Lorelai. You help users by answering
their questions based on the context provided.

Context from various sources:
{context_doc_text}

{conversation_history}
Current question: {question}

Please provide a clear and concise answer based on the context above. If the question refers to
previous messages in the conversation, use that context to provide a more relevant answer. If you
cannot find the answer in the context, say so. Do not make up information.

Format your response in markdown, and include a "### Sources" section at the end listing the
relevant sources used to answer the question.""",
        )

    def _ask_llm(
        self,
        question: str,
        context_list: list[LorelaiContextRetrievalResponse],
        conversation_history: str | None = None,
    ) -> str:
        """Get an answer from local Llama3 7b model."""
        logging.info(f"[OllamaLlama3.get_answer] Question: {question}")

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
        prompt.input_variables = ["context_doc_text", "question", "conversation_history"]

        model = Ollama(model=self.model, base_url=self.api_url)
        output_parser_time = time.time()
        output_parser = StrOutputParser()
        result = (prompt | model | output_parser).invoke(
            {
                "context_doc_text": context_doc_text,
                "question": question,
                "conversation_history": conversation_history or "",
            }
        )
        logging.info(f"StrOutputParser took: {time.time() - output_parser_time}")
        return result

    def get_llm_status(self):
        """Check the current status of the LLM at the local endpoint."""
        response = requests.get(f"{self.api_url}/models/status/{self.model}")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to retrieve model status: {response.text}")
