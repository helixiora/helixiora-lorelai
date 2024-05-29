import logging
import os
import sys
import time
sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../.."))
# import the indexer
from app.utils import get_db_connection
from lorelai.slack.slack_processor import slack_indexer
logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format=logging_format)

start_time=time.time()

indexer=slack_indexer("masood@helixiora.com","helixiora.com")
#indexer.get_messages("sdfsdf","sdfsdf")
#print(indexer.list_channel_ids())
#indexer.get_thread('1715925282.546629',"C06FBKAN70A")
#indexer.get_userid_name()
indexer.process_slack_message('C06FBKAN70A')
print(f"Exec Time: {time.time()-start_time}")
#https://helixiora.slack.com/archives/C06FBKAN70A

