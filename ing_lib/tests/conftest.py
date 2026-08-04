"""
Pytest configuration file with common fixtures and test setup.
"""

import pytest
import tempfile
import os
import json
import contextlib
from unittest.mock import MagicMock, patch, mock_open
import sys
import datetime

# Add the parent directory to Python path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def mock_server():
    """Mock Ingenium server URL for testing."""
    return "https://test-server.example.com"

@pytest.fixture
def mock_authentication():
    """Mock the authentication function to always return True."""
    with patch('common.authenticate', return_value=True) as mock_auth:
        yield mock_auth

@pytest.fixture
def mock_ssl_verify():
    """Mock SSL verification setting."""
    with patch('common.ssl_verify', True):
        yield

@pytest.fixture
def mock_common_globals():
    """Mock common module global variables."""
    mock_store = MagicMock()
    mock_store.get.side_effect = lambda key: {
        'token': 'Bearer mock_token_12345',
        'refresh_time': datetime.datetime.now(datetime.timezone.utc),
        'ssl_verify': True
    }.get(key)
    
    with patch('common.refresh_auth', return_value=True), \
         patch('common._store', mock_store), \
         patch('common.get_ssl_verify', return_value=True), \
         patch('common.get_token', return_value='Bearer mock_token_12345'), \
         patch('common.get_refresh_time', return_value=datetime.datetime.now(datetime.timezone.utc)), \
         patch('common._stale_token', return_value=False):
        yield

@pytest.fixture
def mock_project_config_get_functions():
    """Mock all project_config GET functions."""
    # Mock data for various endpoints
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
    
    mock_dictionary_content = [
        {'command_stem': 'TEST_CMD', 'cmd_description': 'Test command'},
        {'command_stem': 'ANOTHER_CMD', 'cmd_description': 'Another test command'}
    ]
    
    mock_vis = [
        {'vi_id': 'test_vi_1', 'name': 'Test VI 1'},
        {'vi_id': 'test_vi_2', 'name': 'Test VI 2'}
    ]
    
    mock_custom_scripts = [
        {'script_id': 'test_script_1', 'script_name': 'Test Script 1'},
        {'script_id': 'test_script_2', 'script_name': 'Test Script 2'}
    ]

    with patch('project_config.get_dictionary_versions', return_value=mock_versions), \
         patch('project_config.get_dictionary', return_value=mock_dictionary_content), \
         patch('project_config.get_dictionary_element', return_value=mock_dictionary_content[0]), \
         patch('project_config.get_custom_scripts', return_value=mock_custom_scripts), \
         patch('project_config.get_vnv_vis', return_value=mock_vis):
        yield

@pytest.fixture
def mock_project_config_create_functions():
    """Mock all project_config CREATE functions."""
    with patch('project_config.create_dictionary_version', return_value={'status': 'success'}), \
         patch('project_config.create_dictionary_content', return_value={'status': 'success'}), \
         patch('project_config.create_custom_script', return_value={'status': 'success'}), \
         patch('project_config.create_vnv_vis', return_value={'status': 'success'}), \
         patch('project_config.update_custom_script', return_value={'status': 'success'}):
        yield

@pytest.fixture
def mock_project_config_delete_functions():
    """Mock all project_config DELETE functions."""
    with patch('project_config.delete_dictionary_version', return_value=None), \
         patch('project_config.delete_vnv_vi', return_value=None), \
         patch('project_config.delete_custom_script', return_value=None):
        yield

@pytest.fixture
def mock_http_requests():
    """Mock all HTTP requests."""
    # Create a mock response that works for most cases
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"access_token": "mock_token_12345"}'
    mock_response.json.return_value = []
    mock_response.headers = {'x-total-count': '0'}
    
    with patch('urllib3.disable_warnings'), \
         patch('requests.get', return_value=mock_response), \
         patch('requests.post', return_value=mock_response), \
         patch('requests.patch', return_value=mock_response), \
         patch('requests.delete', return_value=mock_response):
        yield

@pytest.fixture
def mock_common_http_functions():
    """Mock common module HTTP functions."""
    # Mock data that matches what get_source_dictionaries expects
    mock_dict_versions = [
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
    
    mock_dictionary_content = [
        {'command_stem': 'TEST_CMD', 'cmd_description': 'Test command'},
        {'command_stem': 'ANOTHER_CMD', 'cmd_description': 'Another test command'}
    ]
    
    mock_vis = [
        {'vi_id': 'test_vi_1', 'name': 'Test VI 1'},
        {'vi_id': 'test_vi_2', 'name': 'Test VI 2'}
    ]
    
    mock_custom_scripts = [
        {'script_id': 'test_script_1', 'script_name': 'Test Script 1'},
        {'script_id': 'test_script_2', 'script_name': 'Test Script 2'}
    ]

    def mock_paginated_side_effect(*args, **kwargs):
        """Return appropriate mock data based on the endpoint being called."""
        if len(args) > 0:
            endpoint = args[0]
            if 'dictionaries/flight/versions' in endpoint or 'dictionaries/sse/versions' in endpoint:
                return mock_dict_versions
            elif 'vis' in endpoint:
                return mock_vis
            elif 'custom_scripts' in endpoint:
                return mock_custom_scripts
        return []

    def mock_get_side_effect(*args, **kwargs):
        """Return appropriate mock data based on the endpoint being called."""
        if len(args) > 0:
            endpoint = args[0]
            if 'dictionaries' in endpoint and ('cmds' in endpoint or 'channels' in endpoint or 
                                             'evrs' in endpoint or 'mil1553' in endpoint):
                return mock_dictionary_content
        return {}

    with patch('common.ingenium_rest_get_paginated', side_effect=mock_paginated_side_effect), \
         patch('common.ingenium_rest_get', side_effect=mock_get_side_effect), \
         patch('common.response_handler', return_value=True):
        yield

@pytest.fixture
def comprehensive_server_mock(mock_authentication, mock_common_globals, 
                            mock_project_config_get_functions,
                            mock_project_config_create_functions,
                            mock_project_config_delete_functions,
                            mock_http_requests, mock_common_http_functions):
    """
    Comprehensive mock for all server communication functions.
    This fixture combines all the individual mocking fixtures.
    """
    yield

@pytest.fixture
def mock_empty_server():
    """
    Mock for server with no existing data (empty dictionaries, VIs, scripts).
    Useful for testing clear operations and restoring to empty servers.
    """
    # Use ExitStack to manage multiple context managers
    with contextlib.ExitStack() as stack:
        # Authentication and globals
        stack.enter_context(patch('common.authenticate', return_value=True))
        stack.enter_context(patch('common.ssl_verify', True))
        stack.enter_context(patch('common.token', 'mock_token_12345'))
        
        # GET functions - return empty data
        stack.enter_context(patch('project_config.get_dictionary_versions', return_value=[]))
        stack.enter_context(patch('project_config.get_dictionary', return_value=[]))
        stack.enter_context(patch('project_config.get_dictionary_element', return_value={}))
        stack.enter_context(patch('project_config.get_custom_scripts', return_value=[]))
        stack.enter_context(patch('project_config.get_vnv_vis', return_value=[]))
        
        # CREATE functions
        stack.enter_context(patch('project_config.create_dictionary_version', return_value={'status': 'success'}))
        stack.enter_context(patch('project_config.create_dictionary_content', return_value={'status': 'success'}))
        stack.enter_context(patch('project_config.create_custom_script', return_value={'status': 'success'}))
        stack.enter_context(patch('project_config.create_vnv_vis', return_value={'status': 'success'}))
        stack.enter_context(patch('project_config.update_custom_script', return_value={'status': 'success'}))
        
        # DELETE functions
        stack.enter_context(patch('project_config.delete_dictionary_version', return_value=None))
        stack.enter_context(patch('project_config.delete_vnv_vi', return_value=None))
        stack.enter_context(patch('project_config.delete_custom_script', return_value=None))
        
        # HTTP requests
        stack.enter_context(patch('urllib3.disable_warnings'))
        stack.enter_context(patch('requests.get'))
        stack.enter_context(patch('requests.post'))
        stack.enter_context(patch('requests.patch'))
        stack.enter_context(patch('requests.delete'))
        
        yield

@pytest.fixture 
def mock_user_input():
    """Mock user input and password functions."""
    with patch('getpass.getpass', return_value='test_password'), \
         patch('getpass.getuser', return_value='test_user'), \
         patch('builtins.input', return_value='yes'):
        yield

@pytest.fixture
def sample_backup_data():
    """Sample backup data structure for testing."""
    return {
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
                'cmds': [{'command_stem': 'TEST_CMD', 'cmd_description': 'Test command'}],
                'channels': [{'channel_name': 'TEST_CH', 'description': 'Test channel'}],
                'evrs': [{'evr_name': 'TEST_EVR', 'evr_message': 'Test EVR'}],
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
        'vis': [],
        'custom_scripts': []
    }

@pytest.fixture
def temp_backup_file(sample_backup_data):
    """Create a temporary backup file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_backup_data, f)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)

@pytest.fixture
def temp_xml_file():
    """Create a temporary XML file for testing."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<command_dictionary>
    <header>
        <mission_name>TEST_MISSION</mission_name>
        <spacecraft_ids>
            <spacecraft_id>999</spacecraft_id>
        </spacecraft_ids>
        <version>1.0</version>
        <build_id>TEST_BUILD_001</build_id>
        <description>Test command dictionary for unit tests</description>
    </header>
    <enum_definitions>
        <enum_table name="ON_OFF_TABLE">
            <enum symbol="OFF" numeric="0"/>
            <enum symbol="ON" numeric="1"/>
        </enum_table>
        <enum_table name="MODE_TABLE">
            <enum symbol="STANDBY" numeric="0"/>
            <enum symbol="ACTIVE" numeric="1"/>
            <enum symbol="SAFE" numeric="2"/>
        </enum_table>
    </enum_definitions>
    <command_definitions>
        <fsw_command opcode="0x1001" stem="TEST_CMD" class="FSW">
            <arguments>
                <int_argument name="param1" bit_length="32">
                    <description>Test integer parameter</description>
                </int_argument>
                <unsigned_argument name="param2" bit_length="16">
                    <description>Test unsigned parameter</description>
                </unsigned_argument>
                <enum_argument name="mode" bit_length="8" enum_name="MODE_TABLE">
                    <description>Operating mode selection</description>
                </enum_argument>
                <var_string_argument name="message" bit_length="64">
                    <description>Variable string message</description>
                </var_string_argument>
                <boolean_argument name="enable" bit_length="8">
                    <description>Enable flag</description>
                </boolean_argument>
            </arguments>
            <categories>
                <ops_category>SYSTEM</ops_category>
                <subsystem>POWER</subsystem>
                <module>BUS_CTRL</module>
            </categories>
            <description>Test FSW command with multiple argument types for comprehensive testing</description>
        </fsw_command>
        <fsw_command opcode="0x1002" stem="SIMPLE_CMD" class="FSW">
            <categories>
                <ops_category>TEST</ops_category>
            </categories>
            <description>Simple test command without arguments</description>
        </fsw_command>
        <hw_command opcode="0x2001" stem="HW_RESET">
            <categories>
                <ops_category>HARDWARE</ops_category>
                <subsystem>POWER</subsystem>
            </categories>
            <description>Hardware reset command</description>
        </hw_command>
    </command_definitions>
</command_dictionary>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)

@pytest.fixture
def temp_custom_script_xml():
    """Create a temporary custom script XML file for testing with comprehensive schema coverage."""
    script_content = """#!/bin/bash
echo "Comprehensive test script for Ingenium"
echo "Processing parameters: $1 $2 $3"
# Generate test outputs
echo "result_value=42" > output.txt
echo "status=SUCCESS" >> output.txt
"""
    
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <header mission_name="TEST_MISSION"/>
    <custom_script script_name="comprehensive_test_script" 
                   script_path="test_script.sh" 
                   description="Comprehensive test script with all field types"
                   hash="abc123def456"
                   script_id="dGVzdF9zY3JpcHQuc2g="
                   is_command="false">
        
        <!-- Input fields covering all types -->
        <input_field name="integer_param" 
                     display_name="Integer Parameter"
                     description="Test integer input parameter" 
                     phase="EXECUTION" 
                     required="YES" 
                     type="INT"
                     default_value="10"/>
        
        <input_field name="string_param" 
                     display_name="String Parameter"
                     description="Test string input parameter" 
                     phase="AUTHORING" 
                     required="NO" 
                     type="STRING"
                     default_value="default_value"/>
        
        <input_field name="float_param" 
                     description="Test float input parameter" 
                     phase="EXECUTION" 
                     required="YES" 
                     type="FLOAT"
                     default_value="3.14"/>
        
        <input_field name="bool_param" 
                     description="Test boolean input parameter" 
                     phase="EXECUTION" 
                     required="NO" 
                     type="BOOL"
                     default_value="YES"/>
        
        <input_field name="enum_param" 
                     description="Test enumeration input parameter" 
                     phase="AUTHORING" 
                     required="YES" 
                     type="ENUM"
                     default_value="OPTION_A">
            <enumeration>
                <enum symbolic="OPTION_A"/>
                <enum symbolic="OPTION_B"/>
                <enum symbolic="OPTION_C"/>
            </enumeration>
        </input_field>
        
        <input_field name="time_param" 
                     description="Test time input parameter" 
                     phase="EXECUTION" 
                     required="NO" 
                     type="TIME"/>
        
        <input_field name="flight_cmd_param" 
                     description="Test flight command parameter" 
                     phase="AUTHORING" 
                     required="NO" 
                     type="FLIGHT_COMMAND"/>
        
        <!-- Script entry with its own inputs and outputs -->
        <script_entry display_value="entry_result">
            <input_field name="entry_input1" 
                         description="Entry-specific input" 
                         phase="EXECUTION" 
                         required="YES" 
                         type="STRING"/>
            
            <input_field name="entry_input2" 
                         description="Entry-specific integer" 
                         phase="EXECUTION" 
                         required="NO" 
                         type="INT"
                         default_value="5"/>
            
            <output_field name="entry_result" 
                          display_name="Entry Result"
                          description="Result from entry processing" 
                          type="STRING"/>
            
            <output_field name="entry_status" 
                          description="Entry processing status" 
                          type="INT"/>
        </script_entry>
        
        <!-- Main output fields -->
        <output_field name="result_code" 
                      display_name="Result Code"
                      description="Script execution result code" 
                      type="INT"/>
        
        <output_field name="result_message" 
                      description="Script execution result message" 
                      type="STRING"/>
        
        <output_field name="output_file" 
                      description="Generated output file" 
                      type="FILE"/>
        
        <output_field name="chart_image" 
                      description="Generated chart image" 
                      type="IMAGE"/>
        
        <output_field name="time_series" 
                      description="Time series data" 
                      type="SERIES"/>
        
        <!-- Output array for tabular data -->
        <output_array max_entries="100" 
                      name="results_table" 
                      display_name="Processing Results"
                      description="Table of processing results">
            
            <output_array_field name="item_id" 
                                display_name="Item ID"
                                description="Unique identifier for each result" 
                                type="INT" 
                                visible="YES"/>
            
            <output_array_field name="item_name" 
                                display_name="Item Name"
                                description="Name of the processed item" 
                                type="STRING" 
                                visible="YES"/>
            
            <output_array_field name="processing_time" 
                                display_name="Processing Time"
                                description="Time taken to process item" 
                                type="FLOAT" 
                                visible="YES"/>
            
            <output_array_field name="status" 
                                display_name="Status"
                                description="Processing status" 
                                type="STRING" 
                                visible="YES"/>
            
            <output_array_field name="details" 
                                description="Detailed processing information" 
                                type="STRING" 
                                visible="NO"/>
        </output_array>
        
        <!-- Advanced layout definition -->
        <advanced_layout>
            <section>
                <section_header>
                    <layout_display>
                        <template template="Script Configuration"/>
                        <layout row="1" column="1" width="12" height="1" align="CENTER"/>
                    </layout_display>
                </section_header>
                
                <section_content>
                    <layout_field field_name="integer_param">
                        <label label_content="Integer Parameter:" label_loc="LEFT" label_align="RIGHT"/>
                        <layout row="1" column="1" width="6" height="1" align="LEFT"/>
                    </layout_field>
                    
                    <layout_field field_name="string_param">
                        <label label_content="String Parameter:" label_loc="LEFT" label_align="RIGHT"/>
                        <layout row="1" column="7" width="6" height="1" align="LEFT"/>
                    </layout_field>
                    
                    <layout_field field_name="float_param">
                        <label label_content="Float Parameter:" label_loc="LEFT" label_align="RIGHT"/>
                        <layout row="2" column="1" width="6" height="1" align="LEFT"/>
                    </layout_field>
                    
                    <layout_field field_name="enum_param">
                        <label label_content="Enum Parameter:" label_loc="LEFT" label_align="RIGHT"/>
                        <layout row="2" column="7" width="6" height="1" align="LEFT"/>
                    </layout_field>
                </section_content>
                
                <section_results>
                    <layout_display>
                        <template template="Execution Results"/>
                        <layout row="1" column="1" width="12" height="1" align="CENTER"/>
                    </layout_display>
                    
                    <layout_field field_name="result_code">
                        <label label_content="Result Code:" label_loc="LEFT" label_align="RIGHT"/>
                        <layout row="2" column="1" width="3" height="1" align="LEFT"/>
                    </layout_field>
                    
                    <layout_field field_name="result_message">
                        <label label_content="Message:" label_loc="LEFT" label_align="RIGHT"/>
                        <layout row="2" column="4" width="9" height="1" align="LEFT"/>
                    </layout_field>
                    
                    <table table_name="results_table" row_height="2">
                        <label label_content="Processing Results:" label_loc="TOP" label_align="LEFT"/>
                        <mouseover_display>
                            <mouseover_element field_name="details" display_name="Detailed Information"/>
                        </mouseover_display>
                        <table_field width="2" column_label="ID">
                            <template template="{item_id}"/>
                        </table_field>
                        <table_field width="4" column_label="Name">
                            <template template="{item_name}"/>
                        </table_field>
                        <table_field width="3" column_label="Time (ms)">
                            <template template="{processing_time:.2f}"/>
                        </table_field>
                        <table_field width="3" column_label="Status">
                            <template template="{status}"/>
                        </table_field>
                    </table>
                    
                    <icon icon_type="STATUS">
                        <layout row="5" column="11" width="2" height="1" align="CENTER"/>
                    </icon>
                </section_results>
            </section>
            
            <entry_section>
                <section_header>
                    <layout_display>
                        <template template="Entry Processing"/>
                        <layout row="1" column="1" width="12" height="1" align="CENTER"/>
                    </layout_display>
                </section_header>
                
                <section_content>
                    <layout_field field_name="entry_input1">
                        <label label_content="Entry Input:" label_loc="TOP" label_align="LEFT"/>
                        <layout row="1" column="1" width="6" height="1" align="LEFT"/>
                    </layout_field>
                    
                    <layout_field field_name="entry_input2">
                        <label label_content="Entry Number:" label_loc="TOP" label_align="LEFT"/>
                        <layout row="1" column="7" width="6" height="1" align="LEFT"/>
                    </layout_field>
                </section_content>
                
                <section_results>
                    <layout_field field_name="entry_result">
                        <label label_content="Entry Result:" label_loc="LEFT" label_align="RIGHT"/>
                        <layout row="1" column="1" width="8" height="1" align="LEFT"/>
                    </layout_field>
                    
                    <icon icon_type="STATUS">
                        <layout row="1" column="10" width="2" height="1" align="CENTER"/>
                    </icon>
                </section_results>
            </entry_section>
        </advanced_layout>
    </custom_script>
</custom-scripts>"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create XML file
        xml_file = os.path.join(temp_dir, 'test_script.xml')
        with open(xml_file, 'w') as f:
            f.write(xml_content)
        
        # Create script file
        script_file = os.path.join(temp_dir, 'test_script.sh')
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        yield xml_file

@pytest.fixture
def temp_simple_custom_script_xml():
    """Create a simple custom script XML file for basic testing."""
    script_content = """#!/usr/bin/env python3
import sys
print(f"Hello from script with args: {sys.argv[1:] if len(sys.argv) > 1 else 'none'}")
"""
    
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <header mission_name="SIMPLE_TEST"/>
    <custom_script script_name="simple_script" 
                   script_path="simple.py" 
                   description="Simple test script"
                   hash="simple123"
                   script_id="c2ltcGxlLnB5">
        
        <input_field name="message" 
                     description="Message to display" 
                     phase="EXECUTION" 
                     required="YES" 
                     type="STRING"/>
        
        <output_field name="result" 
                      description="Script output" 
                      type="STRING"/>
    </custom_script>
</custom-scripts>"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        xml_file = os.path.join(temp_dir, 'simple_script.xml')
        with open(xml_file, 'w') as f:
            f.write(xml_content)
        
        script_file = os.path.join(temp_dir, 'simple.py')
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        yield xml_file

@pytest.fixture
def temp_custom_script_json():
    """Create a temporary custom script JSON file for testing."""
    script_content = """#!/bin/bash
echo "JSON test script"
echo "param1=$1"
echo "param2=$2"
"""
    
    json_content = {
        "script_name": "json_test_script",
        "script_path": "json_test.sh",
        "description": "Test script defined in JSON format",
        "hash": "json456def",
        "script_id": "anNvbl90ZXN0LnNo",
        "status": "ACTIVE",
        "inputs": [
            {
                "name": "input_string",
                "description": "String input parameter",
                "phase": "EXECUTION",
                "input_required": "YES",
                "type": "STRING",
                "default_value": "test_value"
            },
            {
                "name": "input_number",
                "description": "Numeric input parameter",
                "phase": "AUTHORING", 
                "input_required": "NO",
                "type": "INT",
                "default_value": "42"
            },
            {
                "name": "input_enum",
                "description": "Enumeration input",
                "phase": "EXECUTION",
                "input_required": "YES",
                "type": "ENUM",
                "default_value": "OPTION1",
                "enumerations": [
                    {"symbol": "OPTION1", "numeric": 1},
                    {"symbol": "OPTION2"},
                    {"symbol": "OPTION3"}
                ]
            }
        ],
        "outputs": [
            {
                "name": "output_result",
                "description": "Main script result",
                "type": "STRING"
            },
            {
                "name": "output_code",
                "description": "Exit code",
                "type": "INT"
            },
            {
                "name": "output_file",
                "description": "Generated file",
                "type": "FILE"
            }
        ],
        "entries": [],
        "layout": []
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        json_file = os.path.join(temp_dir, 'json_test.json')
        with open(json_file, 'w') as f:
            json.dump(json_content, f, indent=2)
        
        script_file = os.path.join(temp_dir, 'json_test.sh')
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        yield json_file

@pytest.fixture
def temp_custom_script_with_entries():
    """Create a custom script XML with script entries for advanced testing."""
    script_content = """#!/bin/bash
# Script with multiple entries support
echo "Processing entry: $1"
case $1 in
    "entry1") echo "Processing first entry";;
    "entry2") echo "Processing second entry";;
    *) echo "Unknown entry";;
esac
"""
    
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <header mission_name="ENTRY_TEST"/>
    <custom_script script_name="multi_entry_script" 
                   script_path="multi_entry.sh" 
                   description="Script with multiple entry processing"
                   hash="entry789abc"
                   script_id="bXVsdGlfZW50cnkuc2g=">
        
        <!-- Global inputs -->
        <input_field name="global_config" 
                     description="Global configuration parameter" 
                     phase="AUTHORING" 
                     required="YES" 
                     type="STRING"
                     default_value="default_config"/>
        
        <!-- First script entry -->
        <script_entry display_value="entry1_result">
            <input_field name="entry1_input" 
                         description="Input for first entry" 
                         phase="EXECUTION" 
                         required="YES" 
                         type="STRING"/>
            
            <input_field name="entry1_count" 
                         description="Count for first entry" 
                         phase="EXECUTION" 
                         required="NO" 
                         type="INT"
                         default_value="1"/>
            
            <output_field name="entry1_result" 
                          description="Result from first entry" 
                          type="STRING"/>
            
            <output_field name="entry1_status" 
                          description="Status from first entry" 
                          type="INT"/>
            
            <output_array max_entries="10" 
                          name="entry1_details" 
                          description="Detailed results from entry 1">
                <output_array_field name="detail_id" 
                                    description="Detail identifier" 
                                    type="INT" 
                                    visible="YES"/>
                <output_array_field name="detail_value" 
                                    description="Detail value" 
                                    type="STRING" 
                                    visible="YES"/>
            </output_array>
        </script_entry>
        
        <!-- Global outputs -->
        <output_field name="final_status" 
                      description="Overall script status" 
                      type="STRING"/>
        
        <output_field name="total_entries_processed" 
                      description="Total number of entries processed" 
                      type="INT"/>
    </custom_script>
</custom-scripts>"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        xml_file = os.path.join(temp_dir, 'multi_entry.xml')
        with open(xml_file, 'w') as f:
            f.write(xml_content)
        
        script_file = os.path.join(temp_dir, 'multi_entry.sh')
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        yield xml_file

@pytest.fixture
def mock_getpass():
    """Mock getpass functions."""
    with patch('getpass.getpass', return_value='test_password'), \
         patch('getpass.getuser', return_value='test_user'):
        yield

@pytest.fixture
def mock_project_config_functions():
    """Mock all project_config module functions."""
    with patch('project_config.get_dictionary_versions', return_value=[]), \
         patch('project_config.get_dictionary', return_value=[]), \
         patch('project_config.get_custom_scripts', return_value=[]), \
         patch('project_config.get_vnv_vis', return_value=[]), \
         patch('project_config.create_dictionary_version'), \
         patch('project_config.create_dictionary_content'), \
         patch('project_config.create_custom_script'), \
         patch('project_config.create_vnv_vis'), \
         patch('project_config.delete_dictionary_version'), \
         patch('project_config.delete_vnv_vi'), \
         patch('project_config.delete_custom_script'):
        yield

@pytest.fixture
def temp_channel_xml_file():
    """Create a temporary channel/telemetry dictionary XML file for testing."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<telemetry_dictionary>
    <header>
        <mission_name>TEST_MISSION</mission_name>
        <spacecraft_ids>
            <spacecraft_id>999</spacecraft_id>
        </spacecraft_ids>
        <version>1.0</version>
        <build_id>TEST_BUILD_001</build_id>
        <description>Test telemetry dictionary for unit tests</description>
    </header>
    <enum_definitions>
        <enum_table name="STATUS_TABLE">
            <enum symbol="NOMINAL" numeric="0"/>
            <enum symbol="WARNING" numeric="1"/>
            <enum symbol="ERROR" numeric="2"/>
            <enum symbol="CRITICAL" numeric="3"/>
        </enum_table>
    </enum_definitions>
    <derivation_definitions>
        <derivation name="test_derivation" id="DERIV_001">
            <description>Test derivation algorithm</description>
            <parameterized_algorithm>
                <name>polynomial</name>
                <param name="coeff0" value="0.0"/>
                <param name="coeff1" value="1.0"/>
                <param name="coeff2" value="0.0"/>
            </parameterized_algorithm>
        </derivation>
    </derivation_definitions>
    <telemetry_definitions>
        <telemetry abbreviation="T001" name="VOLTAGE_BUS_A" type="float" source="flight" byte_length="4" group_id="POWER">
            <measurement_id>1001</measurement_id>
            <title>Main Bus A Voltage</title>
            <description>Primary power bus A voltage measurement in volts</description>
            <plain_format>
                <printf_format>%6.2f</printf_format>
            </plain_format>
            <raw_units>DN</raw_units>
            <raw_to_eng>
                <parameterized_algorithm>
                    <name>polynomial</name>
                    <param name="coeff0" value="-5.0"/>
                    <param name="coeff1" value="0.01"/>
                    <param name="coeff2" value="0.0"/>
                </parameterized_algorithm>
                <eng_units>V</eng_units>
            </raw_to_eng>
        </telemetry>
        <telemetry abbreviation="T002" name="TEMP_CPU" type="unsigned" source="flight" byte_length="2">
            <measurement_id>1002</measurement_id>
            <title>CPU Temperature</title>
            <description>Central processing unit temperature in degrees Celsius</description>
            <plain_format>
                <printf_format>%d</printf_format>
            </plain_format>
            <raw_units>DN</raw_units>
            <raw_to_eng>
                <parameterized_algorithm>
                    <name>polynomial</name>
                    <param name="coeff0" value="-40.0"/>
                    <param name="coeff1" value="0.1"/>
                </parameterized_algorithm>
                <eng_units>C</eng_units>
            </raw_to_eng>
        </telemetry>
        <telemetry abbreviation="T003" name="SYS_STATUS" type="enum" source="flight" byte_length="1">
            <measurement_id>1003</measurement_id>
            <title>System Status</title>
            <description>Overall system health status</description>
            <enum_format>
                <enum_table_name>STATUS_TABLE</enum_table_name>
            </enum_format>
            <raw_units>code</raw_units>
        </telemetry>
        <telemetry abbreviation="T004" name="ENABLE_FLAG" type="boolean" source="flight" byte_length="1">
            <measurement_id>1004</measurement_id>
            <title>System Enable</title>
            <description>System enable/disable flag</description>
            <boolean_format>
                <true_string>ENABLED</true_string>
                <false_string>DISABLED</false_string>
            </boolean_format>
        </telemetry>
        <telemetry abbreviation="T005" name="SW_VERSION" type="string" source="sse" byte_length="32">
            <title>Software Version</title>
            <description>Software version string from ground system</description>
        </telemetry>
    </telemetry_definitions>
</telemetry_dictionary>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)

@pytest.fixture
def temp_evr_xml_file():
    """Create a temporary EVR dictionary XML file for testing."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<evr_dictionary>
    <header>
        <mission_name>TEST_MISSION</mission_name>
        <spacecraft_ids>
            <spacecraft_id>999</spacecraft_id>
        </spacecraft_ids>
        <version>1.0</version>
        <build_id>TEST_BUILD_001</build_id>
        <description>Test EVR dictionary for unit tests</description>
    </header>
    <enum_definitions>
        <enum_table name="ERROR_CODES">
            <enum symbol="SUCCESS" numeric="0"/>
            <enum symbol="TIMEOUT" numeric="1"/>
            <enum symbol="INVALID_PARAM" numeric="2"/>
            <enum symbol="SYSTEM_ERROR" numeric="3"/>
        </enum_table>
    </enum_definitions>
    <evrs>
        <evr id="0x1001" name="SYSTEM_STARTUP" level="INFO" source="flight">
            <categories>
                <ops_category>SYSTEM</ops_category>
                <subsystem>BOOT</subsystem>
            </categories>
            <format_message><![CDATA[System startup completed in %d seconds, version %s]]></format_message>
            <number_of_arguments>2</number_of_arguments>
            <args>
                <unsigned_arg name="startup_time" bit_length="32">
                    <description>Time taken for system startup in seconds</description>
                </unsigned_arg>
                <string_arg name="sw_version" bit_length="64">
                    <description>Software version string</description>
                </string_arg>
            </args>
        </evr>
        <evr id="0x1002" name="POWER_WARNING" level="WARNING" source="flight">
            <categories>
                <ops_category>POWER</ops_category>
                <subsystem>BUS</subsystem>
            </categories>
            <format_message><![CDATA[Power bus voltage low: %4.2f V, threshold: %4.2f V]]></format_message>
            <number_of_arguments>2</number_of_arguments>
            <args>
                <float_arg name="current_voltage" bit_length="32">
                    <description>Current bus voltage</description>
                </float_arg>
                <float_arg name="threshold_voltage" bit_length="32">
                    <description>Warning threshold voltage</description>
                </float_arg>
            </args>
        </evr>
        <evr id="2001" name="COMMAND_ERROR" level="ERROR" source="flight">
            <categories>
                <ops_category>COMMAND</ops_category>
                <subsystem>CMD_PROC</subsystem>
            </categories>
            <format_message><![CDATA[Command execution failed with error code %ENUM]]></format_message>
            <number_of_arguments>1</number_of_arguments>
            <args>
                <enum_arg name="error_code" bit_length="8" enum_name="ERROR_CODES">
                    <description>Command error code</description>
                </enum_arg>
            </args>
        </evr>
        <evr id="0x1004" name="SIMPLE_EVENT" level="DIAGNOSTIC" source="flight">
            <categories>
                <ops_category>DEBUG</ops_category>
            </categories>
            <format_message><![CDATA[Simple diagnostic event occurred]]></format_message>
            <number_of_arguments>0</number_of_arguments>
        </evr>
    </evrs>
</evr_dictionary>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)

@pytest.fixture
def temp_mil1553_xml_file():
    """Create a temporary MIL-STD-1553 dictionary XML file for testing."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<mil1553_dictionary>
    <header>
        <mission_name>TEST_MISSION</mission_name>
        <spacecraft_ids>
            <spacecraft_id>999</spacecraft_id>
        </spacecraft_ids>
        <version>1.0</version>
        <build_id>TEST_BUILD_001</build_id>
        <description>Test MIL-STD-1553 dictionary for unit tests</description>
    </header>
    <extended_signals>
        <extended_signal name="EXT_SIGNAL_001" description="Extended multi-word signal" 
                         sub_address="1" remote_terminal="5" transmit_receive="R" word_count="4"/>
    </extended_signals>
    <mil1553_signals>
        <mil1553_signal name="VOLTAGE_MONITOR" description="Bus voltage monitoring signal" 
                        ops_cat="POWER" type="FLOAT" units="V">
            <poly>
                <coeff index="0">0.0</coeff>
                <coeff index="1">0.01</coeff>
            </poly>
            <mil1553_map sub_address="1" remote_terminal="2" transmit_receive="R" bus="BUS_A">
                <data_word_maps>
                    <data_word_map word="1" bit_start="0" num_bits="16"/>
                </data_word_maps>
            </mil1553_map>
        </mil1553_signal>
        <mil1553_signal name="STATUS_WORD" description="System status bits" 
                        ops_cat="SYSTEM" type="UINT">
            <enums>
                <enum symbol="NORMAL" numeric="0"/>
                <enum symbol="DEGRADED" numeric="1"/>
                <enum symbol="FAILED" numeric="2"/>
                <enum symbol="UNKNOWN" numeric="3"/>
            </enums>
            <mil1553_map sub_address="2" remote_terminal="3" transmit_receive="T" bus="BUS_B">
                <rtis>
                    <rti>1</rti>
                    <rti>2</rti>
                    <rti>5</rti>
                </rtis>
                <data_word_maps>
                    <data_word_map word="STATUS" bit_start="0" num_bits="8"/>
                </data_word_maps>
            </mil1553_map>
        </mil1553_signal>
        <mil1553_signal name="COUNTER_VALUE" description="Simple counter signal" 
                        ops_cat="DEBUG" type="INT" units="count">
            <mil1553_map sub_address="10" remote_terminal="7" transmit_receive="R">
                <data_word_maps>
                    <data_word_map word="2" bit_start="4" num_bits="12"/>
                </data_word_maps>
            </mil1553_map>
        </mil1553_signal>
    </mil1553_signals>
</mil1553_dictionary>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)

@pytest.fixture
def mock_urllib3_warnings():
    """Mock urllib3 warnings disable."""
    with patch('urllib3.disable_warnings'):
        yield 