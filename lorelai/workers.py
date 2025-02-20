"""RQ worker configuration and setup for Lorelai.

This module configures RQ workers with consistent logging and error handling.
"""

import redis
from rq import Connection, Worker
import logging

from .logging import configure_logging

# Configure logging
logger = logging.getLogger(__name__)


def setup_worker(redis_url, queues=None):
    """Set up an RQ worker with proper logging and configuration.

    Parameters
    ----------
    redis_url : str
        Redis connection URL
    queues : list[str], optional
        List of queue names to listen to, by default ['default']

    Returns
    -------
    Worker
        Configured RQ worker
    """
    if queues is None:
        queues = ["default"]

    # Configure logging using LOG_LEVEL from environment
    configure_logging()
    logger.debug("Setting up RQ worker for queues: %s", queues)

    # Connect to Redis
    redis_conn = redis.from_url(redis_url)
    logger.debug("Connected to Redis at %s", redis_url)

    # Set up worker with all queues
    with Connection(redis_conn):
        worker = Worker(queues)
        logger.debug("Worker initialized and ready to process jobs")
        return worker


def run_worker(redis_url, queues=None):
    """Run an RQ worker with proper logging and configuration.

    This is the main entry point for running a worker process.

    Parameters
    ----------
    redis_url : str
        Redis connection URL
    queues : list[str], optional
        List of queue names to listen to, by default ['default']
    """
    worker = setup_worker(redis_url, queues)

    logger.debug("Starting worker process")
    with Connection(worker.connection):
        worker.work()
