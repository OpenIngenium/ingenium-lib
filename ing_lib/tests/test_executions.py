"""
Tests for executions.py module
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
import datetime

# Import the modules under test
import ing_lib.common as common
import executions

# Test constants
MOCK_BASE_URL = "https://mock-ingenium.example.com"
MOCK_EXECUTION_ID = "test-ingenium-10001"


@pytest.fixture(autouse=True)
def setup_auth():
    """Set up a valid token/ssl state for all tests in this module."""
    common.set_token("test_token")
    common.set_refresh_time(datetime.datetime.now(datetime.timezone.utc))
    common.set_ssl_verify(True)
    yield
    common.set_token(None)
    common.set_refresh_time(None)
    common.set_ssl_verify(True)


class TestGetIngeniumExecutions:
    """Test class for get_ingenium_executions."""

    @patch('executions.ingenium_rest_get_paginated')
    def test_get_ingenium_executions_success(self, mock_paginated):
        """Test successful get_ingenium_executions call hits the right endpoint."""
        mock_paginated.return_value = [{'execution_id': MOCK_EXECUTION_ID, 'status': 'CLOSED'}]

        result = executions.get_ingenium_executions(MOCK_BASE_URL)

        assert result == [{'execution_id': MOCK_EXECUTION_ID, 'status': 'CLOSED'}]
        mock_paginated.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}",
            query_params={}
        )

    @patch('executions.ingenium_rest_get_paginated')
    def test_get_ingenium_executions_with_query(self, mock_paginated):
        """Test get_ingenium_executions passes query params through."""
        mock_paginated.return_value = []

        result = executions.get_ingenium_executions(MOCK_BASE_URL, query={'status': 'CLOSED'})

        assert result == []
        call_args = mock_paginated.call_args
        assert call_args.kwargs['query_params'] == {'status': 'CLOSED'}


class TestGetIngeniumExecutionElements:
    """Test class for get_ingenium_execution_elements."""

    @patch('executions.ingenium_rest_get')
    def test_get_execution_elements_success(self, mock_get):
        """Test the function queries the info and elements endpoints in order."""
        mock_get.side_effect = [
            {'execution_id': MOCK_EXECUTION_ID, 'status': 'CLOSED'},
            [{'elem_id': 'e1', 'elem_type': 'STEP'}]
        ]

        info, elements = executions.get_ingenium_execution_elements(MOCK_BASE_URL, MOCK_EXECUTION_ID)

        assert info == {'execution_id': MOCK_EXECUTION_ID, 'status': 'CLOSED'}
        assert elements == [{'elem_id': 'e1', 'elem_type': 'STEP'}]
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0][0][0] == f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}"
        assert mock_get.call_args_list[1][0][0] == f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/elements/"
        assert mock_get.call_args_list[1].kwargs['query_params'] == {"limit": 10000}

    @patch('executions.ingenium_rest_get')
    def test_get_execution_elements_error(self, mock_get):
        """Test IngeniumLibError propagates from a failed query."""
        mock_get.side_effect = common.IngeniumLibError("Response not completed successfully")

        with pytest.raises(common.IngeniumLibError):
            executions.get_ingenium_execution_elements(MOCK_BASE_URL, MOCK_EXECUTION_ID)


class TestExportExecution:
    """Test class for export_execution."""

    @patch('requests.get')
    def test_export_execution_success(self, mock_get, tmp_path):
        """Test successful export writes streamed content to file."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'chunk1', b'chunk2']
        mock_get.return_value = mock_response

        out_file = tmp_path / "exec.tar.gz"
        executions.export_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID, str(out_file))

        assert out_file.read_bytes() == b'chunk1chunk2'
        mock_get.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/export",
            headers={'Authorization': 'test_token'},
            verify=True,
            stream=True
        )

    @patch('requests.get')
    def test_export_execution_connection_error(self, mock_get, tmp_path):
        """Test export raises IngeniumLibError on connection error."""
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        with pytest.raises(common.IngeniumLibError) as exc_info:
            executions.export_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID,
                                        str(tmp_path / "out.tar.gz"))

        assert "Failed to communicate" in str(exc_info.value)

    @patch('requests.get')
    def test_export_execution_http_error(self, mock_get, tmp_path):
        """Test export raises IngeniumLibError on failed response."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.url = f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/export"
        mock_response.request.method = "GET"
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        with pytest.raises(common.IngeniumLibError) as exc_info:
            executions.export_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID,
                                        str(tmp_path / "out.tar.gz"))

        assert "Response not completed successfully" in str(exc_info.value)


class TestImportExecution:
    """Test class for import_execution."""

    @patch('requests.post')
    def test_import_execution_success(self, mock_post, tmp_path):
        """Test successful import posts the file and returns JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'execution_info': {'execution_id': MOCK_EXECUTION_ID}
        }
        mock_post.return_value = mock_response

        in_file = tmp_path / "exec.tar.gz"
        in_file.write_bytes(b'fake-tarball')

        result = executions.import_execution(MOCK_BASE_URL, str(in_file))

        assert result['execution_info']['execution_id'] == MOCK_EXECUTION_ID
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == f"{MOCK_BASE_URL}{common.as_run_endpoint}/import"
        assert 'execution_file' in call_args.kwargs['files']

    @patch('requests.post')
    def test_import_execution_logs_messages(self, mock_post, tmp_path, caplog):
        """Test import logs warning messages from the response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'messages': ['warning one']}
        mock_post.return_value = mock_response

        in_file = tmp_path / "exec.tar.gz"
        in_file.write_bytes(b'fake-tarball')

        import logging
        with caplog.at_level(logging.WARNING):
            executions.import_execution(MOCK_BASE_URL, str(in_file))

        assert 'warning one' in caplog.text

    def test_import_execution_missing_file(self):
        """Test import raises IngeniumLibError when the file does not exist."""
        with pytest.raises(common.IngeniumLibError) as exc_info:
            executions.import_execution(MOCK_BASE_URL, '/nonexistent/file.tar.gz')

        assert "Failed to open file" in str(exc_info.value)

    @patch('requests.post')
    def test_import_execution_http_error(self, mock_post, tmp_path):
        """Test import raises IngeniumLibError on failed response."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.url = f"{MOCK_BASE_URL}{common.as_run_endpoint}/import"
        mock_response.request.method = "POST"
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        in_file = tmp_path / "exec.tar.gz"
        in_file.write_bytes(b'fake-tarball')

        with pytest.raises(common.IngeniumLibError) as exc_info:
            executions.import_execution(MOCK_BASE_URL, str(in_file))

        assert "Response not completed successfully" in str(exc_info.value)
