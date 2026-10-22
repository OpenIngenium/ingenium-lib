"""
Tests for procedures.py module
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
import datetime

# Import the modules under test
import ing_lib.common as common
import procedures

# Test constants
MOCK_BASE_URL = "https://mock-ingenium.example.com"
MOCK_PROCEDURE_ID = "test-procedure-10001"


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


class TestGetProcedures:
    """Test class for get_procedures."""

    @patch('procedures.ingenium_rest_get_paginated')
    def test_get_procedures_success(self, mock_paginated):
        """Test successful get_procedures call hits the right endpoint."""
        mock_paginated.return_value = [{'procedure_id': MOCK_PROCEDURE_ID}]

        result = procedures.get_procedures(MOCK_BASE_URL)

        assert result == [{'procedure_id': MOCK_PROCEDURE_ID}]
        mock_paginated.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.procedure_endpoint}",
            query_params={}
        )

    @patch('procedures.ingenium_rest_get_paginated')
    def test_get_procedures_with_query(self, mock_paginated):
        """Test get_procedures passes query params through."""
        mock_paginated.return_value = []

        result = procedures.get_procedures(MOCK_BASE_URL, query={'name': 'test'})

        assert result == []
        call_args = mock_paginated.call_args
        assert call_args.kwargs['query_params'] == {'name': 'test'}


class TestGetProcedureVersions:
    """Test class for get_procedure_versions."""

    @patch('procedures.ingenium_rest_get_paginated')
    def test_get_procedure_versions_success(self, mock_paginated):
        """Test successful get_procedure_versions call hits the right endpoint."""
        mock_paginated.return_value = [{'version': 1, 'status': 'RELEASED'}]

        result = procedures.get_procedure_versions(MOCK_BASE_URL, MOCK_PROCEDURE_ID)

        assert result == [{'version': 1, 'status': 'RELEASED'}]
        mock_paginated.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.procedure_endpoint}/{MOCK_PROCEDURE_ID}/versions",
            query_params={}
        )

    @patch('procedures.ingenium_rest_get_paginated')
    def test_get_procedure_versions_with_query(self, mock_paginated):
        """Test get_procedure_versions passes query params through."""
        mock_paginated.return_value = []

        result = procedures.get_procedure_versions(MOCK_BASE_URL, MOCK_PROCEDURE_ID,
                                                   query={'status': 'RELEASED'})

        assert result == []
        call_args = mock_paginated.call_args
        assert call_args.kwargs['query_params'] == {'status': 'RELEASED'}


class TestGetProceduresAndVersions:
    """Test class for get_procedures_and_versions."""

    @patch('procedures.get_procedure_versions')
    @patch('procedures.get_procedures')
    def test_get_procedures_and_versions(self, mock_procs, mock_versions):
        """Test the combined procedure/version listing."""
        mock_procs.return_value = [
            {'procedure_id': 'test-procedure-1'},
            {'procedure_id': 'test-procedure-2'}
        ]
        mock_versions.side_effect = [
            [{'version': 1}, {'version': 2}],
            [{'version': 5}]
        ]

        result = procedures.get_procedures_and_versions(MOCK_BASE_URL)

        assert len(result) == 3
        assert result[0] == {'procedure': {'procedure_id': 'test-procedure-1'}, 'version': {'version': 1}}
        assert result[2] == {'procedure': {'procedure_id': 'test-procedure-2'}, 'version': {'version': 5}}
        assert mock_versions.call_count == 2

    @patch('procedures.get_procedure_versions')
    @patch('procedures.get_procedures')
    def test_get_procedures_and_versions_empty(self, mock_procs, mock_versions):
        """Test no procedures returns an empty list."""
        mock_procs.return_value = []

        result = procedures.get_procedures_and_versions(MOCK_BASE_URL)

        assert result == []
        mock_versions.assert_not_called()


class TestExportProcedureVersion:
    """Test class for export_procedure_version."""

    @patch('requests.get')
    def test_export_procedure_version_success(self, mock_get, tmp_path):
        """Test successful export writes streamed content to file."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'chunk1', b'chunk2']
        mock_get.return_value = mock_response

        out_file = tmp_path / "proc_v1.tar.gz"
        procedures.export_procedure_version(MOCK_BASE_URL, MOCK_PROCEDURE_ID, '1', str(out_file))

        assert out_file.read_bytes() == b'chunk1chunk2'
        mock_get.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.procedure_endpoint}/{MOCK_PROCEDURE_ID}/export_versions",
            headers={'Authorization': 'test_token'},
            verify=True,
            params={'version': '1'},
            stream=True
        )

    @patch('requests.get')
    def test_export_procedure_version_connection_error(self, mock_get, tmp_path):
        """Test export raises IngeniumLibError on connection error."""
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        with pytest.raises(common.IngeniumLibError) as exc_info:
            procedures.export_procedure_version(MOCK_BASE_URL, MOCK_PROCEDURE_ID, '1',
                                                str(tmp_path / "out.tar.gz"))

        assert "Failed to communicate" in str(exc_info.value)

    @patch('requests.get')
    def test_export_procedure_version_http_error(self, mock_get, tmp_path):
        """Test export raises IngeniumLibError on failed response."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.url = f"{MOCK_BASE_URL}{common.procedure_endpoint}/{MOCK_PROCEDURE_ID}/export_versions"
        mock_response.request.method = "GET"
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        with pytest.raises(common.IngeniumLibError) as exc_info:
            procedures.export_procedure_version(MOCK_BASE_URL, MOCK_PROCEDURE_ID, '1',
                                                str(tmp_path / "out.tar.gz"))

        assert "Response not completed successfully" in str(exc_info.value)


class TestImportProcedureVersions:
    """Test class for import_procedure_versions."""

    @patch('requests.post')
    def test_import_procedure_versions_success(self, mock_post, tmp_path):
        """Test successful import posts the file and returns JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'procedure_info': {'procedure_id': MOCK_PROCEDURE_ID},
            'version_infos': [{'version': 1}]
        }
        mock_post.return_value = mock_response

        in_file = tmp_path / "proc_v1.tar.gz"
        in_file.write_bytes(b'fake-tarball')

        result = procedures.import_procedure_versions(MOCK_BASE_URL, str(in_file))

        assert result['procedure_info']['procedure_id'] == MOCK_PROCEDURE_ID
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == f"{MOCK_BASE_URL}{common.procedure_endpoint}/import"
        assert 'procedure_versions_file' in call_args.kwargs['files']

    @patch('requests.post')
    def test_import_procedure_versions_logs_messages(self, mock_post, tmp_path, caplog):
        """Test import logs warning messages from the response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'messages': ['warning one', 'warning two']}
        mock_post.return_value = mock_response

        in_file = tmp_path / "proc_v1.tar.gz"
        in_file.write_bytes(b'fake-tarball')

        import logging
        with caplog.at_level(logging.WARNING):
            procedures.import_procedure_versions(MOCK_BASE_URL, str(in_file))

        assert 'warning one' in caplog.text
        assert 'warning two' in caplog.text

    def test_import_procedure_versions_missing_file(self):
        """Test import raises IngeniumLibError when the file does not exist."""
        with pytest.raises(common.IngeniumLibError) as exc_info:
            procedures.import_procedure_versions(MOCK_BASE_URL, '/nonexistent/file.tar.gz')

        assert "Failed to open file" in str(exc_info.value)

    @patch('requests.post')
    def test_import_procedure_versions_http_error(self, mock_post, tmp_path):
        """Test import raises IngeniumLibError on failed response."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.url = f"{MOCK_BASE_URL}{common.procedure_endpoint}/import"
        mock_response.request.method = "POST"
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        in_file = tmp_path / "proc_v1.tar.gz"
        in_file.write_bytes(b'fake-tarball')

        with pytest.raises(common.IngeniumLibError) as exc_info:
            procedures.import_procedure_versions(MOCK_BASE_URL, str(in_file))

        assert "Response not completed successfully" in str(exc_info.value)
