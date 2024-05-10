#!/usr/bin/env python

"""
Module to perform benchmarking using LaurelAI's validation system.
"""

import argparse
import logging
import os
import sys
import time

import benchmark.operations
import benchmark.run

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../../.."))
from lorelai.utils import load_config


def setup_arg_parser():
    parser = argparse.ArgumentParser(
        description="Dragonfly: Unified Benchmarking Script with Configurable Operations"
    )
    parser.add_argument(
        "verb",
        choices=["download", "upload", "benchmark"],
        help="Operation to perform: \
            download - download NLTK corpus to the location of dragonfly, \
            upload - upload data to google drive \
            benchmark - run benchmarking using LaurelAI's validation system",
    )
    parser.add_argument(
        "--config", help="Path to the JSON formatted config file", default="settings.json"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Perform a dry run of the operation", default=False
    )
    return parser


def validate_config(config, verb):
    # Define necessary keys for each operation
    necessary_keys = {
        "download": ["nltk_corpus_download_dir"],
        "upload": ["drive_service_config", "folder_name", "data_dir"],
        "benchmark": [
            "question_file",
            "org_name",
            "user_name",
            "question_classes_file",
        ],
    }
    missing_keys = [key for key in necessary_keys[verb] if key not in config]
    if missing_keys:
        logging.error(f"Missing configuration keys for {verb}: {', '.join(missing_keys)}")
        sys.exit(1)


def main():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging_format = os.getenv(
        "LOG_FORMAT",
        "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
    )
    logging.basicConfig(level=log_level, format=logging_format)

    parser = setup_arg_parser()
    args = parser.parse_args()

    logging.debug(f"Reading config from: {args}")
    logging.debug(f"Performing operation: {args.verb}")

    config = load_config("dragonfly")

    validate_config(config, args.verb)  # Validate config before proceeding

    if args.verb == "download":
        if args.dry_run:
            logging.info("Dry run enabled. Skipping download operation.")
            sys.exit(0)
        else:
            benchmark.operations.download_nltk_reuters(config["nltk_corpus_download_dir"])

    elif args.verb == "upload":
        if args.data_source == "drive":
            # authenticate with Google Drive
            service = benchmark.operations.google_drive_auth(config["drive_service_config"])

            # find or create folder and upload files
            folder_id = benchmark.operations.find_or_create_folder(service, config["folder_name"])
            benchmark.operations.upload_files(service, folder_id, config["data_dir"])
        else:
            logging.error(f"Data source {args.data_source} not supported for upload operation.")
            sys.exit(1)

    elif args.verb == "benchmark":
        # record the time before benchmarking
        start = time.time()

        benchmark_run = benchmark.run.Run(model_type="OllamaLlama3")
        benchmark_run.benchmark(
            org_name=config["org_name"],
            user_name=config["user_name"],
            question_file=config["question_file"],
            question_classes_file=config["question_classes_file"],
        )

        end = time.time()

        logging.info(f"Benchmarking completed in {end - start} seconds.")
    else:
        logging.error(f"Invalid operation: {args.verb}")
        sys.exit(1)


if __name__ == "__main__":
    main()
