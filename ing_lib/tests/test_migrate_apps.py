"""
Tests for MigrateProcedures.py and MigrateExecutions.py apps
"""

import pytest
from unittest.mock import patch, MagicMock

# Import the modules under test
import ing_lib.common as common
from apps.MigrateProcedures import get_input as proc_get_input
from apps.MigrateProcedures import read_migrate_input, query_proc_ver, compare_procedures, update_input_for_released
from apps.MigrateExecutions import get_input as exec_get_input
from apps.MigrateExecutions import compare_executions


class MockProcInputs:
    """Mock argparse inputs for MigrateProcedures."""
    def __init__(self, force=False, ignore_warnings=False):
        self.force = force
        self.ignore_warnings = ignore_warnings


class MockExecInputs:
    """Mock argparse inputs for MigrateExecutions."""
    def __init__(self, execution_ids='ALL', force=False,
                 source_server='https://source.example.com'):
        self.execution_ids = execution_ids
        self.force = force
        self.source_server = source_server


class TestMigrateProceduresInput:
    """Test get_input for MigrateProcedures."""

    def test_get_input_required_args(self):
        args = [
            'https://source.example.com',
            'https://dest.example.com',
            '/path/to/migrate.txt'
        ]
        inputs = proc_get_input(args)

        assert inputs.source_server == 'https://source.example.com'
        assert inputs.destination_server == 'https://dest.example.com'
        assert inputs.procedures_to_migrate == '/path/to/migrate.txt'
        assert inputs.force is False
        assert inputs.ignore_warnings is False
        assert inputs.temp_dir == '/tmp'

    def test_get_input_optional_args(self):
        args = [
            'https://source.example.com',
            'https://dest.example.com',
            '/path/to/migrate.txt',
            '--force', '--ignore_warnings', '--debug',
            '--username', 'test_user', '--ignore_ssl_error',
            '--temp_dir', '/var/tmp', '--rsa'
        ]
        inputs = proc_get_input(args)

        assert inputs.force is True
        assert inputs.ignore_warnings is True
        assert inputs.debug is True
        assert inputs.username == 'test_user'
        assert inputs.ignore_ssl_error is True
        assert inputs.temp_dir == '/var/tmp'
        assert inputs.rsa is True


class TestMigrateExecutionsInput:
    """Test get_input for MigrateExecutions."""

    def test_get_input_required_args(self):
        args = [
            'https://source.example.com',
            'https://dest.example.com',
            'exec-1,exec-2'
        ]
        inputs = exec_get_input(args)

        assert inputs.source_server == 'https://source.example.com'
        assert inputs.destination_server == 'https://dest.example.com'
        assert inputs.execution_ids == 'exec-1,exec-2'
        assert inputs.force is False
        assert inputs.temp_dir == '/tmp'

    def test_get_input_all(self):
        args = [
            'https://source.example.com',
            'https://dest.example.com',
            'ALL',
            '--force', '--debug', '--rsa'
        ]
        inputs = exec_get_input(args)

        assert inputs.execution_ids == 'ALL'
        assert inputs.force is True
        assert inputs.debug is True
        assert inputs.rsa is True


class TestReadMigrateInput:
    """Test read_migrate_input file parsing."""

    def test_read_migrate_input(self, tmp_path):
        """Test parsing a migration input file with comments, dupes, and merges."""
        input_file = tmp_path / "migrate.txt"
        input_file.write_text(
            "europa-procedure-10005,RELEASED\n"
            "europa-procedure-10403,1\n"
            "europa-procedure-10399,1,2\n"
            "europa-procedure-10395,5 # a comment\n"
            "europa-procedure-10005,15,15,16\n"
            "europa-procedure-10195,RELEASED\n"
            "europa-procedure-10397,1,2\n"
            "\n"
            "# full line comment\n"
        )

        result = read_migrate_input(str(input_file))

        assert set(result.keys()) == {
            'europa-procedure-10005', 'europa-procedure-10403',
            'europa-procedure-10399', 'europa-procedure-10395',
            'europa-procedure-10195', 'europa-procedure-10397'
        }
        # Repeated procedure merges versions and dedupes
        assert set(result['europa-procedure-10005']) == {'RELEASED', '15', '16'}
        assert result['europa-procedure-10403'] == ['1']
        assert set(result['europa-procedure-10399']) == {'1', '2'}
        assert result['europa-procedure-10395'] == ['5']

    def test_read_migrate_input_missing_file(self):
        """Test a missing input file raises IngeniumLibError."""
        with pytest.raises(common.IngeniumLibError) as exc_info:
            read_migrate_input('/nonexistent/migrate.txt')

        assert "Could not open input file" in str(exc_info.value)


class TestQueryProcVer:
    """Test query_proc_ver."""

    @patch('apps.MigrateProcedures.get_procedure_versions')
    def test_query_proc_ver(self, mock_versions):
        """Test query_proc_ver builds the version info structure."""
        mock_versions.return_value = [
            {'version': 1, 'status': 'RELEASED', 'institutional_release_id': 'R1'},
            {'version': 2, 'status': 'RELEASED', 'institutional_release_id': 'R1'},
            {'version': 3, 'status': 'WORKING', 'institutional_release_id': None}
        ]

        result = query_proc_ver('https://source.example.com',
                                {'test-procedure-1': ['1', '2', '3']})

        assert result['test-procedure-1']['1']['status'] == 'RELEASED'
        assert result['test-procedure-1']['2']['release_id'] == 'R1'
        assert result['test-procedure-1']['3']['status'] == 'WORKING'
        mock_versions.assert_called_once_with('https://source.example.com', 'test-procedure-1')


class TestUpdateInputForReleased:
    """Test update_input_for_released."""

    def test_released_expansion(self):
        """Test RELEASED keyword expands to actual released versions."""
        migrate_input = {'test-procedure-1': ['RELEASED', '3']}
        source_procedures = {
            'test-procedure-1': {
                '1': {'status': 'RELEASED', 'release_id': 'R1'},
                '2': {'status': 'RELEASED', 'release_id': 'R1'},
                '3': {'status': 'WORKING', 'release_id': None}
            }
        }

        update_input_for_released(migrate_input, source_procedures)

        assert set(migrate_input['test-procedure-1']) == {'1', '2', '3'}

    def test_released_missing_procedure(self):
        """Test RELEASED on a missing procedure raises IngeniumLibError."""
        migrate_input = {'test-procedure-missing': ['RELEASED']}

        with pytest.raises(common.IngeniumLibError):
            update_input_for_released(migrate_input, {})

    def test_no_released_keyword(self):
        """Test inputs without RELEASED pass through unchanged."""
        migrate_input = {'test-procedure-1': ['1', '2']}

        update_input_for_released(migrate_input, {})

        assert migrate_input['test-procedure-1'] == ['1', '2']


class TestCompareProcedures:
    """Test compare_procedures."""

    def test_missing_in_source_aborts(self):
        """A procedure in the migrate list but not in source raises."""
        migrate_input = {'test-procedure-1': ['1']}

        with pytest.raises(common.IngeniumLibError) as exc_info:
            compare_procedures({}, {}, migrate_input, MockProcInputs())

        assert "can not be located in the Ingenium Source" in str(exc_info.value)

    def test_missing_version_in_source_aborts(self):
        """A version in the migrate list but not in source raises."""
        migrate_input = {'test-procedure-1': ['9']}
        source = {'test-procedure-1': {'1': {'status': 'RELEASED', 'release_id': 'R1'}}}

        with pytest.raises(common.IngeniumLibError):
            compare_procedures(source, {}, migrate_input, MockProcInputs())

    def test_unreleased_version_warns_and_halts(self):
        """Unreleased version halts when ignore_warnings is False."""
        migrate_input = {'test-procedure-1': ['1']}
        source = {'test-procedure-1': {'1': {'status': 'WORKING', 'release_id': None}}}

        with pytest.raises(common.IngeniumLibError) as exc_info:
            compare_procedures(source, {}, migrate_input, MockProcInputs(ignore_warnings=False))

        assert "Warnings not ignored" in str(exc_info.value)

    def test_unreleased_version_ignored(self):
        """Unreleased version proceeds when ignore_warnings is True."""
        migrate_input = {'test-procedure-1': ['1']}
        source = {'test-procedure-1': {'1': {'status': 'WORKING', 'release_id': None}}}

        result = compare_procedures(source, {}, migrate_input, MockProcInputs(ignore_warnings=True))

        assert result == {'test-procedure-1': ['1']}

    def test_new_procedure_queues_all_versions(self):
        """Procedure not on destination queues all requested versions."""
        migrate_input = {'test-procedure-1': ['1', '2']}
        source = {
            'test-procedure-1': {
                '1': {'status': 'RELEASED', 'release_id': 'R1'},
                '2': {'status': 'RELEASED', 'release_id': 'R1'}
            }
        }

        result = compare_procedures(source, {}, migrate_input, MockProcInputs())

        assert result == {'test-procedure-1': ['1', '2']}

    def test_missing_destination_version_queued(self):
        """Only versions missing on destination are queued."""
        migrate_input = {'test-procedure-1': ['1', '2']}
        source = {
            'test-procedure-1': {
                '1': {'status': 'RELEASED', 'release_id': 'R1'},
                '2': {'status': 'RELEASED', 'release_id': 'R1'}
            }
        }
        destination = {
            'test-procedure-1': {'1': {'status': 'RELEASED', 'release_id': 'R1'}}
        }

        result = compare_procedures(source, destination, migrate_input, MockProcInputs())

        assert result == {'test-procedure-1': ['2']}

    def test_force_requeues_existing_versions(self):
        """Force option queues versions even when present on destination."""
        migrate_input = {'test-procedure-1': ['1']}
        source = {'test-procedure-1': {'1': {'status': 'RELEASED', 'release_id': 'R1'}}}
        destination = {'test-procedure-1': {'1': {'status': 'RELEASED', 'release_id': 'R1'}}}

        result = compare_procedures(source, destination, migrate_input, MockProcInputs(force=True))

        assert result == {'test-procedure-1': ['1']}


class TestCompareExecutions:
    """Test compare_executions."""

    def _exec(self, execution_id, status):
        return {'execution_id': execution_id, 'status': status}

    def test_all_migrates_completed_executions(self):
        """ALL migrates source executions with a migratable status."""
        source = [
            self._exec('exec-1', 'CLOSED'),
            self._exec('exec-2', 'RUNNING'),
            self._exec('exec-3', 'FINALIZED')
        ]

        result = compare_executions(source, [], MockExecInputs(execution_ids='ALL'))

        assert result == ['exec-1', 'exec-3']

    def test_specific_ids(self):
        """Only listed execution ids are migrated."""
        source = [
            self._exec('exec-1', 'CLOSED'),
            self._exec('exec-2', 'CLOSED'),
            self._exec('exec-3', 'CLOSED')
        ]

        result = compare_executions(source, [], MockExecInputs(execution_ids='exec-1,exec-3'))

        assert result == ['exec-1', 'exec-3']

    def test_skip_unsupported_status(self):
        """Executions with non-migratable status are skipped."""
        source = [self._exec('exec-1', 'RUNNING')]

        result = compare_executions(source, [], MockExecInputs(execution_ids='ALL'))

        assert result == []

    def test_skip_completed_on_destination(self):
        """Executions already completed on destination are not re-migrated."""
        source = [self._exec('exec-1', 'CLOSED')]
        destination = [self._exec('exec-1', 'FINALIZED')]

        result = compare_executions(source, destination, MockExecInputs(execution_ids='ALL'))

        assert result == []

    def test_migrate_when_destination_incomplete(self):
        """Executions in a non-final state on destination are migrated."""
        source = [self._exec('exec-1', 'CLOSED')]
        destination = [self._exec('exec-1', 'RUNNING')]

        result = compare_executions(source, destination, MockExecInputs(execution_ids='ALL'))

        assert result == ['exec-1']

    def test_force_remigrates_completed(self):
        """Force re-migrates executions already completed on destination."""
        source = [self._exec('exec-1', 'CLOSED')]
        destination = [self._exec('exec-1', 'FINALIZED')]

        result = compare_executions(source, destination,
                                    MockExecInputs(execution_ids='ALL', force=True))

        assert result == ['exec-1']

    def test_results_sorted(self):
        """Returned execution ids are sorted."""
        source = [
            self._exec('exec-9', 'CLOSED'),
            self._exec('exec-1', 'CLOSED'),
            self._exec('exec-5', 'CLOSED')
        ]

        result = compare_executions(source, [], MockExecInputs(execution_ids='ALL'))

        assert result == ['exec-1', 'exec-5', 'exec-9']
