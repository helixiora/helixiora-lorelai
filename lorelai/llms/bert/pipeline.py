import torch
from sklearn.preprocessing import LabelEncoder
from transformers import DistilBertTokenizer


class DistilBertPreprocessingPipeline:
    """
    A preprocessing pipeline for DistilBERT, including tokenization,
    attention mask generation, and label encoding.
    """

    def __init__(self, model_name="distilbert-base-uncased", max_length=128):
        """
        Initialize the preprocessing pipeline.

        """
        self.tokenizer = DistilBertTokenizer.from_pretrained(model_name)
        self.max_length = max_length
        self.label_encoder = LabelEncoder()

    def encode_labels(self, labels):
        """
        Encode string labels into numeric values.

        """
        return self.label_encoder.fit_transform(labels)

    def decode_labels(self, encoded_labels):
        """
        Decode numeric labels back into string labels.

        Args:
            encoded_labels (list of int): List of encoded labels.

        Returns:
            list of str: Decoded string labels.
        """
        return self.label_encoder.inverse_transform(encoded_labels)


    def preprocess_batch(self, texts, labels=None):
        """
        Preprocess a batch of texts and labels.

        """
        tokenized = self.tokenizer(
            texts,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        result = {
            "input_ids": tokenized["input_ids"],
            "attention_mask": tokenized["attention_mask"],
        }
        if labels:
            result["labels"] = torch.tensor(self.encode_labels(labels), dtype=torch.long)
        return result