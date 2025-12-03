"""
Integration tests for ingenium-lib applications
"""

import pytest
import tempfile
import json
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

# Test constants
MOCK_INGENIUM_SERVER = "https://mock-ingenium-server.example.com"


@pytest.mark.integration
class TestIngLibIntegration:
    """Integration tests for the full backup/restore workflow."""
    
    def test_backup_and_restore_workflow(self, comprehensive_server_mock):
        """Test complete backup and restore workflow."""
        from apps.ProjConfigBackup import get_source_dictionaries
        from apps.ProjConfigRestore import restore_dictionaries
        
        # Create a mock inputs object with required attributes
        class MockInputs:
            def __init__(self):
                self.flight_sse = None
                self.filter_retired = False
                self.specific_versions = None
                self.include_vis = True
                self.include_cs = True
        
        # Test backup with mock inputs
        backup_data = get_source_dictionaries(
            MOCK_INGENIUM_SERVER, 'v4', MockInputs()
        )
        
        # Verify backup structure
        assert 'versions' in backup_data
        assert 'flight' in backup_data['versions']
        assert 'vis' in backup_data
        assert 'custom_scripts' in backup_data
        
        # Test restore - should not raise any exceptions
        restore_dictionaries(MOCK_INGENIUM_SERVER, backup_data)

    @patch('os.path.exists')
    @patch('common.authenticate')
    def test_xml_to_script_workflow(self, mock_auth, mock_exists):
        """Test XML parsing and script creation workflow."""
        from apps.ProjConfigCreateUpdateCS import detect_file_type, parse_custom_script_xml
        
        mock_auth.return_value = True
        mock_exists.return_value = True
        
        # Create temporary XML file
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <custom_script script_name="integration_test" script_path="test.sh" description="Integration test script">
        <input_field name="param1" description="Test parameter" type="STRING" required="true" phase="RUN"/>
    </custom_script>
</custom-scripts>"""
        
        script_content = "#!/bin/bash\necho 'Integration test'"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create XML file
            xml_file = os.path.join(temp_dir, 'test.xml')
            with open(xml_file, 'w') as f:
                f.write(xml_content)
            
            # Create script file
            script_file = os.path.join(temp_dir, 'test.sh')
            with open(script_file, 'w') as f:
                f.write(script_content)
            
            # Test file type detection
            file_type = detect_file_type(xml_file)
            assert file_type == 'xml'
            
            # Test XML parsing
            script_data = parse_custom_script_xml(xml_file, '/opt/scripts')
            
            # Verify parsed data
            assert script_data['script_name'] == 'integration_test'
            assert script_data['description'] == 'Integration test script'
            assert len(script_data['inputs']) == 1
            assert script_data['inputs'][0]['name'] == 'param1'

    @patch('requests.delete')  
    @patch('requests.get')
    @patch('common.authenticate')
    @pytest.mark.slow
    def test_error_handling_chain(self, mock_auth, mock_get, mock_delete):
        """Test error handling across multiple components."""
        from apps.ProjConfigClear import clear_project_configuration
        
        # Mock authentication
        mock_auth.return_value = True
        
        # Setup mock responses for GET requests (queries)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'x-total-count': '2'}
        
        # Mock responses for dictionary versions query
        mock_response.json.return_value = [{'dictionary_version': 'v1.0'}, {'dictionary_version': 'v1.1'}]
        mock_get.return_value = mock_response
        
        # Setup mock responses for DELETE requests
        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 204  # No content for successful delete
        mock_delete.return_value = mock_delete_response
        
        # Make some delete operations fail to test error handling
        mock_delete.side_effect = [
            mock_delete_response,  # First delete succeeds
            Exception("Simulated error"),  # Second delete fails
            mock_delete_response,  # Third delete succeeds
            mock_delete_response   # Fourth delete succeeds
        ]
        
        # Mock common._store to avoid authentication issues
        with patch('common._store', {'token': 'Bearer mock_token', 'ssl_verify': True, 'refresh_time': datetime.utcnow()}), \
             patch('common.ssl_verify', True):
            
            # Should not raise exception despite internal failures
            clear_project_configuration(MOCK_INGENIUM_SERVER, ['flight', 'sse'])

    @patch('requests.post')
    @patch('requests.get')
    @patch('os.path.exists')
    @patch('common.authenticate')
    @patch('project_config.get_custom_scripts')
    @patch('project_config.create_custom_script')
    def test_comprehensive_custom_script_workflow(self, mock_create, mock_get_scripts, 
                                                 mock_auth, mock_exists, mock_get, mock_post, 
                                                 temp_custom_script_xml):
        """Test complete custom script parsing and creation workflow."""
        from apps.ProjConfigCreateUpdateCS import (
            detect_file_type, parse_custom_script_xml, validate_script_data, main
        )
        
        mock_auth.return_value = True
        mock_exists.return_value = True
        mock_get_scripts.return_value = []  # No existing scripts
        
        # Setup mock HTTP responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.headers = {'x-total-count': '0'}
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        
        # Test file type detection
        file_type = detect_file_type(temp_custom_script_xml)
        assert file_type == 'xml'
        
        # Test comprehensive parsing
        script_data = parse_custom_script_xml(temp_custom_script_xml, '/opt/scripts')
        
        # Verify comprehensive parsing results
        assert script_data['script_name'] == 'comprehensive_test_script'
        assert len(script_data['inputs']) == 7  # All input types
        assert len(script_data['outputs']) == 5  # All output types
        assert len(script_data['entries']) == 1  # Script entry
        assert 'output_array' in script_data  # Output array
        assert len(script_data['layout']) > 0  # Advanced layout
        
        # Test validation
        assert validate_script_data(script_data) is True
        
        # Test end-to-end workflow with mocks
        with patch('getpass.getpass', return_value='test_password'), \
             patch('getpass.getuser', return_value='test_user'):
            
            args = [
                MOCK_INGENIUM_SERVER,
                temp_custom_script_xml,
                '--base_path', '/opt/scripts'
            ]
            
            main(args)
            
            # Verify HTTP requests were made (but mocked)
            assert mock_get.called or mock_post.called

    @pytest.mark.slow
    def test_multiple_dictionary_parsing_workflow(self, temp_xml_file, temp_channel_xml_file, 
                                                 temp_evr_xml_file, temp_mil1553_xml_file):
        """Test parsing multiple dictionary types in sequence."""
        from apps.ProjConfigLoadAMPCSDict import (
            detect_dictionary_type, parse_command_dictionary, parse_channel_dictionary,
            parse_evr_dictionary, parse_mil1553_dictionary
        )
        
        # Test command dictionary
        assert detect_dictionary_type(temp_xml_file) == 'commands'
        commands = parse_command_dictionary(temp_xml_file)
        assert len(commands) >= 2  # At least FSW and HW commands
        
        # Test channel dictionary  
        assert detect_dictionary_type(temp_channel_xml_file) == 'channels'
        channels = parse_channel_dictionary(temp_channel_xml_file)
        assert len(channels) >= 4  # Multiple channel types
        
        # Test EVR dictionary
        assert detect_dictionary_type(temp_evr_xml_file) == 'evrs'
        evrs = parse_evr_dictionary(temp_evr_xml_file)
        assert len(evrs) >= 3  # Multiple EVR types
        
        # Test MIL-STD-1553 dictionary
        assert detect_dictionary_type(temp_mil1553_xml_file) == 'mil1553'
        signals = parse_mil1553_dictionary(temp_mil1553_xml_file)
        assert len(signals) >= 2  # Multiple signal types
        
        # Verify different data structures are correctly parsed
        assert any(cmd.get('arguments') for cmd in commands)  # Some commands have arguments
        # Fixed assertion - checking for eu_present field that the parser actually creates
        assert any(ch.get('eu_present') == 'Yes' for ch in channels)   # Some channels have EU conversion
        # Fixed assertion - checking for format specifiers in EVR messages which indicates arguments
        assert any('%' in evr.get('evr_message', '') for evr in evrs)  # Some EVRs have arguments (format specifiers)
        assert any(sig.get('enumerations') for sig in signals) # Some signals have enums 