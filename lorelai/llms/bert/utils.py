"""
Module containing utility functions for the DistilBERT model.

This module provides functions for preprocessing data and making predictions using the DistilBERT
model.
"""

import logging
import sys
import os
from transformers import pipeline

# Label mapping as a constant
LABEL_DICT = {
    0: "Clarification",  # Asking for explanation or clarification
    1: "Factual",  # Asking for specific facts or information
    2: "Operational",  # Asking how to do something or requesting an action
    3: "Summarization",  # Asking for overview or comparison
}

# Initialize the classifier at module level
logging.info("Initializing classifier pipeline...")
pipeline_kwargs = {}
if sys.platform == "darwin":
    logging.info("Using macOS-specific pipeline settings")
    # Disable tokenizer parallelism to prevent deadlocks on macOS
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    pipeline_kwargs.update(
        {
            "device": -1,  # Force CPU
            "num_workers": 0,  # Disable multiprocessing
        }
    )

CLASSIFIER = pipeline(
    "text-classification",
    model="helixiora/distilbert-another-classifier",
    top_k=None,  # Return scores for all classes
    **pipeline_kwargs,
)
logging.info("Pipeline initialization completed")


def predict_prompt_type(question: str) -> dict:
    """Predict the prompt type for a given question.

    Args
    ----
        question (str): The question to predict the prompt type for.

    Returns
    -------
        dict: A dictionary containing:
            - success (bool): Whether the prediction was successful
            - predicted_label (str, optional): The predicted prompt type
            - label_scores (dict, optional): Scores for each label
            - highest_score (float, optional): The score of the predicted label
            - error (str, optional): Error message if success is False
    """
    try:
        # Format the input (similar to minimal template)
        input_text = f"Query: {question}"
        logging.debug(f"Formatted input text: {input_text}")

        # Make prediction
        result = CLASSIFIER(input_text)[0]
        logging.debug(f"Raw prediction result: {result}")

        # Convert scores to dict with actual labels
        scores = {
            LABEL_DICT[int(score["label"].split("_")[-1])]: score["score"] for score in result
        }
        logging.debug(f"Processed scores: {scores}")

        # Find the highest scoring label
        predicted_label = max(scores.items(), key=lambda x: x[1])[0]
        logging.info(f"Predicted label: {predicted_label} (score: {scores[predicted_label]:.4f})")

        return {
            "success": True,
            "predicted_label": predicted_label,
            "label_scores": scores,
            "highest_score": scores[predicted_label],
        }
    except Exception as e:
        logging.error(f"Error in predict_prompt_type: {str(e)}")
        logging.exception("Full traceback:")
        return {
            "success": False,
            "error": str(e),
        }
