# Overview

The script called `loreleicli.py` enables querying indexed documents in Pinecone using LangChain and
OpenAI from the Command Line Interface (CLI).

## Usage

To use the script, follow these steps:

1. Install the required dependencies by running:

   ```bash
   pip install -r requirements.txt
   ```

1. Execute the script using the following command:

   ```bash
   python lorelaicli.py <question> [--org-name <org_name>] [--user-name <user_name>] [--model-type <model_type>]
   ```

   Replace `<question>` with your query/question. Optionally, you can specify the organisation name
   (`--org-name`), user name (`--user-name`), and model type (`--model-type`). If not specified,
   default values will be used.

## Arguments

- `question`: The question/query you want to ask.
- `--org-name`: Name of the organisation. (Optional)
- `--user-name`: Name of the user. (Optional)
- `--model-type`: Type of the model to use. (Optional, default: "OpenAILlm")

## Dependencies

- `colorama`: For terminal text colorization.

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open
an issue or create a pull request.
