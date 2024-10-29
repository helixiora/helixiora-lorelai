"""Module to handle interaction with different language model APIs."""

from flask import current_app
from lorelai.context_retriever import ContextRetriever, LorelaiContextRetrievalResponse
import importlib
import logging


class Llm:
    """Base class to handle interaction with different language model APIs."""

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

    @staticmethod
    def create(model_type: str, user_email: str, organisation: str):
        """Create instances of derived classes based on the class name."""
        try:
            module = importlib.import_module(f"lorelai.llms.{model_type.lower()}")
            class_ = getattr(module, model_type)
            if not issubclass(class_, Llm):
                raise ValueError(f"Unsupported model type: {model_type}")
            logging.debug(f"Creating {model_type} instance")
            # Set _allowed to True for the specific class being instantiated
            instance = class_(user_email=user_email, organisation=organisation)
            return instance
        except (ImportError, AttributeError) as exc:
            raise ValueError(f"2: Unsupported model type: {model_type}") from exc

    def __init__(self, user_email: str, organisation: str):
        # if not self._allowed:
        #    raise Exception("This class should be instantiated through a create() factory method.")
        # self._allowed = False  # Reset the flag after successful instantiation

        self.prompt_template = current_app.config.get("prompt_template", self._prompt_template)

        self.user_email = user_email
        self.organisation = organisation

        self.datasources = []

        # the following code goes to every context retriever and creates an instance of it,
        # and appends it to the datasources list
        retriever_types = ["GoogleDriveContextRetriever", "SlackContextRetriever"]
        for retriever_type in retriever_types:
            try:
                retriever = ContextRetriever.create(
                    retriever_type,
                    user_email=user_email,
                    organisation=organisation,
                    environment=current_app.config["LORELAI_ENVIRONMENT"],
                    environment_slug=current_app.config["LORELAI_ENVIRONMENT_SLUG"],
                    reranker=current_app.config["LORELAI_RERANKER"],
                )
                self.datasources.append(retriever)
            except ValueError as e:
                logging.error(f"Failed to create {retriever_type}: {e}")

    def get_answer(self, question: str) -> str:
        """Retrieve an answer to a given question based on provided context.

        This method is in the baseclass as it doesn't need to know which LLM is being used.
        It's purpose is to retrieve context from all the datasources and pass the context to the
        __ask_llm method, which is implemented in the derived classes.
        """
        context_list = []

        # retrieve context from all the datasources and append to context list
        for datasource in self.datasources:
            try:
                context_retrieval_response = datasource.retrieve_context(question=question)
                context_list.append(context_retrieval_response)
            except Exception as e:
                logging.error(f"Failed to retrieve context from {datasource}: {e}")

        logging.info(f"Context (get_answer): {context_list}")

        # ask the LLM for an answer to the question
        answer = self._ask_llm(question=question, context_list=context_list)
        return answer

    def _ask_llm(self, question: str, context_list: list[LorelaiContextRetrievalResponse]) -> str:
        """Ask the language model for an answer to a given question.

        This method is implemented in the derived classes.
        """
        raise NotImplementedError
