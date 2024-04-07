import time

from celery import shared_task
from lorelai.contextretriever import ContextRetriever
from lorelai.llm import Llm

@shared_task(name='execute_rag_llm')
def execute_rag_llm(chat_message, user, organisation):
    """A Celery task to execute the RAG+LLM model
    """
    print(f"Task ID: {execute_rag_llm.request.id}, Message: {chat_message}")
    print(f"Session: {user}, {organisation}")

    # update the task state before we begin processing
    execute_rag_llm.update_state(state='PROGRESS', meta={'status': 'Processing...'})

    # get the context for the question
    enriched_context = ContextRetriever(org_name=organisation, user=user)

    context, source = enriched_context.retrieve_context(chat_message)

    llm = Llm(model="gpt-3.5-turbo")
    answer = llm.get_answer(question=chat_message, context=context)

    print(f"Answer: {answer}")
    print(f"Source: {source}")

    json_data = {
        'answer': answer,
        'source': source
    }

    return json_data

@shared_task(name='run_indexer', bind=True)
def run_indexer(self):
    for i in range(1, 101):
        # Simulate indexing work with progress
        self.update_state(state='PROGRESS', meta={'current': i, 'total': 100})
        print(f"Indexing {i}%")
        # Simulate some work being done
        time.sleep(0.1)
    print("Indexing completed!")
    return {'current': 100, 'total': 100, 'status': 'Task completed!', 'result': 42}
