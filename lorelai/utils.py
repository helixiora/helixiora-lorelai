def pinecone_index_name(org, datasource):
    """returns the pinecone index name for the org
    """
    index_name = org.lower().replace(".", "-")
    
    return f"{index_name}-{datasource}"