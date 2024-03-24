#!/usr/bin/env python3

"""This script is used to crawl the Google Drive and process the documents using Pinecone and
OpenAI API through langchain
"""

import json
import lorelai_pinecone

# load openai creds from file
def load_openai_creds():
    """loads the openai creds from the settings.json file
    """
    with open('settings.json', encoding='utf-8') as f:
        return json.load(f)['openai']

# load pinecone creds from file
def load_pinecone_creds():
    """loads the pinecone creds from the settings.json file
    """
    with open('settings.json', encoding='utf-8') as f:
        return json.load(f)['pinecone']

def load_google_creds():
    """loads the google creds from the settings.json file
    """
    with open('settings.json', encoding='utf-8') as f:
        return json.load(f)['google']

def main():
    """the main function
    """

    google_creds = load_google_creds()

    pinecone_creds = load_pinecone_creds()

    openai_creds = load_openai_creds()

    # Make sure to replace 'your_pinecone_api_key', 'your_environment', and 'your_index_name'
    # with your actual Pinecone API key, environment, and index name.
    processor = lorelai_pinecone.GoogleDriveProcessor(google_creds, pinecone_creds, openai_creds)
    processor.process_drive()

if __name__ == '__main__':
    main()
