"""Module to handle interaction with different language model APIs."""

from lorelai.context_retriever import ContextRetriever
from lorelai.utils import load_config
import importlib
import logging
from pydantic import BaseModel, ConfigDict


class ContextFromDatasource(BaseModel):
    """Class to keep context from a datasource."""

    datasource: ContextRetriever
    context: list
    sources: list

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Llm:
    """Base class to handle interaction with different language model APIs."""

    _prompt_template = """
        Answer the following question based on the provided context alone. ":
        {context_doc_text}

        Question: {question}
        """

    @staticmethod
    def create(model_type: str, user: str, organization: str):
        """Create instances of derived classes based on the class name."""
        try:
            module = importlib.import_module(f"lorelai.llms.{model_type.lower()}")
            class_ = getattr(module, model_type)
            if not issubclass(class_, Llm):
                raise ValueError(f"Unsupported model type: {model_type}")
            logging.debug(f"Creating {model_type} instance")
            # Set _allowed to True for the specific class being instantiated
            instance = class_(user=user, organization=organization)
            return instance
        except (ImportError, AttributeError) as exc:
            raise ValueError(f"2: Unsupported model type: {model_type}") from exc

    def __init__(self, user: str, organization: str):
        # if not self._allowed:
        #    raise Exception("This class should be instantiated through a create() factory method.")
        # self._allowed = False  # Reset the flag after successful instantiation

        config = load_config("lorelai")
        self.prompt_template = config.get("prompt_template", self._prompt_template)

        self.user = user
        self.organization = organization

        self.datasources = []

        # the following code goes to every context retriever and creates an instance of it,
        # and appends it to the datasources list
        retriever_types = ["GoogleDriveContextRetriever", "SlackContextRetriever"]
        for retriever_type in retriever_types:
            try:
                retriever = ContextRetriever.create(
                    retriever_type, user=user, org_name=organization
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
        context = []

        # retrieve context from all the datasources and append to context list
        for datasource in self.datasources:
            datasource_context, datasource_sources = datasource.retrieve_context(question=question)
            logging.debug("[Llm.get_answer] datasource type: %s", type(datasource))
            logging.debug("[Llm.get_answer] datasource_context: %s", datasource_context)
            logging.debug("[Llm.get_answer] datasource_sources: %s", datasource_sources)

            context_from_datasource = ContextFromDatasource(
                datasource=datasource,
                context=datasource_context,
                sources=datasource_sources,
            )
            context.append(context_from_datasource)

        logging.info(f"Context (get_answer): {context}")

        # ask the LLM for an answer to the question
        answer = self._ask_llm(question=question, sources=context)
        return answer

    def _ask_llm(self, question: str, sources: list[ContextFromDatasource]) -> str:
        """Ask the language model for an answer to a given question.

        This method is implemented in the derived classes.
        """
        raise NotImplementedError
