import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from lorelai.utils import load_config


class Llm:
    """Base class to handle interaction with different language model APIs."""

    _allowed = False  # Flag to control constructor access

    @staticmethod
    def create(model_type="OpenAILlm"):
        """Factory method to create instances of derived classes based on the class name."""
        Llm._allowed = True
        class_ = globals().get(model_type)
        if class_ is None or not issubclass(class_, Llm):
            Llm._allowed = False
            raise ValueError(f"Unsupported model type: {model_type}")
        instance = class_()
        Llm._allowed = False
        return instance

    def __init__(self):
        if not self._allowed:
            raise Exception("This class should be instantiated through a create() factory method.")

    def get_answer(self, question, context):
        """Retrieve an answer to a given question based on provided context."""
        raise NotImplementedError

    def get_llm_status(self):
        """Retrieve the status of the language model."""
        raise NotImplementedError


class OpenAILlm(Llm):
    """Class to interact with the OpenAI LLM for answering context-based questions."""

    def __init__(self):
        super().__init__()
        self.openai_creds = load_config("openai")
        os.environ["OPENAI_API_KEY"] = self.openai_creds["api_key"]
        self.model = "gpt-3.5-turbo"

    def get_answer(self, question, context):
        """Implementation specific to OpenAI models."""
        prompt_template = f"""
        Answer the following question based on the provided context:
        {context}

        Question: {question}
        """
        prompt = PromptTemplate.from_template(prompt_template)
        prompt.format(context=context, question=question)

        model = ChatOpenAI(model=self.model)
        output_parser = StrOutputParser()
        result = (prompt | model | output_parser).invoke({"context": context, "question": question})
        return result

    def get_llm_status(self):
        """Check the current status of the LLM."""
        model = ChatOpenAI(model=self.model)
        return model.get_status()
