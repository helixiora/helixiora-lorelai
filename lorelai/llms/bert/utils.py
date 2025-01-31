from lorelai.llms.bert.pipeline import DistilBertPreprocessingPipeline
from transformers import AutoModelForSequenceClassification, DistilBertTokenizer
import torch
import timm

label_dict = {
    0:"Clarification",
    1:"Factual",
    2:"Operational",
    3:"Summarization"
}

def preprocess_data(texts, labels=None, model_name="distilbert-base-uncased", max_length=128):
    """
    Preprocess the data using the pipeline.
    Input:
        texts (list of str): List of raw input texts.
        labels (list of str, optional): label list.
        model_name (str): Name of the pretrained DistilBERT model.
        max_length (int): Maximum sequence length.
    Output:
        dict: Preprocessed inputs.
    """
    pipeline = DistilBertPreprocessingPipeline(model_name=model_name, max_length=max_length)
    return pipeline.preprocess_batch(texts, labels)

# tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
# model = timm.create_model('hf_hub:Hristo-Karagyozov/distilbert-prompt-classifier', pretrained=True)
# pipeline = DistilBertPreprocessingPipeline()

# Function to process inputs and return predictions
def predict_prompt_type(question):
    preprocessed = preprocess_data(question)
    input_ids = preprocessed["input_ids"]
    attention_mask = preprocessed["attention_mask"]
    ids = torch.tensor(input_ids)
    mask = torch.tensor(attention_mask)

    with torch.no_grad():
        outputs = model(input_ids=ids, attention_mask=mask)
        predictions = torch.argmax(outputs.logits, dim=1).item()

    return label_dict[predictions]