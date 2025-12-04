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

    def test_get_input_invalid_api_version(self):
        """Test get_input with invalid API version."""
        args = [
            'https://test-server.example.com',
            'v5',  # Invalid version
            '/path/to/backup.json'
        ]
        
        with pytest.raises(SystemExit):
            get_input(args)

    @patch('apps.ProjConfigBackup.get_dictionary_versions')
    def test_get_source_dictionaries_v4(self, mock_get_versions, comprehensive_server_mock):
        """Test get_source_dictionaries with v4 API."""
        # Setup mock return value
        mock_versions = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Test Dict v1.0',
                'state': 'PUBLISHED'
            },
            {
                'dictionary_version': 'v1.1',
                'dictionary_description': 'Test Dict v1.1',
                'state': 'PUBLISHED'
            }
        ]
        # Set the return value for both flight and sse calls
        mock_get_versions.return_value = mock_versions
        
        # Create a mock inputs object with required attributes
        class MockInputs:
            flight_sse = None
            specific_versions = None
            filter_retired = False
            include_vis = False
            include_cs = False
            
        inputs = MockInputs()
        result = get_source_dictionaries('https://test-server.example.com', 'v4', inputs)
        
        # Check that get_dictionary_versions was called twice (once for flight, once for sse)
        assert mock_get_versions.call_count == 2
        mock_get_versions.assert_any_call('https://test-server.example.com', 'flight', api_version='v4')
        mock_get_versions.assert_any_call('https://test-server.example.com', 'sse', api_version='v4')
        
        # Check the basic structure
        assert 'versions' in result
        assert 'flight' in result['versions']
        assert 'sse' in result['versions']
        
        # Check that the versions are correctly processed
        assert isinstance(result['versions']['flight'], dict)
        assert len(result['versions']['flight']) == 2  # Should have exactly 2 versions
        
        # Check that both versions are present and have the correct structure
        assert 'v1.0' in result['versions']['flight']
        assert 'v1.1' in result['versions']['flight']
        
        # Check that the version information is correctly stored
        v1_0 = result['versions']['flight']['v1.0']
        assert v1_0['dictionary_version'] == 'v1.0'
        assert v1_0['dictionary_description'] == 'Test Dict v1.0'
        assert v1_0['state'] == 'PUBLISHED'
        
        v1_1 = result['versions']['flight']['v1.1']
        assert v1_1['dictionary_version'] == 'v1.1'
        assert v1_1['dictionary_description'] == 'Test Dict v1.1'
        assert v1_1['state'] == 'PUBLISHED'

    @patch('apps.ProjConfigBackup.get_dictionary_versions')
    def test_get_source_dictionaries_filter_retired(self, mock_get_versions):
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

        class MockInputs:
            def __init__(self, filter_retired=False):
                self.filter_retired = filter_retired
                self.flight_sse = []          # limit to specific flight/sse if needed
                self.specific_versions = []   # no version filter
                self.include_vis = False
                self.include_cs = False

        # Mock the dictionary versions returned for both flight and sse
        mock_get_versions.return_value = mock_versions

        inputs = MockInputs(filter_retired=True)
        result = get_source_dictionaries('https://test-server.example.com', 'v4', inputs)

        # Should only contain the published version
        assert 'v1.0' in result['versions']['flight']
        assert 'v0.9' not in result['versions']['flight']

    @patch('apps.ProjConfigBackup.get_dictionary_versions')
    def test_get_source_dictionaries_include_retired(self, mock_get_versions):
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

        class MockInputs:
            def __init__(self, filter_retired=False):
                self.filter_retired = filter_retired
                # flight_sse = None -> process both 'sse' and 'flight'
                self.flight_sse = None
                self.specific_versions = []   # no version filter
                self.include_vis = False
                self.include_cs = False

        mock_get_versions.return_value = mock_versions

        inputs = MockInputs(filter_retired=False)
        result = get_source_dictionaries('https://test-server.example.com', 'v4', inputs)

        # Should contain both versions
        assert 'v1.0' in result['versions']['flight']
        assert 'v0.9' in result['versions']['flight']

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
        with patch('builtins.open', mock_open()), \
             patch('json.dump'), \
             patch('common.authenticate', return_value=True) as mock_auth:
            
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


    @patch('apps.ProjConfigBackup.get_dictionary_versions')
    def test_get_source_dictionaries_v3(self, mock_get_versions, comprehensive_server_mock):
        """Test get_source_dictionaries with v3 API."""
        # Mock versions returned by the v3 API
        mock_versions = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Test Dict v1.0',
                'state': 'PUBLISHED',
            }
        ]
        mock_get_versions.return_value = mock_versions

        # Create a simple object to mock the inputs parameter
        class MockInputs:
            def __init__(self):
                # This will make the function process both 'sse' and 'flight' dict types
                self.flight_sse = None
                self.specific_versions = []
                self.filter_retired = False
                self.include_vis = False
                self.include_cs = False

        inputs = MockInputs()
        result = get_source_dictionaries('https://test-server.example.com', 'v3', inputs)

        assert 'versions' in result
        assert 'flight' in result['versions']
        assert 'v1.0' in result['versions']['flight']

    @patch('project_config.ingenium_rest_get_paginated')
    @patch('apps.ProjConfigBackup.get_dictionary_versions')
    def test_get_source_dictionaries_exception_handling(self, mock_get_versions, mock_rest_get):
        """Test exception handling in get_source_dictionaries."""
        # Setup mock to return test versions
        mock_versions = [
            {
                'dictionary_version': 'v1.0',
                'dictionary_description': 'Test Dict v1.0',
                'state': 'PUBLISHED'
            }
        ]
        mock_rest_get.return_value = mock_versions
        mock_get_versions.return_value = mock_versions

        # Create a simple object to mock the inputs parameter
        class MockInputs:
            def __init__(self):
                # Process both 'sse' and 'flight'
                self.flight_sse = None
                self.specific_versions = []
                self.filter_retired = False
                self.include_vis = False
                self.include_cs = False

        inputs = MockInputs()

        with patch('common.ingenium_rest_get', side_effect=Exception("Network error")):
            # Should not raise exception but log warning
            result = get_source_dictionaries('https://test-server.example.com', 'v4', inputs)

            assert 'versions' in result
            assert 'v1.0' in result['versions']['flight']

            # Verify get_dictionary_versions was called for both sse and flight
            assert mock_get_versions.call_count == 2
            mock_get_versions.assert_any_call(
                'https://test-server.example.com', 'sse', api_version='v4'
            )
            mock_get_versions.assert_any_call(
                'https://test-server.example.com', 'flight', api_version='v4'
            )
            mock_rest_get.assert_called()

    def test_main_with_ssl_ca_bundle(self, comprehensive_server_mock, mock_user_input):
        """Test main execution with SSL CA bundle."""
        with patch('builtins.open', mock_open()), \
             patch('json.dump'), \
             patch('common.ssl_verify') as mock_ssl_verify:
            
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
        with patch('builtins.open', mock_open()), \
             patch('json.dump'), \
             patch('common.authenticate', return_value=True) as mock_auth, \
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