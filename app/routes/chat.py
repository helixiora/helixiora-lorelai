from flask import blueprints, request, jsonify, session
from tasks import execute_rag_llm
from redis import Redis
from rq import Queue

chat_bp = blueprints.Blueprint('chat', __name__)

# a get and post route for the chat page
@chat_bp.route('/chat', methods=['POST'])
def chat():
    """the chat route
    """
    content = request.get_json()
    if not content:
        return jsonify({'status': 'ERROR', 'message': 'Request body is required'}), 400
    
    if 'message' not in content:
        return jsonify({'status': 'ERROR', 'message': 'Message is required'}), 400
    
    if 'email' not in session:
        return jsonify({'status': 'ERROR', 'message': 'User is not authenticated'}), 401

    # this is used to post a task to the celery worker
    print("Posting task to rq worker...")    
    queue = Queue(connection=Redis())
    job = queue.enqueue(execute_rag_llm, content['message'], session['email'], session['organisation'])
    
    job_id = job.get_id()
    return jsonify({'job': job_id}), 202

@chat_bp.route('/chat', methods=['GET'])
def fetch_chat_result():
    """Fetches the result of a chat task based on its ID."""
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'status': 'ERROR', 'message': 'Task ID is required'}), 400

    task = execute_rag_llm.AsyncResult(task_id)

    if task.state == 'SUCCESS':
        # Task completed successfully
        return jsonify({'status': 'SUCCESS', 'result': task.result})
    elif task.state == 'FAILURE':
        # Task failed
        # You can include more error information from task.info if needed
        return jsonify({'status': 'FAILED', 'error': str(task.info)}), 500
    elif task.state in ['PENDING', 'RETRY']:
        # Task is still running or pending to be executed
        return jsonify({'status': 'PENDING'}), 202
    elif task.state == 'PROGRESS':
        # Task is currently being processed
        # Here, you can also include any custom progress metadata if your task emits such information
        return jsonify({'status': 'IN PROGRESS', 'progress': task.info}), 202
    else:
        # Handle other states if necessary (like REVOKED)
        return jsonify({'status': task.state}), 202