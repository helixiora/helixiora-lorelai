import logging
import os
import sys

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../../.."))
from lorelai.utils import load_config, get_db_connection  # noqa E402


class BenchmarkManager:
    def __init__(self):
        self.config = load_config("dragonfly")

    def run(self, template_name, description, dry_run):
        print(f"Running benchmark with template {template_name} and description {description}")
        logging.error("Not implemented")
        sys.exit(1)

    def view_results(self, benchmark_id):
        print(f"Viewing results for benchmark {benchmark_id}")
        logging.error("Not implemented")
        sys.exit(1)

    def delete_results(self, benchmark_id):
        print(f"Deleting results for benchmark {benchmark_id}")
        logging.error("Not implemented")
        sys.exit(1)
