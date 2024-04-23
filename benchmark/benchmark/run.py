import os
import sys
import time
from typing import Tuple

from tonic_validate import Benchmark, LLMResponse, ValidateApi, ValidateScorer
from tonic_validate.metrics import (
    AnswerConsistencyMetric,
    AnswerSimilarityMetric,
    AugmentationAccuracyMetric,
    AugmentationPrecisionMetric,
    LatencyMetric,
    RetrievalPrecisionMetric,
)

sys.path.insert(1, os.path.join(os.path.dirname(__file__), ".."))
from lorelai.contextretriever import ContextRetriever  # noqa E402
from lorelai.llm import Llm  # noqa E402


class Run:
    def __init__(self):
        self.llm = Llm(model="gpt-3.5-turbo")

    def ask_lorelai(self, question: str, context_ret: ContextRetriever) -> Tuple[str, str, float]:
        """
        Function that does all the preload for asking a question.
        Params:
                question, string, the question you want to ask
                context, ContextRetriever object containing the context.
        Returns:
                a tuple with 0 element answer, 1 element context, 2 is time in s.
        """
        context = context_ret.retrieve_context(question)[0]
        start = time.time()
        answer = self.llm.get_answer(question=question, context=context)
        end = time.time()
        # We calculate run time yet the metrics don't seem to have it :(
        run_time = round((end - start), 3)
        contexts = []
        for i in enumerate(context):
            contexts.append(i[1].page_content)
        return (answer, contexts, run_time)

    def do_benchmark(self, responses: list, evaluator: str):
        # Somebody help me get this damned annotation right
        # -> tonic_validate.classes.run.Run
        # it complains that this doesn't "exist"
        # yet that's the actual class...
        """
        Does the actual benchmarking
        Params:
            responses, list, list of LLMResponse objects
            evaluator, str, the model evaluator
        """
        scorer = ValidateScorer(
            [
                AnswerConsistencyMetric(),
                AnswerSimilarityMetric(),
                AugmentationPrecisionMetric(),
                AugmentationAccuracyMetric(),
                RetrievalPrecisionMetric(),
                LatencyMetric(),
            ],
            model_evaluator=evaluator,
        )
        run = scorer.score_responses(responses)
        return run

    def generate_output(self, run, api_key: str, project_id: str) -> None:
        """
        Does all of the output printing, file gen and optional push
        to tonic's dashboard thing.
        Params:
            run, a ValidateScorer object, your actual benchmark run
            api_key, str, your api key for tonic's ui
            project_id, str, the project ID for the UI.
        Returns:
            None
        """
        print("Overall Scores")
        print(run.overall_scores)
        print("------")
        for item in run.run_data:
            print("Question: ", item.reference_question)
            print("Answer: ", item.reference_answer)
            print("LLM Answer: ", item.llm_answer)
            print("Scores: ", item.scores)
            print("------")
        if api_key:
            validate_api = ValidateApi(api_key)
            validate_api.upload_run(project_id, run)

    def benchmark(self, org_name, user_name, question_file, evaluator, api_key, project_id):
        context_retriever = ContextRetriever(org_name=org_name, user_name=user_name)
        questions = [q["question"] for q in question_file]
        answers = [a["answer"] for a in question_file]
        responses = []
        benchmark = Benchmark(questions, answers)
        for question, answer in zip(questions, answers):
            answer, context_contents, elapsed_time = self.ask_lorelai(question, context_retriever)
            llm_response = LLMResponse(
                llm_answer=answer,
                llm_context_list=context_contents,
                benchmark_item=benchmark.item_for(question, answer),
                run_time=elapsed_time,
            )
            responses.append(llm_response)

        run = self.do_benchmark(responses, evaluator)
        self.generate_output(run, api_key, project_id)
