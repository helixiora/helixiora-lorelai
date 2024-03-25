#!/usr/bin/env python3

"""This script is used to crawl the Google Drive and process the documents using Pinecone and
OpenAI API through langchain
"""

# import the indexer
from lorelai.indexer import Indexer

def main():
    """the main function
    """
    # Make sure to replace 'your_pinecone_api_key', 'your_environment', and 'your_index_name'
    # with your actual Pinecone API key, environment, and index name.
    processor = Indexer()
    processor.process_drive()

if __name__ == '__main__':
    main()
