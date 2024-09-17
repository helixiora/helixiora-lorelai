"""Module to handle interaction with different language model APIs."""

from lorelai.context_retriever import ContextRetriever
from lorelai.utils import load_config
import importlib
import logging


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
        self.datasources.append(
            ContextRetriever.create("GoogleDriveContextRetriever", user=user, org_name=organization)
        )
        self.datasources.append(
            ContextRetriever.create("SlackContextRetriever", user=user, org_name=organization)
        )

    def get_answer(self, question):
        """Retrieve an answer to a given question based on provided context."""
        context = []

        for datasource in self.datasources:
            context.append(datasource.retrieve_context(question))

        answer = self.__ask_llm(question, context)
        return answer

    def __ask_llm(self, question, context):
        """Ask the language model for an answer to a given question."""
        raise NotImplementedError
