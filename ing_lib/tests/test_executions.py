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


MOCK_PROCEDURE_SECTION = {
    'execution_id': 'test-ingenium-10001',
    'imported': True,
    'child_execution_id': '',
    'number': '2-1',
    'title': 'Call Procedure',
    'execution_user_input': {
        'callable': True,
        'reference_procedure_id': 'proc-1',
        'reference_procedure_title': 'Test Proc',
        'reference_procedure_version': '1',
        'reference_procedure_institutional_id': 'INST-1',
        'reference_procedure_institutional_release_id': 'RevA',
        'run_for_score': True,
        'tag_selections': [{'name': 'tag1', 'selected': True},
                           {'name': 'tag2', 'selected': False}]
    }
}


class TestGetIngeniumExecutionInfo:
    """Test class for get_ingenium_execution_info."""

    @patch('executions.ingenium_rest_get')
    def test_get_execution_info_success(self, mock_get):
        mock_get.return_value = {'execution_id': MOCK_EXECUTION_ID, 'status': 'CLOSED'}

        result = executions.get_ingenium_execution_info(MOCK_BASE_URL, MOCK_EXECUTION_ID)

        assert result['execution_id'] == MOCK_EXECUTION_ID
        mock_get.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}")


class TestGetIngeniumExecution:
    """Test class for get_ingenium_execution (info + history)."""

    @patch('executions.ingenium_rest_get')
    def test_get_execution_success(self, mock_get):
        mock_get.side_effect = [
            {'execution_id': MOCK_EXECUTION_ID, 'status': 'CLOSED'},
            [{'elem_id': 'e1'}]
        ]

        info, history = executions.get_ingenium_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID)

        assert info['execution_id'] == MOCK_EXECUTION_ID
        assert history == [{'elem_id': 'e1'}]
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[1][0][0] == \
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/history"
        assert mock_get.call_args_list[1].kwargs['query_params'] == {"limit": 10000}


class TestGetIngeniumProcedureSections:
    """Test class for get_ingenium_procedure_sections."""

    @patch('executions.ingenium_rest_get')
    def test_get_procedure_sections_success(self, mock_get):
        mock_get.return_value = [MOCK_PROCEDURE_SECTION]

        result = executions.get_ingenium_procedure_sections(MOCK_BASE_URL, MOCK_EXECUTION_ID)

        assert result == [MOCK_PROCEDURE_SECTION]
        mock_get.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/procedure_sections",
            query_params={"limit": 10000})


class TestRefreshIngeniumExecution:
    """Test class for refresh_ingenium_execution."""

    @patch('requests.post')
    def test_refresh_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'elem_id': 'e1'}]
        mock_post.return_value = mock_response

        result = executions.refresh_ingenium_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID)

        assert result == [{'elem_id': 'e1'}]
        mock_post.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/refresh",
            headers={'Authorization': 'test_token'}, json={}, verify=True)

    @patch('requests.post')
    def test_refresh_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.url = 'x'
        mock_response.request.method = 'POST'
        mock_response.text = 'err'
        mock_post.return_value = mock_response

        with pytest.raises(common.IngeniumLibError):
            executions.refresh_ingenium_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID)


class TestParseProcedureSection:
    """Test class for parse_procedure_section."""

    def test_parse(self):
        result = executions.parse_procedure_section(MOCK_PROCEDURE_SECTION)

        assert result['procedure_id'] == 'proc-1'
        assert result['procedure_title'] == 'Test Proc'
        assert result['institutional_id'] == 'INST-1'
        assert result['institutional_release_id'] == 'RevA'
        assert result['run_for_score'] is True
        assert result['tags'] == ['tag1']
        assert result['step_number'] == '2-1'
        assert result['callable'] is True


class TestGetProcedureSectionInfos:
    """Test class for get_procedure_section_infos recursion."""

    @patch('executions.get_ingenium_procedure_sections')
    def test_collects_sections_no_children(self, mock_sections):
        mock_sections.return_value = [MOCK_PROCEDURE_SECTION]
        infos = []
        executions.get_procedure_section_infos(MOCK_BASE_URL, MOCK_EXECUTION_ID, infos, False)

        assert len(infos) == 1
        assert infos[0]['procedure_id'] == 'proc-1'
        mock_sections.assert_called_once()

    @patch('executions.get_ingenium_procedure_sections')
    def test_recurses_into_children(self, mock_sections):
        parent = dict(MOCK_PROCEDURE_SECTION)
        parent['child_execution_id'] = 'child-exec-1'

        def sections_side_effect(server, exec_id):
            if exec_id == MOCK_EXECUTION_ID:
                return [parent]
            return []

        mock_sections.side_effect = sections_side_effect
        infos = []
        executions.get_procedure_section_infos(MOCK_BASE_URL, MOCK_EXECUTION_ID, infos, False)

        assert mock_sections.call_count == 2
        assert mock_sections.call_args_list[1][0][1] == 'child-exec-1'

    @patch('executions.get_ingenium_procedure_sections')
    def test_exclude_children(self, mock_sections):
        parent = dict(MOCK_PROCEDURE_SECTION)
        parent['child_execution_id'] = 'child-exec-1'
        mock_sections.return_value = [parent]
        infos = []
        executions.get_procedure_section_infos(MOCK_BASE_URL, MOCK_EXECUTION_ID, infos, True)

        mock_sections.assert_called_once()


class TestHaltExecution:
    """Test class for halt_execution."""

    @patch('requests.post')
    def test_halt_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'HALTED'}
        mock_post.return_value = mock_response

        result = executions.halt_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID)

        assert result['status'] == 'HALTED'
        mock_post.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/halt",
            headers={'Authorization': 'test_token'}, verify=True, json={})

    @patch('requests.post')
    def test_halt_connection_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("fail")
        with pytest.raises(common.IngeniumLibError) as exc_info:
            executions.halt_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID)
        assert "Failed to communicate" in str(exc_info.value)


class TestUpdateIngeniumExecution:
    """Test class for update_ingenium_execution."""

    @patch('requests.patch')
    def test_update_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'updated': True}
        mock_patch.return_value = mock_response

        result = executions.update_ingenium_execution(MOCK_BASE_URL, MOCK_EXECUTION_ID,
                                                    {'description': 'new'})

        assert result['updated'] is True
        mock_patch.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}",
            headers={'Authorization': 'test_token'}, verify=True, json={'description': 'new'})


class TestSetExecutionMode:
    """Test class for set_execution_mode."""

    @patch('requests.patch')
    def test_set_mode_success(self, mock_patch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'mode': 'MANUAL'}
        mock_patch.return_value = mock_response

        result = executions.set_execution_mode(MOCK_BASE_URL, MOCK_EXECUTION_ID, 'MANUAL')

        assert result['mode'] == 'MANUAL'
        call_args = mock_patch.call_args
        assert call_args.kwargs['json'] == {'mode': 'MANUAL'}


class TestUpdateExecutionStatus:
    """Test class for update_execution_status."""

    @patch('executions.get_ingenium_execution_info')
    @patch('requests.post')
    def test_suspend_success(self, mock_post, mock_info):
        mock_info.return_value = {'status': 'IDLE'}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'SUSPENDED'}
        mock_post.return_value = mock_response

        result = executions.update_execution_status(MOCK_BASE_URL, MOCK_EXECUTION_ID, 'SUSPENDED')

        assert result['status'] == 'SUSPENDED'
        mock_post.assert_called_once_with(
            f"{MOCK_BASE_URL}{common.as_run_endpoint}/{MOCK_EXECUTION_ID}/status",
            headers={'Authorization': 'test_token'}, verify=True,
            json={'status': 'SUSPENDED', 'comment': 'SUSPENDED via external script'})

    @patch('executions.get_ingenium_execution_info')
    def test_invalid_dest_status(self, mock_info):
        mock_info.return_value = {'status': 'IDLE'}
        with pytest.raises(common.IngeniumLibError) as exc_info:
            executions.update_execution_status(MOCK_BASE_URL, MOCK_EXECUTION_ID, 'RUNNING')
        assert 'Limited to' in str(exc_info.value)

    @patch('executions.get_ingenium_execution_info')
    def test_cannot_suspend_closed(self, mock_info):
        mock_info.return_value = {'status': 'CLOSED'}
        with pytest.raises(common.IngeniumLibError) as exc_info:
            executions.update_execution_status(MOCK_BASE_URL, MOCK_EXECUTION_ID, 'SUSPENDED')
        assert 'closed' in str(exc_info.value)

    @patch('executions.get_ingenium_execution_info')
    @patch('requests.post')
    def test_close_before_in_review(self, mock_post, mock_info):
        """IN_REVIEW from IDLE closes the execution first."""
        mock_info.side_effect = [
            {'status': 'IDLE'},    # current status for outer call
            {'status': 'IDLE'},    # current status for recursive CLOSED call
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'DONE'}
        mock_post.return_value = mock_response

        result = executions.update_execution_status(MOCK_BASE_URL, MOCK_EXECUTION_ID, 'IN_REVIEW')

        # Two POSTs: one for CLOSED, one for IN_REVIEW
        assert mock_post.call_count == 2
        assert mock_post.call_args_list[0].kwargs['json']['status'] == 'CLOSED'
        assert mock_post.call_args_list[1].kwargs['json']['status'] == 'IN_REVIEW'
