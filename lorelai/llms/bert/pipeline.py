"""
Module containing a preprocessing pipeline for DistilBERT.

The pipeline includes tokenization, attention mask generation, and label encoding.
"""

import torch
from sklearn.preprocessing import LabelEncoder
from transformers import DistilBertTokenizer


class DistilBertPreprocessingPipeline:
    """
    A preprocessing pipeline for DistilBERT.

    This pipeline includes tokenization, attention mask generation, and label encoding.
    """

    def __init__(self, model_name: str = "distilbert-base-uncased", max_length: int = 128):
        """Initialize the preprocessing pipeline.

        Args
        ----
            model_name (str): The name of the model to use.
            max_length (int): The maximum length of the input text.
        """
        self.tokenizer = DistilBertTokenizer.from_pretrained(model_name)
        self.max_length = max_length
        self.label_encoder = LabelEncoder()

    def encode_labels(self, labels: list[str]) -> list[int]:
        """
        Encode string labels into numeric values.

        Args
        ----
            labels (list of str): List of string labels.

        Returns
        -------
            list of int: List of encoded numeric labels.
        """
        return self.label_encoder.fit_transform(labels)

    def decode_labels(self, encoded_labels: list[int]) -> list[str]:
        """
        Decode numeric labels back into string labels.

        Args
        ----
            encoded_labels (list of int): List of encoded labels.

        Returns
        -------
            list of str: Decoded string labels.
        """
        return self.label_encoder.inverse_transform(encoded_labels)

    def preprocess_batch(self, texts: list[str], labels: list[str] | None = None) -> dict:
        """
        Preprocess a batch of texts and labels.

        Args
        ----
            texts (list of str): List of texts to preprocess.
            labels (list of str): List of string labels.

        Returns
        -------
            dict: Preprocessed data with input IDs, attention mask, and labels.
        """
        tokenized = self.tokenizer(
            texts=texts,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        result = {
            "input_ids": tokenized["input_ids"],
            "attention_mask": tokenized["attention_mask"],
        }
        if labels:
            result["labels"] = torch.tensor(self.encode_labels(labels), dtype=torch.long)
        return result
