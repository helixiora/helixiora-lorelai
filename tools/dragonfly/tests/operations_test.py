"""Unit tests for benchmarking including NLTK Reuters download and GDrive folder management."""

import os
from unittest.mock import MagicMock, Mock

import nltk
import pytest

# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
from benchmark import operations


class MockMediaFileUpload(MagicMock):
    """Mock class for MediaFileUpload to bypass file handling in tests."""

    def __init__(self, *args, **kwargs):
        pass


@pytest.fixture
def mock_service():
    """Fixture to mock Google Drive service."""
    service_mock = Mock()
    files_mock = Mock()
    service_mock.files.return_value = files_mock
    return service_mock


def test_download_nltk_reuters(mocker):
    """Test the download_nltk_reuters function, mocking necessary file operations and NLTK download.

    Arguments
    ---------
    mocker : pytest_mock.plugin.MockerFixture
        The mocker fixture provided by pytest-mock to mock objects.

    Asserts
    -------
    Checks if the necessary directories are created and the NLTK Reuters corpus is downloaded.
    """
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.makedirs")
    mocker.patch("nltk.data.find", side_effect=LookupError)
    mocker.patch("nltk.download")

    # Mock file operations
    mocker.patch("builtins.open", mocker.mock_open())

    # Run the function
    operations.download_nltk_reuters("dummy_path")

    # Assert calls
    os.makedirs.assert_called_with("dummy_path")
    nltk.download.assert_called_with("reuters")


def test_find_or_create_folder(mock_service):
    """Test the find_or_create_folder function for both existing and new folder scenarios.

    Arguments
    ---------
    mock_service : Mock
        Mock object for Google Drive service.

    Asserts
    -------
    Checks if the function correctly identifies an existing folder or creates a new one if it
    doesn't exist.
    """
    mock_service.files().list().execute.return_value = {"files": [{"id": "123"}]}

    folder_id = operations.find_or_create_folder(mock_service, "TestFolder")
    assert folder_id == "123"

    # Test case where folder does not exist
    mock_service.files().list().execute.return_value = {"files": []}
    mock_service.files().create().execute.return_value = {"id": "new_id"}

    new_folder_id = operations.find_or_create_folder(mock_service, "NewFolder")
    assert new_folder_id == "new_id"


# Include more detailed edge cases and error handling tests as necessary.
