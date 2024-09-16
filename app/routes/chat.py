"""Routes for the chat page."""

import logging

from flask import (
    blueprints,
    jsonify,
    request,
    session,
    redirect,
    url_for,
    current_app,
    render_template,
)
from redis import Redis
from rq import Queue

from app.helpers.users import user_is_logged_in
from app.helpers.chat import get_chat_template_requirements, delete_thread
from app.tasks import execute_rag_llm
from app.helpers.chat import get_msg_count_last_24hr, get_all_thread_messages
from app.helpers.notifications import (
    get_notifications,
    mark_notification_as_read,
    mark_notification_as_dismissed,
)
from lorelai.utils import load_config
from ulid import ULID

chat_bp = blueprints.Blueprint("chat", __name__)


# a get and post route for the chat page
@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    """Post messages to rq to process."""
    content = request.get_json()
    if not content or "message" not in content:
        return jsonify({"status": "ERROR", "message": "Message is required"}), 400

    logging.info(
        "Chat request received: %s from user %s", content["message"], session.get("user_email")
    )
    logging.info("Datasource: %s", content["datasource"])

    lorelaicreds = load_config("lorelai")
    user_id = session.get("user_id")
    msg_count = get_msg_count_last_24hr(user_id=session.get("user_id"))
    msg_limit = int(lorelaicreds["free_msg_limit"])
    logging.info(f"{user_id} User id Msg Count last 24hr: {msg_count}")
    if int(msg_count) >= int(msg_limit):
        return jsonify({"status": "ERROR", "message": "Message limit exceeded"}), 429

    redis = load_config("redis")
    redis_host = redis["url"]
    if not redis_host:
        return jsonify({"status": "ERROR", "message": "Redis URL is not set"}), 500
    redis_conn = Redis.from_url(redis_host)
    queue = Queue(connection=redis_conn)

    lorelai_config = load_config("lorelai")
    # set the chat task timeout to 20 seconds if not set
    chat_task_timeout = lorelai_config["chat_task_timeout"] or 20

    llm_model = "OpenAILlm"
    # llm_model = "OllamaLlama3"

    # if the thread_id is set in the session, use it; otherwise, create a new one
    if "thread_id" in session:
        thread_id = session["thread_id"]
    else:
        thread_id = str(ULID().to_uuid())
        session["thread_id"] = thread_id

    # enqueue the chat task
    job = queue.enqueue(
        execute_rag_llm,
        thread_id,
        content["message"],
        session.get("user_id"),
        session.get("user_email"),
        session.get("org_name"),
        llm_model,
        datasource=content["datasource"],
        job_timeout=chat_task_timeout,
        description=f"Execute RAG+LLM model: {content['message']} for {session.get('user_email')} \
            using {llm_model}",
    )

    return jsonify({"job": job.get_id()}), 202


@chat_bp.route("/api/chat", methods=["GET"])
def fetch_chat_result():
    """Endpoint to fetch the result of a chat operation."""
    job_id = request.args.get("job_id")
    thread_id = request.args.get("thread_id")
    if not job_id:
        return jsonify({"status": "ERROR", "message": "Job ID is required"}), 400

    logging.debug("Fetching job result for job ID: %s", job_id)

    redis = load_config("redis")
    redis_host = redis["url"]

    redis_conn = Redis.from_url(redis_host)
    queue = Queue(connection=redis_conn)
    job = queue.fetch_job(job_id)

    logging.debug("Job status: %s", job.get_status())
    if job is None:
        return jsonify({"status": "ERROR", "message": "Job not found"}), 404
    elif job.is_failed:
        return jsonify({"status": "FAILED", "error": str(job.exc_info)}), 500
    elif job.is_finished:
        logging.info("Job result: %s", job.result)
        if job.result["status"] == "Failed":
            return jsonify({"status": "FAILED", "error": job.result}), 500
        if job.result["status"] == "No Relevant Source":
            return jsonify({"status": "NO_RELEVANT_SOURCE", "result": job.result}), 500
        return jsonify({"status": "SUCCESS", "result": job.result, "thread_id": thread_id})
    else:
        # Job is either queued or started but not yet finished
        return jsonify({"status": "IN PROGRESS"}), 202


@chat_bp.route("/api/notifications", methods=["GET"])
def api_notifications():
    """Get notifications for the current user."""
    try:
        # Fetch unread notifications for the current user
        notifications = get_notifications(session.get("user_id"))

        return jsonify(notifications), 200
    except Exception as e:
        # Log the error (you should set up proper logging)
        logging.error(f"Error fetching notifications: {str(e)}")
        return jsonify({"error": "Unable to fetch notifications"}), 500


@chat_bp.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
def api_notifications_read(notification_id):
    """Mark a notification as read."""
    logging.info(
        f"Marking notification {notification_id} as read for user {session.get('user_id')}"
    )
    result = mark_notification_as_read(notification_id, session.get("user_id"))
    logging.debug(f"Notification read result: {result}")
    if isinstance(result, dict) and result.get("success", False):
        return jsonify(result), 200
    else:
        return jsonify({"status": "error", "message": "Failed to mark notification as read"}), 400


@chat_bp.route("/api/notifications/<int:notification_id>/dismiss", methods=["POST"])
def api_notifications_dismiss(notification_id):
    """Mark a notification as dismissed."""
    logging.info(
        f"Marking notification {notification_id} as dismissed for user {session.get('user_id')}"
    )
    result = mark_notification_as_dismissed(notification_id, session.get("user_id"))
    if isinstance(result, dict) and result.get("success", False):
        return jsonify(result), 200
    else:
        return jsonify({"status": "error", "message": "Failed to dismiss notification"}), 400


@chat_bp.route("/conversation/<thread_id>", methods=["GET"])
def conversation(thread_id):
    """Return the conversation page.

    Returns
    -------
        string: the conversation page
    """
    session["thread_id"] = thread_id
    lorelai_settings = load_config("lorelai")
    chat_template_requirements = get_chat_template_requirements(thread_id, session["user_id"])
    return render_template(
        template_name_or_list="index_logged_in.html",
        user_email=session["user_email"],
        recent_conversations=chat_template_requirements["recent_conversations"],
        is_admin=chat_template_requirements["is_admin_status"],
        datasource_list=chat_template_requirements["datasources"],
        support_portal=lorelai_settings["support_portal"],
        support_email=lorelai_settings["support_email"],
    )


# route to delete a thread and all its messages
@chat_bp.route("/api/conversation/<thread_id>/delete", methods=["DELETE"])
def delete_conversation(thread_id):
    """Delete a thread and all its messages."""
    delete_thread(thread_id)
    return jsonify({"status": "success"}), 200


# get all messages for a given thread
@chat_bp.route("/api/conversation/<thread_id>")
def api_conversation(thread_id):
    """Get all messages for a given thread."""
    messages = get_all_thread_messages(thread_id)
    return jsonify(messages), 200


# Improved index route using render_template
@chat_bp.route("/")
def index():
    """Return the index page.

    Returns
    -------
        string: the index page
    """
    logging.debug("Index route")

    if current_app.config.get("LORELAI_SETUP"):
        # redirect to /admin/setup if the app is not set up
        logging.info("App is not set up. Redirecting to /admin/setup")
        return redirect(url_for("admin.setup"))

    # if the user_id is in the session, the user is logged in
    # render the index_logged_in page
    if user_is_logged_in(session):
        lorelai_settings = load_config("lorelai")
        thread_id = session.get("thread_id")
        chat_template_requirements = get_chat_template_requirements(thread_id, session["user_id"])

        return render_template(
            "index_logged_in.html",
            user_email=session["user_email"],
            recent_conversations=chat_template_requirements["recent_conversations"],
            is_admin=chat_template_requirements["is_admin_status"],
            datasource_list=chat_template_requirements["datasources"],
            support_portal=lorelai_settings["support_portal"],
            support_email=lorelai_settings["support_email"],
        )

    # if we're still here, there was no user_id in the session meaning we are not logged in
    # render the front page with the google client id
    # if the user clicks login from that page, the javascript function `onGoogleCredentialResponse`
    # will handle the login using the /login route in auth.py.
    # Depending on the output of that route, it's redirecting to /register if need be

    secrets = load_config("google")
    return render_template("index.html", google_client_id=secrets["client_id"])
