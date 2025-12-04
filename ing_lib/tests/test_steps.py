"""
Test suite for ing_lib.steps module.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import json
import os
import sys

# Import the module to test
from .. import steps

class TestApplyBitMask:
    """Test cases for the apply_bit_mask function."""
    
    def test_apply_bit_mask_binary_and(self):
        """Test AND operation with binary mask."""
        result = steps.apply_bit_mask(0b1010, '0b1100', 'AND')
        assert result == 0b1000
        
    def test_apply_bit_mask_binary_or(self):
        """Test OR operation with binary mask."""
        result = steps.apply_bit_mask(0b1010, '0b1100', 'OR')
        assert result == 0b1110
        
    def test_apply_bit_mask_hex(self):
        """Test with hexadecimal mask."""
        result = steps.apply_bit_mask(0x0F, '0x0A', 'AND')
        assert result == 0x0A
        
    def test_apply_bit_mask_decimal(self):
        """Test with decimal mask."""
        result = steps.apply_bit_mask(15, '10', 'AND')
        assert result == 10
        
    def test_apply_bit_mask_invalid_input_value(self):
        """Test with non-integer input value."""
        with pytest.raises(steps.BitMaskError):
            steps.apply_bit_mask('not_an_int', '0b1010', 'AND')
            
    def test_apply_bit_mask_invalid_bit_mask(self):
        """Test with invalid bit mask format."""
        with pytest.raises(steps.BitMaskError):
            steps.apply_bit_mask(10, '0b2', 'AND')
            
    def test_apply_bit_mask_invalid_operation(self):
        """Test with invalid bit operation."""
        with pytest.raises(steps.BitMaskError):
            steps.apply_bit_mask(10, '0b1010', 'XOR')


class TestCheckTelemetryQuery:
    """Test cases for the check_telemetry_query function."""
    
    def test_check_telemetry_query_valid_record(self):
        """Test valid RECORD condition."""
        query = [{
            'verification_condition': 'RECORD',
            'verification_values': [],
            'dn_eu': 'DN',
            'verify_wait': 'WAIT'
        }]
        steps.check_telemetry_query(query)  # Should not raise
        
    def test_check_telemetry_query_invalid_condition(self):
        """Test invalid verification condition."""
        query = [{
            'verification_condition': 'INVALID_CONDITION',
            'verification_values': [],
            'dn_eu': 'DN',
            'verify_wait': 'WAIT'
        }]
        with pytest.raises(steps.InputError):
            steps.check_telemetry_query(query)
            
    def test_check_telemetry_query_bitmask_no_op(self):
        """Test bitmask provided but no operation."""
        query = [{
            'verification_condition': 'EQUAL',
            'verification_values': ['10'],
            'dn_eu': 'DN',
            'verify_wait': 'WAIT',
            'bit_mask': '0xFF'
        }]
        with pytest.raises(steps.InputError):
            steps.check_telemetry_query(query)
            
    def test_check_telemetry_query_non_numeric_prior_value(self):
        """Test with non-numeric prior_value."""
        query = [{
            'verification_condition': 'GREATER_THAN',
            'verification_values': ['10'],
            'dn_eu': 'DN',
            'verify_wait': 'WAIT',
            'prior_value': 'not_a_number',
            'bit_mask': '0xFF',
            'bit_op': 'AND'
        }]
        with pytest.raises(steps.InputError) as exc_info:
            steps.check_telemetry_query(query)
        assert 'not numeric' in str(exc_info.value)
        
    def test_check_telemetry_query_non_numeric_verification_value_with_prior(self):
        """Test with non-numeric verification value when prior_value is present."""
        query = [{
            'verification_condition': 'EQUAL',
            'verification_values': ['not_a_number'],
            'dn_eu': 'DN',
            'verify_wait': 'WAIT',
            'prior_value': 10,
            'bit_mask': '0xFF',
            'bit_op': 'AND'
        }]
        with pytest.raises(steps.InputError) as exc_info:
            steps.check_telemetry_query(query)
        assert 'not numeric' in str(exc_info.value)
        
    def test_check_telemetry_query_non_numeric_verification_with_bitmask(self):
        """Test with non-numeric verification value when bitmask is used."""
        query = [{
            'verification_condition': 'EQUAL',
            'verification_values': ['not_a_number'],
            'dn_eu': 'DN',
            'verify_wait': 'WAIT',
            'bit_mask': '0xFF',
            'bit_op': 'AND'
        }]
        with pytest.raises(steps.InputError) as exc_info:
            steps.check_telemetry_query(query)
        assert 'not numeric' in str(exc_info.value)
    
    def test_check_telemetry_query_numeric_verification_with_bitmask(self):
        """Test with valid numeric verification value and bitmask."""
        query = [{
            'verification_condition': 'EQUAL',
            'verification_values': ['42'],
            'dn_eu': 'DN',
            'verify_wait': 'WAIT',
            'bit_mask': '0xFF',
            'bit_op': 'AND'
        }]
        steps.check_telemetry_query(query)  # Should not raise
        
    def test_verification_condition_value_counts(self):
        """Test verification conditions with correct and incorrect number of values."""
        # Test conditions that require no values
        for condition in ['RECORD', 'NOT_PRESENT']:
            # Should not raise
            steps.check_telemetry_query([{
                'verification_condition': condition,
                'verification_values': [],
                'dn_eu': 'DN',
                'verify_wait': 'WAIT'
            }])
            
            # Should raise for non-empty values
            with pytest.raises(steps.InputError) as exc_info:
                steps.check_telemetry_query([{
                    'verification_condition': condition,
                    'verification_values': ['1'],
                    'dn_eu': 'DN',
                    'verify_wait': 'WAIT'
                }])
            assert 'requires no verification values' in str(exc_info.value)
        
        # Test conditions that require exactly one value
        single_value_conditions = [
            'GREATER_THAN', 'GREATER_THAN_OR_EQUAL', 
            'LESS_THAN', 'LESS_THAN_OR_EQUAL', 
            'EQUAL', 'NOT_EQUAL'
        ]
        
        for condition in single_value_conditions:
            # Test with one value (should pass)
            steps.check_telemetry_query([{
                'verification_condition': condition,
                'verification_values': ['42'],
                'dn_eu': 'DN',
                'verify_wait': 'WAIT'
            }])
            
            # Test with zero values (should fail)
            with pytest.raises(steps.InputError) as exc_info:
                steps.check_telemetry_query([{
                    'verification_condition': condition,
                    'verification_values': [],
                    'dn_eu': 'DN',
                    'verify_wait': 'WAIT'
                }])
            assert 'requires one verification value' in str(exc_info.value)
            
            # Test with two values (should fail)
            with pytest.raises(steps.InputError) as exc_info:
                steps.check_telemetry_query([{
                    'verification_condition': condition,
                    'verification_values': ['1', '2'],
                    'dn_eu': 'DN',
                    'verify_wait': 'WAIT'
                }])
            assert 'requires one verification value' in str(exc_info.value)
        
        # Test conditions that require exactly two values
        range_conditions = ['INCLUSIVE_RANGE', 'EXCLUSIVE_RANGE']
        
        for condition in range_conditions:
            # Test with two values (should pass)
            steps.check_telemetry_query([{
                'verification_condition': condition,
                'verification_values': ['10', '20'],
                'dn_eu': 'DN',
                'verify_wait': 'WAIT'
            }])
            
            # Test with one value (should fail)
            with pytest.raises(steps.InputError) as exc_info:
                steps.check_telemetry_query([{
                    'verification_condition': condition,
                    'verification_values': ['10'],
                    'dn_eu': 'DN',
                    'verify_wait': 'WAIT'
                }])
            assert 'requires two verification values' in str(exc_info.value)
            
            # Test with three values (should fail)
            with pytest.raises(steps.InputError) as exc_info:
                steps.check_telemetry_query([{
                    'verification_condition': condition,
                    'verification_values': ['10', '20', '30'],
                    'dn_eu': 'DN',
                    'verify_wait': 'WAIT'
                }])
            assert 'requires two verification values' in str(exc_info.value)
            
    def test_unknown_verification_condition(self):
        """Test that an unknown verification condition raises an error."""
        with pytest.raises(steps.InputError) as exc_info:
            steps.check_telemetry_query([{
                'verification_condition': 'UNKNOWN_CONDITION',
                'verification_values': [],
                'dn_eu': 'DN',
                'verify_wait': 'WAIT'
            }])
        assert 'Unknown Verification Condition' in str(exc_info.value)


class TestConfirmNumeric:
    """Test cases for the confirm_numeric function."""
    
    def test_confirm_numeric_int(self):
        """Test with integer input."""
        assert steps.confirm_numeric(42) is True
        
    def test_confirm_numeric_float(self):
        """Test with float input."""
        assert steps.confirm_numeric(3.14) is True
        
    def test_confirm_numeric_numeric_string(self):
        """Test with numeric string input."""
        assert steps.confirm_numeric("42") is True
        
    def test_confirm_numeric_non_numeric(self):
        """Test with non-numeric input."""
        assert steps.confirm_numeric("not a number") is False


class TestFileOperations:
    """Test cases for file operation functions."""
    
    @pytest.fixture
    def temp_files(self, tmp_path):
        """Create temporary files for testing."""
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        return input_file, output_file
        
    def test_write_and_read_file(self, temp_files):
        """Test writing and reading a JSON file."""
        input_file, output_file = temp_files
        test_data = {"test": "data", "value": 42}
        
        # Test write_output_file
        steps.write_output_file(test_data, str(output_file))
        assert output_file.exists()
        
        # Test read_input_file
        loaded_data = steps.read_input_file(str(output_file))
        assert loaded_data == test_data
        
    def test_read_nonexistent_file(self, tmp_path):
        """Test reading a non-existent file raises InputError."""
        non_existent_file = tmp_path / "nonexistent.json"
        with pytest.raises(steps.InputError):
            steps.read_input_file(str(non_existent_file))
    
    @pytest.mark.skipif(os.name == 'nt', reason="Unix-specific permission test")
    def test_read_permission_denied(self, tmp_path):
        """Test reading a file without read permission raises InputError."""
        test_file = tmp_path / "restricted.json"
        test_file.write_text('{"test": "data"}')
        test_file.chmod(0o000)  # Remove all permissions
        
        try:
            with pytest.raises(steps.InputError):
                steps.read_input_file(str(test_file))
        finally:
            # Restore permissions to allow cleanup
            test_file.chmod(0o644)
    
    @pytest.mark.skipif(os.name == 'nt', reason="Unix-specific permission test")
    def test_write_permission_denied(self, tmp_path):
        """Test writing to a directory without write permission raises InputError."""
        # Create a directory without write permissions
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir()
        restricted_dir.chmod(0o555)  # Read and execute, no write
        
        output_file = restricted_dir / "output.json"
        test_data = {"test": "data"}
        
        try:
            with pytest.raises(steps.InputError):
                steps.write_output_file(test_data, str(output_file))
        finally:
            # Restore permissions to allow cleanup
            restricted_dir.chmod(0o755)


class TestInputOutputPaths:
    """Test cases for get_input_output_paths function."""
    
    @patch('sys.argv', ['script.py', 'input.json', 'output.json'])
    def test_get_input_output_paths(self, tmp_path):
        """Test getting input and output paths."""
        with patch('os.path.abspath', side_effect=lambda x: str(tmp_path / x)):
            input_path, output_path = steps.get_input_output_paths("Test error")
            assert input_path == str(tmp_path / 'input.json')
            assert output_path == str(tmp_path / 'output.json')
    
    @patch('sys.argv', ['script.py'])
    def test_get_input_output_paths_insufficient_args(self):
        """Test with insufficient command line arguments."""
        with pytest.raises(steps.InputError, match="Test error"):
            steps.get_input_output_paths("Test error")
    
    @patch('sys.argv', ['script.py', 'nonexistent/input.json', 'output.json'])
    def test_get_input_output_paths_nonexistent_input(self, tmp_path):
        """Test with non-existent input file path."""
        with patch('os.path.abspath', side_effect=lambda x: str(tmp_path / x)):
            input_path, output_path = steps.get_input_output_paths("Test error")
            # The function should still return the paths even if they don't exist
            assert input_path == str(tmp_path / 'nonexistent/input.json')
            assert output_path == str(tmp_path / 'output.json')
    
    @pytest.mark.skipif(os.name == 'nt', reason="Unix-specific permission test")
    @patch('sys.argv', ['script.py', 'input.json', 'output.json'])
    def test_get_input_output_paths_no_read_permission(self, tmp_path):
        """Test with input file that can't be read due to permissions."""
        input_file = tmp_path / "input.json"
        input_file.write_text('{"test": "data"}')
        input_file.chmod(0o000)  # Remove all permissions
        
        try:
            with patch('os.path.abspath', side_effect=lambda x: str(tmp_path / x)):
                input_path, _ = steps.get_input_output_paths("Test error")
                # The function should still return the path even if we can't read it
                assert input_path == str(input_file)
        finally:
            # Restore permissions to allow cleanup
            input_file.chmod(0o644)
    
    @pytest.mark.skipif(os.name == 'nt', reason="Unix-specific permission test")
    @patch('sys.argv', ['script.py', 'input.json', 'restricted/output.json'])
    def test_get_output_path_no_write_permission(self, tmp_path):
        """Test with output directory that can't be written to."""
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir()
        restricted_dir.chmod(0o555)  # Read and execute, no write
        
        try:
            with patch('os.path.abspath', side_effect=lambda x: str(tmp_path / x)):
                _, output_path = steps.get_input_output_paths("Test error")
                # The function should still return the path even if we can't write to it
                assert output_path == str(restricted_dir / "output.json")
        finally:
            # Restore permissions to allow cleanup
            restricted_dir.chmod(0o755)


class TestEvaluateVerifyCondition:
    """Test cases for evaluate_verify_condition function."""
    
    def _create_telemetry(self, value, raw_value=None):
        """Helper to create telemetry data with both value and raw_value."""
        return [{
            'value': str(value),
            'raw_value': str(raw_value if raw_value is not None else value),
            'eng_value': str(value)
        }]
    
    def _create_predicts(self, condition, values, dn_eu='DN', **kwargs):
        """Helper to create predict dictionary with common fields."""
        predict = {
            'verification_condition': condition,
            'verification_values': [str(v) for v in values],
            'dn_eu': dn_eu
        }
        predict.update(kwargs)
        return predict
    
    # Test basic verification conditions
    def test_verification_conditions(self):
        """Test all verification conditions with basic values."""
        test_cases = [
            # (condition, telemetry_value, verification_values, expected_result)
            ('EQUAL', 42, [42], 'PASS'),
            ('EQUAL', 42, [43], 'FAIL'),
            ('NOT_EQUAL', 42, [43], 'PASS'),
            ('NOT_EQUAL', 42, [42], 'FAIL'),
            ('GREATER_THAN', 43, [42], 'PASS'),
            ('GREATER_THAN', 42, [42], 'FAIL'),
            ('GREATER_THAN', 41, [42], 'FAIL'),
            ('LESS_THAN', 41, [42], 'PASS'),
            ('LESS_THAN', 42, [42], 'FAIL'),
            ('LESS_THAN', 43, [42], 'FAIL'),
            ('GREATER_THAN_OR_EQUAL', 43, [42], 'PASS'),
            ('GREATER_THAN_OR_EQUAL', 42, [42], 'PASS'),
            ('GREATER_THAN_OR_EQUAL', 41, [42], 'FAIL'),
            ('LESS_THAN_OR_EQUAL', 41, [42], 'PASS'),
            ('LESS_THAN_OR_EQUAL', 42, [42], 'PASS'),
            ('LESS_THAN_OR_EQUAL', 43, [42], 'FAIL'),
            ('INCLUSIVE_RANGE', 42, [40, 45], 'PASS'),
            ('INCLUSIVE_RANGE', 40, [40, 45], 'PASS'),
            ('INCLUSIVE_RANGE', 45, [40, 45], 'PASS'),
            ('INCLUSIVE_RANGE', 39, [40, 45], 'FAIL'),
            ('INCLUSIVE_RANGE', 46, [40, 45], 'FAIL'),
            ('EXCLUSIVE_RANGE', 42, [40, 45], 'PASS'),
            ('EXCLUSIVE_RANGE', 40, [40, 45], 'FAIL'),
            ('EXCLUSIVE_RANGE', 45, [40, 45], 'FAIL'),
            ('EXCLUSIVE_RANGE', 39, [40, 45], 'FAIL'),
            ('EXCLUSIVE_RANGE', 46, [40, 45], 'FAIL'),
            ('RECORD', 42, [], 'PASS'),  # RECORD always passes when data is present
        ]
        
        for condition, telemetry_value, values, expected in test_cases:
            telemetry = self._create_telemetry(telemetry_value)
            predicts = self._create_predicts(condition, values)
            result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
            assert result['verification_status'] == expected, \
                f"{condition} failed for {telemetry_value} {condition} {values}: expected {expected}, got {result['verification_status']}"
    
    def test_eu_vs_dn_values(self):
        """Test handling of DN vs EU values."""
        # Raw value is 100, engineering value is 42
        telemetry = [{'raw_value': '100', 'eng_value': '42', 'value': '42'}]
        
        # Test with DN (should use raw_value)
        predicts = self._create_predicts('EQUAL', [100], dn_eu='DN')
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
        assert result['actual_value'] == '100'
        
        # Test with EU (should use eng_value)
        predicts = self._create_predicts('EQUAL', [42], dn_eu='EU')
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
        assert result['actual_value'] == '42'
    
    def test_bitmask_operations(self):
        """Test bitmask operations."""
        # Test AND operation (0b1010 & 0b1100 = 0b1000 = 8)
        telemetry = self._create_telemetry(10, raw_value=10)  # 1010 in binary
        predicts = self._create_predicts(
            'EQUAL', 
            [8],  # Expected value after masking
            bit_mask='0b1100',  # 12 in decimal, 1100 in binary
            bit_op='AND',
            dn_eu='DN'  # Must use DN for raw value
        )
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
        assert int(result['actual_value']) == 8
        
        # Test OR operation (0b1010 | 0b0101 = 0b1111 = 15)
        telemetry = self._create_telemetry(10, raw_value=10)  # 1010 in binary
        predicts = self._create_predicts(
            'EQUAL',
            [15],  # Expected value after masking
            bit_mask='0b0101',  # 5 in decimal, 0101 in binary
            bit_op='OR',
            dn_eu='DN'  # Must use DN for raw value
        )
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
        assert int(result['actual_value']) == 15
    
    def test_prior_value(self):
        """Test evaluation with prior value subtraction."""
        telemetry = self._create_telemetry(50, raw_value=50)
        predicts = self._create_predicts(
            'EQUAL',
            [30],  # 50 - 20 = 30
            prior_value=20
        )
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
        assert int(result['actual_value']) == 30
        
        # Test with bitmask and prior value
        # (0b1010 & 0b1100 = 0b1000 = 8) - 3 = 5
        telemetry = self._create_telemetry(10, raw_value=10)  # 1010 in binary
        predicts = self._create_predicts(
            'EQUAL',
            [5],  # Expected value after masking and prior value subtraction
            bit_mask='0b1100',  # 12 in decimal, 1100 in binary
            bit_op='AND',
            prior_value=3,
            dn_eu='DN'  # Must use DN for raw value
        )
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
        assert int(result['actual_value']) == 5
    
    def test_not_present_conditions(self):
        """Test NOT_PRESENT verification conditions."""
        # Test NOT_PRESENT with no telemetry (should pass)
        predicts = self._create_predicts('NOT_PRESENT', [])
        result = steps.evaluate_verify_condition([], 'test_id', predicts, True)
        assert result['verification_status'] == 'PASS'
        
        # Test NOT_PRESENT with telemetry (should fail)
        telemetry = self._create_telemetry(42)
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'FAIL'
    
    def test_record_condition(self):
        """Test RECORD verification condition (should always pass when data is present)."""
        telemetry = self._create_telemetry(42)
        predicts = self._create_predicts('RECORD', [])
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
        
        # Should also pass with any value, as long as data is present
        telemetry = self._create_telemetry(999)
        result = steps.evaluate_verify_condition(telemetry, 'test_id', predicts, False)
        assert result['verification_status'] == 'PASS'
    
    def test_pending_status(self):
        """Test PENDING status when no telemetry but query hasn't timed out."""
        predicts = self._create_predicts('EQUAL', [42])
        result = steps.evaluate_verify_condition([], 'test_id', predicts, False)
        assert result['verification_status'] == 'PENDING'
        
        # With NOT_PRESENT, should still be PENDING if no timeout
        predicts = self._create_predicts('NOT_PRESENT', [])
        result = steps.evaluate_verify_condition([], 'test_id', predicts, False)
        assert result['verification_status'] == 'PENDING'


class TestVerifyWaitTelemetry:
    """Test cases for verify_wait_telemetry function."""
    
    @patch('ing_lib.steps.check_telemetry_query')
    @patch('ing_lib.steps.evaluate_verify_condition')
    def test_verify_wait_telemetry(self, mock_eval, mock_check):
        """Test basic verify_wait_telemetry functionality."""
        # Setup test data
        query = {
            'CHANNEL1': {
                'verification_condition': 'EQUAL',
                'verification_values': ['42'],
                'dn_eu': 'DN',
                'verify_wait': 'WAIT'
            }
        }
        
        # Mock the telemetry query function
        def mock_telemetry_query(channels, timeout, lookback, start_time, return_on):
            return {
                'channels': {
                    'CHANNEL1': [
                        {'value': '42', 'time': '2023-01-01T00:00:00'}
                    ]
                }
            }
            
        # Mock the evaluate function
        mock_eval.return_value = {
            'verification_status': 'PASS',
            'actual_value': '42'
        }
        
        # Call the function
        result = steps.verify_wait_telemetry(
            query,
            mock_telemetry_query,
            start_time=datetime.now(),
            timeout=1,
            lookback=0
        )
        
        # Verify results
        assert result['query_matches_predict'] is True
        assert 'CHANNEL1' in result['channels']
        assert result['channels']['CHANNEL1']['verification_status'] == 'PASS'
        mock_check.assert_called_once()
        mock_eval.assert_called()
