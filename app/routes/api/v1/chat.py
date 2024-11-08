"""API routes for chat operations."""

from flask import current_app, jsonify, request, session
from pydantic import ValidationError
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import current_user
from redis import Redis
from rq import Queue


import logging
import uuid

from flask_restx import Namespace, Resource

from app.models import User
from app.tasks import get_answer_from_rag
from app.helpers.chat import can_send_message

chat_ns = Namespace("chat", description="Chat operations")


# a post route for chat messages
@chat_ns.route("/")
class ChatResource(Resource):
    """Resource for chat operations."""

    @jwt_required(optional=False, locations=["cookies"])
    def post(self):
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
            logging.info(
                "Chat request received: %s from user %s", message_content, current_user.email
            )

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
                current_user.organisation.name,
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

    def get(self):
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
