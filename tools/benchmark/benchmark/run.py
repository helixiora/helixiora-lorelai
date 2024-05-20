import json
import logging
import os
import sys

import yaml

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../../.."))
from lorelai.contextretriever import ContextRetriever  # noqa E402
from lorelai.llm import Llm  # noqa E402
from benchmark.validate import Validate  # noqa E402
from lorelai.utils import get_db_connection  # noqa E402


class Run:
    def __init__(self, model_type="OpenAILlm"):
        self.llm = Llm.create(model_type=model_type)

    def benchmark(
        self,
        benchmark_name: str,
        benchmark_description: str,
        org_name: str,
        user_name: str,
        question_file: str,
        question_classes_file: str,
    ):
        logging.info("Starting benchmarking")
        # {
        #     "question": "What was the closing price of IBM stock on July 5, 1987?",
        #     "class": "fact_retrieval",
        #     "answer": "$125.50",
        #     "context": {
        #         "excerpt": "On July 5, 1987, the closing price of IBM stock was  $125.50.",
        #         "source": "google drive://stocks/IBM STOCK PRICES JULY 1987"
        #     }
        # },
        with open(question_file, "r") as f:
            question_file = json.load(f)

        # question_classes:
        # - class_name: "fact_retrieval"
        #     description: >
        #     Questions that require retrieving factual information from a knowledge base.
        #     validation_method: >
        #     Check if the retrieved answer matches verified factual sources.
        #     python_function: "validate_fact_retrieval"
        with open(question_classes_file, "r") as f:
            question_classes_file = yaml.safe_load(f)

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # insert new benchmark into the database
        result = cursor.execute(
            "INSERT into benchmarks (name, desc) VALUES (%s)",
            (benchmark_name, benchmark_description),
        )
        if result == 0:
            logging.error("Failed to insert benchmark into the database")
            db.rollback()
            return
        else:
            db.commit()

        # get the benchmark id
        # benchmark_id = cursor.lastrowid

        for question in question_file:
            logging.info(f"==> Processing question: {question['question']}")

            # get the question class by looking up the class in question_classes_file
            question_class = None
            for qc in question_classes_file["question_classes"]:
                if qc["class_name"] == question["class"]:
                    question_class = qc
                    break

            assert (
                question_class is not None
            ), f"Question class not found for question: {question['question']}"

            context_retriever = ContextRetriever(org_name=org_name, user=user_name)
            context = context_retriever.retrieve_context(question["question"])

            answer = self.llm.get_answer(question["question"], context)
            logging.info(f"Answer: {answer}")

            # validate the answer based on the question class
            validation_function = question_class["python_function"]
            # create an instance of the Validate class
            validation = Validate()
            # call the validation function based on the question class
            validation_result = getattr(validation, validation_function)(question, answer)

            if validation_result:
                logging.info("Correct answer!")
            else:
                logging.info(f"Incorrect answer! Expected: {question['answer']}, Actual: {answer}")
