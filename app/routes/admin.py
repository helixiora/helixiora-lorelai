"""Contains the routes for the admin page."""

import logging
import os

import mysql.connector
from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    session,
    url_for,
    request,
    flash,
    redirect,
)
from redis import Redis
from rq import Queue

from app.tasks import run_indexer, run_slack_indexer

from app.helpers.users import (
    is_super_admin,
    is_org_admin,
    is_admin,
    user_is_logged_in,
    get_users,
    role_required,
    create_invited_user_in_db,
)
from app.helpers.database import get_db_connection, get_query_result, run_flyway_migrations

from lorelai.pinecone import PineconeHelper
from lorelai.utils import load_config, send_invite_email, create_jwt_token_invite_user

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
@role_required(["super_admin", "org_admin"])
def admin():
    """Return the admin page.

    This page is only accessible to users who are admins.
    """
    if is_super_admin(session["user_id"]):
        users = get_users()
    elif is_org_admin(session["user_id"]):
        users = get_users(org_id=session["org_id"])
    else:
        users = None

    if user_is_logged_in(session) and is_admin(session["user_id"]):
        return render_template("admin.html", is_admin=True, users=users)

    return "You are not logged in!"


@admin_bp.route("/admin/job-status/<job_id>")
# note we don't require a role because a regular user should be able to index their own stuff
def job_status(job_id: str) -> str:
    """Return the status of a job given its job_id.

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

    logging.info(f"Job {job_id} status: {job._status}")
    match job:
        case None:
            logging.error(f"Job {job_id} not found")
            response = {"job_id": job_id, "state": "unknown", "status": "unknown"}
        case job.is_queued:
            logging.info(f"Job {job_id} queued")
            response = {
                "job_id": job_id,
                "state": "queued",
                "metadata": job.meta,
            }
        case job.is_finished:
            logging.info(f"Job {job_id} finished")
            response = {
                "job_id": job_id,
                "state": "finished",
                "metadata": job.meta,
                "result": job.result,
            }
        case job.is_failed:
            logging.error(f"Job {job_id} failed")
            response = {
                "job_id": job_id,
                "state": "failed",
                "metadata": job.meta,
                "result": job.result,
            }
        case job.is_started:
            logging.info(f"Job {job_id} started")
            response = {
                "job_id": job_id,
                "state": "started",
                "metadata": job.meta,
                "result": job.result,
            }
        case _:
            logging.info(f"Job {job_id} unknown state")
            response = {
                "job_id": job_id,
                "state": job._status,
                "metadata": job.meta,
                "result": job.result,
            }

    logging.debug(f"Job id: {job_id}, status: {response}")
    return jsonify(response)


@admin_bp.route("/admin/index/<type>", methods=["POST"])
# note we don't require a role because a regular user should be able to index their own stuff
def start_indexing(type) -> str:
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
    logging.info("Started indexing (type: %s)", type)
    if type == "organisation" and not is_org_admin(session["user_id"]):
        return jsonify({"error": "Only organisation admins can index their organisation"}), 403
    if type == "all" and not is_super_admin(session["user_id"]):
        return jsonify({"error": "Only super admins can index all organisations"}), 403

    if type not in ["user", "organisation", "all"]:
        return jsonify({"error": "Invalid type"}), 400

    try:
        redis_config = load_config("redis")
        redis_conn = Redis.from_url(redis_config["url"])
        queue = Queue(connection=redis_conn)

        user_id = session["user_id"]
        org_id = session.get("org_id")
        if not org_id and type != "all":
            return jsonify(
                {"error": "No organisation ID found for the user in the session details"}
            ), 403

        jobs = []

        # First we get the org_rows. If the type is user or organisation,
        # we only need the current org

        if type in ["user", "organisation"]:
            org_rows = get_query_result(
                "SELECT id, name FROM organisation WHERE id = %s", (org_id,), fetch_one=True
            )
            if not org_rows:
                return jsonify({"error": "Organisation not found"}), 404
            org_rows = [org_rows]  # Ensure it's a list for consistent handling
        # If the type is all, we get all organisations
        elif type == "all":
            org_rows = get_query_result("SELECT id, name FROM organisation")
            if not org_rows:
                return jsonify({"error": "No organisations found"}), 404

        logging.debug(
            f"Starting indexing for {len(org_rows)} organisations (type: {type}, \
                user_id: {user_id}, org_id: {org_id})"
        )

        # Go through all org_rows and start indexing
        for org_row in org_rows:
            # If the type is organisation or all, we get all users in the organisation
            if type in ["organisation", "all"]:
                user_rows = get_query_result(
                    "SELECT user_id, email FROM user WHERE org_id = %s", (org_row["id"],)
                )
            # If the type is user, we only get the current user
            elif type == "user":
                user_rows = get_query_result(
                    "SELECT user_id, email FROM user WHERE user_id = %s AND org_id = %s",
                    (user_id, org_id),
                )
            # Only continue if we have users
            if user_rows:
                user_auth_rows = []
                user_data_rows = []
                for user_row in user_rows:
                    # Get the user auth rows for the user
                    user_auth_rows_for_user = get_query_result(
                        "SELECT user_id, auth_key, auth_value, auth_type \
                            FROM user_auth \
                                WHERE user_id = %s",
                        (user_row["user_id"],),
                    )
                    user_auth_rows.extend(user_auth_rows_for_user)

                    user_data_rows_for_user = get_query_result(
                        "SELECT \
                            user_id, \
                            google_drive_id, \
                            item_name, \
                            mime_type, \
                            item_type, \
                            last_indexed_at \
                        FROM \
                            google_drive_items \
                        WHERE \
                            user_id = %s",
                        (user_row["user_id"],),
                    )
                    user_data_rows.extend(user_data_rows_for_user)

                    logging.debug(
                        f"Starting indexing for user {user_row['email']} in org {org_row['name']}"
                    )
                    job = queue.enqueue(
                        run_indexer,
                        org_row=org_row,
                        user_rows=user_rows,
                        user_auth_rows=user_auth_rows,
                        user_data_rows=user_data_rows,
                        started_by_user_id=user_id,
                        job_timeout=3600,
                        description=f"Indexing GDrive: {len(user_rows)} users in {org_row['name']}",
                    )

                    # Add the job to the list of started jobs
                    job_id = job.get_id()
                    jobs.append(job_id)

        logging.info("Started indexing for %s jobs", len(jobs))
        return jsonify({"jobs": jobs}), 202

    except Exception as e:
        logging.error(f"Error starting indexing: {e}")
        return jsonify({"error": "Failed to start indexing"}), 500


@admin_bp.route("/admin/startslackindex", methods=["POST"])
@role_required(["super_admin", "org_admin"])
# For Slack it logical that only org admin can run the indexer as the bot need to be added to slack then added to channel  # noqa: E501
def start_slack_indexing() -> str:
    """Start slack indexing the data for the organization of the logged-in user.

    Returns
    -------
    str
        The job_id of the indexing job.

    Raises
    ------
    ConnectionError
        If the connection to the Redis server or the database fails.
    """
    try:
        jobs = []
        redis_config = load_config("redis")
        redis_conn = Redis.from_url(redis_config["url"])
        queue = Queue(connection=redis_conn)
        user_email = session["user_email"]
        org_name = session["org_name"]
        job = queue.enqueue(
            run_slack_indexer,
            user_email=user_email,
            org_name=org_name,
            job_timeout=3600 * 2,
            description=f"Indexing Slack: for {org_name}",
        )
        job_id = job.get_id()
        jobs.append(job_id)
        logging.info("Started Slack Indexer")
        return jsonify({"jobs": jobs}), 202
    except Exception as e:
        logging.error(f"Error starting Slack indexing: {e}")
        return jsonify({"error": "Failed to start Slack indexing"}), 500


@admin_bp.route("/admin/pinecone")
@role_required(["super_admin", "org_admin"])
def list_indexes() -> str:
    """Return the list indexes page.

    Returns
    -------
    str
        The rendered template of the list indexes page.
    """
    pinecone_helper = PineconeHelper()
    indexes = pinecone_helper.list_indexes()

    return render_template(
        "admin/pinecone.html", indexes=indexes, is_admin=is_admin(session["user_id"])
    )


@admin_bp.route("/admin/pinecone/<host_name>")
@role_required(["super_admin", "org_admin"])
def index_details(host_name: str) -> str:
    """Return the index details page."""
    pinecone_helper = PineconeHelper()

    index_metadata = pinecone_helper.get_index_details(index_host=host_name)

    return render_template(
        "admin/index_details.html",
        index_host=host_name,
        metadata=index_metadata,
        is_admin=is_admin(session["user_id"]),
    )


@admin_bp.route("/admin/setup", methods=["GET"])
@role_required(["super_admin", "org_admin"])
def setup() -> str:
    """Return the LorelAI setup page.

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
@role_required(["super_admin", "org_admin"])
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

        with open(baseline_schema_path) as file:
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


@admin_bp.route("/admin/invite_user", methods=["POST"])
def invite_user():
    """
    Handle user invitation process by sending an invite email with a registration link.

    This function performs the following steps:
    1. Retrieves the invitee's email from the request form.
    2. Creates a JWT token for the invitee using their email, the organization admin's email, and
    the organization's name.
    3. Generates an invite registration URL with the JWT token.
    4. Sends an invite email to the invitee with the registration URL.
    5. Displays a success or error message based on the email sending status.
    6. Redirects to the admin page.

    Returns
    -------
        Redirect: A redirect response to the admin page.

    Flask Context:
        - Expects 'user_email' and 'org_name' to be present in the session.
        - Expects 'email' to be present in the request form.
    """
    email = request.form["email"]
    token = create_jwt_token_invite_user(
        invitee_email=email, org_admin_email=session["user_email"], org_name=session["org_name"]
    )
    invite_register_url = url_for("chat.index", token=token, _external=True)

    email_status = send_invite_email(
        org_admin_email=session["user_email"],
        invitee_email=email,
        invite_url=invite_register_url,
    )
    if email_status:
        create_invited_user_in_db(email=email, org_name=session["org_name"])
        flash(f"Invitation to {email} sent successfully!", "success")
        logging.info(f"Invitation to {email} sent successfully!")
    else:
        flash("Invitation failed", "error")
        logging.error(f"Invitation to {email} failed")

    return redirect(url_for("admin.admin"))


@admin_bp.route("/admin/test_connection", methods=["POST"])
@role_required(["super_admin", "org_admin"])
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
