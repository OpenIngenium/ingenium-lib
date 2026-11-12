"""
Tests for ExecutionReport.py app
"""

import pytest
import datetime
import csv
from unittest.mock import patch, MagicMock
from openpyxl import load_workbook

# Import the module under test
import ing_lib.common as common
from apps.ExecutionReport import get_input, query_ingenium_execution, ingest_external_data_sources, output_report


MOCK_BASE_URL = "https://mock-ingenium.example.com"


class MockInputs:
    """Mock argparse inputs for ExecutionReport."""
    def __init__(self, output_file='/tmp/report.xlsx', execution_ids='test-ingenium-10001',
                 ingenium_server=MOCK_BASE_URL, begin_time=None, end_time=None,
                 exclude_child_executions=False, external_data_files=None, debug=False):
        self.output_file = output_file
        self.execution_ids = execution_ids
        self.ingenium_server = ingenium_server
        self.begin_time = begin_time
        self.end_time = end_time
        self.exclude_child_executions = exclude_child_executions
        self.external_data_files = external_data_files
        self.debug = debug


def make_execution_info(execution_id='test-ingenium-10001'):
    return {
        'execution_id': execution_id,
        'description': 'Test execution',
        'time_started': '2025-01-01T10:00:00.000Z',
        'time_completed': '2025-01-01T12:00:00.000Z',
        'transitions': [],
        'venue_name': 'TESTBED',
        'test_conductors': ['testuser'],
        'version': '1.0.0',
        'flight_dictionary_version': 'flight-v1',
        'sse_dictionary_version': 'sse-v2',
        'num_steps_executed': 2,
        'num_steps_passed': 1,
        'num_steps_failed': 1,
        'num_steps_errored': 0,
    }


def make_step_mock(status='PASS', procedure_id='', step_type='WAIT',
                   time_started='2025-01-01T10:00:00.000Z',
                   time_completed='2025-01-01T10:01:00.000Z'):
    step = MagicMock()
    step.elem_type = 'STEP'
    step.step_type = step_type
    step.procedure_id = procedure_id
    step.procedure_title = ''
    step.execution_id = 'test-ingenium-10001'
    step.number = '1-1'
    step.title = 'Test Step'
    step.print_format = 'step details'
    step.meta_data = {'status': status,
                      'time_started': time_started,
                      'time_completed': time_completed}
    step.procedure_modification_status = 'NONE'
    step.procedure_modification = {}
    return step


def make_report_entry(ingenium=True, start_end='START', status='PASS', source='test-ingenium-10001'):
    return {'ert': datetime.datetime(2025, 1, 1, 10, 0, 0),
            'scet': '',
            'sclk': '',
            'source': source,
            'type': 'WAIT',
            'id': '1-1 Test Step',
            'data': 'step details',
            'sequence_id': status,
            'start_end': start_end,
            'ingenium': ingenium,
            'override_note': None,
            'modification_note': None}


class TestExecutionReportInput:
    """Test get_input for ExecutionReport."""

    def test_get_input_parses_required_args(self):
        inputs = get_input([MOCK_BASE_URL, 'exec-1,exec-2', '/tmp/out.xlsx'])
        assert inputs.ingenium_server == MOCK_BASE_URL
        assert inputs.execution_ids == 'exec-1,exec-2'
        assert inputs.output_file == '/tmp/out.xlsx'
        assert inputs.exclude_child_executions is False

    def test_get_input_optional_flags(self):
        inputs = get_input([MOCK_BASE_URL, 'exec-1', '/tmp/out.xlsx',
                            '--exclude_child_executions',
                            '--begin_time', '2025-001T10:00:00',
                            '--end_time', '2025-001T12:00:00'])
        assert inputs.exclude_child_executions is True
        assert inputs.begin_time == '2025-001T10:00:00'
        assert inputs.end_time == '2025-001T12:00:00'

    def test_get_input_bad_begin_time(self):
        with pytest.raises(common.IngeniumLibError):
            get_input([MOCK_BASE_URL, 'exec-1', '/tmp/out.xlsx',
                       '--begin_time', '2025-01-01'])

    def test_get_input_bad_end_time(self):
        with pytest.raises(common.IngeniumLibError):
            get_input([MOCK_BASE_URL, 'exec-1', '/tmp/out.xlsx',
                       '--end_time', 'Jan 1 2025'])


class TestQueryIngeniumExecution:
    """Test query_ingenium_execution with mocked library calls."""

    @patch('apps.ExecutionReport.get_ingenium_execution')
    @patch('apps.ExecutionReport.get_procedure_section_infos')
    @patch('apps.ExecutionReport.parse_ingenium_steps')
    def test_report_entries_created(self, mock_parse, mock_sections, mock_get_exec):
        """Executed steps produce START/END report entries."""
        inputs = MockInputs()

        def collect_sections(server, exec_id, infos, exclude_children):
            infos.append({'execution_id': exec_id, 'child_execution_id': '',
                          'imported': True, 'callable': False,
                          'procedure_id': 'p', 'procedure_title': 't', 'procedure_version': '1',
                          'institutional_id': 'i', 'institutional_release_id': 'r',
                          'run_for_score': False, 'step_number': '1', 'step_title': 's', 'tags': []})
        mock_sections.side_effect = collect_sections
        mock_get_exec.return_value = (make_execution_info(), [{'fake': 'element'}])
        mock_parse.return_value = [make_step_mock(status='PASS')]

        infos, entries, procs = query_ingenium_execution(inputs)

        assert len(infos) == 1
        assert len(entries) == 2
        assert entries[0]['start_end'] == 'START'
        assert entries[1]['start_end'] == 'END'
        assert entries[0]['ingenium'] is True
        assert entries[0]['sequence_id'] == 'PASS'

    @patch('apps.ExecutionReport.get_ingenium_execution')
    @patch('apps.ExecutionReport.get_procedure_section_infos')
    @patch('apps.ExecutionReport.parse_ingenium_steps')
    def test_time_filter_excludes_steps(self, mock_parse, mock_sections, mock_get_exec):
        """Steps outside the time range are excluded."""
        inputs = MockInputs(begin_time='2025-001T11:00:00', end_time='2025-001T12:00:00')
        mock_sections.side_effect = lambda *a, **k: None
        mock_get_exec.return_value = (make_execution_info(), [])
        mock_parse.return_value = [make_step_mock(time_completed='2025-01-01T10:01:00.000Z')]

        infos, entries, procs = query_ingenium_execution(inputs)
        assert entries == []

    @patch('apps.ExecutionReport.get_ingenium_execution')
    @patch('apps.ExecutionReport.get_procedure_section_infos')
    @patch('apps.ExecutionReport.parse_ingenium_steps')
    def test_override_and_modification_notes(self, mock_parse, mock_sections, mock_get_exec):
        """Override and redline notes are captured in START entries."""
        inputs = MockInputs()
        mock_sections.side_effect = lambda *a, **k: None
        mock_get_exec.return_value = (make_execution_info(), [])

        step = make_step_mock(status='OVERRIDE_PASS')
        step.meta_data['overridden_by'] = 'testuser'
        step.meta_data['override_justification'] = 'ok'
        step.procedure_modification_status = 'ADDED'
        step.procedure_modification = {'justification': {'modification_type': 'REDLINE',
                                                          'user_name': 'req',
                                                          'content': 'why'},
                                        'approval': {'user_name': 'app',
                                                     'content': 'approved'}}
        mock_parse.return_value = [step]

        infos, entries, procs = query_ingenium_execution(inputs)

        assert entries[0]['override_note'] is not None
        assert 'testuser' in entries[0]['override_note']
        assert entries[0]['modification_note'] is not None
        assert 'REDLINE' in entries[0]['modification_note']

    @patch('apps.ExecutionReport.get_ingenium_execution')
    @patch('apps.ExecutionReport.get_procedure_section_infos')
    @patch('apps.ExecutionReport.parse_ingenium_steps')
    def test_unexecuted_steps_skipped(self, mock_parse, mock_sections, mock_get_exec):
        """Steps without executed status are skipped."""
        inputs = MockInputs()
        mock_sections.side_effect = lambda *a, **k: None
        mock_get_exec.return_value = (make_execution_info(), [])
        mock_parse.return_value = [make_step_mock(status='NONE')]

        infos, entries, procs = query_ingenium_execution(inputs)
        assert entries == []


class TestIngestExternalData:
    """Test ingest_external_data_sources."""

    def test_ingest_csv(self, tmp_path):
        csv_file = tmp_path / "external.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['2025-001T10:00:00.000', '2025-001T09:59:00.000', '123.45',
                             'MYSRC', 'EVR', 'EVR-1', 'some data', 'seq1'])

        inputs = MockInputs(external_data_files=[str(csv_file)])
        entries = ingest_external_data_sources(inputs)

        assert len(entries) == 1
        assert entries[0]['source'] == 'External Data: MYSRC'
        assert entries[0]['ingenium'] is False
        assert entries[0]['scet'] == '2025-001T09:59:00.000'

    def test_no_files(self):
        inputs = MockInputs(external_data_files=None)
        assert ingest_external_data_sources(inputs) == []

    def test_bad_rows_skipped(self, tmp_path):
        csv_file = tmp_path / "external.csv"
        csv_file.write_text('too,short\n')
        inputs = MockInputs(external_data_files=[str(csv_file)])
        assert ingest_external_data_sources(inputs) == []


class TestOutputReport:
    """Test output_report XLSX generation."""

    def test_workbook_contents(self, tmp_path):
        out_file = str(tmp_path / "report.xlsx")
        inputs = MockInputs(output_file=out_file)

        report = [make_report_entry(start_end='START', status='PASS'),
                  make_report_entry(start_end='END', status='PASS')]
        procedures = [{'execution_id': 'test-ingenium-10001',
                       'imported': True, 'callable': False,
                       'procedure_id': 'proc-1', 'procedure_title': 'Test Proc',
                       'procedure_version': '1', 'institutional_id': 'INST-1',
                       'institutional_release_id': 'RevA', 'run_for_score': True,
                       'step_number': '2-1', 'tags': ['tag1']}]

        output_report(report, [make_execution_info()], inputs, procedures)

        wb = load_workbook(out_file)
        assert 'Summary' in wb.sheetnames
        assert 'Execution_Report_1' in wb.sheetnames

        # Summary checks
        summary = wb['Summary']
        assert summary.cell(row=1, column=1).value == 'Ingenium Executions'
        assert summary.cell(row=1, column=2).value == 'test-ingenium-10001'
        assert summary.cell(row=5, column=2).value == '02:00:00'

        # Report sheet checks
        ws = wb['Execution_Report_1']
        assert ws.cell(row=1, column=1).value == 'ERT'
        assert ws.cell(row=1, column=11).value == 'DISPOSITION NOTES'
        assert ws.freeze_panes == 'A2'
        assert ws.auto_filter.ref == 'A1:K3'
        # Header comment exists
        assert ws.cell(row=1, column=1).comment is not None
        # Data rows
        assert ws.cell(row=2, column=6).value == 'START:1-1 Test Step'
        assert ws.cell(row=3, column=6).value == 'END:1-1 Test Step'
        assert ws.cell(row=2, column=9).value == 'PASS'
        # Data validation applied to disposition column
        assert len(ws.data_validations.dataValidation) == 1
        wb.close()

    def test_external_data_row(self, tmp_path):
        out_file = str(tmp_path / "report.xlsx")
        inputs = MockInputs(output_file=out_file)

        entry = make_report_entry(ingenium=False, source='External Data: X', start_end='')
        output_report([entry], [make_execution_info()], inputs, [])

        wb = load_workbook(out_file)
        ws = wb['Execution_Report_1']
        assert ws.cell(row=2, column=7).value == '1-1 Test Step'
        # openpyxl drops empty strings on save, so blank cells read back as None
        assert ws.cell(row=2, column=6).value in (None, '')
        wb.close()

    def test_override_comment(self, tmp_path):
        out_file = str(tmp_path / "report.xlsx")
        inputs = MockInputs(output_file=out_file)

        entry = make_report_entry(status='OVERRIDE_PASS')
        entry['override_note'] = 'Overriden by testuser - Justification: ok.'
        entry['modification_note'] = 'REDLINE: note'

        output_report([entry], [make_execution_info()], inputs, [])

        wb = load_workbook(out_file)
        ws = wb['Execution_Report_1']
        assert ws.cell(row=2, column=9).comment is not None
        assert 'testuser' in ws.cell(row=2, column=9).comment.text
        assert ws.cell(row=2, column=6).comment is not None
        wb.close()

    def test_empty_report(self, tmp_path):
        out_file = str(tmp_path / "report.xlsx")
        inputs = MockInputs(output_file=out_file)
        output_report([], [make_execution_info()], inputs, [])
        wb = load_workbook(out_file)
        assert 'Summary' in wb.sheetnames
        wb.close()
