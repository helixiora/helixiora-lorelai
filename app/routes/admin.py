"""This module contains the routes for the admin page.
"""

from pprint import pprint

from flask import blueprints, jsonify, render_template, session
from redis import Redis
from rq import Queue
from app.tasks import run_indexer

from app.utils import is_admin
from lorelai.contextretriever import ContextRetriever

admin_bp = blueprints.Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin():
    """The admin page."""
    if 'google_id' in session and is_admin(session['google_id']):
        return render_template('admin.html', is_admin=is_admin(session['google_id']))
    return 'You are not logged in!'

@admin_bp.route('/admin/job-status/job_id')
def job_status(job_id):
    """Return the status of a job given its job_id"""

    queue = Queue(connection=Redis())
    job = queue.fetch_job(job_id)

    if job is None:
        response = {
            'state': 'unknown',
            'status': 'unknown'
        }
        return jsonify(response)

    if job.is_finished:
        response = {
            'state': 'done',
            'status': 'done'
        }
        return jsonify(response)

    if job.is_failed:
        response = {
            'state': 'failed',
            'status': 'failed'
        }
        return jsonify(response)

    if job.is_started:
        response = {
            'state': 'running',
            'status': 'running'
        }
        return jsonify(response)

    response = {
        'state': 'unknown',
        'status': 'unknown'
    }
    return jsonify(response)

@admin_bp.route('/admin/index', methods=['POST'])
def start_indexing():
    """Start indexing the data"""
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
    return render_template('admin/pinecone.html', indexes=indexes,
                           is_admin=is_admin(session['google_id']))

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
