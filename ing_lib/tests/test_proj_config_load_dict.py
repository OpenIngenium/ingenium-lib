"""
Tests for ProjConfigLoadDict.py (formerly ProjConfigLoadAMPCSDict.py)
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
import sys

# Import the module under test
from apps.ProjConfigLoadDict import (
    detect_ampcs_type, parse_command_dictionary, parse_channel_dictionary,
    parse_evr_dictionary, parse_mil1553_dictionary, ensure_dictionary_version_exists,
    upload_dictionary_content, process_xml_file, parse_arguments, main,
    detect_xtce_type, parse_xtce_command_dictionary, parse_xtce_channel_dictionary
)


class TestProjConfigLoadDict:
    """Test class for ProjConfigLoadDict functionality."""
    
    def test_detect_ampcs_dictionary_type_command(self):
        """Test detection of AMPCS command dictionary type."""
        xml_content = """<?xml version="1.0"?>
<command_dictionary>
    <command_definitions>
    </command_definitions>
</command_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            dict_type = detect_ampcs_type(temp_file)
            assert dict_type == 'commands'
        finally:
            os.remove(temp_file)

    def test_detect_ampcs_dictionary_type_channel(self):
        """Test detection of AMPCS channel dictionary type."""
        xml_content = """<?xml version="1.0"?>
<telemetry_dictionary>
    <telemetry_definitions>
    </telemetry_definitions>
</telemetry_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            dict_type = detect_ampcs_type(temp_file)
            assert dict_type == 'channels'
        finally:
            os.remove(temp_file)

    def test_detect_ampcs_dictionary_type_evr(self):
        """Test detection of AMPCS EVR dictionary type."""
        xml_content = """<?xml version="1.0"?>
<evr_dictionary>
    <evrs>
    </evrs>
</evr_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            dict_type = detect_ampcs_type(temp_file)
            assert dict_type == 'evrs'
        finally:
            os.remove(temp_file)

    def test_detect_ampcs_dictionary_type_mil1553(self):
        """Test detection of AMPCS MIL-STD-1553 dictionary type."""
        xml_content = """<?xml version="1.0"?>
<mil1553_dictionary>
    <mil1553_signals>
    </mil1553_signals>
</mil1553_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            dict_type = detect_ampcs_type(temp_file)
            assert dict_type == 'mil1553'
        finally:
            os.remove(temp_file)

    def test_detect_ampcs_dictionary_type_unknown(self):
        """Test detection of unknown AMPCS dictionary type."""
        xml_content = """<?xml version="1.0"?>
<unknown_dictionary>
</unknown_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            dict_type = detect_ampcs_type(temp_file)
            assert dict_type is None
        finally:
            os.remove(temp_file)

    def test_parse_command_dictionary(self):
        """Test parsing of command dictionary XML."""
        xml_content = """<?xml version="1.0"?>
<command_dictionary>
    <command_definitions>
        <fsw_command stem="TEST_CMD" class="FSW">
            <description>Test command description</description>
            <categories>
                <ops_category>TEST_CAT</ops_category>
            </categories>
            <arguments>
                <int_argument bit_length="32">Test integer argument</int_argument>
                <string_argument bit_length="64">Test string argument</string_argument>
            </arguments>
        </fsw_command>
        <hw_command stem="HW_CMD">
            <description>Hardware command</description>
        </hw_command>
    </command_definitions>
</command_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            commands = parse_command_dictionary(temp_file)
            assert len(commands) == 2
            
            # Check FSW command
            fsw_cmd = commands[0]
            assert fsw_cmd['command_stem'] == 'TEST_CMD'
            assert fsw_cmd['cmd_type'] == 'FSW'
            assert fsw_cmd['cmd_description'] == 'Test command description'
            assert fsw_cmd['operations_category'] == 'TEST_CAT'
            assert len(fsw_cmd['arguments']) == 2
            
            # Check HW command
            hw_cmd = commands[1]
            assert hw_cmd['command_stem'] == 'HW_CMD'
            assert hw_cmd['cmd_type'] == 'HW'
            
        finally:
            os.remove(temp_file)

    def test_parse_channel_dictionary(self):
        """Test parsing of channel dictionary XML."""
        xml_content = """<?xml version="1.0"?>
<telemetry_dictionary>
    <telemetry_definitions>
        <telemetry name="TEST_CH" abbreviation="TCH" type="integer" byte_length="4" source="sse">
            <description>Test channel description</description>
            <categories>
                <ops_category>TEST_CAT</ops_category>
            </categories>
            <eu_conversion>
                <polynomial>y = x * 2</polynomial>
            </eu_conversion>
        </telemetry>
        <telemetry name="ENUM_CH" abbreviation="ECH" type="enum" byte_length="2" source="flight">
            <description>Enum channel</description>
        </telemetry>
    </telemetry_definitions>
</telemetry_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            channels = parse_channel_dictionary(temp_file)
            assert len(channels) == 2
            
            # Check first channel
            channel = channels[0]
            assert channel['channel_name'] == 'TEST_CH'
            assert channel['channel_id'] == 'TCH'
            assert channel['type'] == 'integer'
            assert channel['bit_size'] == 32  # 4 bytes * 8 bits
            assert channel['derived'] == 'Yes'  # SSE source
            assert channel['eu_present'] == 'Yes'  # Has EU conversion
            
            # Check enum channel
            enum_channel = channels[1]
            assert enum_channel['channel_name'] == 'ENUM_CH'
            assert enum_channel['type'] == 'enum'
            assert enum_channel['derived'] == 'No'  # Flight source
            
        finally:
            os.remove(temp_file)

    def test_parse_evr_dictionary(self):
        """Test parsing of EVR dictionary XML."""
        xml_content = """<?xml version="1.0"?>
<evr_dictionary>
    <evrs>
        <evr name="TEST_EVR" id="0x1001" level="INFO">
            <format_message>Test EVR message with %d parameter</format_message>
            <description>Test EVR description</description>
            <categories>
                <ops_category>TEST_CAT</ops_category>
            </categories>
        </evr>
        <evr name="ERROR_EVR" id="2002" level="ERROR">
            <format_message>Error occurred</format_message>
        </evr>
    </evrs>
</evr_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            evrs = parse_evr_dictionary(temp_file)
            assert len(evrs) == 2
            
            # Check first EVR (hex ID)
            evr = evrs[0]
            assert evr['evr_name'] == 'TEST_EVR'
            assert evr['evr_id'] == '4097'  # 0x1001 converted to decimal
            assert evr['evr_level'] == 'INFO'
            assert evr['evr_message'] == 'Test EVR message with %d parameter'
            assert evr['evr_description'] == 'Test EVR description'
            assert evr['operations_category'] == 'TEST_CAT'
            
            # Check second EVR (decimal ID)
            error_evr = evrs[1]
            assert error_evr['evr_name'] == 'ERROR_EVR'
            assert error_evr['evr_id'] == '2002'
            assert error_evr['evr_level'] == 'ERROR'
            
        finally:
            os.remove(temp_file)

    def test_parse_mil1553_dictionary(self):
        """Test parsing of MIL-STD-1553 dictionary XML."""
        xml_content = """<?xml version="1.0"?>
<mil1553_dictionary>
    <mil1553_signals>
        <mil1553_signal name="TEST_1553" description="Test 1553 signal" ops_cat="TEST_CAT" type="INTEGER">
            <mil1553_map sub_address="1" remote_terminal="2" transmit_receive="T"/>
            <poly>y = x * 0.5</poly>
            <enums>
                <enum symbol="ON" numeric="1"/>
                <enum symbol="OFF" numeric="0"/>
            </enums>
        </mil1553_signal>
        <mil1553_signal name="SIMPLE_1553" description="Simple signal" type="FLOAT">
            <mil1553_map sub_address="3" remote_terminal="4" transmit_receive="R"/>
        </mil1553_signal>
    </mil1553_signals>
</mil1553_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            signals = parse_mil1553_dictionary(temp_file)
            assert len(signals) == 2
            
            # Check first signal
            signal = signals[0]
            assert signal['mil1553_name'] == 'TEST_1553'
            assert signal['description'] == 'Test 1553 signal'
            assert signal['operations_category'] == 'TEST_CAT'
            assert signal['output_type'] == 'INTEGER'
            assert signal['sub_address'] == 1
            assert signal['remote_terminal'] == 2
            assert signal['transmit_receive'] == 'TRANSMIT'
            assert signal['eu_present'] == 'Yes'  # Has polynomial
            assert len(signal['enumerations']) == 2
            
            # Check enumeration
            enum_on = signal['enumerations'][0]
            assert enum_on['symbol'] == 'ON'
            assert enum_on['numeric'] == 1
            
            # Check second signal
            simple_signal = signals[1]
            assert simple_signal['mil1553_name'] == 'SIMPLE_1553'
            assert simple_signal['transmit_receive'] == 'RECEIVE'
            assert simple_signal['eu_present'] == 'No'  # No polynomial
            
        finally:
            os.remove(temp_file)

    @patch('apps.ProjConfigLoadDict.get_dictionary_versions')
    @patch('apps.ProjConfigLoadDict.create_dictionary_version')
    def test_ensure_dictionary_version_exists_new(self, mock_create, mock_get_versions):
        """Test ensuring dictionary version exists when it doesn't."""
        mock_get_versions.return_value = []  # No existing versions
        mock_create.return_value = True
        
        result = ensure_dictionary_version_exists(
            'https://test-server.example.com', 'flight', 'v1.0', 'Test description'
        )
        
        assert result is True
        mock_create.assert_called_once()

    @patch('apps.ProjConfigLoadDict.get_dictionary_versions')
    def test_ensure_dictionary_version_exists_existing(self, mock_get_versions):
        """Test ensuring dictionary version exists when it already does."""
        mock_get_versions.return_value = [
            {'dictionary_version': 'v1.0', 'state': 'PUBLISHED'}
        ]
        
        result = ensure_dictionary_version_exists(
            'https://test-server.example.com', 'flight', 'v1.0'
        )
        
        assert result is True

    @patch('apps.ProjConfigLoadDict.create_dictionary_content')
    def test_upload_dictionary_content_success(self, mock_create_content):
        """Test successful upload of dictionary content."""
        mock_create_content.return_value = True
        content = [
            {'command_stem': 'TEST_CMD', 'cmd_description': 'Test command'}
        ]
        
        result = upload_dictionary_content(
            'https://test-server.example.com', 'flight', 'v1.0', 'commands', content
        )
        
        assert result is True
        mock_create_content.assert_called_once_with(
            'https://test-server.example.com', 'flight', content, 'v1.0', 'cmds'
        )

    def test_upload_dictionary_content_empty(self):
        """Test upload of empty dictionary content."""
        result = upload_dictionary_content(
            'https://test-server.example.com', 'flight', 'v1.0', 'commands', []
        )
        
        assert result is True  # Should succeed with empty content

    @patch('os.path.exists')
    @patch('apps.ProjConfigLoadDict.detect_dictionary_type')
    @patch('apps.ProjConfigLoadDict.parse_command_dictionary')
    @patch('apps.ProjConfigLoadDict.upload_dictionary_content')
    def test_process_xml_file_success(self, mock_upload, mock_parse, mock_detect, mock_exists):
        """Test successful processing of XML file."""
        mock_exists.return_value = True
        mock_detect.return_value = 'commands'
        mock_parse.return_value = [{'command_stem': 'TEST_CMD'}]
        mock_upload.return_value = True
        
        result = process_xml_file(
            '/path/to/dict.xml', 'https://test-server.example.com', 'flight', 'v1.0', 'ampcs'
        )
        
        assert result is True
        mock_detect.assert_called_once()
        mock_parse.assert_called_once()
        mock_upload.assert_called_once()

    @patch('os.path.exists')
    def test_process_xml_file_missing(self, mock_exists):
        """Test processing of missing XML file."""
        mock_exists.return_value = False
        
        result = process_xml_file(
            '/nonexistent/dict.xml', 'https://test-server.example.com', 'flight', 'v1.0', 'ampcs'
        )
        
        assert result is False

    def test_parse_arguments(self):
        """Test argument parsing."""
        args = [
            'https://test-server.example.com',
            'v1.0',
            'flight',
            '--format', 'ampcs',
            'dict1.xml',
            'dict2.xml',
            '--debug',
            '--rsa'
        ]
        
        with patch('sys.argv', ['script_name'] + args):
            parsed = parse_arguments()
            
            assert parsed.server == 'https://test-server.example.com'
            assert parsed.dictionary_version == 'v1.0'
            assert parsed.flight_sse == 'flight'
            assert parsed.format == 'ampcs'
            assert parsed.xml_files == ['dict1.xml', 'dict2.xml']
            assert parsed.debug is True
            assert parsed.rsa is True

    @patch('apps.ProjConfigLoadDict.common.authenticate')
    @patch('apps.ProjConfigLoadDict.getpass.getpass')
    @patch('os.getenv')
    @patch('os.path.exists')
    @patch('apps.ProjConfigLoadDict.ensure_dictionary_version_exists')
    @patch('apps.ProjConfigLoadDict.process_xml_file')
    def test_main_success(self, mock_process, mock_ensure, mock_exists, mock_getenv,
                         mock_getpass, mock_auth):
        """Test successful main execution."""
        mock_auth.return_value = True
        mock_getenv.return_value = 'test_user'
        mock_getpass.return_value = 'test_password'
        mock_exists.return_value = True
        mock_ensure.return_value = True
        mock_process.return_value = True
        
        with patch('sys.argv', [
            'script',
            'https://test-server.example.com',
            'v1.0',
            'flight',
            '--format', 'ampcs',
            'dict.xml'
        ]):
            main()
            
            mock_auth.assert_called_once()
            mock_ensure.assert_called_once()
            mock_process.assert_called_once()

    @patch('apps.ProjConfigLoadDict.common.authenticate')
    @patch('apps.ProjConfigLoadDict.getpass.getpass')
    @patch('os.getenv')
    def test_main_authentication_failure(self, mock_getenv, mock_getpass, mock_auth):
        """Test main execution with authentication failure."""
        mock_auth.return_value = False
        mock_getenv.return_value = 'test_user'
        mock_getpass.return_value = 'test_password'
        
        with patch('sys.argv', [
            'script',
            'https://test-server.example.com',
            'v1.0',
            'flight',
            '--format', 'ampcs',
            'dict.xml'
        ]), patch('os.path.exists', return_value=True):
            
            with pytest.raises(SystemExit):
                main()

    @patch('apps.ProjConfigLoadDict.common.authenticate')
    @patch('apps.ProjConfigLoadDict.getpass.getpass')
    @patch('os.getenv')
    @patch('os.path.exists')
    @patch('apps.ProjConfigLoadDict.ensure_dictionary_version_exists')
    @patch('apps.ProjConfigLoadDict.process_xml_file')
    def test_main_partial_failure(self, mock_process, mock_ensure, mock_exists, 
                                 mock_getenv, mock_getpass, mock_auth):
        """Test main execution with partial file processing failure."""
        mock_auth.return_value = True
        mock_getenv.return_value = 'test_user'
        mock_getpass.return_value = 'test_password'
        mock_exists.return_value = True
        mock_ensure.return_value = True
        
        # First file succeeds, second fails
        mock_process.side_effect = [True, False]
        
        with patch('sys.argv', [
            'script',
            'https://test-server.example.com',
            'v1.0',
            'flight',
            '--format', 'ampcs',
            'dict1.xml',
            'dict2.xml'
        ]):
            with pytest.raises(SystemExit):
                main()

    def test_parse_command_dictionary_empty(self):
        """Test parsing command dictionary with no commands."""
        xml_content = """<?xml version="1.0"?>
<command_dictionary>
    <command_definitions>
    </command_definitions>
</command_dictionary>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            commands = parse_command_dictionary(temp_file)
            assert len(commands) == 0
        finally:
            os.remove(temp_file)

    def test_parse_invalid_xml(self):
        """Test parsing of invalid XML."""
        xml_content = "<?xml version='1.0'?><invalid>unclosed tag"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name
        
        try:
            commands = parse_command_dictionary(temp_file)
            assert len(commands) == 0  # Should return empty list on parse error
        finally:
            os.remove(temp_file) 