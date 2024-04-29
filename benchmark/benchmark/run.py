import json
import logging
import os
import sys

import yaml

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../.."))
from lorelai.contextretriever import ContextRetriever  # noqa E402
from lorelai.llm import Llm  # noqa E402


class Run:
    def __init__(self, model_type="OpenAILlm"):
        self.llm = Llm.create(model_type=model_type)

    def benchmark(self, org_name, user_name, question_file, question_classes_file):
        logging.info("Starting benchmarking")
        # {
        #     "question": "What was the closing price of IBM stock in the article published on July 5, 1987?",
        #     "class": "fact_retrieval",
        #     "answer": "$125.50",
        #     "context": {
        #         "excerpt": "On July 5, 1987, the closing price of IBM stock was reported to be $125.50.",
        #         "source": "google drive://stocks/IBM STOCK PRICES JULY 1987"
        #     }
        # },
        with open(question_file, "r") as f:
            question_file = json.load(f)

        # question_classes:
        # - class_name: "fact_retrieval"
        #     description: >
        #     Questions that require retrieving factual information from a knowledge base or external sources.
        #     validation_method: >
        #     Check if the retrieved answer matches verified factual sources.
        #     python_function: "validate_fact_retrieval"
        with open(question_classes_file, "r") as f:
            question_classes_file = yaml.safe_load(f)

        for question in question_file:
            logging.info(f"Processing question: {question['question']}")

            # get the question class by looking up the class in question_classes_file
            question_class = None
            for qc in question_classes_file["question_classes"]:
                if qc["class_name"] == question["class"]:
                    question_class = qc
                    break

            assert (
                question_class is not None
            ), f"Question class not found for question: {question['question']}"
            # logging.info(f"Question class: {question_class["class_name"]}: {question_class["description"]}")

            context_retriever = ContextRetriever(org_name=org_name, user=user_name)
            context = context_retriever.retrieve_context(question["question"])

            answer = self.llm.get_answer(question["question"], context)
            logging.info(f"Answer: {answer}")
