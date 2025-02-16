"""Module for interacting with the OpenAI LLM.

Note: the filename has to be openaillm.py to match the class lowercase name.
"""

import logging
import os
import time

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from flask import current_app
from pydantic import BaseModel, Field, ValidationError
from openai import OpenAIError
import langchain_core.exceptions

from lorelai.llm import Llm, LorelaiContextRetrievalResponse
from app.models.config import Config


class Source(BaseModel):
    """Model for a source used in the answer.

    This model represents a single source document used in generating the answer,
    including metadata about its relevance and origin.
    """

    datasource: str = Field(
        description="The name of the datasource (e.g., 'Slack', 'Google Drive')"
    )
    title: str = Field(description="The title or name of the source document")
    link: str = Field(description="URL or path to access the source")
    relevance_score: float = Field(
        description="How relevant this source was to the answer (0-1)", ge=0.0, le=1.0
    )
    relevance_explanation: str = Field(
        description="Brief explanation of why this source was relevant to the answer"
    )


class AnswerResponse(BaseModel):
    """Model for the structured answer from the LLM.

    This model defines the complete structure of a response, including the main answer,
    sources used, and reasoning process.
    """

    answer: str = Field(description="The main answer text formatted in markdown")
    sources: list[Source] = Field(description="List of sources used to generate the answer")
    reasoning: str = Field(description="Explanation of how the answer was derived from the sources")


class OpenAILlm(Llm):
    """Class to interact with the OpenAI LLM for answering context-based questions.

    This class handles:
    - Structured output generation using Pydantic models
    - Proper error handling for API and parsing errors
    - Consistent markdown formatting of responses
    """

    def __init__(self, user_email: str, organisation: str) -> None:
        """Initialize the OpenAI LLM with user context and configuration.

        Args:
            user_email: Email of the user making the request
            organisation: Organization context for the request
        """
        try:
            super().__init__(user_email, organisation)
            os.environ["OPENAI_API_KEY"] = current_app.config["OPENAI_API_KEY"]
            self.model = current_app.config["OPENAI_MODEL"]

            # Get prompt template from config or use default
            self.prompt_template = Config.get_value(
                "openai_prompt_template",
                default="""You are a helpful AI assistant named Lorelai. You help users by answering
their questions based on the context provided.

Context from various sources:
{context_doc_text}

{conversation_history}
Current question: {question}

Provide a clear and concise answer based on the context above. If the question refers to previous
messages in the conversation, use that context to provide a more relevant answer. If you cannot
find the answer in the context, say so. Do not make up information.

You must respond with a valid JSON object that matches this schema:
{format_instructions}

IMPORTANT JSON FORMATTING RULES:
1. Do not include trailing commas after the last property in objects
2. Ensure all property names are in double quotes
3. Make sure all strings are properly escaped
4. The response must be a single, valid JSON object

Make sure to:
1. Include all relevant sources in the sources list
2. Explain your reasoning process
3. Format the answer text using markdown
4. Only include sources that were actually used in the answer
5. Provide specific relevance explanations for each source""",
            )
            logging.info(f"Initialized OpenAILlm with model {self.model}")
        except Exception as e:
            logging.error(f"Failed to initialize OpenAILlm: {str(e)}")
            raise

    def _format_markdown_response(self, structured_response: dict[str, any]) -> str:
        """Format the structured response into a markdown string.

        Args
        ----
            structured_response: Dictionary containing the structured response
                               from the LLM (must match AnswerResponse schema)

        Returns
        -------
            A formatted markdown string containing the answer, reasoning, and sources

        Raises
        ------
            KeyError: If required fields are missing from the response
            ValueError: If the response format is invalid
        """
        try:
            # Validate the response has required fields
            if "answer" not in structured_response:
                raise KeyError("Response missing required 'answer' field")

            markdown = structured_response["answer"] + "\n\n"

            if structured_response.get("reasoning"):
                markdown += "### Reasoning\n" + structured_response["reasoning"] + "\n\n"

            if structured_response.get("sources"):
                markdown += "### Sources\n"
                for source in structured_response["sources"]:
                    markdown += (
                        f"- [{source['title']}]({source['link']}) from {source['datasource']}\n"
                    )
                    markdown += f"  - Relevance ({source['relevance_score'] * 100:.0f}%): \
{source['relevance_explanation']}\n"

            return markdown
        except (KeyError, TypeError) as e:
            logging.error(f"Error formatting markdown response: {str(e)}")
            raise ValueError(f"Invalid response format: {str(e)}") from e

    def _ask_llm(
        self,
        question: str,
        context_list: list[LorelaiContextRetrievalResponse],
        conversation_history: str | None = None,
    ) -> str:
        """Get an answer specifically from the OpenAI models.

        Args:
            question: The user's question to answer
            context_list: List of context documents to use in generating the answer
            conversation_history: Optional string containing previous conversation context

        Returns
        -------
            A markdown formatted string containing the answer

        Raises
        ------
            OpenAIError: If there's an error communicating with the OpenAI API
            ValidationError: If the response doesn't match the expected schema
            ValueError: If there's an error formatting the response
        """
        start_time = time.time()
        logging.info(f"[OpenAILlm.get_answer] Processing question: {question}")

        try:
            # Concatenate all the context from the sources
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

            # Create the output parser with our schema
            parser = JsonOutputParser(pydantic_object=AnswerResponse)

            # Create the prompt with format instructions
            prompt = PromptTemplate(
                template=self.prompt_template,
                partial_variables={"format_instructions": parser.get_format_instructions()},
                input_variables=["context_doc_text", "question", "conversation_history"],
            )

            # Create the chain and get response
            model = ChatOpenAI(model=self.model)
            chain = prompt | model | parser

            try:
                structured_response = chain.invoke(
                    {
                        "context_doc_text": context_doc_text,
                        "question": question,
                        "conversation_history": conversation_history or "",
                    }
                )
            except langchain_core.exceptions.OutputParserException as e:
                # Extract the raw response for better error handling
                raw_response = str(e.llm_output)
                logging.error(f"Failed to parse LLM output as JSON: {str(e)}")
                logging.debug(f"Raw LLM output: {raw_response}")

                # Try to clean and repair common JSON issues
                if raw_response.strip().endswith(",}"):
                    # Fix trailing comma
                    raw_response = raw_response.replace(",}", "}")
                    try:
                        # Try parsing again with cleaned JSON
                        structured_response = parser.parse(raw_response)
                        logging.info(
                            "Successfully recovered from JSON parsing error by cleaning output"
                        )
                    except Exception as parse_error:
                        logging.error(
                            f"Failed to recover from JSON parsing error: {str(parse_error)}"
                        )
                        raise ValueError(
                            "The language model returned invalid JSON that could not be \
automatically fixed"
                        ) from e
                else:
                    raise ValueError(
                        "The language model returned a response in an invalid format"
                    ) from e

            # Format the response as markdown
            # Handle both dictionary and Pydantic model responses
            response_dict = (
                structured_response.model_dump()
                if hasattr(structured_response, "model_dump")
                else structured_response
            )
            markdown_response = self._format_markdown_response(response_dict)

            logging.info(f"Successfully generated response in {time.time() - start_time:.2f}s")
            return markdown_response

        except OpenAIError as e:
            logging.error(f"OpenAI API error: {str(e)}")
            raise
        except ValidationError as e:
            logging.error(f"Response validation error: {str(e)}")
            raise ValueError("Failed to parse LLM response into expected format") from e
        except Exception as e:
            logging.error(f"Unexpected error in _ask_llm: {str(e)}")
            raise
