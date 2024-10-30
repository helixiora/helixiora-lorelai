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
from flask_login import current_user
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.helpers.chat import get_chat_template_requirements, delete_thread
from app.tasks import get_answer_from_rag
from app.helpers.chat import get_all_thread_messages, can_send_message
from app.helpers.notifications import (
    get_notifications,
    mark_notification_as_read,
    mark_notification_as_dismissed,
)
from pydantic import ValidationError
import uuid
from app.models import User

chat_bp = blueprints.Blueprint("chat", __name__)


# a post route for chat messages
@chat_bp.route("/api/chat", methods=["POST"])
@jwt_required(optional=False, locations=["cookies"])
def chat():
    """Post messages to RQ to process."""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"status": "ERROR", "message": "User not found"}), 404

    try:
        content = request.get_json()
        if not content or "message" not in content:
            return jsonify({"status": "ERROR", "message": "Message is required"}), 400

        message_content = content["message"]
        logging.info("Chat request received: %s from user %s", message_content, current_user.email)

        user_id = current_user.id
        if not can_send_message(user_id=user_id):
            return jsonify({"status": "ERROR", "message": "Message limit exceeded"}), 429

        redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
        queue = Queue(connection=redis_conn)

        # Create or retrieve chat thread
        thread_id = session.get("thread_id") or str(uuid.uuid4())
        session["thread_id"] = thread_id

        # Enqueue task
        job = queue.enqueue(
            get_answer_from_rag,
            thread_id,
            message_content,
            current_user.id,
            current_user.email,
            current_user.organisation,
            model_type="OpenAILlm",
        )
        logging.info("Enqueued job for chat, message %s, thread %s", message_content, thread_id)

        return jsonify(
            {
                "status": "success",
                "message": "Your message is being processed.",
                "job": job.id,
                "thread_id": thread_id,
            }
        ), 200

    except ValidationError as e:
        return jsonify({"status": "ERROR", "message": e.errors()}), 400
    except Exception:
        logging.exception("An error occurred while processing chat message")
        return jsonify({"status": "ERROR", "message": "An internal error occurred."}), 500


@chat_bp.route("/api/chat", methods=["GET"])
def fetch_chat_result():
    """Endpoint to fetch the result of a chat operation."""
    job_id = request.args.get("job_id")
    thread_id = request.args.get("thread_id")
    if not job_id:
        return jsonify({"status": "ERROR", "message": "Job ID is required"}), 400

    logging.debug("Fetching job result for job ID: %s", job_id)

    redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
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
        notifications = get_notifications(session.get("user.id"))

        # Convert notifications to a JSON-serializable format
        serialized_notifications = [
            {
                "id": notification.id,
                "user_id": notification.user_id,
                "message": notification.message,
                "created_at": notification.created_at.isoformat(),
                "read_at": notification.read_at.isoformat() if notification.read_at else None,
                "dismissed_at": notification.dismissed_at.isoformat()
                if notification.dismissed_at
                else None,
                "type": notification.type,
            }
            for notification in notifications
        ]

        return jsonify(serialized_notifications), 200
    except Exception as e:
        # Log the error (you should set up proper logging)
        logging.error(f"Error fetching notifications: {str(e)}")
        return jsonify({"error": "Unable to fetch notifications"}), 500


@chat_bp.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
def api_notifications_read(notification_id):
    """Mark a notification as read."""
    logging.info(
        f"Marking notification {notification_id} as read for user {session.get('user.id')}"
    )
    result = mark_notification_as_read(notification_id, session.get("user.id"))
    logging.debug(f"Notification read result: {result}")
    if isinstance(result, dict) and result.get("success", False):
        return jsonify(result), 200
    else:
        return jsonify({"status": "error", "message": "Failed to mark notification as read"}), 400


@chat_bp.route("/api/notifications/<int:notification_id>/dismiss", methods=["POST"])
def api_notifications_dismiss(notification_id):
    """Mark a notification as dismissed."""
    logging.info(
        f"Marking notification {notification_id} as dismissed for user {session.get('user.id')}"
    )
    result = mark_notification_as_dismissed(notification_id, session.get("user.id"))
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
    chat_template_requirements = get_chat_template_requirements(thread_id, session["user.id"])
    return render_template(
        template_name_or_list="index_logged_in.html",
        user_email=session["user.email"],
        recent_conversations=chat_template_requirements["recent_conversations"],
        is_admin=chat_template_requirements["is_admin_status"],
        support_portal=current_app.config["LORELAI_SUPPORT_PORTAL"],
        support_email=current_app.config["LORELAI_SUPPORT_EMAIL"],
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

    # check if the user is logged in
    if current_user.is_authenticated:
        # render the index_logged_in page
        thread_id = str(uuid.uuid4())
        session["thread_id"] = thread_id
        chat_template_requirements = get_chat_template_requirements(thread_id, current_user.id)

        return render_template(
            "index_logged_in.html",
            user_email=current_user.email,
            user_name=current_user.user_name,
            recent_conversations=chat_template_requirements["recent_conversations"],
            is_admin=chat_template_requirements["is_admin_status"],
            support_portal=current_app.config["LORELAI_SUPPORT_PORTAL"],
            support_email=current_app.config["LORELAI_SUPPORT_EMAIL"],
        )

    # if we're still here, there was no user_id in the session meaning we are not logged in
    # render the front page with the google client id
    # if the user clicks login from that page, the javascript function `onGoogleCredentialResponse`
    # will handle the login using the /login route in auth.py.
    # Depending on the output of that route, it's redirecting to /register if need be

    return render_template("index.html", google_client_id=current_app.config["GOOGLE_CLIENT_ID"])
