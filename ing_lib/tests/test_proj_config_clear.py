"""
Tests for ProjConfigClear.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch
from apps.ProjConfigClear import get_input, clear_project_configuration, main, common


class TestProjConfigClear:
    """Test class for ProjConfigClear functionality."""

    def test_get_input_required_args(self):
        """Test get_input with required arguments."""
        args = ['https://test-server.example.com']
        inputs = get_input(args)

        assert inputs.server == 'https://test-server.example.com'
        assert inputs.debug is False
        assert inputs.username is None
        assert inputs.ignore_ssl_error is False
        assert inputs.rsa is False
        assert inputs.types is None

    def test_get_input_with_optional_args(self):
        """Test get_input with optional arguments."""
        args = [
            'https://test-server.example.com',
            '--debug',
            '--username', 'test_user',
            '--ignore_ssl_error',
            '--rsa',
            '--types', 'flight', 'sse'
        ]
        inputs = get_input(args)

        assert inputs.debug is True
        assert inputs.username == 'test_user'
        assert inputs.ignore_ssl_error is True
        assert inputs.rsa is True
        assert inputs.types == ['flight', 'sse']

    def test_clear_project_configuration_all_types(self, comprehensive_server_mock):
        """Test successful clearing of all configuration types."""
        # This test relies on comprehensive_server_mock to ensure no exceptions are raised.
        # It mainly verifies that the function completes without error.
        clear_project_configuration('https://test-server.example.com', ['flight', 'sse', 'vis', 'custom-scripts'])

    def test_clear_project_configuration_with_exceptions(self, comprehensive_server_mock):
        """Test clearing configurations when some deletions fail."""
        mock_versions = [{'dictionary_version': 'v1.0'}, {'dictionary_version': 'v1.1'}]

        with patch('apps.ProjConfigClear.get_dictionary_versions', return_value=mock_versions), \
             patch('apps.ProjConfigClear.get_vnv_vis', return_value=[]), \
             patch('apps.ProjConfigClear.get_custom_scripts', return_value=[]), \
             patch('apps.ProjConfigClear.delete_dictionary_version') as mock_delete_version, \
             patch('apps.ProjConfigClear.delete_vnv_vi'), \
             patch('apps.ProjConfigClear.delete_custom_script'):

            # Make some deletions fail
            mock_delete_version.side_effect = [None, Exception("Delete failed"), None, None]

            # Should not raise an exception, just continue
            clear_project_configuration('https://test-server.example.com', ['flight', 'sse'])

            # Verify it attempted to delete all versions despite failures
            assert mock_delete_version.call_count == 4

    def test_clear_large_number_of_vis(self, comprehensive_server_mock):
        """Test clearing a large number of VIs (tests the counter logic)."""
        # Create 1500 VIs to test the counter
        vis = [{'vi_id': f'vi{i}'} for i in range(1500)]

        with patch('apps.ProjConfigClear.get_dictionary_versions', return_value=[]), \
             patch('apps.ProjConfigClear.get_custom_scripts', return_value=[]), \
             patch('apps.ProjConfigClear.get_vnv_vis', return_value=vis), \
             patch('apps.ProjConfigClear.delete_vnv_vi') as mock_delete_vi, \
             patch('apps.ProjConfigClear.delete_dictionary_version'), \
             patch('apps.ProjConfigClear.delete_custom_script'):

            clear_project_configuration('https://test-server.example.com', ['vis'])

            # Verify all VIs were deleted
            assert mock_delete_vi.call_count == 1500

    def test_main_user_confirms_yes_with_types(self, comprehensive_server_mock):
        """Test main execution when user confirms 'yes' and types are specified."""
        with patch('builtins.input', return_value='yes') as mock_input, \
             patch('getpass.getpass', return_value='test_password'), \
             patch('getpass.getuser', return_value='test_user'), \
             patch('apps.ProjConfigClear.clear_project_configuration') as mock_clear:
            args = ['https://test-server.example.com', '--types', 'flight', 'custom-scripts']
            main(args)

            mock_input.assert_called_once_with(
                "Are you sure you want to clear the following project configuration types: flight, custom-scripts from https://test-server.example.com? This operation can not be undone. (yes/no): ")
            mock_clear.assert_called_once_with('https://test-server.example.com', ['flight', 'custom-scripts'])

    def test_main_user_confirms_yes_no_types(self, comprehensive_server_mock):
        """Test main execution when user confirms with 'yes' and no types specified."""
        with patch('builtins.input', return_value='yes') as mock_input, \
             patch('getpass.getpass', return_value='test_password'), \
             patch('getpass.getuser', return_value='test_user'), \
             patch('apps.ProjConfigClear.clear_project_configuration') as mock_clear:
            args = ['https://test-server.example.com']
            main(args)

            mock_input.assert_called_once_with(
                f"Are you sure you want to clear all project configuration information from https://test-server.example.com? This operation can not be undone. (yes/no): ")
            # Verify clear function was called with all types
            mock_clear.assert_called_once_with('https://test-server.example.com',
                                               ['flight', 'sse', 'vis', 'custom-scripts'])

    def test_main_user_confirms_no(self, comprehensive_server_mock):
        """Test main execution when user cancels with 'no'."""
        with patch('builtins.input', return_value='no'), \
             patch('getpass.getpass', return_value='test_password'), \
             patch('getpass.getuser', return_value='test_user'), \
             patch('apps.ProjConfigClear.clear_project_configuration') as mock_clear:
            args = ['https://test-server.example.com']
            main(args)

            # Verify clear function was NOT called
            mock_clear.assert_not_called()

    def test_main_user_invalid_then_valid_input(self, comprehensive_server_mock):
        """Test main execution with invalid input followed by valid input."""
        with patch('getpass.getpass', return_value='test_password'), \
             patch('getpass.getuser', return_value='test_user'), \
             patch('apps.ProjConfigClear.clear_project_configuration') as mock_clear:
            # Simulate invalid input followed by valid input
            with patch('builtins.input', side_effect=['maybe', 'invalid', 'yes']) as mock_input:
                args = ['https://test-server.example.com']
                main(args)

                # Should have been called 3 times (invalid, invalid, valid)
                assert mock_input.call_count == 3
                mock_clear.assert_called_once()

    def test_main_authentication_failure(self):
        """Test main execution with authentication failure."""
        with patch('common.authenticate', return_value=False), \
             patch('getpass.getpass', return_value='wrong_password'), \
             patch('getpass.getuser', return_value='test_user'):
            args = ['https://test-server.example.com']

            with pytest.raises(common.IngeniumLibError):
                main(args)

    def test_main_with_rsa_authentication(self, comprehensive_server_mock):
        """Test main execution with RSA authentication."""
        with patch('builtins.input', return_value='no'), \
             patch('getpass.getpass') as mock_getpass, \
             patch('getpass.getuser', return_value='test_user'):
            args = ['https://test-server.example.com', '--rsa']
            main(args)

            # Check that the prompt is correct for RSA
            mock_getpass.assert_called_once_with("Enter RSA Passcode for test_user:")

    def test_main_with_ssl_ca_bundle(self, comprehensive_server_mock):
        """Test main execution with SSL CA bundle."""
        with patch('builtins.input', return_value='no'), \
             patch('getpass.getpass', return_value='test_password'), \
             patch('getpass.getuser', return_value='test_user'), \
             patch('ing_lib.common.set_ssl_verify') as mock_set_ssl_verify:
            args = ['https://test-server.example.com', '--ssl_ca_bundle', '/path/to/ca.pem']
            main(args)

            # Verify SSL CA bundle setting was correctly set
            mock_set_ssl_verify.assert_called_once_with('/path/to/ca.pem') 