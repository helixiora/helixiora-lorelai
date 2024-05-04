"""This module contains the routes for the admin page."""

from flask import blueprints, jsonify, render_template, session
from redis import Redis
from rq import Queue

from app.tasks import run_indexer
from app.utils import get_db_connection, is_admin
from lorelai.contextretriever import ContextRetriever
from lorelai.utils import load_config

admin_bp = blueprints.Blueprint("admin", __name__)


@admin_bp.route("/admin")
def admin():
    """The admin page."""
    if "google_id" in session and is_admin(session["google_id"]):
        return render_template("admin.html", is_admin=is_admin(session["google_id"]))
    return "You are not logged in!"


@admin_bp.route("/admin/job-status/<job_id>")
def job_status(job_id):
    """Return the status of a job given its job_id"""
    redis = load_config("redis")
    redis_host = redis["url"]
    redis_conn = Redis.from_url(redis_host)
    queue = Queue(connection=redis_conn)
    job = queue.fetch_job(job_id)

    if job is None:
        response = {"state": "unknown", "status": "unknown"}
        return jsonify(response)

    if job.is_finished:
        response = {"state": "done", "status": "done"}
        return jsonify(response)

    if job.is_failed:
        response = {"state": "failed", "status": "failed"}
        return jsonify(response)

    if job.is_started:
        response = {"state": "running", "status": "running"}
        return jsonify(response)

    response = {"state": "unknown", "status": "unknown"}
    return jsonify(response)


@admin_bp.route("/admin/index", methods=["POST"])
def start_indexing():
    """Start indexing the data for the organization of the logged-in user."""
    if "google_id" in session and is_admin(session["google_id"]):
        print("Posting task to rq worker...")

        # Load Redis configuration
        redis_config = load_config("redis")
        redis_host = redis_config["url"]
        if not redis_host:
            raise ConnectionError("Failed to connect to the Redis server.")
        redis_conn = Redis.from_url(redis_host)
        queue = Queue(connection=redis_conn)

        # Establish database connection
        try:
            connection = get_db_connection()
            if not connection:
                raise ConnectionError("Failed to connect to the database.")

            # Assuming the user's org_id is stored in the session
            org_id = session.get("org_id")
            if not org_id:
                return "No organization ID found for the user in the session details", 403

            with connection.cursor(dictionary=True) as cur:
                # Fetch only the organization related to the logged-in user
                cur.execute("SELECT id, name FROM organisations WHERE id = %s", (org_id,))
                org_row = cur.fetchone()
                if not org_row:
                    return "Organization not found", 404

                # Fetch users belonging to the organization
                cur.execute(
                    "SELECT user_id, name, email, refresh_token FROM users WHERE org_id = %s",
                    (org_row["id"],),
                )
                user_rows = cur.fetchall()
                if not user_rows:
                    return "No users found in the organization", 404

                # Enqueue the job
                job = queue.enqueue(run_indexer, org_row=org_row, user_rows=user_rows)
                job_id = job.get_id()

        finally:
            if connection:
                connection.close()

        return jsonify({"job": job_id}), 202

    else:
        return "Unauthorized", 403


@admin_bp.route("/admin/pinecone")
def list_indexes():
    """the list indexes page"""

    enriched_context = ContextRetriever(org_name=session["organisation"], user=session["email"])

    indexes = enriched_context.get_all_indexes()

    # Render a template, passing the indexes and their metadata
    return render_template(
        "admin/pinecone.html", indexes=indexes, is_admin=is_admin(session["google_id"])
    )


@admin_bp.route("/admin/pinecone/<host_name>")
def index_details(host_name: str) -> str:
    """the index details page"""
    enriched_context = ContextRetriever(org_name=session["organisation"], user=session["email"])

    # Assume getIndexDetails function exists to fetch metadata for a specific index
    index_metadata = enriched_context.get_index_details(index_host=host_name)

    return render_template(
        "admin/index_details.html",
        index_host=host_name,
        metadata=index_metadata,
        is_admin=is_admin(session["google_id"]),
    )
