import logging
import os
import sys

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../.."))
# import the indexer
from app.utils import get_db_connection
logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)
