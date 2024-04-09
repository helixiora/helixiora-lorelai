
from flask import blueprints, render_template, session, jsonify
from pprint import pprint

from tasks import run_indexer
from lorelai.contextretriever import ContextRetriever
from redis import Redis
from rq import Queue

from app.utils import is_admin

admin_bp = blueprints.Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin():
    """The admin page."""
    if 'google_id' in session and is_admin(session['google_id']):  # Assuming is_admin() checks if the user is an admin
        return render_template('admin.html', is_admin=is_admin(session['google_id']))
    return 'You are not logged in!'

@admin_bp.route('/admin/task-status/<task_id>')
def task_status(task_id):
    # task = run_indexer.AsyncResult(task_id)
    # if task.state == 'PENDING':
    #     response = {
    #         'state': task.state,
    #         'status': 'Pending...'
    #     }
    # elif task.state != 'FAILURE':
    #     response = {
    #         'state': task.state,
    #         'current': task.info.get('current', 0),
    #         'total': task.info.get('total', 1),
    #         'status': task.info.get('status', '')
    #     }
    #     if 'result' in task.info:
    #         response['result'] = task.info['result']
    # else:
    #     # something went wrong in the background job
    response = {
        'state': 'task.state',
        'status': 'str(task.info),  # this is the exception raised'
    }
    return jsonify(response)

@admin_bp.route('/admin/index', methods=['POST'])
def start_indexing():
    if 'google_id' in session and is_admin(session['google_id']):
        print("Posting task to rq worker...")    
        queue = Queue(connection=Redis())
        job = queue.enqueue(run_indexer)
        
        job_id = job.get_id()
        return jsonify({'job': job_id}), 202

    else:
        return 'Unauthorized', 403

@admin_bp.route('/admin/pinecone')
def list_indexes():
    """the list indexes page
    """

    enriched_context = ContextRetriever(org_name=session['organisation'], user=session['email'])

    indexes = enriched_context.get_all_indexes()

    pprint(indexes)
    # Render a template, passing the indexes and their metadata
    return render_template('admin/pinecone.html', indexes=indexes, is_admin=is_admin(session['google_id']))

@admin_bp.route('/admin/pinecone/<host_name>')
def index_details(host_name: str) -> str:
    """the index details page
    """
    enriched_context = ContextRetriever(org_name=session['organisation'], user=session['email'])

    # Assume getIndexDetails function exists to fetch metadata for a specific index
    index_metadata = enriched_context.get_index_details(index_host=host_name)

    pprint(index_metadata)

    return render_template('admin/index_details.html', index_host=host_name,
                           metadata=index_metadata, is_admin=is_admin(session['google_id']))
