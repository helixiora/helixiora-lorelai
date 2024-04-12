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

#### Obtain API Keys and Credentials

1. Obtain a Pinecone API key from [Pinecone's portal](https://app.pinecone.io/organizations/). If you don't have access to Helixiora's Pinecone, ask Walter.
2. Acquire an OpenAI API key through [OpenAI's platform](https://platform.openai.com/api-keys). If you don't have access to Helixiora's OpenAI, ask Walter.
3. Generate Google OAuth credentials via [Google Cloud Console](https://console.cloud.google.com/apis/credentials). If you don't have access to Lorelai's Google Cloud Profile, ask Walter.
4. Copy the `settings.json.example` file to `settings.json` and fill in the placeholders with the obtained values.
    1. The project id is the id of the project in the [google console](https://console.cloud.google.com/cloud-resource-manager)

#### Running in a python venv

1. Create a Python virtual environment: `python -m venv .venv` and activate it with `source .venv/bin/activate`.
2. Install required dependencies: `pip install -r requirements.txt`.
3. Ensure all `.py` scripts are executable: `chmod +x indexer.py lorelaicli.py`.
4. Set up redis and start it locally
   1. On a mac: `brew install redis` followed by `redis-server`
   2. On linux: <add instructions>
5. Run a celery worker:
   ```
   (.venv) walterheck in ~/source/helixiora/helixiora-crawler on frontend-app-merge
   > celery -A app.celery worker

   ```
6. Create a .env file with this variables
   ```
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   ```
7. Launch the Flask application: `flask run`

#### Running using docker compose

1. Install and run [docker desktop](https://docs.docker.com/desktop/).
   1. on a mac, run `brew install docker` to install docker desktop
1. Get the stack of redis, celery and the flask app up and running using `docker-compose up --build`

### Google OAuth Configuration

1. Once you followed the setup steps above, navigate to the local server URL ([http://127.0.0.1:5000](http://127.0.0.1:5000)).
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

Very rudimentary admin interface to see what you have stored in pinecone, accessible from [https://127.0.0.1:5000/admin/pinecone]()

### Executing the Crawler

1. Initiate the document crawling process: `./indexer.py`.
2. Check Pinecone to ensure your documents have been indexed successfully.

### Running Test Queries

1. Execute the test query script: `./lorelaicli.py` to simulate querying with context from Pinecone and processing through OpenAI.

This documentation provides a comprehensive guide to getting started with the Lorelai RAG POC. Follow the outlined steps to set up your environment, configure access, and execute the components to explore the capabilities of this integration.

# FAQ

Below a number of questions that are open

## 1. [Walter - 21-03-2024] A Pinecone Index has a property called 'dimension', what is it and what value should it have?

   A: (From ChatGPT): The "dimension" in the context of a Pinecone Index refers to the size of the vector embeddings that the index is designed to store and query. Vector embeddings are numerical representations of data points (such as text, images, or any other data type that can be converted into a high-dimensional space) in a vector space. Each vector is an array of numbers, and the "dimension" is the length of this array.

   The value that the "dimension" property should have depends on the model or process used to generate the embeddings. Different models produce embeddings of different sizes. For example, embeddings from one type of natural language processing (NLP) model might be 300-dimensional, while embeddings from another model might be 768-dimensional. This means that each vector from the first model would have 300 numbers, and each vector from the second model would have 768 numbers.

   When creating a Pinecone Index, it's important to set the "dimension" property to match the size of the embeddings you plan to store. If your embeddings are 768-dimensional, you should create a Pinecone Index with a dimension of 768. This ensures that the index can accurately store and perform similarity search or other operations on your embeddings.

   Here's a brief example of how you might determine the dimension for a Pinecone Index:

   1. **Determine Embedding Model Output Size**: First, identify the model you are using for generating embeddings and check the documentation or configuration to find out the size of the output vectors (the dimensionality).

   2. **Configure Pinecone Index**: When setting up your Pinecone Index, use this dimension size as the value for the index's "dimension" property.

   It's crucial that the "dimension" of the Pinecone Index matches the dimensionality of the vectors you intend to store in it. Misalignment in dimensions would lead to errors when trying to insert vectors into the index or retrieve them for queries.

## 2. [Walter - 21-03-2024] We have signed an AWS marketplace agreement for Pinecone, but it seems like now we are being billed directly. Which is it, and what's the difference?

## 3. [Walter - 21-03-2024] We will have many users of our chat app, and each user might have dozens of data sources, with thousands of documents per datasource. Should we be running a pinecone index per user, or one index per user per service? or one index overall?

   Given your emphasis on data isolation, particularly ensuring that users cannot access data from other users (or companies), alongside the desire for efficiency in data storage and indexing, a more nuanced approach is warranted. Your system needs to balance strict data isolation with the efficiency of not redundantly indexing identical documents for users within the same company. Here's a strategy that could work well for your requirements:

   ### Multi-Tenant Indexing with Access Control

   **Concept**: Implement a multi-tenant system where each company has its own index (or set of indexes) within Pinecone (or your chosen vector database). Within each company's index, documents are indexed once, but access control mechanisms ensure that users can only query and retrieve documents they're authorized to see.

   **How It Works**:

   1. **Company-Level Indexing**:
   - Create a separate Pinecone index for each company. This index stores all documents accessible to users within that company, avoiding redundant indexing of shared documents.
   - This approach isolates data at the company level, ensuring no cross-company data access.

   2. **Document Access Control**:
   - Implement an access control layer in your application logic that manages which users can access which documents. This could involve tagging each document with user or group permissions upon indexing.
   - When a user performs a query, the access control layer filters the query to only include documents that user is authorized to access. This filtering can happen before querying Pinecone or as a post-query filtering step, depending on the capabilities of your vector database and the specifics of your implementation.

   3. **Efficient Querying**:
   - To support efficient querying within this framework, design your query processor to first validate user access rights based on the document metadata, then execute the query against the company's Pinecone index, and finally filter the results based on the user's permissions.

   **Advantages**:

   - **Data Isolation**: Complete isolation of company data is maintained, with no possibility of cross-company data access.
   - **Efficiency**: Documents shared by users within the same company are indexed once, reducing storage and processing overhead.
   - **Scalability**: Each company's index can scale independently, allowing for resource allocation based on company size and usage patterns.
   - **Security**: By integrating document access control at the application layer, you ensure that security policies can be dynamically adjusted without reindexing data.

   **Considerations**:

   - **Complexity in Access Control Logic**: This approach requires careful implementation of access control logic to ensure accurate and secure data access.
   - **Resource Allocation**: While more efficient than indexing documents per user, company-level indexing still requires careful resource management, especially as the number of companies and documents grows.
   - **Compliance and Auditing**: Implement logging and auditing mechanisms to track access and queries, ensuring compliance with data protection regulations.

   ### Implementation Steps:

   1. **Index Setup**: When onboarding a new company, create a dedicated Pinecone index for that company.
   2. **Document Indexing**: As documents are added, index them in the company's Pinecone index with associated access control metadata.
   3. **Query Processing**: Implement a query processing system that checks user permissions, filters queries based on those permissions, and retrieves results from the relevant company index.

   By carefully designing your system with these principles in mind, you can achieve the dual goals of strict data isolation and efficient data management, ensuring that your chat application remains secure, scalable, and cost-effective.

## 4. [Walter - 21-03-2024] We have something called OpenAIEmbeddings. What are these and how do they work? How are they different for other models?

   A: (from ChatGPT): The sizes of the embeddings produced by different OpenAI models, particularly those designed for generating embeddings, can vary based on the specific model and version you are using. As of my last update, OpenAI offers several models that can produce embeddings, such as the ones based on the GPT (Generative Pre-trained Transformer) architecture and specialized embedding models.

   ### GPT-3 Embeddings

   For the GPT-3 models, the embeddings size isn't directly specified because GPT-3 is primarily known as a generative model. However, when working with embeddings derived from GPT-3 or similar models, the dimensionality can be linked to the size of the model's hidden layers. For example, GPT-3 models have sizes ranging from 125 million to 175 billion parameters, but the "dimension" of interest for embeddings typically corresponds to the model's hidden state size, not the total number of parameters. This size can vary but might be around 768 for smaller models up to 4096 for some of the larger configurations.

   ### Specialized Embedding Models

   OpenAI has released models specifically designed for generating embeddings, which might be more directly applicable to your question. These models, such as those accessible through the OpenAI API for embeddings, provide a more straightforward approach to generating embeddings for various types of data, including text.

   - **text-embedding-ada-002**: Produces 1024-dimensional embeddings.
   - **text-embedding-babbage-001**: Produces 2048-dimensional embeddings.
   - **text-embedding-curie-001**: Produces 4096-dimensional embeddings.
   - **text-embedding-davinci-001**: Produces 12288-dimensional embeddings.

   ### Choosing the Right Dimension

   When using Pinecone or any vector database with OpenAI's models, you need to set the dimension of your index to match the output size of the embeddings you're working with. For instance, if you're using the `text-embedding-ada-002` model for generating text embeddings, you would set the dimension of your Pinecone Index to 1024 to accommodate the size of the vectors produced by this model.

   ### Important Notes

   - **Model Updates**: The information about model sizes and capabilities can change as OpenAI releases new models or updates existing ones. Always check the latest documentation for the most accurate and up-to-date information.
   - **Use Case**: Choose the model based on your specific needs, considering factors like the trade-offs between computational cost and the level of semantic richness required for your application.

   For the most current information about OpenAI models and their embedding sizes, refer directly to the OpenAI API documentation.

## 5. [Walter - 21-03-2024] It seems like the vectorizer (the code that translates our documents into vector format) is a key component. How do these work, what are the best practices?

## 6. [Walter - 21-03-2024] If my assumption is correct, data that is vectorized with a specific algorithm is only usable with an algorithm that knows the same format, kind of like encryption. Is this true? And if so, how do we handle that coupling?

   A: Pinecone stores metadata with every vector, which can be used for many things. As of this answer, the default metadata is: METADATA

    source: "<<google docs link>>"
    text: "<<the original text that is in the vector>>"
    title: "<<the title of the doc>>"
    when: "<<when was this stored>>"

   We are able to add fields to the metadata, so this might help. However, the index has a dimension that can't be changed, so changing that might be tricky

## 7. [Walter - 21-03-2024] How do we make this thing have chat memory, used for context to the LLM? Langchain has stuff for this, but is it stateless?

## 8. [Walter - 21-03-2024] The GoogleDriveLoader currently has to write it's creds to file in order to use them, how do we make this multi-user safe?

## 9. [Walter - 21-03-2024] Does it make sense to develop a full-fledged client? or should we do API based development so we can talk to the lorelai API endpoints from any client (eg. a Slack bot, a mobile client, a web app, etc)

   A: either way, API based backend development seems prudent so we have flexibility. In addition, we should have an organisation be the main signup with billing and such, and as such we have <orgname>.domain.com as the main thing.

## 10. [Walter - 21-03-2024] How do we make this modular with regards to supporting multiple LLM backends?

## 11. [Walter - 21-03-2024] How do we architect Lorelai so we can add an unlimited amount of data sources for the RAG?

## 12. [Walter - 21-03-2024] Currently RAG with a vectordatabase is the hot thing, but it's not certain this will stay. How do we make the context generator as smart and flexible as possible?

## 13. [Walter - 21-03-2024] How do we support a flexible number of users, data sources, etc.

## 14. [Walter - 21-03-2024] Should we invest time/money/effort in deduplicating the indexer? ie. If 100 people have access to a document, how do we not store that 100x in our vector database?

# initial system diagram

Below a schematic of how we could build each of these modules so that we can keep the architecture manageable

![Lorelai System Diagram](./imgs/Lorelai%20System%20Diagram.png)
