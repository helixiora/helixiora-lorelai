from flask import blueprints, request, jsonify, session
from tasks import execute_rag_llm
from redis import Redis
from rq import Queue

chat_bp = blueprints.Blueprint('chat', __name__)

# a get and post route for the chat page
@chat_bp.route('/chat', methods=['POST'])
def chat():
    """Endpoint to post chat messages."""
    content = request.get_json()
    if not content or 'message' not in content:
        return jsonify({'status': 'ERROR', 'message': 'Message is required'}), 400

    # Assuming session['email'] and session['organisation'] are set after user authentication
    queue = Queue(connection=Redis())
    job = queue.enqueue(execute_rag_llm, content['message'], session.get('email'), session.get('organisation'))

    return jsonify({'job': job.get_id()}), 202
    
@chat_bp.route('/chat', methods=['GET'])
def fetch_chat_result():
    """Endpoint to fetch the result of a chat operation."""
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({'status': 'ERROR', 'message': 'Job ID is required'}), 400

    redis_conn = Redis()
    job = Queue(connection=redis_conn).fetch_job(job_id)

    if job is None:
        return jsonify({'status': 'ERROR', 'message': 'Job not found'}), 404
    elif job.is_failed:
        return jsonify({'status': 'FAILED', 'error': str(job.exc_info)}), 500
    elif job.result is not None:
        return jsonify({'status': 'SUCCESS', 'result': job.result})
    else:
        # Job is either queued or started but not yet finished
        return jsonify({'status': 'IN PROGRESS'}), 202