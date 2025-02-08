"""Module to handle interaction with different language model APIs."""

import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import current_app

from app.models import Datasource, User, UserAuth
from lorelai.context_retriever import ContextRetriever, LorelaiContextRetrievalResponse


class Llm(ABC):
    """Base class for LLM interactions."""

    datasources: list[LorelaiContextRetrievalResponse] = []
    _prompt_template = """
        Answer the following question based on the provided context alone. In the answer, refer to
        the sources to provide evidence for the answer. Use numbered references [1], [2], [3] etc.
        that link to the numbered sources list below. End the message with a list of sources per
        datasource, and mention the relevance of that source to the answer as a percentage. Also
        mentioned the relevance score of the source. Hyperlink to the source which opens in a new
        tab.
        Context":
        {context_doc_text}

        Question: {question}
        """

    @classmethod
    def create(cls, model_type: str, user_email: str, org_name: str) -> "Llm":
        """Create an instance of the specified LLM type."""
        from lorelai.llms.ollamallama3 import OllamaLlama3
        from lorelai.llms.openaillm import OpenAILlm

        llm_classes = {"OpenAILlm": OpenAILlm, "OllamaLlama3": OllamaLlama3}

        if model_type not in llm_classes:
            raise ValueError(f"Unknown model type: {model_type}")

        return llm_classes[model_type](user_email=user_email, organisation=org_name)

    def __init__(self, user_email: str, organisation: str) -> None:
        """Initialize the LLM with user and organization context."""
        self.user_email = user_email
        self.organisation = organisation
        self.datasources = []
        self.prompt_template = None
        self._initialize_datasources()

    def _initialize_datasources(self) -> None:
        """Initialize the datasources for this LLM instance."""
        # Get user's authenticated datasources from the database
        user = User.query.filter_by(email=self.user_email).first()
        if not user:
            logging.error(f"User not found: {self.user_email}")
            return

        # Get user's authenticated datasources
        user_auths = (
            UserAuth.query.join(Datasource, UserAuth.datasource_id == Datasource.datasource_id)
            .filter(UserAuth.user_id == user.id)
            .with_entities(Datasource.datasource_name)
            .all()
        )

        # Get authenticated datasource names
        authenticated_datasources = {auth[0] for auth in user_auths}

        # Check Slack feature flag and authentication
        if int(current_app.config["FEATURE_SLACK"]) == 1 and "Slack" in authenticated_datasources:
            try:
                self.datasources.append(
                    ContextRetriever.create(
                        "SlackContextRetriever",
                        org_name=self.organisation,
                        user_email=self.user_email,
                        environment=current_app.config["LORELAI_ENVIRONMENT"],
                        environment_slug=current_app.config["LORELAI_ENVIRONMENT_SLUG"],
                        reranker=current_app.config["LORELAI_RERANKER"],
                    )
                )
                logging.info("Created SlackContextRetriever for authenticated user")
            except ValueError as e:
                logging.error(f"Failed to create SlackContextRetriever: {e}")

        # Check Google Drive feature flag and authentication
        if (
            int(current_app.config["FEATURE_GOOGLE_DRIVE"]) == 1
            and "Google Drive" in authenticated_datasources
        ):
            try:
                self.datasources.append(
                    ContextRetriever.create(
                        "GoogleDriveContextRetriever",
                        org_name=self.organisation,
                        user_email=self.user_email,
                        environment=current_app.config["LORELAI_ENVIRONMENT"],
                        environment_slug=current_app.config["LORELAI_ENVIRONMENT_SLUG"],
                        reranker=current_app.config["LORELAI_RERANKER"],
                    )
                )
                logging.info("Created GoogleDriveContextRetriever for authenticated user")
            except ValueError as e:
                logging.error(f"Failed to create GoogleDriveContextRetriever: {e}")


    def get_answer(self, question: str, conversation_history: str | None = None) -> str:
        """Retrieve an answer to a given question based on provided context.

        This method is in the baseclass as it doesn't need to know which LLM is being used.
        Its purpose is to retrieve context from all the datasources and pass the context to the
        _ask_llm method, which is implemented in the derived classes.

        Args:
            question: The question to answer
            conversation_history: Optional string containing the conversation history
        """
        context_list = []
        retrieve_context_time = time.time()

        def retrieve_context_wrapper(datasource):
            """Wrap datasource context retrieval."""
            try:
                return datasource.retrieve_context(question=question)
            except Exception as e:
                logging.error(f"Failed to retrieve context from {datasource}: {e}")
                logging.error("Traceback:", exc_info=True)
                return None

        # Use ThreadPoolExecutor for multithreading
        with ThreadPoolExecutor() as executor:
            future_to_datasource = {
                executor.submit(retrieve_context_wrapper, ds): ds for ds in self.datasources
            }  # noqa: E501

            for future in as_completed(future_to_datasource):
                try:
                    result = future.result()
                    if result:
                        context_list.append(result)
                except Exception as e:
                    logging.error(f"Exception during context retrieval: {e}")
        logging.info(f"retrieve_context took: {time.time() - retrieve_context_time}")
        # Ask the LLM for an answer to the question
        ask_llm_time = time.time()
        answer = self._ask_llm(
            question=question, context_list=context_list, conversation_history=conversation_history
        )
        end_time = time.time()
        logging.info(f"ASK LLM took: {end_time - ask_llm_time}")
        return answer

    @abstractmethod
    def _ask_llm(
        self,
        question: str,
        context_list: list[LorelaiContextRetrievalResponse],
        conversation_history: str | None = None,
    ) -> str:
        """Ask the language model for an answer to a given question.

        This method is implemented in the derived classes.
        """
        raise NotImplementedError
