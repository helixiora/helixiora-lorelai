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

    def show(self, benchmark_id):
        print(f"Showing benchmark with ID {benchmark_id}")
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT benchmark_template_id, name, description FROM benchmark_run WHERE id = %s",
                (benchmark_id,),
            )
            row = cursor.fetchone()
            if row:
                print(f"Benchmark ID: {benchmark_id}")
                print(f"Template ID: {row[0]}")
                print(f"Name: {row[1]}")
                print(f"Description: {row[2]}")
            else:
                print(f"Benchmark with ID {benchmark_id} not found")

    def prepare(self, template_id, benchmark_name, benchmark_description):
        print(
            f"Preparing benchmark with template {template_id}, name {benchmark_name}, and description {benchmark_description}"
        )
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO benchmark_run (benchmark_template_id, name, description) VALUES (%s, %s, %s)",
                (template_id, benchmark_name, benchmark_description),
            )
            benchmark_run_id = cursor.lastrowid
            print(f"Benchmark {benchmark_name} with ID: {benchmark_run_id} created")
            db.commit()
