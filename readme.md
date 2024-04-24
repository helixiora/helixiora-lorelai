# Lorelai readme

## Overview

Lorelai: a RAG (Retrieval-Augmented Generation) application. The project integrates with Google Drive via OAuth for content crawling, utilizes Pinecone for indexing, and leverages OpenAI's API for query processing. Its main components include a Flask-based web application for Google OAuth setup, nightly document indexing, and a testing script for query execution.

### Key Features

- **Ask questions to your private google docs** A chat interface to ask questions to the info you have indexed
- **Google Drive Integration:** Securely crawl a user's Google Drive contents using OAuth.
- **Automated Indexing:** Nightly indexing of Google Drive documents into Pinecone for efficient retrieval.
- **Query Processing:** Leverage OpenAI's API to process queries with context retrieved from Pinecone.
- **Admin backend** See what info you have indexed in pinecone

### Components
Check out the [docs](./docs) for the individual components or the Architecture Diagram.

## Prerequisites
Before starting out with LorelAI, please make sure you've met the [prerequesites](./prerequisites.md)

## Getting Started
Follow [these steps](getting_started.md) to set up the project and run the components.

## Contributing
Please make sure to read up on our [contributing guide](https://github.com/helixiora/.github/blob/main/CONTRIBUTING.md)

Most importantly for this project though we use [ruff](https://docs.astral.sh/ruff/), please ensure your IDE has it installed per their guides.

## CI

To ensure that the code quality is maintained across all branches, we integrate these tools into our CI/CD pipeline using GitHub Actions.

### Pre-commit Setup

Pre-commit hooks help enforce standards by automatically checking and formatting code before it's committed to the repository.

1. Install pre-commit on your local development machine. It's recommended to install it globally using `pip install pre-commit`
2. Install the hooks using `pre-commit install`

Now, everytime you commit the hooks in `.pre-commit-config.yaml` will be run and the commit will fail if those hooks make a change

## Architecture diagram

Below a schematic of how we could build each of these modules so that we can keep the architecture manageable

![Lorelai System Diagram](./imgs/Lorelai%20System%20Diagram.png)

# Benchmarking

See [the benchmark directory](benchmark/readme.md)

# Frequently Asked Questions
For a number of in-depth questions, see the [FAQ](docs/faq.md)
