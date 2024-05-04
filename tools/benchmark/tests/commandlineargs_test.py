import sys
from unittest import mock

import pytest
from dragonfly import (  # Make sure to import correctly from your actual script
    main,
    setup_arg_parser,
)


def test_parser_with_valid_verb():
    parser = setup_arg_parser()
    # Test with each valid verb
    for verb in ["download", "upload", "benchmark"]:
        args = parser.parse_args([verb])
        assert args.verb == verb
        assert args.data_source == "drive"  # default
        assert args.config == "config.yaml"  # default


def test_parser_with_invalid_verb():
    parser = setup_arg_parser()
    with pytest.raises(SystemExit):  # argparse throws SystemExit on invalid args
        parser.parse_args(["invalid_verb"])


def test_parser_with_optional_arguments():
    parser = setup_arg_parser()
    args = parser.parse_args(["download", "--data_source", "drive", "--config", "custom.yaml"])
    assert args.verb == "download"
    assert args.data_source == "drive"
    assert args.config == "custom.yaml"


def test_main_with_no_args():
    testargs = ["prog"]
    with mock.patch.object(sys, "argv", testargs):
        with pytest.raises(SystemExit) as excinfo:
            main()
    assert excinfo.type == SystemExit
    assert excinfo.value.code != 0  # Should exit with an error since no verb is provided


def test_main_with_invalid_args():
    testargs = ["prog", "invalid_verb"]
    with mock.patch.object(sys, "argv", testargs):
        with pytest.raises(SystemExit) as excinfo:
            main()
    assert excinfo.type == SystemExit
    assert excinfo.value.code != 0  # Should exit with an error due to invalid verb


def test_main_with_valid_args():
    testargs = ["prog", "download", "--config", "custom.yaml"]
    with mock.patch.object(sys, "argv", testargs):
        with mock.patch("builtins.open", mock.mock_open(read_data="data")) as mock_file:
            with mock.patch("yaml.safe_load", return_value={"nltk_corpus_download_dir": "dir"}):
                with mock.patch("benchmark.operations.download_nltk_reuters") as mock_download:
                    main()
                    mock_download.assert_called_once_with("dir")
                    mock_file.assert_called_once_with("custom.yaml", "r")
