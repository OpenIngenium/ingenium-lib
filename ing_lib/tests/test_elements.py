"""
Tests for elements.py module (Ingenium element parsing to print_format text)
"""

import pytest

# Import the modules under test
import elements


def make_element(elem_type='STEP', step_type='WAIT', authoring=None, execution_input=None,
                 results=None, status='PASS', **kwargs):
    """Build a minimal Ingenium element dict for tests."""
    element = {
        'title': 'Test Step',
        'number': '1-1',
        'description': 'A test step',
        'procedure_title': '',
        'procedure_id': '',
        'execution_id': 'test-exec-1',
        'conversations': [],
        'tag_ids': [],
        'run_for_score': False,
        'elem_id': 'elem-1',
        'procedure_modification': {},
        'procedure_modification_status': 'NONE',
        'elem_type': elem_type,
        'authoring_user_input': authoring or {},
        'execution_user_input': execution_input or {},
        'execution': {
            'meta_data': {'status': status,
                          'time_started': '2025-01-01T00:00:00.000Z',
                          'time_completed': '2025-01-01T00:00:01.000Z'},
            'results': results or {}
        }
    }
    if elem_type == 'STEP':
        element['step_type'] = step_type
    element.update(kwargs)
    return element


class TestVerificationCondition:
    """Test class for VerificationCondition."""

    def test_equal(self):
        vc = elements.VerificationCondition('X', 'EQUAL', ['5'])
        assert vc.printformat == 'X = 5'

    def test_not_equal(self):
        vc = elements.VerificationCondition('X', 'NOT_EQUAL', ['5'])
        assert vc.printformat == 'X != 5'

    def test_record(self):
        vc = elements.VerificationCondition('X', 'RECORD', [])
        assert vc.printformat == 'Record: X'

    def test_greater_than(self):
        vc = elements.VerificationCondition('X', 'GREATER_THAN', ['5'])
        assert vc.printformat == 'X > 5'

    def test_less_than(self):
        vc = elements.VerificationCondition('X', 'LESS_THAN', ['5'])
        assert vc.printformat == 'X < 5'

    def test_greater_than_or_equal(self):
        vc = elements.VerificationCondition('X', 'GREATER_THAN_OR_EQUAL', ['5'])
        assert vc.printformat == 'X >= 5'

    def test_less_than_or_equal(self):
        vc = elements.VerificationCondition('X', 'LESS_THAN_OR_EQUAL', ['5'])
        assert vc.printformat == 'X <= 5'

    def test_not_present(self):
        vc = elements.VerificationCondition('X', 'NOT_PRESENT', [])
        assert vc.printformat == 'X Not Present'

    def test_contains(self):
        vc = elements.VerificationCondition('X', 'CONTAINS', ['abc'])
        assert vc.printformat == 'X Contains abc'

    def test_inclusive_range(self):
        vc = elements.VerificationCondition('X', 'INCLUSIVE_RANGE', ['1', '10'])
        assert vc.printformat == '1 <= X <= 10'

    def test_exclusive_range(self):
        vc = elements.VerificationCondition('X', 'EXCLUSIVE_RANGE', ['1', '10'])
        assert vc.printformat == '1 < X < 10'

    def test_missing_values(self):
        vc = elements.VerificationCondition('X', 'EQUAL', [])
        assert vc.printformat == 'Missing predicts'


class TestStepParsers:
    """Test class for individual step parsers (as-run state)."""

    def test_wait_step_duration_asrun(self):
        data = make_element(step_type='WAIT',
                            results={'wait_type': 'DURATION', 'time_value': '10'})
        step = elements.IngeniumStepParser(data, 'as-run')
        assert isinstance(step, elements.WaitStep)
        assert step.print_format == 'Waiting for 10 seconds'

    def test_wait_step_until_procedure(self):
        data = make_element(step_type='WAIT',
                            authoring={'wait_type': 'UNTIL', 'time_value': '2025-001T00:00:00'})
        step = elements.IngeniumStepParser(data, 'procedure')
        assert step.print_format == 'Waiting until: 2025-001T00:00:00'

    def test_cmd_step_asrun(self):
        data = make_element(step_type='CMD',
                            results={'data_path': 'FSW',
                                     'entries': [{'cmd_string': 'CMD_NO_OP',
                                                  'hw_fsw': 'FSW',
                                                  'timeout': 10,
                                                  'verify': True,
                                                  'radiated': True,
                                                  'radiated_time': '2025-001T00:00:00'}]})
        step = elements.IngeniumStepParser(data, 'as-run')
        assert isinstance(step, elements.CMDStep)
        assert 'Sending commands via: FSW' in step.print_format
        assert 'CMD_NO_OP' in step.print_format
        assert 'DEFAULT' in step.print_format

    def test_verify_eha_step_asrun(self):
        data = make_element(step_type='VERIFY_EHA',
                            execution_input={'start_time': '', 'lookback': 0, 'timeout': 60},
                            results={'entries': [{'channel_id': 'A-0001',
                                                  'data_path': 'FSW',
                                                  'verify_on': 'RAW',
                                                  'dn_eu': 'DN',
                                                  'verification_condition': 'GREATER_THAN',
                                                  'verification_values': ['5'],
                                                  'actual_value': '10',
                                                  'verification_status': 'PASS'}]})
        step = elements.IngeniumStepParser(data, 'as-run')
        assert isinstance(step, elements.VerifyEhaStep)
        assert 'A-0001' in step.print_format
        assert 'Actual: 10 - PASS' in step.print_format

    def test_procedure_step_asrun(self):
        data = make_element(elem_type='PROCEDURE_SECTION',
                            execution_input={'reference_procedure_title': 'Ref Proc',
                                             'reference_procedure_id': 'proc-1',
                                             'reference_procedure_version': '2',
                                             'run_for_score': True,
                                             'tag_selections': [],
                                             'elements': []})
        data.pop('step_type', None)
        step = elements.IngeniumStepParser(data, 'as-run')
        assert isinstance(step, elements.ProcedureStep)
        assert 'Reference Procedure: Ref Proc (proc-1) Version: 2 R4S: True' == step.print_format

    def test_unknown_step_returns_base(self):
        data = make_element(step_type='MADE_UP_TYPE')
        step = elements.IngeniumStepParser(data, 'as-run')
        # An unmapped step_type returns the base IngeniumElement
        assert type(step) is elements.IngeniumElement


class TestCustomScriptStep:
    """Test class for CustomScriptStep and the output_summary override."""

    def _make_cs(self, results):
        return make_element(step_type='CUSTOM_SCRIPT', results=results)

    def test_output_summary_overrides(self):
        """When the script populates output_summary it should be used as print_format."""
        data = self._make_cs({'script_name': 'my_script',
                              'timeout': 60,
                              'custom_script_status': 'PASS',
                              'script_path': 'scripts/my_script.py',
                              'output_summary': 'Queried 10 channels\nAll PASS'})
        step = elements.IngeniumStepParser(data, 'as-run')
        assert isinstance(step, elements.CustomScriptStep)
        assert step.print_format == 'Queried 10 channels\nAll PASS'

    def test_fallback_without_output_summary(self):
        """Legacy executions without output_summary fall back to the generated format."""
        data = self._make_cs({'script_name': 'my_script',
                              'timeout': 60,
                              'custom_script_status': 'PASS',
                              'script_path': 'scripts/my_script.py'})
        step = elements.IngeniumStepParser(data, 'as-run')
        assert 'Ran Custom Script: my_script (timeout: 60) Status: PASS' in step.print_format
        assert 'Script Path: scripts/my_script.py' in step.print_format

    def test_fallback_with_empty_output_summary(self):
        """An empty output_summary should also fall back to the generated format."""
        data = self._make_cs({'script_name': 'my_script',
                              'timeout': 60,
                              'custom_script_status': 'FAIL',
                              'script_path': 'scripts/my_script.py',
                              'output_summary': ''})
        step = elements.IngeniumStepParser(data, 'as-run')
        assert 'Ran Custom Script: my_script (timeout: 60) Status: FAIL' in step.print_format

    def test_procedure_state(self):
        data = make_element(step_type='CUSTOM_SCRIPT',
                            authoring={'script_name': 'my_script',
                                       'timeout': 60,
                                       'script_path': 'scripts/my_script.py'})
        step = elements.IngeniumStepParser(data, 'procedure')
        assert 'Running Custom Script: my_script (timeout: 60)' in step.print_format


class TestParseIngeniumSteps:
    """Test class for parse_ingenium_steps."""

    def test_parse_multiple(self):
        data = [
            make_element(step_type='WAIT',
                         results={'wait_type': 'DURATION', 'time_value': '5'}),
            make_element(step_type='WAIT',
                         results={'wait_type': 'DURATION', 'time_value': '15'})
        ]
        steps = elements.parse_ingenium_steps(data, 'as-run')
        assert len(steps) == 2
        assert steps[0].print_format == 'Waiting for 5 seconds'
        assert steps[1].print_format == 'Waiting for 15 seconds'

    def test_parse_empty(self):
        assert elements.parse_ingenium_steps([], 'as-run') == []
