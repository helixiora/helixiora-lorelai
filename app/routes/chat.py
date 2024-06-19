import logging

from flask import blueprints, jsonify, request, session
from redis import Redis
from rq import Queue

from app.tasks import execute_rag_llm
from app.utils import load_config

chat_bp = blueprints.Blueprint("chat", __name__)


# a get and post route for the chat page
@chat_bp.route("/chat", methods=["POST"])
def chat():
    """Endpoint to post chat messages."""

    content = request.get_json()
    print("$$$$$$$$$$",content)
    if not content or "message" not in content:
        return jsonify({"status": "ERROR", "message": "Message is required"}), 400

    logging.info("Chat request received: %s", content["message"])

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

    job = queue.enqueue(
        execute_rag_llm,
        content["message"],
        session.get("email"),
        session.get("organisation"),
        llm_model,
        datasource=content["datasource"],
        job_timeout=chat_task_timeout,
        description=f"Execute RAG+LLM model: {content['message']} for {session.get('email')} \
            using {llm_model}",
    )

    return jsonify({"job": job.get_id()}), 202


@chat_bp.route("/chat", methods=["GET"])
def fetch_chat_result():
    """Endpoint to fetch the result of a chat operation."""
    job_id = request.args.get("job_id")
    if not job_id:
        return jsonify({"status": "ERROR", "message": "Job ID is required"}), 400

    logging.info("Fetching job result for job ID: %s", job_id)

    redis = load_config("redis")
    redis_host = redis["url"]

    redis_conn = Redis.from_url(redis_host)
    queue = Queue(connection=redis_conn)
    job = queue.fetch_job(job_id)

    if job is None:
        return jsonify({"status": "ERROR", "message": "Job not found"}), 404
    elif job.is_failed:
        return jsonify({"status": "FAILED", "error": str(job.exc_info)}), 500
    elif job.result is not None:
        return jsonify({"status": "SUCCESS", "result": job.result})
    else:
        # Job is either queued or started but not yet finished
        return jsonify({"status": "IN PROGRESS"}), 202
