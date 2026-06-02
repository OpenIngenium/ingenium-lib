"""
Tests for ProjConfigCreateUpdateCS.py
"""

import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock, mock_open
import sys

# Import the module under test
from apps.ProjConfigCreateUpdateCS import (
    get_input, detect_file_type, generate_hash,
    parse_custom_script_xml, parse_custom_script_json, validate_script_data, main,
    compare_and_log_differences, generate_server_script_path, validate_advanced_layout
)


class TestProjConfigCreateUpdateCS:
    """Test class for ProjConfigCreateUpdateCS functionality."""
    
    def test_get_input_required_args(self):
        """Test get_input with required arguments."""
        args = [
            'https://test-server.example.com',
            '/path/to/script.xml',
            '--base_path', '/opt/scripts'
        ]
        inputs = get_input(args)
        
        assert inputs.server == 'https://test-server.example.com'
        assert inputs.input_file == '/path/to/script.xml'
        assert inputs.base_path == '/opt/scripts'
        assert inputs.debug is False

    def test_get_input_with_optional_args(self):
        """Test get_input with optional arguments."""
        args = [
            'https://test-server.example.com',
            '/path/to/script.json',
            '--base_path', '/opt/scripts',
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

    def test_detect_file_type_xml(self):
        """Test file type detection for XML files."""
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as f:
            f.write(b'<?xml version="1.0"?><root></root>')
            temp_file = f.name
        
        try:
            file_type = detect_file_type(temp_file)
            assert file_type == 'xml'
        finally:
            os.remove(temp_file)

    def test_detect_file_type_json(self):
        """Test file type detection for JSON files."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{"test": "data"}')
            temp_file = f.name
        
        try:
            file_type = detect_file_type(temp_file)
            assert file_type == 'json'
        finally:
            os.remove(temp_file)

    def test_detect_file_type_unknown(self):
        """Test file type detection for unknown files."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'plain text content')
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError):
                detect_file_type(temp_file)
        finally:
            os.remove(temp_file)

    def test_generate_hash(self):
        """Test hash generation for script files."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("#!/bin/bash\necho 'test script'")
            temp_file = f.name
        
        try:
            hash_value = generate_hash(temp_file)
            assert len(hash_value) == 64  # SHA256 hex length
            assert hash_value.isalnum()
        finally:
            os.remove(temp_file)

    def test_generate_hash_missing_file(self):
        """Test hash generation for missing file."""
        hash_value = generate_hash('/nonexistent/file.sh')
        assert hash_value == ""

    def test_compare_and_log_differences(self):
        """Test the comparison and logging of generated vs provided values."""
        # Test when values match
        result = compare_and_log_differences('test_script', 'hash', 'abc123', 'abc123')
        assert result == 'abc123'
        
        # Test when values differ - should return generated value
        result = compare_and_log_differences('test_script', 'hash', 'generated123', 'provided456')
        assert result == 'generated123'
        
        # Test when no provided value - should return generated value
        result = compare_and_log_differences('test_script', 'script_id', 'generated_id', None)
        assert result == 'generated_id'

    def test_generate_server_script_path(self):
        """Test server script path generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            script_file = os.path.join(temp_dir, 'test.sh')
            with open(script_file, 'w') as f:
                f.write('#!/bin/bash\necho test')
            
            # Test normal case - script under base path
            result = generate_server_script_path(script_file, temp_dir, temp_dir)
            assert result == 'test.sh'
            
            # Test with subdirectory structure
            sub_dir = os.path.join(temp_dir, 'scripts')
            os.makedirs(sub_dir)
            sub_script = os.path.join(sub_dir, 'subscript.sh')
            with open(sub_script, 'w') as f:
                f.write('#!/bin/bash\necho sub')
            
            result = generate_server_script_path(sub_script, temp_dir, temp_dir)
            assert result == 'scripts/subscript.sh'

    def test_parse_custom_script_xml(self, temp_custom_script_xml):
        """Test parsing of comprehensive custom script XML file."""
        xml_dir = os.path.dirname(temp_custom_script_xml)
        with patch.dict(os.environ, {'PWD': xml_dir}):
            script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, xml_dir)
        
        # Test basic script attributes
        assert script_data['script_name'] == 'comprehensive_test_script'
        assert script_data['description'] == 'Comprehensive test script with all field types'
        # Hash is generated from actual file, not hardcoded XML value
        assert len(script_data['hash']) == 64  # SHA256 hex length
        assert 'hash' in script_data
        
        # Test input fields - should have multiple types
        assert len(script_data['inputs']) == 7  # 7 different input field types
        
        # Find specific input fields by name
        input_fields = {field['name']: field for field in script_data['inputs']}
        
        # Test integer input
        assert 'integer_param' in input_fields
        int_field = input_fields['integer_param']
        assert int_field['type'] == 'INT'
        assert int_field['phase'] == 'EXECUTION'
        assert int_field['input_required'] == 'YES'
        assert int_field['default_value'] == '10'
        assert int_field['display_name'] == 'Integer Parameter'
        
        # Test string input
        assert 'string_param' in input_fields
        str_field = input_fields['string_param']
        assert str_field['type'] == 'STRING'
        assert str_field['phase'] == 'AUTHORING'
        assert str_field['input_required'] == 'NO'
        
        # Test enum input with enumerations
        assert 'enum_param' in input_fields
        enum_field = input_fields['enum_param']
        assert enum_field['type'] == 'ENUM'
        assert 'enumerations' in enum_field
        assert len(enum_field['enumerations']) == 3
        enum_values = [e['symbol'] for e in enum_field['enumerations']]
        assert 'OPTION_A' in enum_values
        assert 'OPTION_B' in enum_values
        assert 'OPTION_C' in enum_values
        
        # Test float input
        assert 'float_param' in input_fields
        float_field = input_fields['float_param']
        assert float_field['type'] == 'FLOAT'
        assert float_field['default_value'] == '3.14'
        
        # Test boolean input
        assert 'bool_param' in input_fields
        bool_field = input_fields['bool_param']
        assert bool_field['type'] == 'BOOL'
        
        # Test specialized Ingenium types
        assert 'flight_cmd_param' in input_fields
        cmd_field = input_fields['flight_cmd_param']
        assert cmd_field['type'] == 'FLIGHT_COMMAND'
        
        # Test output fields - should have multiple types
        assert len(script_data['outputs']) == 5
        output_fields = {field['name']: field for field in script_data['outputs']}
        
        # Test different output types
        assert 'result_code' in output_fields
        assert output_fields['result_code']['type'] == 'INT'
        assert 'output_file' in output_fields
        assert output_fields['output_file']['type'] == 'FILE'
        assert 'chart_image' in output_fields
        assert output_fields['chart_image']['type'] == 'IMAGE'
        assert 'time_series' in output_fields
        assert output_fields['time_series']['type'] == 'SERIES'
        
        # Test script entries
        assert len(script_data['entries']) == 1
        entry = script_data['entries'][0]
        assert entry['display_field'] == 'entry_result'
        
        # Test entry inputs
        assert len(entry['entry_inputs']) == 2
        entry_inputs = {field['name']: field for field in entry['entry_inputs']}
        assert 'entry_input1' in entry_inputs
        assert 'entry_input2' in entry_inputs
        assert entry_inputs['entry_input2']['default_value'] == '5'
        
        # Test entry outputs
        assert len(entry['entry_outputs']) == 2
        entry_outputs = {field['name']: field for field in entry['entry_outputs']}
        assert 'entry_result' in entry_outputs
        assert 'entry_status' in entry_outputs
        
        # Test output array
        assert 'output_array' in script_data
        output_array = script_data['output_array']
        assert output_array['name'] == 'results_table'
        assert output_array['max_entries'] == 100
        assert output_array['description'] == 'Table of processing results'
        
        # Test output array fields
        assert len(output_array['outputs']) == 5
        array_fields = {field['name']: field for field in output_array['outputs']}
        assert 'item_id' in array_fields
        assert array_fields['item_id']['visible'] == 'YES'
        assert 'details' in array_fields
        assert array_fields['details']['visible'] == 'NO'
        
        # Test advanced layout exists
        assert len(script_data['layout']) > 0

    def test_parse_custom_script_json(self, temp_custom_script_json):
        """Test parsing of custom script JSON file with comprehensive content."""
        json_dir = os.path.dirname(temp_custom_script_json)
        script_data, script_id = parse_custom_script_json(temp_custom_script_json, json_dir)
        
        # Test basic script attributes
        assert script_data['script_name'] == 'json_test_script'
        assert script_data['description'] == 'Test script defined in JSON format'
        # Hash is generated from actual file, not hardcoded JSON value
        assert len(script_data['hash']) == 64  # SHA256 hex length
        assert script_data['status'] == 'ACTIVE'
        
        # Test inputs
        assert len(script_data['inputs']) == 3
        input_fields = {field['name']: field for field in script_data['inputs']}
        
        # Test string input
        assert 'input_string' in input_fields
        str_input = input_fields['input_string']
        assert str_input['type'] == 'STRING'
        assert str_input['input_required'] == 'YES'
        assert str_input['default_value'] == 'test_value'
        
        # Test integer input
        assert 'input_number' in input_fields
        int_input = input_fields['input_number']
        assert int_input['type'] == 'INT'
        assert int_input['phase'] == 'AUTHORING'
        assert int_input['default_value'] == '42'
        
        # Test enum input with enumerations
        assert 'input_enum' in input_fields
        enum_input = input_fields['input_enum']
        assert enum_input['type'] == 'ENUM'
        assert 'enumerations' in enum_input
        assert len(enum_input['enumerations']) == 3
        enum_values = [e['symbol'] for e in enum_input['enumerations']]
        assert 'OPTION1' in enum_values
        assert 'OPTION2' in enum_values
        assert 'OPTION3' in enum_values
        
        # Test outputs
        assert len(script_data['outputs']) == 3
        output_fields = {field['name']: field for field in script_data['outputs']}
        
        assert 'output_result' in output_fields
        assert output_fields['output_result']['type'] == 'STRING'
        assert 'output_code' in output_fields
        assert output_fields['output_code']['type'] == 'INT'
        assert 'output_file' in output_fields
        assert output_fields['output_file']['type'] == 'FILE'

    def test_parse_simple_custom_script_xml(self, temp_simple_custom_script_xml):
        """Test parsing of simple custom script XML file."""
        xml_dir = os.path.dirname(temp_simple_custom_script_xml)
        script_data, script_id = parse_custom_script_xml(temp_simple_custom_script_xml, xml_dir)
        
        # Test basic attributes
        assert script_data['script_name'] == 'simple_script'
        assert script_data['description'] == 'Simple test script'
        # Hash is generated from actual file, not hardcoded XML value
        assert len(script_data['hash']) == 64  # SHA256 hex length
        
        # Test simple structure
        assert len(script_data['inputs']) == 1
        assert len(script_data['outputs']) == 1
        
        # Test input field
        input_field = script_data['inputs'][0]
        assert input_field['name'] == 'message'
        assert input_field['type'] == 'STRING'
        assert input_field['phase'] == 'EXECUTION'
        assert input_field['input_required'] == 'YES'
        
        # Test output field
        output_field = script_data['outputs'][0]
        assert output_field['name'] == 'result'
        assert output_field['type'] == 'STRING'

    def test_parse_custom_script_with_entries(self, temp_custom_script_with_entries):
        """Test parsing of custom script XML with multiple script entries."""
        xml_dir = os.path.dirname(temp_custom_script_with_entries)
        script_data, script_id = parse_custom_script_xml(temp_custom_script_with_entries, xml_dir)
        
        # Test basic attributes
        assert script_data['script_name'] == 'multi_entry_script'
        assert script_data['description'] == 'Script with multiple entry processing'
        # Verify hash is generated correctly
        assert len(script_data['hash']) == 64  # SHA256 hex length
        
        # Test global inputs
        assert len(script_data['inputs']) == 1
        global_input = script_data['inputs'][0]
        assert global_input['name'] == 'global_config'
        assert global_input['phase'] == 'AUTHORING'
        assert global_input['default_value'] == 'default_config'
        
        # Test script entries
        assert len(script_data['entries']) == 1
        
        # Test first entry
        entry1 = script_data['entries'][0]
        assert entry1['display_field'] == 'entry1_result'
        assert len(entry1['entry_inputs']) == 2
        assert len(entry1['entry_outputs']) == 2
        
        # Check first entry has output array
        assert 'entry_output_array' in entry1
        output_array = entry1['entry_output_array']
        assert output_array['name'] == 'entry1_details'
        assert output_array['max_entries'] == 10
        assert len(output_array['outputs']) == 2
        
        # Test global outputs
        assert len(script_data['outputs']) == 2
        output_fields = {field['name']: field for field in script_data['outputs']}
        assert 'final_status' in output_fields
        assert 'total_entries_processed' in output_fields

    def test_parse_custom_script_all_input_types(self, temp_custom_script_xml):
        """Test parsing of all supported input field types."""
        script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, '/opt/scripts')
        
        input_fields = {field['name']: field for field in script_data['inputs']}
        
        # Test all input types from schema
        expected_types = {
            'integer_param': 'INT',
            'string_param': 'STRING', 
            'float_param': 'FLOAT',
            'bool_param': 'BOOL',
            'enum_param': 'ENUM',
            'time_param': 'TIME',
            'flight_cmd_param': 'FLIGHT_COMMAND'
        }
        
        for field_name, expected_type in expected_types.items():
            assert field_name in input_fields
            assert input_fields[field_name]['type'] == expected_type

    def test_parse_custom_script_all_output_types(self, temp_custom_script_xml):
        """Test parsing of all supported output field types."""
        script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, '/opt/scripts')
        
        output_fields = {field['name']: field for field in script_data['outputs']}
        
        # Test all output types from schema
        expected_types = {
            'result_code': 'INT',
            'result_message': 'STRING',
            'output_file': 'FILE',
            'chart_image': 'IMAGE',
            'time_series': 'SERIES'
        }
        
        for field_name, expected_type in expected_types.items():
            assert field_name in output_fields
            assert output_fields[field_name]['type'] == expected_type

    def test_parse_custom_script_phase_validation(self, temp_custom_script_xml):
        """Test that input field phases are correctly parsed."""
        xml_dir = os.path.dirname(temp_custom_script_xml)
        script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, xml_dir)
        
        input_fields = {field['name']: field for field in script_data['inputs']}
        
        # Test different phases
        assert input_fields['integer_param']['phase'] == 'EXECUTION'
        assert input_fields['string_param']['phase'] == 'AUTHORING'
        assert input_fields['enum_param']['phase'] == 'AUTHORING'

    def test_parse_custom_script_required_validation(self, temp_custom_script_xml):
        """Test that input field required flags are correctly parsed."""
        xml_dir = os.path.dirname(temp_custom_script_xml)
        script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, xml_dir)
        
        input_fields = {field['name']: field for field in script_data['inputs']}
        
        # Test required vs optional fields
        assert input_fields['integer_param']['input_required'] == 'YES'
        assert input_fields['string_param']['input_required'] == 'NO'
        assert input_fields['bool_param']['input_required'] == 'NO'

    def test_parse_custom_script_default_values(self, temp_custom_script_xml):
        """Test that default values are correctly parsed."""
        xml_dir = os.path.dirname(temp_custom_script_xml)
        script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, xml_dir)
        
        input_fields = {field['name']: field for field in script_data['inputs']}
        
        # Test various default value types
        assert input_fields['integer_param']['default_value'] == '10'
        assert input_fields['float_param']['default_value'] == '3.14'
        assert input_fields['enum_param']['default_value'] == 'OPTION_A'
        assert input_fields['string_param']['default_value'] == 'default_value'

    def test_validate_script_data_valid(self):
        """Test validation of valid script data."""
        script_data = {
            'script_name': 'valid_script',
            'script_path': 'scripts/valid_script.sh',
            'description': 'Valid test script',
            'is_command': 'false'
        }
        
        assert validate_script_data(script_data) is True

    def test_validate_script_data_missing_fields(self):
        """Test validation of script data with missing required fields."""
        script_data = {
            'script_name': 'test_script',
            # Missing required fields
        }
        
        assert validate_script_data(script_data) is False

    def test_validate_script_data_invalid_name(self):
        """Test validation of script data with invalid script name."""
        script_data = {
            'script_name': 'invalid@script#name',
            'script_path': 'scripts/script.sh',
            'description': 'Test script',
            'script_id': 'test_id'
        }
        
        assert validate_script_data(script_data) is False

    @patch('ing_lib.common.authenticate')
    @patch('getpass.getpass')
    @patch('getpass.getuser')
    @patch('apps.ProjConfigCreateUpdateCS.update_custom_script')
    @patch('apps.ProjConfigCreateUpdateCS.get_custom_scripts')
    @patch('apps.ProjConfigCreateUpdateCS.create_custom_script')
    @patch('os.path.exists')
    def test_main_create_new_script(self, mock_exists, mock_create, mock_get_scripts,
                                   mock_update, mock_getuser, mock_getpass, mock_auth,
                                   temp_custom_script_xml):
        """Test main execution for creating a new script."""
        mock_auth.return_value = True
        mock_getuser.return_value = 'test_user'
        mock_getpass.return_value = 'test_password'
        mock_get_scripts.return_value = []  # No existing scripts
        mock_exists.return_value = True
        mock_update.return_value = {'script_name': 'comprehensive_test_script', 'script_id': 'dGVzdF9zY3JpcHQuc2g='}
        
        xml_dir = os.path.dirname(temp_custom_script_xml)
        args = [
            'https://test-server.example.com',
            temp_custom_script_xml,
            '--base_path', xml_dir
        ]
        
        main(args)
        
        # Verify update was called (since XML has script_id)
        mock_update.assert_called_once()

    @patch('ing_lib.common.authenticate')
    @patch('getpass.getpass')
    @patch('getpass.getuser')
    @patch('apps.ProjConfigCreateUpdateCS.get_custom_scripts')
    @patch('apps.ProjConfigCreateUpdateCS.update_custom_script')
    @patch('os.path.exists')
    def test_main_update_existing_script(self, mock_exists, mock_update, mock_get_scripts,
                                        mock_getuser, mock_getpass, mock_auth,
                                        temp_custom_script_xml):
        """Test main execution for updating an existing script."""
        mock_auth.return_value = True
        mock_getuser.return_value = 'test_user'
        mock_getpass.return_value = 'test_password'
        mock_exists.return_value = True
        
        # Mock existing script with same name
        with patch('apps.ProjConfigCreateUpdateCS.parse_custom_script_xml') as mock_parse:
            mock_parse.return_value = ({
                'script_name': 'test_script',
                'script_path': 'test_script.sh',
                'description': 'Test script',
                'is_command': 'false',
                'hash': 'a'*64,  # Valid SHA256 hash format
                'inputs': [],
                'outputs': []
            }, 'dGVzdF9zY3JpcHQuc2g=')
            
            mock_get_scripts.return_value = [{'script_name': 'test_script'}]
            
            xml_dir = os.path.dirname(temp_custom_script_xml)
            args = [
                'https://test-server.example.com',
                temp_custom_script_xml,
                '--base_path', xml_dir
            ]
            
            main(args)
            
            # Verify update was called
            mock_update.assert_called_once()

    @patch('ing_lib.common.authenticate')
    def test_main_authentication_failure(self, mock_auth):
        """Test main execution with authentication failure."""
        mock_auth.return_value = False
        
        args = [
            'https://test-server.example.com',
            '/path/to/script.xml',
            '--base_path', '/opt/scripts'
        ]
        
        with pytest.raises(Exception):  # Should raise IngeniumLibError
            main(args)

    @patch('os.path.exists')
    def test_main_missing_base_path(self, mock_exists):
        """Test main execution with missing base path."""
        mock_exists.return_value = False
        
        args = [
            'https://test-server.example.com',
            '/path/to/script.xml'
            # No base_path provided and no environment variable
        ]
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                main(args)

    @patch('os.path.exists')
    def test_main_missing_input_file(self, mock_exists):
        """Test main execution with missing input file."""
        mock_exists.return_value = False
        
        args = [
            'https://test-server.example.com',
            '/nonexistent/script.xml',
            '--base_path', '/opt/scripts'
        ]
        
        with pytest.raises(Exception):  # Should raise IngeniumLibError
            main(args)

    @patch('os.path.exists')
    def test_main_with_environment_base_path(self, mock_exists):
        """Test main execution using environment variable for base path."""
        mock_exists.return_value = True
        
        with patch.dict(os.environ, {'ING_CS_BASE_PATH': '/env/scripts'}), \
             patch('common.authenticate', return_value=False):
            
            args = [
                'https://test-server.example.com',
                '/path/to/script.xml'
                # No --base_path, should use environment variable
            ]
            
            try:
                main(args)
            except:
                pass  # We expect authentication to fail, just testing path resolution
            
            # The main function should have recognized the environment variable

    def test_parse_xml_missing_script_file(self):
        """Test XML parsing when script file is missing."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <custom_script script_name="test_script" script_path="missing_script.sh" description="Test script">
    </custom_script>
</custom-scripts>"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_file = os.path.join(temp_dir, 'test.xml')
            with open(xml_file, 'w') as f:
                f.write(xml_content)
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                parse_custom_script_xml(xml_file, '/opt/scripts')

    def test_parse_json_invalid_format(self):
        """Test JSON parsing with invalid format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(["array", "instead", "of", "object"], f)
            temp_file = f.name
        
        try:
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                parse_custom_script_json(temp_file, '/opt/scripts')
        finally:
            os.remove(temp_file)

    def test_parse_custom_script_xml_invalid_root(self):
        """Test XML parsing with invalid root element."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<invalid-root>
    <custom_script script_name="test" script_path="test.sh" description="Test">
    </custom_script>
</invalid-root>"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_file = os.path.join(temp_dir, 'invalid.xml')
            with open(xml_file, 'w') as f:
                f.write(xml_content)
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                parse_custom_script_xml(xml_file, '/opt/scripts')

    def test_parse_custom_script_xml_multiple_scripts(self):
        """Test XML parsing with multiple custom script elements."""
        script_content = "#!/bin/bash\necho 'test'"
        
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <header mission_name="TEST"/>
    <custom_script script_name="script1" script_path="test.sh" description="First script">
    </custom_script>
    <custom_script script_name="script2" script_path="test.sh" description="Second script">
    </custom_script>
</custom-scripts>"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_file = os.path.join(temp_dir, 'multiple.xml')
            with open(xml_file, 'w') as f:
                f.write(xml_content)
            
            script_file = os.path.join(temp_dir, 'test.sh')
            with open(script_file, 'w') as f:
                f.write(script_content)
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError for multiple scripts
                parse_custom_script_xml(xml_file, '/opt/scripts')

    def test_parse_custom_script_xml_missing_required_attributes(self):
        """Test XML parsing with missing required attributes."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <header mission_name="TEST"/>
    <custom_script script_path="test.sh">
        <!-- Missing script_name and description -->
    </custom_script>
</custom-scripts>"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_file = os.path.join(temp_dir, 'missing_attrs.xml')
            with open(xml_file, 'w') as f:
                f.write(xml_content)
            
            script_file = os.path.join(temp_dir, 'test.sh')
            with open(script_file, 'w') as f:
                f.write("#!/bin/bash\necho 'test'")
            
            with pytest.raises(Exception):  # Should raise IngeniumLibError
                parse_custom_script_xml(xml_file, '/opt/scripts')

    def test_parse_custom_script_display_name_handling(self, temp_custom_script_xml):
        """Test that display_name attributes are correctly parsed."""
        script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, '/opt/scripts')
        
        input_fields = {field['name']: field for field in script_data['inputs']}
        output_fields = {field['name']: field for field in script_data['outputs']}
        
        # Test that display_name is parsed when present
        assert 'display_name' in input_fields['integer_param']
        assert input_fields['integer_param']['display_name'] == 'Integer Parameter'
        
        assert 'display_name' in output_fields['result_code']
        assert output_fields['result_code']['display_name'] == 'Result Code'
        
        # Test that missing display_name is handled gracefully
        assert 'display_name' not in input_fields['float_param']

    def test_validate_script_data_complex_validation(self, temp_custom_script_xml):
        """Test validation of complex script data."""
        script_data, script_id = parse_custom_script_xml(temp_custom_script_xml, '/opt/scripts')
        
        # Should pass validation
        assert validate_script_data(script_data) is True
        
        # Test with missing field
        invalid_data = script_data.copy()
        del invalid_data['script_name']
        assert validate_script_data(invalid_data) is False

    @patch('ing_lib.common.authenticate')
    @patch('getpass.getpass')
    @patch('getpass.getuser')
    @patch('apps.ProjConfigCreateUpdateCS.update_custom_script')
    @patch('apps.ProjConfigCreateUpdateCS.get_custom_scripts')
    @patch('apps.ProjConfigCreateUpdateCS.create_custom_script')
    @patch('os.path.exists')
    def test_main_comprehensive_workflow(self, mock_exists, mock_create, mock_get_scripts,
                                        mock_update, mock_getuser, mock_getpass, mock_auth,
                                        temp_custom_script_xml):
        """Test main execution with comprehensive custom script parsing."""
        mock_auth.return_value = True
        mock_getuser.return_value = 'test_user'
        mock_getpass.return_value = 'test_password'
        mock_get_scripts.return_value = []  # No existing scripts
        mock_exists.return_value = True
        mock_update.return_value = {'script_name': 'comprehensive_test_script', 'script_id': 'dGVzdF9zY3JpcHQuc2g='}
        
        xml_dir = os.path.dirname(temp_custom_script_xml)
        args = [
            'https://test-server.example.com',
            temp_custom_script_xml,
            '--base_path', xml_dir
        ]
        
        main(args)
        
        # Verify update was called (since XML has script_id)
        mock_update.assert_called_once()
        
        # Verify the script data passed to update function
        call_args = mock_update.call_args
        script_id = call_args[0][1]  # Second argument should be the script_id
        script_data = call_args[0][2]  # Third argument should be the script data
        
        assert script_id == 'dGVzdF9zY3JpcHQuc2g='
        assert script_data['script_name'] == 'comprehensive_test_script'
        assert len(script_data['inputs']) == 7
        assert len(script_data['outputs']) == 5
        assert len(script_data['entries']) == 1
        assert 'output_array' in script_data 

class TestAdvancedLayoutValidation:
    """Test class for advanced layout validation functionality."""

    def test_validate_advanced_layout_valid(self):
        """Tests a completely valid advanced layout configuration."""
        custom_script = {
            'inputs': [{'name': 'main_input'}],
            'outputs': [{'name': 'main_output'}],
            'output_array': {'outputs': [{'name': 'table_output_1'}]},
            'entries': [{
                'entry_inputs': [{'name': 'entry_input'}],
                'entry_outputs': [{'name': 'entry_output'}],
                'entry_output_array': {'outputs': [{'name': 'entry_table_output_1'}]}
            }],
            'layout': [
                {
                    'section_name': 'Standard Section',
                    'entry': 'FALSE',
                    'content': {
                        'contentlayout': [
                            {'layout_type': 'FIELD', 'field_name': 'main_input', 'layout': {'row': 0, 'column': 0}},
                            {'layout_type': 'DISPLAY', 'template': {'template': 'Value: {main_output}'}, 'layout': {'row': 0, 'column': 1}},
                            {'layout_type': 'TABLE', 'table_name': 'Main Table',
                             'table_column': [{'template': {'template': '{table_output_1}'}, 'width': 6}],
                             'layout': {'row': 1, 'column': 0, 'width': 12}}
                        ]
                    }
                },
                {
                    'section_name': 'Entry Section',
                    'entry': 'TRUE',
                    'content': {
                        'contentlayout': [
                            {'layout_type': 'FIELD', 'field_name': 'entry_input', 'layout': {'row': 0, 'column': 0}},
                            {'layout_type': 'DISPLAY', 'template': {'template': 'Value: {entry_output}'}, 'layout': {'row': 0, 'column': 1}},
                            {'layout_type': 'TABLE', 'table_name': 'Entry Table',
                             'table_column': [{'template': {'template': '{entry_table_output_1}'}, 'width': 12}],
                             'layout': {'row': 1, 'column': 0, 'width': 12}}
                        ]
                    }
                }
            ]
        }
        assert validate_advanced_layout(custom_script) is True

    def test_validate_advanced_layout_overlapping(self):
        """Tests detection of overlapping layout elements."""
        custom_script = {
            'layout': [{
                'content': {
                    'contentlayout': [
                        {'layout_type': 'FIELD', 'field_name': 'f1', 'layout': {'row': 0, 'column': 0, 'width': 2, 'height': 1}},
                        {'layout_type': 'FIELD', 'field_name': 'f2', 'layout': {'row': 0, 'column': 1, 'width': 1, 'height': 1}}
                    ]
                }
            }],
            'inputs': [{'name': 'f1'}, {'name': 'f2'}]
        }
        assert validate_advanced_layout(custom_script) is False

    def test_validate_advanced_layout_invalid_display_template(self):
        """Tests validation of DISPLAY template with undefined variables."""
        custom_script = {
            'inputs': [{'name': 'real_input'}],
            'layout': [{
                'content': {
                    'contentlayout': [
                        {'layout_type': 'DISPLAY', 'template': {'template': 'Value: {fake_input}'}, 'layout': {'row': 0, 'column': 0}}
                    ]
                }
            }]
        }
        assert validate_advanced_layout(custom_script) is False

    def test_validate_advanced_layout_invalid_table_template(self):
        """Tests validation of TABLE template with undefined variables."""
        custom_script = {
            'output_array': {'outputs': [{'name': 'real_output'}]},
            'layout': [{
                'content': {
                    'contentlayout': [
                        {'layout_type': 'TABLE',
                         'table_column': [{'template': {'template': '{fake_output}'}}],
                         'layout': {'row': 0, 'column': 0}}
                    ]
                }
            }]
        }
        assert validate_advanced_layout(custom_script) is False

    def test_validate_advanced_layout_table_width_exceeded(self):
        """Tests validation of TABLE column widths exceeding 12."""
        custom_script = {
            'output_array': {'outputs': [{'name': 'col1'}, {'name': 'col2'}]},
            'layout': [{
                'content': {
                    'contentlayout': [
                        {'layout_type': 'TABLE',
                         'table_column': [
                             {'template': {'template': '{col1}'}, 'width': 7},
                             {'template': {'template': '{col2}'}, 'width': 6}
                         ],
                         'layout': {'row': 0, 'column': 0}}
                    ]
                }
            }]
        }
        assert validate_advanced_layout(custom_script) is False

    def test_validate_advanced_layout_undefined_field_reference(self):
        """Tests validation of layout referencing an undefined field_name."""
        custom_script = {
            'inputs': [{'name': 'real_input'}],
            'layout': [{
                'content': {
                    'contentlayout': [
                        {'layout_type': 'FIELD', 'field_name': 'fake_input', 'layout': {'row': 0, 'column': 0}}
                    ]
                }
            }]
        }
        assert validate_advanced_layout(custom_script) is False

    def test_validate_advanced_layout_entry_section_invalid_template(self):
        """Tests validation of entry section with invalid template variables."""
        custom_script = {
            'entries': [{
                'entry_inputs': [{'name': 'real_entry_input'}]
            }],
            'layout': [{
                'entry': 'TRUE',
                'content': {
                    'contentlayout': [
                        {'layout_type': 'DISPLAY', 'template': {'template': '{fake_entry_input}'}, 'layout': {'row': 0, 'column': 0}}
                    ]
                }
            }]
        }
        assert validate_advanced_layout(custom_script) is False

    def test_validate_advanced_layout_entry_section_invalid_table_template(self):
        """Tests validation of entry section table with invalid template variables."""
        custom_script = {
            'entries': [{
                'entry_output_array': {'outputs': [{'name': 'real_entry_output'}]}
            }],
            'layout': [{
                'entry': 'TRUE',
                'content': {
                    'contentlayout': [
                        {'layout_type': 'TABLE',
                         'table_column': [{'template': {'template': '{fake_entry_output}'}}],
                         'layout': {'row': 0, 'column': 0}}
                    ]
                }
            }]
        }
        assert validate_advanced_layout(custom_script) is False
