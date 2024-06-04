"""This module contains the routes for the admin page."""

import logging
import os

import mysql.connector
from flask import blueprints, jsonify, render_template, session, url_for, current_app
from redis import Redis
from rq import Queue

from app.tasks import run_indexer
from app.utils import get_db_connection, is_admin, run_flyway_migrations
from lorelai.contextretriever import ContextRetriever
from lorelai.utils import load_config

admin_bp = blueprints.Blueprint("admin", __name__)


@admin_bp.route("/admin")
def admin():
    """The admin page.

    This page is only accessible to users who are admins.
    """
    if "google_id" in session and is_admin(session["google_id"]):
        return render_template("admin.html", is_admin=is_admin(session["google_id"]))
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
    if "google_id" in session and is_admin(session["google_id"]):
        logging.debug("Posting task to rq worker...")

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
                    "SELECT user_id, name, email, refresh_token FROM user WHERE org_id = %s",
                    (org_row["id"],),
                )
                user_rows = cur.fetchall()
                if not user_rows:
                    return "No users found in the organization", 404

                # Enqueue the job
                job = queue.enqueue(
                    run_indexer,
                    org_row=org_row,
                    user_rows=user_rows,
                    job_timeout=3600,
                    description=f"Indexing GDrive: ${len(user_rows)} users in ${org_row['name']}",
                )
                job_id = job.get_id()

        finally:
            if connection:
                connection.close()

        return jsonify({"job": job_id}), 202

    else:
        return "Unauthorized", 403


@admin_bp.route("/admin/pinecone")
def list_indexes() -> str:
    """the list indexes page

    Returns
    -------
    str
        The rendered template of the list indexes page.
    """

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
    db = load_config("db")
    return render_template(
        "admin/setup.html",
        setup_url=url_for("admin.setup_post"),
        test_connection=url_for("admin.test_connection"),
        db=db,
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
    db = None
    cursor = None

    try:
        msg += "Connecting to MySQL...<br/>"
        db = get_db_connection(with_db=False)
        msg += f"MySQL connection successful.<br/>{db.get_server_info()}<br/>"

        db_name = load_config("db")["database"]
        dir_path = os.path.dirname(os.path.realpath(__file__ + "/../.."))
        baseline_schema_path = os.path.join(dir_path, "db", "baseline_schema.sql")

        if not os.path.exists(baseline_schema_path):
            raise FileNotFoundError(f"Baseline schema file not found at {baseline_schema_path}")

        with open(baseline_schema_path, "r") as file:
            baseline_schema = file.read()

        msg += "Creating the database...<br/>"
        msg += f"Baseline schema loaded:<br/>{baseline_schema}<br/>"

        cursor = db.cursor()

        # Combine all statements into one multi-statement string
        full_statement = f"""
        CREATE DATABASE IF NOT EXISTS {db_name};
        USE {db_name};
        {baseline_schema}
        """

        # Execute the combined statements and echo each one
        for result in cursor.execute(full_statement, multi=True):
            if result.statement:
                msg += f"Executing: {result.statement}<br/>"
            if result.with_rows:
                msg += f"Affected {result.rowcount} rows<br/>"

        msg += "Database created.<br/>"

        # Close cursor and database connection
        cursor.close()
        db.close()
        cursor = None
        db = None

        # Run Flyway migrations
        flyway_success, flyway_result = run_flyway_migrations(
            load_config("db")["host"],
            db_name,
            load_config("db")["user"],
            load_config("db")["password"],
        )
        if flyway_success:
            current_app.config["LORELAI_SETUP"] = False
        msg += f"Flyway migrations completed. Flyway result:<br/>{flyway_result}<br/>"

        msg += "</pre>"
        return msg

    except FileNotFoundError as fnf_error:
        error_message = f"File error: {fnf_error}"
        logging.error(error_message)
        return jsonify({"error": error_message}), 500
    except Exception as e:
        error_message = f"An error occurred: {e}"
        logging.error(error_message)
        return jsonify({"error": error_message}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
        logging.info(msg)


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
        If the connection to the MySQL database fails."""
    health = get_db_connection(with_db=False)
    if health:
        try:
            config = load_config("db")
            db = config["database"]
            msg = "<strong>Testing MySQL credentials without selecting the database.</strong> </br>"
            msg += "MySQL connection succesful with user credentials. </br>"
            msg += "User: " + config["user"] + "</br>"
            msg += "Host: " + config["host"] + "</br>"
        except mysql.connector.Error:
            msg = "MySQL is not up and running. </br>"

        msg += "<br>"
        msg += "<strong>Testing MySQL credentials with selecting the database.</strong> </br>"

        try:
            # check if we can connect to the database
            health.database = db
            cursor = health.cursor()
            cursor.execute("SELECT 1")
            msg += "MySQL database is found and can be connected to. </br>"

        except mysql.connector.Error as e:
            # get the error class
            if e.errno == 1049:
                msg += f"{e.msg} (error {str(e.errno)})</br>"
            else:
                raise
        msg += "Please proceed to press 'Create Database'"
    else:
        msg = "MySQL connection failed."

    return msg
