"""Unit tests for the Dragonfly benchmarking script."""

import json
import sys
from unittest import mock

import pytest
from dragonfly import (  # Make sure to import correctly from your actual script
    main,
    setup_arg_parser,
)


def test_parser_with_valid_verb():
    """Test the argument parser with valid verbs."""
    parser = setup_arg_parser()
    # Test with each valid verb
    for verb in ["download", "upload", "benchmark"]:
        args = parser.parse_args([verb])
        assert args.verb == verb
        assert args.config == "settings.json"  # default


def test_parser_with_no_verbs():
    """Test the argument parser with no verbs, expecting a SystemExit."""
    parser = setup_arg_parser()
    with pytest.raises(SystemExit):  # argparse throws SystemExit on invalid args
        parser.parse_args(["invalid_verb"])


def test_parser_with_invalid_verbs(capfd):
    """Test the argument parser with invalid verbs, expecting an error message."""
    parser = setup_arg_parser()
    # expect argparse to throw an ArgumentError since "dostuff" is not a valid verb
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["dostuff"])
    assert excinfo.type == SystemExit

    # Capture the output to stderr and stdout
    out, err = capfd.readouterr()

    # Check the stderr output for the expected error message
    assert "invalid choice" in err
    assert "dostuff" in err


def test_parser_with_optional_arguments():
    """Test the argument parser with optional arguments."""
    parser = setup_arg_parser()
    args = parser.parse_args(["download", "--config", "settings.json"])
    assert args.verb == "download"
    assert args.config == "settings.json"


def test_main_with_no_args():
    """Test the main function with no arguments, expecting a SystemExit."""
    testargs = ["prog"]
    with mock.patch.object(sys, "argv", testargs):
        with pytest.raises(SystemExit) as excinfo:
            main()
    assert excinfo.type == SystemExit
    assert excinfo.value.code != 0  # Should exit with an error since no verb is provided


def test_main_with_invalid_args():
    """Test the main function with invalid arguments, expecting a SystemExit."""
    testargs = ["prog", "invalid_verb"]
    with mock.patch.object(sys, "argv", testargs):
        with pytest.raises(SystemExit) as excinfo:
            main()
    assert excinfo.type == SystemExit
    assert excinfo.value.code != 0  # Should exit with an error due to invalid verb


def test_main_with_valid_args():
    """Test the main function with valid arguments, mocking file operations and function calls."""
    testargs = ["prog", "download", "--config", "custom.json"]
    config_data = '{"nltk_corpus_download_dir": "dir"}'
    with mock.patch.object(sys, "argv", testargs):
        with mock.patch("builtins.open", mock.mock_open(read_data=config_data)) as mock_file:
            with mock.patch("json.load", return_value=json.loads(config_data)):
                with mock.patch("benchmark.operations.download_nltk_reuters") as mock_download:
                    main()
                    mock_download.assert_called_once_with("dir")
                    mock_file.assert_called_once_with("custom.json", "r")
