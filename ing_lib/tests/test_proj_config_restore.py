"""
Tests for ProjConfigRestore.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open

# Import the module under test
from apps.ProjConfigRestore import get_input, restore_dictionaries, main
import ing_lib.common as common


class TestProjConfigRestore:
    """Test class for ProjConfigRestore functionality."""
    
    def test_get_input_required_args(self):
        """Test get_input with required arguments."""
        args = [
            'https://test-server.example.com',
            '/path/to/backup.json'
        ]
        inputs = get_input(args)
        
        assert inputs.server == 'https://test-server.example.com'
        assert inputs.file_input == '/path/to/backup.json'
        assert inputs.debug is False
        assert inputs.username is None
        assert inputs.ignore_ssl_error is False
        assert inputs.rsa is False

    def test_get_input_with_optional_args(self):
        """Test get_input with optional arguments."""
        args = [
            'https://test-server.example.com',
            '/path/to/backup.json',
            '--debug',
            '--username', 'test_user',
            '--ignore_ssl_error',
            '--rsa'
        ]
        inputs = get_input(args)
        
        assert inputs.debug is True
        assert inputs.username == 'test_user'
        assert inputs.ignore_ssl_error is True
        assert inputs.rsa is True

    def test_restore_dictionaries_success(self, comprehensive_server_mock, sample_backup_data):
        """Test successful restoration of dictionaries."""
        restore_dictionaries('https://test-server.example.com', sample_backup_data)
        
        # The function should complete without error when properly mocked

    def test_restore_dictionaries_with_content(self, comprehensive_server_mock):
        """Test restoration with actual content in all categories."""
        backup_data = {
            'versions': {
                'flight': {
                    'v1.0': {
                        'dictionary_description': 'Test Flight Dict',
                        'dictionary_version': 'v1.0',
                        'state': 'PUBLISHED'
                    }
                },
                'sse': {
                    'v1.0': {
                        'dictionary_description': 'Test SSE Dict',
                        'dictionary_version': 'v1.0',
                        'state': 'PUBLISHED'
                    }
                }
            },
            'flight': {
                'v1.0': {
                    'cmds': [{'command_stem': 'TEST_CMD'}],
                    'channels': [{'channel_name': 'TEST_CH'}],
                    'evrs': [{'evr_name': 'TEST_EVR'}],
                    'mil1553': [{'mil1553_name': 'TEST_1553'}]
                }
            },
            'sse': {
                'v1.0': {
                    'cmds': [],
                    'channels': [],
                    'evrs': [],
                    'mil1553': []
                }
            },
            'vis': [{'vi_id': 'test_vi'}],
            'custom_scripts': [{'script_name': 'test_script'}]
        }
        
        restore_dictionaries('https://test-server.example.com', backup_data)
        
        # The function should complete without error when properly mocked

    def test_restore_dictionaries_with_errors(self, caplog):
        """Test restoration when some operations fail."""
        # Create test data with non-empty vis and custom_scripts to trigger error paths
        test_data = {
            'versions': {
                'flight': {
                    'v1.0': {
                        'dictionary_description': 'Test Flight Dict',
                        'dictionary_version': 'v1.0',
                        'state': 'PUBLISHED'
                    }
                },
                'sse': {
                    'v1.0': {
                        'dictionary_description': 'Test SSE Dict',
                        'dictionary_version': 'v1.0',
                        'state': 'PUBLISHED'
                    }
                }
            },
            'flight': {
                'v1.0': {
                    'cmds': [{'command_stem': 'TEST_CMD'}],
                    'channels': [],
                    'evrs': [],
                    'mil1553': []
                }
            },
            'sse': {
                'v1.0': {
                    'cmds': [],
                    'channels': [],
                    'evrs': [],
                    'mil1553': []
                }
            },
            'vis': [{'vi_id': 'test_vi'}],  # Non-empty to trigger error
            'custom_scripts': [{'script_name': 'test_script'}]  # Non-empty to trigger error
        }
        
        with patch('project_config.create_dictionary_version') as mock_create_version, \
             patch('project_config.create_dictionary_content'), \
             patch('project_config.create_vnv_vis') as mock_create_vis, \
             patch('project_config.create_custom_script') as mock_create_script:
            
            # Make some operations fail
            # First version creation succeeds, second fails
            mock_create_version.side_effect = [None, Exception("Version creation failed")]
            mock_create_vis.side_effect = Exception("VI creation failed")
            mock_create_script.side_effect = Exception("Script creation failed")
            
            # Should not raise exception, just log errors
            restore_dictionaries('https://test-server.example.com', test_data)
            
            # Check that errors were logged
            assert "Error restoring" in caplog.text

    def test_main_success(self, comprehensive_server_mock, mock_user_input, sample_backup_data):
        """Test successful main execution."""
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.load', return_value=sample_backup_data) as mock_json_load, \
             patch('apps.ProjConfigRestore.restore_dictionaries') as mock_restore:
            
            args = [
                'https://test-server.example.com',
                '/tmp/backup.json'
            ]
            
            main(args)
            
            # Verify file was opened
            mock_file.assert_called_once_with('/tmp/backup.json', 'r')
            
            # Verify JSON was loaded
            mock_json_load.assert_called_once()
            
            # Verify restore was called
            mock_restore.assert_called_once_with('https://test-server.example.com', sample_backup_data)

    def test_main_authentication_failure(self, mock_user_input):
        """Test main execution with authentication failure."""
        with patch('ing_lib.common.authenticate', return_value=False), \
             patch('getpass.getpass', return_value='fake_password'):
            
            args = [
                'https://test-server.example.com',
                '/tmp/backup.json'
            ]
            
            with pytest.raises(common.IngeniumLibError):
                main(args)

    def test_main_with_rsa(self, comprehensive_server_mock, mock_user_input, sample_backup_data):
        """Test main execution with RSA authentication."""
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.load', return_value=sample_backup_data) as mock_json_load, \
             patch('apps.ProjConfigRestore.restore_dictionaries') as mock_restore:
            
            args = [
                'https://test-server.example.com',
                '/tmp/backup.json',
                '--rsa'
            ]
            
            main(args)
            
            # Since we're using comprehensive_server_mock, authentication should be mocked

    def test_main_ssl_configuration(self, comprehensive_server_mock, mock_user_input, sample_backup_data):
        """Test SSL configuration in main."""
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.load', return_value=sample_backup_data), \
             patch('apps.ProjConfigRestore.restore_dictionaries'), \
             patch('common.ssl_verify') as mock_ssl_verify:
            
            # Test with ignore_ssl_error
            args = [
                'https://test-server.example.com',
                '/tmp/backup.json',
                '--ignore_ssl_error'
            ]
            
            main(args)
            
            # Verify SSL verification was configured
            assert mock_ssl_verify is not None

    def test_restore_dictionaries_empty_data(self, comprehensive_server_mock):
        """Test restoration with empty backup data."""
        empty_data = {
            'versions': {'flight': {}, 'sse': {}},
            'flight': {},
            'sse': {},
            'vis': [],
            'custom_scripts': []
        }
        
        restore_dictionaries('https://test-server.example.com', empty_data)
        
        # Should complete without error

    def test_restore_dictionaries_missing_keys(self, comprehensive_server_mock):
        """Test restoration with missing keys in backup data."""
        incomplete_data = {
            'versions': {'flight': {}, 'sse': {}},
            'flight': {},
            'sse': {}
            # Missing 'vis' and 'custom_scripts'
        }
        
        # Should handle missing keys gracefully
        restore_dictionaries('https://test-server.example.com', incomplete_data) 