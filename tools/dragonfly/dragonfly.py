#!/usr/bin/env python3

import argparse
import logging
import os
import sys

from benchmark.benchmarkmanager import BenchmarkManager
from benchmark.datamanager import DataManager
from benchmark.templatemanager import TemplateManager


def main():
    logging_format = os.getenv(
        "LOG_FORMAT",
        "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
    )
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level, format=logging_format)

    parser = setup_arg_parser()
    args = parser.parse_args()

    if args.verb == "data":
        handle_data(args)
    elif args.verb == "benchmark":
        handle_benchmark(args)
    elif args.verb == "template":
        handle_template(args)


sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../../.."))


def setup_arg_parser():
    # Create the main parser and a subparsers container
    parser = argparse.ArgumentParser(
        description="""Dragonfly: Unified Benchmarking Script with Configurable Operations
        \nUse this script to manage data operations, benchmarking processes, and template management.
        \nCommands are structured into categories: 'data', 'benchmark', and 'template'.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="For more information, use the '-h' or '--help' after a sub-command.",
    )
    subparsers = parser.add_subparsers(dest="verb", required=True, help="Operation to perform")

    # Data subparser
    data_parser = subparsers.add_parser(
        "data", help="manage data operations such as upload and download"
    )
    data_subparsers = data_parser.add_subparsers(
        dest="data_verb", required=True, help="Data operation to perform"
    )
    setup_data_subparsers(data_subparsers)

    # Benchmark subparser
    benchmark_parser = subparsers.add_parser(
        "benchmark", help="run benchmarking using a configurable system"
    )
    benchmark_subparsers = benchmark_parser.add_subparsers(
        dest="benchmark_verb", required=True, help="Benchmark operation to perform"
    )
    setup_benchmark_subparsers(benchmark_subparsers)

    # Template subparser
    template_parser = subparsers.add_parser("template", help="manage benchmarking templates")
    template_subparsers = template_parser.add_subparsers(
        dest="template_verb", required=True, help="Template operation to perform"
    )
    setup_template_subparsers(template_subparsers)

    return parser


def setup_data_subparsers(subparsers):
    download_parser = subparsers.add_parser(
        "download", help="download data to the specified location"
    )
    download_parser.add_argument("--path", required=True, help="Local path to download data to")
    download_parser.add_argument(
        "--config", default="settings.json", help="Path to the JSON formatted config file"
    )
    download_parser.add_argument(
        "--dry-run", action="store_true", help="Perform a dry run of the operation"
    )

    upload_parser = subparsers.add_parser("upload", help="upload data from a specified location")
    upload_parser.add_argument("--path", required=True, help="Local path to upload data from")
    upload_parser.add_argument(
        "--config", default="settings.json", help="Path to the JSON formatted config file"
    )
    upload_parser.add_argument(
        "--dry-run", action="store_true", help="Perform a dry run of the operation"
    )


def setup_benchmark_subparsers(subparsers):
    run_parser = subparsers.add_parser("run", help="execute a benchmark run")
    run_parser.add_argument("--template-id", required=True, help="Template to run")
    run_parser.add_argument(
        "--config", default="settings.json", help="Path to the JSON formatted config file"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Perform a dry run of the operation"
    )

    prepare_parser = subparsers.add_parser("prepare", help="prepare a benchmark run")
    prepare_parser.add_argument(
        "--template-id", required=True, help="Template to prepare for a benchmark run"
    )
    prepare_parser.add_argument(
        "--benchmark-name", required=True, help="Name of the benchmarking run"
    )
    prepare_parser.add_argument(
        "--benchmark-description", default="", help="Description of the benchmarking run"
    )

    show_parser = subparsers.add_parser("show", help="show the details of a benchmark run")
    show_parser.add_argument("--benchmark-id", required=True, help="Specify the benchmark to show")

    results_parser = subparsers.add_parser("results", help="manage the results of benchmark runs")
    results_parser.add_argument(
        "--benchmark-id", required=True, help="Specify the ID of the benchmark to manage results"
    )
    results_parser.add_argument(
        "--action",
        choices=["view", "delete"],
        required=True,
        help="Action to perform on the benchmark results",
    )


def setup_template_subparsers(subparsers):
    subparsers.add_parser("list", help="list all available benchmarking templates")

    create_parser = subparsers.add_parser("create", help="create a new benchmarking template")
    create_parser.add_argument("--template-name", required=True, help="Name of the new template")
    create_parser.add_argument(
        "--template-description", required=True, help="Description of the new template"
    )
    create_parser.add_argument(
        "--config", default="settings.json", help="Path to the JSON formatted config file"
    )

    delete_parser = subparsers.add_parser("delete", help="delete a benchmarking template")
    delete_parser.add_argument(
        "--template-id", required=True, help="Specify the template to delete"
    )

    show_parser = subparsers.add_parser("show", help="show the details of a benchmarking template")
    show_parser.add_argument("--template-id", required=True, help="Specify the template to show")

    list_parameters_parser = subparsers.add_parser(
        "list-parameters", help="list the parameters of a benchmarking template"
    )
    list_parameters_parser.add_argument(
        "--template-id", required=True, help="Specify the template to list parameters"
    )

    add_parameter_parser = subparsers.add_parser(
        "add-parameter", help="add a parameter to a benchmarking template"
    )
    add_parameter_parser.add_argument(
        "--template-id", required=True, help="Specify the template to add a parameter to"
    )
    add_parameter_parser.add_argument(
        "--parameter-name", required=True, help="Name of the parameter to add"
    )
    add_parameter_parser.add_argument(
        "--parameter-type", required=True, help="Type of the parameter to add"
    )
    add_parameter_parser.add_argument(
        "--parameter-value", required=True, help="Value of the parameter to add"
    )

    delete_parameter_parser = subparsers.add_parser(
        "delete-parameter", help="delete a parameter from a benchmarking template"
    )
    delete_parameter_parser.add_argument(
        "--template-id", required=True, help="Specify the template to delete a parameter from"
    )
    delete_parameter_parser.add_argument(
        "--parameter-name", required=True, help="Name of the parameter to delete"
    )


def handle_data(args):
    data_manager = DataManager()
    if args.data_verb == "download":
        data_manager.download(args.path, args.dry_run)
    elif args.data_verb == "upload":
        data_manager.upload(args.path, args.dry_run)


def handle_benchmark(args):
    benchmark_manager = BenchmarkManager()
    if args.benchmark_verb == "run":
        benchmark_manager.run(template_id=args.template_id, dry_run=args.dry_run)
    elif args.benchmark_verb == "prepare":
        benchmark_manager.prepare(args.template_id, args.benchmark_name, args.benchmark_description)
    elif args.benchmark_verb == "show":
        benchmark_manager.show(args.benchmark_id)
    elif args.benchmark_verb == "results":
        if args.action == "view":
            benchmark_manager.view_results(args.benchmark_id)
        elif args.action == "delete":
            benchmark_manager.delete_results(args.benchmark_id)


def handle_template(args):
    try:
        template_manager = TemplateManager()
        if args.template_verb == "list":
            template_manager.list_templates()
        elif args.template_verb == "create":
            template_manager.create_template(args.template_name, args.template_description)
        elif args.template_verb == "delete":
            template_manager.delete_template(args.template_id)
        elif args.template_verb == "show":
            template_manager.show_template(args.template_id)
        elif args.template_verb == "list-parameters":
            template_manager.list_parameters(args.template_id)
        elif args.template_verb == "add-parameter":
            template_manager.add_parameter(
                args.template_id, args.parameter_name, args.parameter_type, args.parameter_value
            )  # noqa E501
        elif args.template_verb == "delete-parameter":
            template_manager.delete_parameter(args.template_id, args.parameter_name)
    except ValueError as e:
        logging.error(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
