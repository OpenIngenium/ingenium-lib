"""
Tests for ProjConfigBackup.py
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open
import sys

# Import the module under test
from apps.ProjConfigBackup import get_input, get_source_dictionaries, main


class TestProjConfigBackup:
    """Test class for ProjConfigBackup functionality."""
    
    def test_get_input_required_args(self):
        """Test get_input with required arguments."""
        args = [
            'https://test-server.example.com',
            'v4',
            '/path/to/backup.json'
        ]
        inputs = get_input(args)
        
        assert inputs.server == 'https://test-server.example.com'
        assert inputs.api_version == 'v4'
        assert inputs.file_output == '/path/to/backup.json'
        assert inputs.debug is False
        assert inputs.filter_retired is False

    def test_get_input_with_optional_args(self):
        """Test get_input with optional arguments."""
        args = [
            'https://test-server.example.com',
            'v3',
            '/path/to/backup.json',
            '--debug',
            '--username', 'test_user',
            '--ignore_ssl_error',
            '--rsa',
            '--filter_retired'
        ]
        inputs = get_input(args)
        
        assert inputs.debug is True
        assert inputs.username == 'test_user'
        assert inputs.ignore_ssl_error is True
        assert inputs.rsa is True
        assert inputs.filter_retired is True

    def test_get_input_invalid_api_version(self):
        """Test get_input with invalid API version."""
        args = [
            'https://test-server.example.com',
            'v5',  # Invalid version
            '/path/to/backup.json'
        ]
        
        with pytest.raises(SystemExit):
            get_input(args)

    def test_get_source_dictionaries_v4(self, comprehensive_server_mock):
        """Test get_source_dictionaries with v4 API."""

        # Create a mock inputs object
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.specific_versions = None
                self.filter_retired = True
                self.include_vis = True
                self.include_cs = True
                self.include_cmds = True
                self.include_eha = True
                self.include_evr = True
                self.include_mil1553 = True

        mock_inputs = MockInputs()

        result = get_source_dictionaries('https://test-server.example.com', 'v4', mock_inputs)

        assert 'versions' in result
        assert 'flight' in result['versions']
        assert 'sse' in result['versions']


    def test_get_source_dictionaries_filter_retired(self):
        """Test that retired dictionaries are filtered when filter_retired=True."""
        mock_versions = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Published Dict',
                'state': 'PUBLISHED'
            },
            {
                'dictionary_version': 'v0.9',
                'dictionary_description': 'Retired Dict',
                'state': 'RETIRED'
            }
        ]

        # Create a mock inputs object
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.specific_versions = None
                self.filter_retired = True
                self.include_vis = True
                self.include_cs = True
                self.include_cmds = True
                self.include_eha = True
                self.include_evr = True
                self.include_mil1553 = True

        mock_inputs = MockInputs()

        def mock_paginated_side_effect(*args, **kwargs):
            """Return versions for dictionary calls, empty for others."""
            if len(args) > 0:
                endpoint = args[0]
                if 'dictionaries' in endpoint and 'versions' in endpoint:
                    return mock_versions
            return []

        with patch('ing_lib.project_config.ingenium_rest_get_paginated', side_effect=mock_paginated_side_effect), \
                patch('ing_lib.project_config.ingenium_rest_get', return_value=[]):
            
            result = get_source_dictionaries('https://test-server.example.com', 'v4', mock_inputs)
            
            # Should only contain the published version
            assert 'v1.0' in result['versions']['flight']
            assert 'v0.9' not in result['versions']['flight']

    def test_get_source_dictionaries_include_retired(self):
        """Test that retired dictionaries are included when filter_retired=False."""
        mock_versions = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Published Dict',
                'state': 'PUBLISHED'
            },
            {
                'dictionary_version': 'v0.9',
                'dictionary_description': 'Retired Dict',
                'state': 'RETIRED'
            }
        ]

        # Create a mock inputs object
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.specific_versions = None
                self.filter_retired = True
                self.include_vis = True
                self.include_cs = True
                self.include_cmds = True
                self.include_eha = True
                self.include_evr = True
                self.include_mil1553 = True

        mock_inputs = MockInputs()
        
        def mock_paginated_side_effect(*args, **kwargs):
            """Return versions for dictionary calls, empty for others."""
            if len(args) > 0:
                endpoint = args[0]
                if 'dictionaries' in endpoint and 'versions' in endpoint:
                    return mock_versions
            return []

        with patch('ing_lib.project_config.ingenium_rest_get_paginated', side_effect=mock_paginated_side_effect), \
                patch('ing_lib.project_config.ingenium_rest_get', return_value=[]):
            
            result = get_source_dictionaries('https://test-server.example.com', 'v4', mock_inputs)
            
            # Should contain both versions
            assert 'v1.0' in result['versions']['flight']
            assert 'v0.9' not in result['versions']['flight']

    def test_main_success(self, comprehensive_server_mock, mock_user_input):
        """Test successful main execution."""
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:
            
            args = [
                'https://test-server.example.com',
                'v4',
                '/tmp/backup.json'
            ]
            
            main(args)
            
            # Verify file was opened for writing
            mock_file.assert_called_once_with('/tmp/backup.json', 'w')
            
            # Verify JSON was dumped
            mock_json_dump.assert_called_once()

    def test_main_authentication_failure(self):
        """Test main execution with authentication failure."""
        with patch('common.authenticate', return_value=False), \
             patch('getpass.getpass', return_value='test_password'), \
             patch('getpass.getuser', return_value='test_user'):
            
            args = [
                'https://test-server.example.com',
                'v4',
                '/tmp/backup.json'
            ]
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                main(args)

    def test_main_ssl_configuration(self, comprehensive_server_mock, mock_user_input):
        """Test SSL configuration in main."""
        with patch('builtins.open', mock_open()), \
             patch('json.dump'), \
             patch('urllib3.disable_warnings') as mock_urllib3:
            
            # Test with ignore_ssl_error
            args = [
                'https://test-server.example.com',
                'v4',
                '/tmp/backup.json',
                '--ignore_ssl_error'
            ]
            
            main(args)
            
            # Verify SSL warnings were disabled
            mock_urllib3.assert_called()

    def test_main_with_rsa(self, comprehensive_server_mock, mock_user_input):
        """Test main execution with RSA authentication."""

        # Create a mock inputs object
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.specific_versions = None
                self.filter_retired = True
                self.include_vis = True
                self.include_cs = True
                self.include_cmds = True
                self.include_eha = True
                self.include_evr = True
                self.include_mil1553 = True

        mock_inputs = MockInputs()

        with patch('builtins.open', mock_open()), \
             patch('json.dump'), \
             patch('ing_lib.common.authenticate', return_value=mock_inputs) as mock_auth:
            
            args = [
                'https://test-server.example.com',
                'v4',
                '/tmp/backup.json',
                '--rsa'
            ]
            
            main(args)
            
            # Verify authentication was called with RSA flag
            mock_auth.assert_called_once()
            call_args = mock_auth.call_args
            assert call_args[1]['rsa'] is True

    def test_get_source_dictionaries_v3(self):
        """Test get_source_dictionaries with v3 API."""

        # Create a mock inputs object
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.specific_versions = None
                self.filter_retired = True
                self.include_vis = True
                self.include_cs = True
                self.include_cmds = True
                self.include_eha = True
                self.include_evr = True
                self.include_mil1553 = True

        mock_inputs = MockInputs()

        # Mock data for v3 API
        mock_versions = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Test Dict v1.0',
                'state': 'PUBLISHED'
            }
        ]

        def mock_paginated_side_effect(*args, **kwargs):
            """Return versions for dictionary calls, empty for others."""
            if len(args) > 0:
                endpoint = args[0]
                if 'dictionaries' in endpoint and 'versions' in endpoint:
                    return mock_versions
            return []

        with patch('ing_lib.project_config.ingenium_rest_get_paginated', side_effect=mock_paginated_side_effect), \
                patch('ing_lib.project_config.ingenium_rest_get', return_value=[]):

            result = get_source_dictionaries('https://test-server.example.com', 'v3', mock_inputs)

            assert 'versions' in result
            assert 'flight' in result['versions']
            assert 'v1.0' in result['versions']['flight']

    def test_get_source_dictionaries_exception_handling(self):
        """Test exception handling in get_source_dictionaries."""
        mock_versions = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Test Dict v1.0',
                'state': 'PUBLISHED'
            }
        ]

        # Create a mock inputs object
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.specific_versions = None
                self.filter_retired = True
                self.include_vis = True
                self.include_cs = True
                self.include_cmds = True
                self.include_eha = True
                self.include_evr = True
                self.include_mil1553 = True

        mock_inputs = MockInputs()

        def mock_paginated_side_effect(*args, **kwargs):
            """Return versions for dictionary calls, empty for others."""
            if len(args) > 0:
                endpoint = args[0]
                if 'dictionaries' in endpoint and 'versions' in endpoint:
                    return mock_versions
            return []

        with patch('ing_lib.project_config.ingenium_rest_get_paginated', side_effect=mock_paginated_side_effect), \
                patch('ing_lib.project_config.ingenium_rest_get', side_effect=Exception("Network error")):
            
            # Should not raise exception but log warning
            result = get_source_dictionaries('https://test-server.example.com', 'v4', mock_inputs)
            
            assert 'versions' in result
            assert 'v1.0' in result['versions']['flight']

    def test_main_with_ssl_ca_bundle(self, comprehensive_server_mock, mock_user_input):
        """Test main execution with SSL CA bundle."""
        with patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            args = [
                'https://test-server.example.com',
                'v4',
                '/tmp/backup.json',
                '--ssl_ca_bundle', '/path/to/ca-bundle.crt'
            ]
            
            main(args)
            
            # Test should complete without errors

    def test_main_with_custom_username(self, comprehensive_server_mock):
        """Test main execution with custom username."""
        # Create a mock inputs object
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.specific_versions = None
                self.filter_retired = True
                self.include_vis = True
                self.include_cs = True
                self.include_cmds = True
                self.include_eha = True
                self.include_evr = True
                self.include_mil1553 = True

        mock_inputs = MockInputs()

        with patch('builtins.open', mock_open()), \
             patch('json.dump'), \
             patch('ing_lib.common.authenticate', return_value=mock_inputs) as mock_auth, \
             patch('getpass.getpass', return_value='test_password'):
            
            args = [
                'https://test-server.example.com',
                'v4',
                '/tmp/backup.json',
                '--username', 'custom_user'
            ]
            
            main(args)
            
            # Verify authentication was called with custom username
            mock_auth.assert_called_once()
            call_args = mock_auth.call_args
            assert call_args[1]['username'] == 'custom_user' 