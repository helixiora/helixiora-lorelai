"""API routes for chat operations."""

from flask import current_app, request, session
from pydantic import ValidationError
from flask_jwt_extended import jwt_required, get_jwt_identity
from redis import Redis
from rq import Queue


import logging
import uuid

from flask_restx import Namespace, Resource, fields

from app.models import User
from app.tasks import get_answer_from_rag
from app.helpers.chat import can_send_message

chat_ns = Namespace("chat", description="Chat operations")

# Add model definitions
message_input = chat_ns.model(
    "MessageInput",
    {"message": fields.String(required=True, description="Message content to process")},
)

message_response = chat_ns.model(
    "MessageResponse",
    {
        "status": fields.String(description="Response status"),
        "message": fields.String(description="Response message"),
        "job": fields.String(description="Job ID for the processing task"),
        "conversation_id": fields.String(description="Unique conversation identifier"),
    },
)

result_response = chat_ns.model(
    "ResultResponse",
    {
        "status": fields.String(description="Response status"),
        "result": fields.Raw(description="Processing result"),
        "conversation_id": fields.String(description="Conversation identifier"),
    },
)


# a post route for chat messages
@chat_ns.route("/")
class ChatResource(Resource):
    """Resource for chat operations."""

    @chat_ns.expect(message_input)
    @chat_ns.response(200, "Success", message_response)
    @chat_ns.response(400, "Validation Error")
    @chat_ns.response(401, "Unauthorized")
    @chat_ns.response(404, "User Not Found")
    @chat_ns.response(429, "Message Limit Exceeded")
    @chat_ns.response(500, "Internal Server Error")
    @chat_ns.doc(security="jwt")
    @jwt_required(locations=["headers"])
    def post(self):
        """
        Submit a new chat message for processing.

        Returns a job ID and conversation ID for tracking the request.

        Requires a valid JWT token in cookies for authentication.
        """
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user:
            return {"status": "ERROR", "message": "User not found"}, 404

        try:
            content = request.get_json()
            if not content or "message" not in content:
                return {"status": "ERROR", "message": "Message is required"}, 400

            message_content = content["message"]
            logging.info(
                "Chat request received: %s from user %s",
                message_content,
                current_user.email,
            )

            user_id = current_user.id
            if not can_send_message(user_id=user_id):
                return {"status": "ERROR", "message": "Message limit exceeded"}, 429

            redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
            queue = Queue(current_app.config["REDIS_QUEUE_QUESTION"], connection=redis_conn)

            # Create or retrieve chat conversation
            conversation_id = session.get("conversation_id") or str(uuid.uuid4())
            session["conversation_id"] = conversation_id

            # Enqueue task
            job = queue.enqueue(
                get_answer_from_rag,
                conversation_id,
                message_content,
                current_user.id,
                current_user.email,
                current_user.organisation.name,
                model_type="OpenAILlm",
            )
            logging.info(
                "Enqueued job for chat, message %s, conversation %s",
                message_content,
                conversation_id,
            )

            return {
                "status": "success",
                "message": "Your message is being processed.",
                "job": job.id,
                "conversation_id": conversation_id,
            }, 200

        except ValidationError as e:
            return {"status": "ERROR", "message": e.errors()}, 400
        except Exception:
            logging.exception("An error occurred while processing chat message")
            return {"status": "ERROR", "message": "An internal error occurred."}, 500

    @chat_ns.doc(
        params={
            "job_id": "ID of the processing job to fetch results for",
            "conversation_id": "ID of the conversation",
        }
    )
    @chat_ns.response(200, "Success", result_response)
    @chat_ns.response(202, "Processing In Progress")
    @chat_ns.response(400, "Missing Job ID")
    @chat_ns.response(404, "Job Not Found")
    @chat_ns.response(500, "Processing Failed")
    @jwt_required(optional=False, locations=["headers"])
    def get(self):
        """
        Fetch the result of a chat processing job.

        Requires job_id query parameter.
        """
        job_id = request.args.get("job_id")
        conversation_id = request.args.get("conversation_id")

        if not job_id:
            return {"status": "ERROR", "message": "Job ID is required"}, 400

        logging.debug("Fetching job result for job ID: %s", job_id)

        redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
        queue = Queue(current_app.config["REDIS_QUEUE_QUESTION"], connection=redis_conn)
        job = queue.fetch_job(job_id)

        logging.debug("Job status: %s", job.get_status())
        if job is None:
            return {"status": "ERROR", "message": "Job not found"}, 404
        elif job.is_failed:
            return {"status": "FAILED", "error": str(job.exc_info)}, 500
        elif job.is_finished:
            logging.info("Job result: %s", job.result)
            if job.result["status"] == "Failed":
                return {"status": "FAILED", "error": job.result}, 500
            if job.result["status"] == "No Relevant Source":
                return {"status": "NO_RELEVANT_SOURCE", "result": job.result}, 500
            return {
                "status": "SUCCESS",
                "result": job.result,
                "conversation_id": conversation_id,
            }
        else:
            # Job is either queued or started but not yet finished
            return {"status": "IN PROGRESS"}, 202
