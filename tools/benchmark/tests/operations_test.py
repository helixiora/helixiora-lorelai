import os
from unittest.mock import MagicMock, Mock

import nltk
import pytest

# from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
from benchmark import operations


class MockMediaFileUpload(MagicMock):
    def __init__(self, *args, **kwargs):
        # Avoid calling the superclass constructor to bypass file handling
        pass


@pytest.fixture
def mock_service():
    # Mock Google Drive service
    service_mock = Mock()
    files_mock = Mock()
    service_mock.files.return_value = files_mock
    return service_mock


def test_download_nltk_reuters(mocker):
    # Mock os.path.exists, os.makedirs, and nltk.download
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


# def test_google_drive_auth(mocker):
#     # Ensure correct mocking of external dependencies
#     mock_flow = Mock()
#     mocker.patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file', return_value=mock_flow)
#     mock_build = Mock()
#     mocker.patch('googleapiclient.discovery.build', return_value=mock_build)

#     # Call the function
#     service = operations.google_drive_auth("credentials.json")

#     # Check if the returned service is indeed the mock build
#     assert service == mock_build, "The returned service should be the mock build"

# def test_upload_files(mock_service, mocker):
#     mocker.patch("os.listdir", return_value=["file1.txt", "file2.txt"])
#     mocker.patch("os.path.join", side_effect=lambda *args: "/".join(args))
#     mocker.patch("builtins.open", mocker.mock_open())

#     # Use the new MockMediaFileUpload for the patch
#     mocker.patch("googleapiclient.http.MediaFileUpload", new=MockMediaFileUpload)

#     # Call the function
#     operations.upload_files(mock_service, "folder_id", "directory")

#     # Verify that Google Drive's create method was called correctly
#     assert mock_service.files().create.call_count == 2


def test_find_or_create_folder(mock_service):
    # Setup response for the Google Drive list API
    mock_service.files().list().execute.return_value = {"files": [{"id": "123"}]}

    folder_id = operations.find_or_create_folder(mock_service, "TestFolder")
    assert folder_id == "123"

    # Test case where folder does not exist
    mock_service.files().list().execute.return_value = {"files": []}
    mock_service.files().create().execute.return_value = {"id": "new_id"}

    new_folder_id = operations.find_or_create_folder(mock_service, "NewFolder")
    assert new_folder_id == "new_id"


# Include more detailed edge cases and error handling tests as necessary.
