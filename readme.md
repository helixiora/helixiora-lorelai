# Lorelai readme

## Overview

This repository is dedicated to showcasing a Proof of Concept (POC) for Lorelai, a RAG (Retrieval-Augmented Generation) application. The project integrates with Google Drive via OAuth for content crawling, utilizes Pinecone for indexing, and leverages OpenAI's API for query processing. Its main components include a Flask-based web application for Google OAuth setup, nightly document indexing, and a testing script for query execution.

### Key Features

- **Ask questions to your private google docs** A chat interface to ask questions to the info you have indexed
- **Google Drive Integration:** Securely crawl a user's Google Drive contents using OAuth.
- **Automated Indexing:** Nightly indexing of Google Drive documents into Pinecone for efficient retrieval.
- **Query Processing:** Leverage OpenAI's API to process queries with context retrieved from Pinecone.
- **Admin backend** See what info you have indexed in pinecone

### Components

- `app.py`: A Flask application to chat with your information. Includes signup, an admin backend and a chat interface
- `indexer.py`: A script for nightly crawling of Google Drive documents to index them into Pinecone.
- `lorelaicli.py`: Executes a test query using context from Pinecone before querying OpenAI.

## Getting Started

Follow these steps to set up the project and run the components.

### Initial Setup

### Prerequisites

Redis
a) On Linux:

1. Ubuntu/Debian:

```
sudo apt update
sudo apt install redis-server
```
2. CentOS/RedHat

```
sudo yum install epel-release
sudo yum install redis
sudo systemctl start redis
sudo systemctl enable redis
```
b) On macOS:

1. Using Homebrew

```
brew install redis
```
SQLite
a) On Linux:

1. Ubuntu/Debian:

```
sudo apt update
sudo apt install sqlite3
```

2. CentOS/RedHat

```
sudo yum install sqlite
```

b) on macOS

1. Using Homebrew

```
brew install sqlite
```



#### Obtain API Keys and Credentials

1. Obtain a Pinecone API key from [Pinecone's portal](https://app.pinecone.io/organizations/). If you don't have access to Helixiora's Pinecone, ask Walter.
2. Acquire an OpenAI API key through [OpenAI's platform](https://platform.openai.com/api-keys). If you don't have access to Helixiora's OpenAI, ask Walter.
3. Generate Google OAuth credentials via [Google Cloud Console](https://console.cloud.google.com/apis/credentials). If you don't have access to Lorelai's Google Cloud Profile, ask Walter.
4. In order to pass these values there are two options:

    a) Copy the `settings.json.example` file to `settings.json` and fill in the placeholders with the obtained values.

    b) You need to export the following env vars:

```
GOOGLE_CLIENT_ID
GOOGLE_PROJECT_ID
GOOGLE_AUTH_URI
GOOGLE_TOKEN_URI
GOOGLE_AUTH_PROVIDER_X509_CERT_U
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URIS
PINECONE_API_KEY
OPENAI_API_KEY
LORELAI_ENVIRONMENT
LORELAI_ENVIRONMENT_SLUG
```
Note that the project id is the id of the project in the [google console](https://console.cloud.google.com/cloud-resource-manager)

#### Running in a python venv

1. Create a Python virtual environment: `python -m venv .venv`
2. Activate it with `source .venv/bin/activate`.
3. Install required dependencies: `pip install -r requirements.txt`.
4. Ensure all `.py` scripts are executable: `chmod +x indexer.py lorelaicli.py`.
5. Run an rq worker:

   `.venv/bin/rq worker &`

   ```
    Worker rq:worker:dd2b92d43db1495383d426d5cb44ff79 started with PID 82721, version 1.16.1
    Subscribing to channel rq:pubsub:dd2b92d43db1495383d426d5cb44ff79
    *** Listening on default...
    Cleaning registries for queue: default

   ```
6. Launch the Flask application:
   ```
   export FLASK_APP=run.py
   flask run 
   ```
   Note: add an `&` to `flask run` to have it run in the background, or use multiple terminals.

#### Running using docker compose

1. Install and run [docker desktop](https://docs.docker.com/desktop/).
   1. on a mac, run `brew install docker` to install docker desktop
1. Get the stack of redis, celery and the flask app up and running using `docker-compose up --build`

### Initial Configuration

1. Once you followed the setup steps above, navigate to the local server URL ([http://127.0.0.1:5000](http://127.0.0.1:5000)).
    - You wil be asked to create an organisation if ./userdb.sqlite doesn't exist.
    - Note that this organization name will be the index name of the vector database folowing this structure: $env_name-$slug-$whatever_you_put_in_org_name
    - There's a limitation to the length of the index name sot the above string should not exceed 45 characters.
    - Follow the on-screen instructions to log in and authorize access to Google Drive.
2. Confirm that credentials are stored correctly in SQLite by accessing the `userdb.sqlite` database and querying the `users` table. Example commands:
    ```bash
    sqlite3 userdb.sqlite
    .mode table
    .tables
    SELECT * FROM users;
    ```

### Chat application

When logged in, you will see the chat interface at [https://127.0.0.1:5000]()

### Admin interface

Very rudimentary admin interface to see what you have stored in pinecone and run the indexer, accessible from [https://127.0.0.1:5000/admin]()

### Executing the Crawler

#### From the command line

1. Initiate the document crawling process: `./indexer.py`.
2. Check Pinecone to ensure your documents have been indexed successfully.

#### From the web UI

1. Go to [https://127.0.0.1:5000/admin]() and press the indexer button
2. Check the rq worker logs in case something goes wrong

### Running Test Queries

1. Execute the test query script: `./lorelaicli.py` to simulate querying with context from Pinecone and processing through OpenAI.

This documentation provides a comprehensive guide to getting started with the Lorelai RAG POC. Follow the outlined steps to set up your environment, configure access, and execute the components to explore the capabilities of this integration.

### Code quality: Flake8 and Black

We use flake8 and black as our code quality tools. It's convenient to run them in three places: your code editor, as git pre-commit hooks and using GitHub actions

#### VS Code

1. Install the following extensions from the Visual Studio Code marketplace:

   - Python (official extension by Microsoft)
   - Pylance (optional but recommended for better IntelliSense)
2. Adjust your settings to format and lint code on save. Add these lines to your settings.json in VS Code:

   ```json
   {
      "python.linting.enabled": true,
      "python.linting.flake8Enabled": true,
      "python.formatting.provider": "black",
      "editor.formatOnSave": true,
      "python.linting.flake8Args": [
         "--max-line-length=88",
         "--ignore=E203,W503"
      ]
   }
   ```

   These settings enable linting with Flake8 and formatting with Black on each file save, promoting a workflow of continuous code quality.

#### GitHub Actions Integration

To ensure that the code quality is maintained across all branches, we integrate these tools into our CI/CD pipeline using GitHub Actions.

#### Pre-commit Setup

Pre-commit hooks help enforce standards by automatically checking and formatting code before it's committed to the repository.

1. Install pre-commit on your local development machine. It's recommended to install it globally using `pip install pre-commit`
2. Install the hooks using `pre-commit install`

Now, everytime you commit the hooks in `.pre-commit-config.yaml` will be run and the commit will fail if those hooks make a change

# Architecture diagram

Below a schematic of how we could build each of these modules so that we can keep the architecture manageable

![Lorelai System Diagram](./imgs/Lorelai%20System%20Diagram.png)

# Benchmarking

See [the benchmark directory](benchmark/readme.md)

# Frequently Asked Questions

for a number of in-depth questions, see the [FAQ](docs/faq.md)
