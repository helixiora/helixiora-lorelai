#!/usr/bin/env python

"""
Module to perform benchmarking using LaurelAI's validation system.
"""

import argparse
import json

import yaml

import benchmark.operations
import benchmark.run


def setup_arg_parser():
    parser = argparse.ArgumentParser(
        description="Unified Benchmarking Script with Configurable Operations"
    )
    parser.add_argument(
        "verb", choices=["download_extract", "upload", "benchmark"], help="Operation to perform"
    )
    parser.add_argument(
        "--data_source", choices=["drive"], default="drive", help="Destination to upload data"
    )
    parser.add_argument("--config", help="Path to the config file", default="config.yaml")
    return parser


def main():
    parser = setup_arg_parser()
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    if args.verb == "download_extract":
        benchmark.operations.download_and_extract(
            config["url"], config["save_path"], config["extract_to"]
        )

    elif args.verb == "upload":
        if args.data_source == "drive":
            service = benchmark.operations.google_drive_auth(config["drive_service_config"])
            folder_id = benchmark.operations.find_or_create_folder(service, config["folder_name"])
            benchmark.operations.upload_files(service, folder_id, config["extract_to"])

    elif args.verb == "benchmark":
        if not all([args.question_file, args.org_name, args.user_name]):
            print("Question file, organization name, and user name are required for benchmarking.")
            return
        with open(args.question_file, "r", encoding="utf-8") as f:
            q_a = json.load(f)

        benchmark_run = benchmark.Run()
        benchmark_run.benchmark(
            args.org_name, args.user_name, q_a, args.evaluator, args.api_key, args.project_id
        )


if __name__ == "__main__":
    main()
