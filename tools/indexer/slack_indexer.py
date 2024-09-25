"""CLI for slack."""

import logging
import os
import sys
import time

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../.."))
# import the indexer
from lorelai.slack.slack_processor import SlackIndexer

logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)

start_time = time.time()

indexer = SlackIndexer("masood@helixiora.com", "helixiora.com")
# https://helixiora.slack.com/archives/C06FBKAN70A
indexer.process_slack_message("C06FBKAN70A")
# indexer.get_messages("C06FBKAN70A","Engineering")
print("*****************")
# indexer.get_thread("1725613957.159699", "C06FBKAN70A")
logging.info(f"Exec Time: {time.time()-start_time}")
