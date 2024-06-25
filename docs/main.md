<a id="tasks"></a>

# tasks

The rq jobs that are executed asynchronously.

<a id="tasks.execute_rag_llm"></a>

#### execute_rag_llm

```python
def execute_rag_llm(chat_message, user, organisation)
```

An rq job to execute the RAG+LLM model.

<a id="tasks.run_indexer"></a>

#### run_indexer

```python
def run_indexer(org_row: list[Any], user_rows: list[list[Any]])
```

Run the indexer job to index the Google Drive documents in Pinecone.

<a id="lorelaicli"></a>

# lorelaicli

Query indexed documents in Pinecone using LangChain and OpenAI in the CLI

<a id="lorelaicli.main"></a>

#### main

```python
def main() -> None
```

Retrieve the context, ask a question, and display the results.

<a id="lorelaicli.setup_arg_parser"></a>

#### setup_arg_parser

```python
def setup_arg_parser() -> argparse.ArgumentParser
```

Set up argument parser for command-line options. Params: none Returns: ArgumentParser object

<a id="lorelaicli.get_organisation"></a>

#### get_organisation

```python
def get_organisation(org_name: str or None) -> tuple
```

Retrieve or select an organisation. Params: org_name: str, name of the organisation Returns: tuple
with org ID as the 0 object or select_organisation function

<a id="lorelaicli.select_organisation"></a>

#### select_organisation

```python
def select_organisation() -> tuple
```

Interactively select an organisation from a list. Params: none Returns: tuple with the org ID and
name

<a id="lorelaicli.get_user_from_organisation"></a>

#### get_user_from_organisation

```python
def get_user_from_organisation(org_id: int,
                               user_name: str or None = None) -> int
```

Retrieve or select a user from a specific organisation. Params: org_id, int, the organisation ID
user_name, str, the user name

**Returns**:

user ID int or results from select_user_from_organisation function

<a id="lorelaicli.select_user_from_organisation"></a>

#### select_user_from_organisation

```python
def select_user_from_organisation(org_id: int) -> int
```

Interactively select a user from a list. Params: org_id: int, the ID of the organisation

**Returns**:

user id: int

<a id="lorelaicli.display_results"></a>

#### display_results

```python
def display_results(answer: str, sources: dict) -> None
```

Display the results in a formatted manner.

<a id="run"></a>

# run

the main application file for the OAuth2 flow flask app

<a id="run.index"></a>

#### index

```python
@app.route("/")
def index()
```

the index page

**Returns**:

- `string` - the index page

<a id="run.serve_js"></a>

#### serve_js

```python
@app.route("/js/<script_name>.js")
def serve_js(script_name)
```

the javascript endpoint

<a id="run.logout"></a>

#### logout

```python
@app.route("/logout")
def logout()
```

the logout route

<a id="run.page_not_found"></a>

#### page_not_found

```python
@app.errorhandler(404)
def page_not_found(e)
```

the error handler for 404 errors

<a id="run.internal_server_error"></a>

#### internal_server_error

```python
@app.errorhandler(500)
def internal_server_error(e)
```

the error handler for 500 errors

<a id="indexer"></a>

# indexer

Crawl the Google Drive and index the documents.

It processes the documents using Pinecone and OpenAI API through langchain

<a id="indexer.main"></a>

#### main

```python
def main() -> None
```

Implement the main function.

<a id="lorelai"></a>

# lorelai

<a id="lorelai.contextretriever"></a>

# lorelai.contextretriever

This module contains the ContextRetriever class, which is responsible for retrieving context for a
given question from Pinecone.

The ContextRetriever class manages the integration with Pinecone and OpenAI services, facilitating
the retrieval of relevant document contexts for specified questions. It leverages Pinecone's vector
search capabilities alongside OpenAI's embeddings and language models to generate responses based on
the retrieved contexts.

<a id="lorelai.contextretriever.ContextRetriever"></a>

## ContextRetriever Objects

```python
class ContextRetriever()
```

A class to retrieve context for a given question from Pinecone.

This class manages the integration with Pinecone and OpenAI services, facilitating the retrieval of
relevant document contexts for specified questions. It leverages Pinecone's vector search
capabilities alongside OpenAI's embeddings and language models to generate responses based on the
retrieved contexts.

<a id="lorelai.contextretriever.ContextRetriever.__init__"></a>

#### \_\_init\_\_

```python
def __init__(org_name: str, user: str)
```

Initializes the ContextRetriever instance.

**Arguments**:

- `org_name` _str_ - The organization name, used for Pinecone index naming.
- `user` _str_ - The user name, potentially used for logging or customization.

<a id="lorelai.contextretriever.ContextRetriever.retrieve_context"></a>

#### retrieve_context

```python
def retrieve_context(
        question: str) -> Tuple[List[Document], List[Dict[str, Any]]]
```

Retrieves context for a given question using Pinecone and OpenAI.

**Arguments**:

- `question` _str_ - The question for which context is being retrieved.

**Returns**:

- `tuple` - A tuple containing the retrieval result and a list of sources for the context.

<a id="lorelai.contextretriever.ContextRetriever.get_all_indexes"></a>

#### get_all_indexes

```python
def get_all_indexes() -> IndexList
```

Retrieves all indexes in Pinecone along with their metadata.

**Returns**:

- `list` - A list of dictionaries containing the metadata for each index.

<a id="lorelai.contextretriever.ContextRetriever.get_index_details"></a>

#### get_index_details

```python
def get_index_details(index_host: str) -> List[Dict[str, Any]]
```

Retrieves details for a specified index in Pinecone.

**Arguments**:

- `index_host` _str_ - The host of the index for which to retrieve details.

**Returns**:

List\[Dict\[str, Any\]\]: A list of dictionaries, each containing metadata for vectors in the
specified index.

<a id="lorelai.utils"></a>

# lorelai.utils

This module contains utility functions for the Lorelai package.

<a id="lorelai.utils.pinecone_index_name"></a>

#### pinecone_index_name

```python
def pinecone_index_name(org: str,
                        datasource: str,
                        environment: str = "dev",
                        env_name: str = "lorelai",
                        version: str = "v1") -> str
```

Return the pinecone index name for the org.

<a id="lorelai.utils.get_creds_from_os"></a>

#### get_creds_from_os

```python
def get_creds_from_os(service: str) -> dict[str, str]
```

Load credentials from OS env vars.

**Arguments**:

______________________________________________________________________

- `service` _str_ - The name of the service (e.g 'openai', 'pinecone') for which to load

**Returns**:

______________________________________________________________________

- `dict` - A dictionary containing the creds for the specified service.

<a id="lorelai.utils.load_config"></a>

#### load_config

```python
def load_config(service: str) -> dict[str, str]
```

Load credentials for a specified service from settings.json.

If file is non-existent or has syntax errors will try to pull from OS env vars.

**Arguments**:

______________________________________________________________________

- `service` _str_ - The name of the service (e.g 'openai', 'pinecone') for which to load
  credentials.

**Returns**:

______________________________________________________________________

- `dict` - A dictionary containing the creds for the specified service.

<a id="lorelai.utils.get_db_connection"></a>

#### get_db_connection

```python
def get_db_connection()
```

Get a database connection.

## Returns

```
conn: a connection to the database
```

<a id="lorelai.utils.save_google_creds_to_tempfile"></a>

#### save_google_creds_to_tempfile

```python
def save_google_creds_to_tempfile(refresh_token, token_uri, client_id,
                                  client_secret)
```

load the google creds to a tempfile.

This is needed because the GoogleDriveLoader uses the Credentials.from_authorized_user_file method
to load the credentials

**Arguments**:

- `refresh_token`: the refresh token
- `token_uri`: the token uri
- `client_id`: the client id
- `client_secret`: the client secret

<a id="lorelai.utils.get_embedding_dimension"></a>

#### get_embedding_dimension

```python
def get_embedding_dimension(model_name) -> int
```

Returns the dimension of embeddings for a given model name.

This function currently uses a hardcoded mapping based on documentation, as there's no API endpoint
to retrieve this programmatically. See: https://platform.openai.com/docs/models/embeddings

**Arguments**:

- `model_name`: The name of the model to retrieve the embedding dimension for.

<a id="lorelai.utils.get_index_stats"></a>

#### get_index_stats

```python
def get_index_stats(index_name: str) -> DescribeIndexStatsResponse | None
```

Retrieve the details for a specified index in Pinecone.

**Arguments**:

- `index_name`: the name of the index for which to retrieve details

**Returns**:

a list of dictionaries containing the metadata for the specified index

<a id="lorelai.utils.print_index_stats_diff"></a>

#### print_index_stats_diff

```python
def print_index_stats_diff(index_stats_before, index_stats_after)
```

prints the difference in the index statistics

<a id="lorelai.llm"></a>

# lorelai.llm

a class that takes a question and context and sends it to the LLM, then returns the answer

<a id="lorelai.llm.Llm"></a>

## Llm Objects

```python
class Llm()
```

A class to interact with the OpenAI llm for answering questions based on context

<a id="lorelai.llm.Llm.get_answer"></a>

#### get_answer

```python
def get_answer(question, context)
```

Get the answer to a question based on the provided context using the OpenAI language model.

parameters: question (str): The question to be answered. context (str): The context in which the
question is asked.

<a id="lorelai.llm.Llm.get_llm_status"></a>

#### get_llm_status

```python
def get_llm_status()
```

Get the status of the LLM model.

<a id="lorelai.processor"></a>

# lorelai.processor

Contains the Processor class that processes and indexes them in Pinecone.

<a id="lorelai.processor.Processor"></a>

## Processor Objects

```python
class Processor()
```

This class is used to process the Google Drive documents and index them in Pinecone.

<a id="lorelai.processor.Processor.__init__"></a>

#### \_\_init\_\_

```python
def __init__()
```

Initialize the Processor class.

<a id="lorelai.processor.Processor.pinecone_filter_deduplicate_documents_list"></a>

#### pinecone_filter_deduplicate_documents_list

```python
def pinecone_filter_deduplicate_documents_list(documents: Iterable[Document],
                                               pc_index) -> list
```

Process the vectors and removes vector which exist in database.

Also tag doc metadata with new user

**Arguments**:

- `documents`: the documents to process
- `pc_index`: pinecone index object

**Returns**:

1. (list of documents deduplicated and filtered , ready to be inserted in pinecone)
1. (number of documents updated)

<a id="lorelai.processor.Processor.pinecone_format_vectors"></a>

#### pinecone_format_vectors

```python
def pinecone_format_vectors(documents: Iterable[Document],
                            embeddings_model: Embeddings) -> list
```

process the documents and format them for pinecone insert.

**Arguments**:

- `docs`: the documents to process
- `embeddings_model`: embeddings_model object

**Returns**:

list of documents ready to be inserted in pinecone

<a id="lorelai.processor.Processor.remove_nolonger_accessed_documents"></a>

#### remove_nolonger_accessed_documents

```python
def remove_nolonger_accessed_documents(formatted_documents, pc_index,
                                       embedding_dimension, user_email)
```

Delete document from pinecone, which user no longer have accessed

**Arguments**:

- `formatted_documents`: document user currently have access to
- `pc_index`: pinecone index object
- `embedding_dimension`: embedding model dimension

**Returns**:

None

<a id="lorelai.processor.Processor.store_docs_in_pinecone"></a>

#### store_docs_in_pinecone

```python
def store_docs_in_pinecone(docs: Iterable[Document], index_name,
                           user_email) -> None
```

process the documents and index them in Pinecone

**Arguments**:

- `docs`: the documents to process
- `index_name`: name of index
- `user_email`: the user to process

<a id="lorelai.processor.Processor.google_docs_to_pinecone_docs"></a>

#### google_docs_to_pinecone_docs

```python
def google_docs_to_pinecone_docs(document_ids: list[str],
                                 credentials: Credentials, org_name: str,
                                 user_email: str) -> None
```

Process the Google Drive documents and divide them into pinecone compatible chunks.

**Arguments**:

- `document_id`: the document to process
- `credentials`: the credentials to use to process the document
- `org`: the organisation to process
- `user`: the user to process

**Returns**:

None

<a id="lorelai.indexer"></a>

# lorelai.indexer

this file creates a class to process google drive documents using the google drive api, chunk them
using langchain and then index them in pinecone

<a id="lorelai.indexer.Indexer"></a>

## Indexer Objects

```python
class Indexer()
```

Used to process the Google Drive documents and index them in Pinecone.

<a id="lorelai.indexer.Indexer.index_org_drive"></a>

#### index_org_drive

```python
def index_org_drive(org: list[Any], users: list[list[Any]]) -> None
```

Process the Google Drive documents for an organisation.

**Arguments**:

- `org`: the organisation to process, a list of org details (org_id, name)
- `users`: the users to process, a list of user details (user_id, name, email, token, refresh_token)

**Returns**:

None

<a id="lorelai.indexer.Indexer.index_user_drive"></a>

#### index_user_drive

```python
def index_user_drive(user: list[Any], org: list[Any]) -> None
```

Process the Google Drive documents for a user and index them in Pinecone.

**Arguments**:

- `user`: the user to process, a list of user details (user_id, name, email, token, refresh_token)
- `org`: the organisation to process, a list of org details (org_id, name)

**Returns**:

None

<a id="lorelai.indexer.Indexer.get_google_docs_ids"></a>

#### get_google_docs_ids

```python
def get_google_docs_ids(credentials) -> list[str]
```

Retrieve all Google Docs document IDs from the user's Google Drive.

**Arguments**:

- `credentials`: Google-auth credentials object for the user

**Returns**:

List of document IDs

<a id="app"></a>

# app

Basic init in order to make this an explicit package.

<a id="app.utils"></a>

# app.utils

Utility functions for the application.

<a id="app.utils.is_admin"></a>

#### is_admin

```python
def is_admin(google_id: str) -> bool
```

Check if the user is an admin.

<a id="app.utils.get_db_connection"></a>

#### get_db_connection

```python
def get_db_connection()
```

Get a database connection.

## Returns

```
conn: a connection to the database
```

<a id="app.routes.auth"></a>

# app.routes.auth

Routes for user authentication.

<a id="app.routes.auth.profile"></a>

#### profile

```python
@auth_bp.route("/profile")
def profile()
```

the profile page

<a id="app.routes.auth.register"></a>

#### register

```python
@auth_bp.route("/register", methods=["GET", "POST"])
def register()
```

Register a new user.

<a id="app.routes.auth.oauth_callback"></a>

#### oauth_callback

```python
@auth_bp.route("/oauth2callback")
def oauth_callback()
```

OAuth2 callback route.

<a id="app.routes.auth.login_user"></a>

#### login_user

```python
def login_user(name: str, email: str, org_id: int, organisation: str) -> None
```

Log the user in by setting the session variables.

<a id="app.routes.auth.check_user_in_database"></a>

#### check_user_in_database

```python
def check_user_in_database(email: str) -> UserInfo
```

Check if the user exists in the database.""

<a id="app.routes.auth.process_user"></a>

#### process_user

```python
def process_user(organisation: str, username: str, user_email: str,
                 access_token: str, refresh_token: str, expires_in: str,
                 token_type: str, scope: list) -> dict
```

Process the user information obtained from Google.

<a id="app.routes.admin"></a>

# app.routes.admin

This module contains the routes for the admin page.

<a id="app.routes.admin.admin"></a>

#### admin

```python
@admin_bp.route("/admin")
def admin()
```

The admin page.

<a id="app.routes.admin.job_status"></a>

#### job_status

```python
@admin_bp.route("/admin/job-status/<job_id>")
def job_status(job_id)
```

Return the status of a job given its job_id

<a id="app.routes.admin.start_indexing"></a>

#### start_indexing

```python
@admin_bp.route("/admin/index", methods=["POST"])
def start_indexing()
```

Start indexing the data

<a id="app.routes.admin.list_indexes"></a>

#### list_indexes

```python
@admin_bp.route("/admin/pinecone")
def list_indexes()
```

the list indexes page

<a id="app.routes.admin.index_details"></a>

#### index_details

```python
@admin_bp.route("/admin/pinecone/<host_name>")
def index_details(host_name: str) -> str
```

the index details page

<a id="app.routes.chat"></a>

# app.routes.chat

<a id="app.routes.chat.chat"></a>

#### chat

```python
@chat_bp.route("/chat", methods=["POST"])
def chat()
```

Endpoint to post chat messages.

<a id="app.routes.chat.fetch_chat_result"></a>

#### fetch_chat_result

```python
@chat_bp.route("/chat", methods=["GET"])
def fetch_chat_result()
```

Endpoint to fetch the result of a chat operation.

<a id="app.tasks"></a>

# app.tasks

This module contains the tasks that are executed asynchronously.

<a id="app.tasks.execute_rag_llm"></a>

#### execute_rag_llm

```python
def execute_rag_llm(chat_message: str, user: str, organisation: str) -> dict
```

A task to execute the RAG+LLM model.

<a id="app.tasks.run_indexer"></a>

#### run_indexer

```python
def run_indexer()
```

An rq job to run the indexer
