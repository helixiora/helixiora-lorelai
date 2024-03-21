# Enhanced README for Lorelai RAG Proof of Concept Repository

# **WIP** This is a Work in Progress!

Walter: This repo is a work in progress. It's not meant to be beautiful, done or working. Rather, I'm working in the open so that others can see what I am doing.

### Todo:
1. the flask app is very basic but works
1. the crawler currently picks a specific file defined in [lorelai_pinecone.py#L30-L31]() instead of crawling the whole drive
1. the `test_query` script is not working yet

## Overview

This repository is dedicated to showcasing a Proof of Concept (POC) for Lorelai, a RAG (Retrieval-Augmented Generation) application. The project integrates with Google Drive via OAuth for content crawling, utilizes Pinecone for indexing, and leverages OpenAI's API for query processing. Its main components include a Flask-based web application for Google OAuth setup, nightly document indexing, and a testing script for query execution.

### Key Features

- **Google Drive Integration:** Securely crawl a user's Google Drive contents using OAuth.
- **Automated Indexing:** Nightly indexing of Google Drive documents into Pinecone for efficient retrieval.
- **Query Processing:** Leverage OpenAI's API to process queries with context retrieved from Pinecone.

### Components

- `app.py`: A Flask application to facilitate Google OAuth permission setup.
- `crawler.py`: A script for nightly crawling of Google Drive documents to index them into Pinecone.
- `test_query.py`: Executes a test query using context from Pinecone before querying OpenAI.

## Getting Started

Follow these steps to set up the project and run the components.

### Initial Setup

#### Obtain API Keys and Credentials

1. Obtain a Pinecone API key from [Pinecone's portal](https://app.pinecone.io/organizations/).
2. Acquire an OpenAI API key through [OpenAI's platform](https://platform.openai.com/api-keys).
3. Generate Google OAuth credentials via [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
4. Copy the `settings.json.example` file to `settings.json` and fill in the placeholders with the obtained values.
    1. The project id is the id of the project in the [google console](https://console.cloud.google.com/cloud-resource-manager) 

#### Prepare Your Environment

1. Create a Python virtual environment: `python -m venv .venv` and activate it with `source .venv/bin/activate`.
2. Install required dependencies: `pip install -r requirements.txt`.
3. Ensure all `.py` scripts are executable: `chmod +x crawler.py test_query.py`.

### Google OAuth Configuration

1. Launch the Flask application: `flask run`, and navigate to the local server URL ([http://127.0.0.1:5000](http://127.0.0.1:5000)).
    - Follow the on-screen instructions to log in and authorize access to Google Drive.
2. Confirm that credentials are stored correctly in SQLite by accessing the `userdb.sqlite` database and querying the `user_tokens` table. Example commands:
    ```bash
    sqlite3 userdb.sqlite
    .mode table
    .tables
    SELECT * FROM user_tokens;
    ```

### Executing the Crawler

1. Initiate the document crawling process: `./crawler.py`.
2. Check Pinecone to ensure your documents have been indexed successfully.

### Running Test Queries

1. Execute the test query script: `./test_query.py` to simulate querying with context from Pinecone and processing through OpenAI.

This documentation provides a comprehensive guide to getting started with the Lorelai RAG POC. Follow the outlined steps to set up your environment, configure access, and execute the components to explore the capabilities of this integration.