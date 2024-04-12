"""
  LaurelAI benchmarking module
"""

import argparse
import json
import time
from tonic_validate import ValidateApi, ValidateScorer, Benchmark, LLMResponse
from tonic_validate.metrics import (
    AnswerConsistencyMetric,
    AnswerSimilarityMetric,
    AugmentationPrecisionMetric,
    AugmentationAccuracyMetric,
    RetrievalPrecisionMetric,
    LatencyMetric,
)
from lorelai.contextretriever import ContextRetriever
from lorelai.llm import Llm


def setup_arg_parser() -> argparse.ArgumentParser:
    """
    Does the arg parser things.
    Params:
            None
    Returns:
            argparser object.
    """
    parser = argparse.ArgumentParser(description="Runs a benchmark.")
    parser.add_argument(
        "--question_file", "-q", help="Path to json containing questions and answers", required=True
    )
    parser.add_argument("--org_name", "-o", help="Name of the organisation", required=True)
    parser.add_argument("--user_name", "-u", help="Name of the user", required=True)
    parser.add_argument("--api_key", help="Api key for tonic UI", default=None)
    parser.add_argument("--project_id", help="Project ID for tonic UI", default=None)
    parser.add_argument(
        "--evaluator", help="Model used to evaluate benchmarks", default="gpt-3.5-turbo"
    )

    return parser


def ask_lorelai(question: str, context_ret: ContextRetriever) -> (str, str, float):
    """
    Function that does all the preload for asking a question.
    Params:
             question, string, the question you want to ask
             context, ContextRetriever object containing the context.
    Returns:
             a tuple with 0 element answer, 1 element context, 2 is time in s.
    """
    context = context_ret.retrieve_context(question)[0]
    llm = Llm(model="gpt-3.5-turbo")
    start = time.time()
    answer = llm.get_answer(question=question, context=context)
    end = time.time()
    # We calculate run time yet the metrics don't seem to have it :(
    run_time = round((end - start), 3)
    contexts = []
    for i in enumerate(context):
        contexts.append(i[1].page_content)
    return (answer, contexts, run_time)


def do_benchmark(responses: list, evaluator: str):
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


def generate_output(run, api_key: str, project_id: str) -> None:
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


def main() -> None:
    """
    Tie it all together
    """
    parser = setup_arg_parser()
    args = parser.parse_args()

    with open(args.question_file, "r", encoding="utf-8") as f:
        q_a = json.load(f)

    enriched_context = ContextRetriever(org_name=args.org_name, user=args.user_name)
    questions = [q["question"] for q in q_a]
    answers = [a["answer"] for a in q_a]
    responses = []
    benchmark = Benchmark(questions, answers)
    for i in benchmark:
        resp = ask_lorelai(i.question, enriched_context)
        llm_response = LLMResponse(
            llm_answer=resp[0], llm_context_list=resp[1], benchmark_item=i, run_time=resp[2]
        )
        responses.append(llm_response)

    run = do_benchmark(responses, args.evaluator)
    generate_output(run, args.api_key, args.project_id)


if __name__ == "__main__":
    main()
