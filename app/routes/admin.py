"""This module contains the routes for the admin page."""

import logging
import os

import mysql.connector
from flask import Blueprint, current_app, jsonify, render_template, session, url_for
from redis import Redis
from rq import Queue

from app.tasks import run_indexer
from app.utils import (
    get_db_connection,
    get_query_result,
    is_admin,
    run_flyway_migrations,
)
from lorelai.contextretriever import ContextRetriever
from lorelai.utils import load_config

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
def admin():
    """The admin page.

    This page is only accessible to users who are admins.
    """
    if "user_id" in session and is_admin(session["user_id"]):
        return render_template("admin.html", is_admin=True)
    return "You are not logged in!"


@admin_bp.route("/admin/job-status/<job_id>")
def job_status(job_id: str) -> str:
    """Return the status of a job given its job_id

    Parameters
    ----------
    job_id : str
        The job_id of the job to check the status of.

    Returns
    -------
    str
        The status of the job.
    """
    redis_config = load_config("redis")
    redis_conn = Redis.from_url(redis_config["url"])
    queue = Queue(connection=redis_conn)
    job = queue.fetch_job(job_id)

    if job is None:
        response = {"state": "unknown", "status": "unknown"}
    elif job.is_finished:
        response = {"state": "done", "status": "done"}
    elif job.is_failed:
        response = {"state": "failed", "status": "failed"}
    elif job.is_started:
        response = {"state": "running", "status": "running"}
    else:
        response = {"state": "unknown", "status": "unknown"}

    return jsonify(response)


@admin_bp.route("/admin/index", methods=["POST"])
def start_indexing() -> str:
    """Start indexing the data for the organization of the logged-in user.

    Returns
    -------
    str
        The job_id of the indexing job.

    Raises
    ------
    ConnectionError
        If the connection to the Redis server or the database fails.
    """
    logging.info("Started indexing")
    if "user_id" in session and is_admin(session["user_id"]):
        logging.debug("Posting task to rq worker...")

        redis_config = load_config("redis")
        redis_conn = Redis.from_url(redis_config["url"])
        queue = Queue(connection=redis_conn)

        org_id = session.get("org_id")
        if not org_id:
            return jsonify(
                {"error": "No organization ID found for the user in the session details"}
            ), 403

        org_row = get_query_result(
            "SELECT id, name FROM organisations WHERE id = %s", (org_id,), fetch_one=True
        )
        if not org_row:
            return jsonify({"error": "Organization not found"}), 404

        user_rows = get_query_result(
            "SELECT user_id, name, email FROM user WHERE org_id = %s", (org_row["id"],)
        )
        if not user_rows:
            return jsonify({"error": "No users found in the organization"}), 404

        job = queue.enqueue(
            run_indexer,
            org_row=org_row,
            user_rows=user_rows,
            job_timeout=3600,
            description=f"Indexing GDrive: {len(user_rows)} users in {org_row['name']}",
        )
        job_id = job.get_id()

        return jsonify({"job": job_id}), 202

    else:
        return jsonify({"error": "Unauthorized"}), 403


@admin_bp.route("/admin/pinecone")
def list_indexes() -> str:
    """The list indexes page

    Returns
    -------
    str
        The rendered template of the list indexes page.
    """
    enriched_context = ContextRetriever(
        org_name=session["org_name"], user_email=session["user_email"]
    )
    indexes = enriched_context.get_all_indexes()

    return render_template(
        "admin/pinecone.html", indexes=indexes, is_admin=is_admin(session["user_id"])
    )


@admin_bp.route("/admin/pinecone/<host_name>")
def index_details(host_name: str) -> str:
    """The index details page"""
    enriched_context = ContextRetriever(
        org_name=session["org_name"], user_email=session["user_email"]
    )
    index_metadata = enriched_context.get_index_details(index_host=host_name)

    return render_template(
        "admin/index_details.html",
        index_host=host_name,
        metadata=index_metadata,
        is_admin=is_admin(session["user_id"]),
    )


@admin_bp.route("/admin/setup", methods=["GET"])
def setup() -> str:
    """The setup route.

    Shows the parameters for the database connection,
    and two buttons to test the connection and run the database creation.
    Note that it doesn't support changing the database parameters.

    Returns
    -------
    str
        The rendered template of the setup page.
    """
    db_config = load_config("db")
    return render_template(
        "admin/setup.html",
        setup_url=url_for("admin.setup_post"),
        test_connection_url=url_for("admin.test_connection"),
        db=db_config,
    )


@admin_bp.route("/admin/setup", methods=["POST"])
def setup_post() -> str:
    """Create the database using the .db/baseline_schema.sql file.

    After the database is created, run the Flyway migrations in ./db/migrations.

    Returns
    -------
    str
        A message indicating the result of the setup.

    Raises
    ------
    FileNotFoundError
        If the baseline schema file is not found.
    """
    msg = "<strong>Creating the database and running Flyway migrations.</strong><br/>"
    msg += "<pre style='font-family: monospace;'>"
    cursor = None
    conn = None

    try:
        msg += "Connecting to MySQL...<br/>"
        conn = get_db_connection(with_db=False)
        msg += f"MySQL connection successful.<br/>{conn.get_server_info()}<br/>"

        db_config = load_config("db")
        db_name = db_config["database"]
        dir_path = os.path.dirname(os.path.realpath(__file__ + "/../.."))
        baseline_schema_path = os.path.join(dir_path, "db", "baseline_schema.sql")

        if not os.path.exists(baseline_schema_path):
            raise FileNotFoundError(f"Baseline schema file not found at {baseline_schema_path}")

        with open(baseline_schema_path, "r") as file:
            baseline_schema = file.read()

        msg += "Creating the database...<br/>"
        msg += f"Baseline schema loaded:<br/>{baseline_schema}<br/>"

        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")
        for result in cursor.execute(baseline_schema, multi=True):
            if result.with_rows:
                msg += f"Affected {result.rowcount} rows<br/>"

        cursor.close()
        conn.close()

        flyway_success, flyway_result = run_flyway_migrations(
            db_config["host"],
            db_name,
            db_config["user"],
            db_config["password"],
        )
        if flyway_success:
            current_app.config["LORELAI_SETUP"] = False
        msg += f"Flyway migrations completed. Flyway result:<br/>{flyway_result}<br/>"

        msg += "</pre>"
        return msg

    except FileNotFoundError as fnf_error:
        logging.error(f"File error: {fnf_error}")
        return jsonify({"error": f"File error: {fnf_error}"}), 500
    except mysql.connector.Error as db_error:
        logging.error(f"Database error: {db_error}")
        return jsonify({"error": f"Database error: {db_error}"}), 500
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@admin_bp.route("/admin/test_connection", methods=["POST"])
def test_connection() -> str:
    """The test connection route.

    Test the connection to the MySQL database.

    Returns
    -------
    str
        A message indicating the result of the connection test.

    Raises
    ------
    mysql.connector.Error
        If the connection to the MySQL database fails.
    """
    try:
        conn = get_db_connection(with_db=False)
        db_config = load_config("db")
        msg = "<strong>Testing MySQL credentials without selecting the database.</strong><br/>"
        msg += "MySQL connection successful with user credentials.<br/>"
        msg += f"User: {db_config['user']}<br/>"
        msg += f"Host: {db_config['host']}<br/>"

        conn.database = db_config["database"]
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        msg += "MySQL database is found and can be connected to.<br/>"
        cursor.close()
        conn.close()

        msg += "Please proceed to press 'Create Database'."
        return msg
    except mysql.connector.Error as e:
        if e.errno == 1049:
            msg = f"{e.msg} (error {str(e.errno)})<br/>"
        else:
            raise
    return msg
