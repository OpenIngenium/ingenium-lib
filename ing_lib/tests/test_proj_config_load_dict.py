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

    def test_parse_xtce_channel_dictionary_container_naming(self):
        """Test that XTCE channel names are built as SpaceSystem__Container__Param
        and that the same parameter referenced by two containers yields two
        distinct channel entries."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="ID_Type" shortDescription="Test ID param" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="GAIN_Type" shortDescription="Gain dB" signed="true">
        <xtce:IntegerDataEncoding sizeInBits="32" encoding="twosComplement"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="ID" parameterTypeRef="ID_Type"/>
      <xtce:Parameter name="GAIN" parameterTypeRef="GAIN_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="RX_STATUS">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="ID"/>
          <xtce:ParameterRefEntry parameterRef="GAIN"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
      <xtce:SequenceContainer name="SOH1">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="ID"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            names = {c['channel_name'] for c in channels}

            # ID appears in both containers -> two distinct channel entries
            assert 'TESTSYS__RX_STATUS__ID' in names
            assert 'TESTSYS__SOH1__ID' in names
            assert 'TESTSYS__RX_STATUS__GAIN' in names
            assert len(channels) == 3

            gain_channel = next(c for c in channels if c['channel_name'] == 'TESTSYS__RX_STATUS__GAIN')
            assert gain_channel['type'] == 'integer'
            assert gain_channel['bit_size'] == 32
            assert gain_channel['description'] == 'Gain dB'
            assert gain_channel['channel_id'] == 'TESTSYS__RX_STATUS__GAIN'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_size_in_bits_element(self):
        """Test that bit_size is captured from a SizeInBits child element,
        both as plain text and via a nested FixedValue element, in addition
        to the sizeInBits attribute form."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="ATTR_Type" shortDescription="attr sizeInBits" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="32" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="TEXT_Type" shortDescription="text SizeInBits" signed="false">
        <xtce:IntegerDataEncoding encoding="unsigned">
          <xtce:SizeInBits>24</xtce:SizeInBits>
        </xtce:IntegerDataEncoding>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="FIXED_Type" shortDescription="FixedValue SizeInBits" signed="false">
        <xtce:IntegerDataEncoding encoding="unsigned">
          <xtce:SizeInBits>
            <xtce:FixedValue>12</xtce:FixedValue>
          </xtce:SizeInBits>
        </xtce:IntegerDataEncoding>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="ATTR" parameterTypeRef="ATTR_Type"/>
      <xtce:Parameter name="TEXT" parameterTypeRef="TEXT_Type"/>
      <xtce:Parameter name="FIXED" parameterTypeRef="FIXED_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="SOH1">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="ATTR"/>
          <xtce:ParameterRefEntry parameterRef="TEXT"/>
          <xtce:ParameterRefEntry parameterRef="FIXED"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            assert by_name['TESTSYS__SOH1__ATTR']['bit_size'] == 32
            assert by_name['TESTSYS__SOH1__TEXT']['bit_size'] == 24
            assert by_name['TESTSYS__SOH1__FIXED']['bit_size'] == 12
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_string_size_in_bits_fixed_element(self):
        """Test that bit_size is captured from a StringDataEncoding's nested
        SizeInBits -> Fixed -> FixedValue structure."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:StringParameterType name="STR_Type" shortDescription="fixed string param">
        <xtce:StringDataEncoding encoding="UTF-8">
          <xtce:SizeInBits>
            <xtce:Fixed>
              <xtce:FixedValue>128</xtce:FixedValue>
            </xtce:Fixed>
            <xtce:TerminationChar>00</xtce:TerminationChar>
          </xtce:SizeInBits>
        </xtce:StringDataEncoding>
      </xtce:StringParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="STR" parameterTypeRef="STR_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="SOH1">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="STR"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            assert by_name['TESTSYS__SOH1__STR']['bit_size'] == 128
            assert by_name['TESTSYS__SOH1__STR']['type'] == 'string'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_description_combines_container_and_type(self):
        """Test that channel description is built as
        f"{SequenceContainer short description} - {ParameterType short description}",
        falling back to whichever piece is available when only one exists."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="BOTH_Type" shortDescription="Gain dB" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:IntegerParameterType name="NODESC_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="BOTH" parameterTypeRef="BOTH_Type"/>
      <xtce:Parameter name="NODESC" parameterTypeRef="NODESC_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="RX_STATUS" shortDescription="RX Status Container">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="BOTH"/>
          <xtce:ParameterRefEntry parameterRef="NODESC"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
      <xtce:SequenceContainer name="NOCONTAINERDESC">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="BOTH"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            # Both container and type descriptions present -> combined
            assert by_name['TESTSYS__RX_STATUS__BOTH']['description'] == 'RX Status Container - Gain dB'
            # Only container description present -> fall back to container description
            assert by_name['TESTSYS__RX_STATUS__NODESC']['description'] == 'RX Status Container'
            # Only type description present -> fall back to type description
            assert by_name['TESTSYS__NOCONTAINERDESC__BOTH']['description'] == 'Gain dB'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_multi_spacesystem(self):
        """Test channel naming across multiple (nested) SpaceSystems, including
        cross-SpaceSystem parameterRef resolution via relative paths."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="ROOT">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="SHARED_Type" shortDescription="shared param" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="SHARED" parameterTypeRef="SHARED_Type"/>
    </xtce:ParameterSet>
  </xtce:TelemetryMetaData>
  <xtce:SpaceSystem name="CHILD">
    <xtce:TelemetryMetaData>
      <xtce:ParameterTypeSet>
        <xtce:IntegerParameterType name="LOCAL_Type" shortDescription="local param" signed="true">
          <xtce:IntegerDataEncoding sizeInBits="16" encoding="twosComplement"/>
        </xtce:IntegerParameterType>
      </xtce:ParameterTypeSet>
      <xtce:ParameterSet>
        <xtce:Parameter name="LOCAL" parameterTypeRef="LOCAL_Type"/>
      </xtce:ParameterSet>
      <xtce:ContainerSet>
        <xtce:SequenceContainer name="CHILD_CONTAINER">
          <xtce:EntryList>
            <xtce:ParameterRefEntry parameterRef="LOCAL"/>
            <xtce:ParameterRefEntry parameterRef="../SHARED"/>
          </xtce:EntryList>
        </xtce:SequenceContainer>
      </xtce:ContainerSet>
    </xtce:TelemetryMetaData>
  </xtce:SpaceSystem>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            names = {c['channel_name']: c for c in channels}

            assert 'CHILD__CHILD_CONTAINER__LOCAL' in names
            assert names['CHILD__CHILD_CONTAINER__LOCAL']['type'] == 'integer'
            assert names['CHILD__CHILD_CONTAINER__LOCAL']['bit_size'] == 16

            # Cross-SpaceSystem parameterRef ("../SHARED") resolved from the ROOT SpaceSystem
            assert 'CHILD__CHILD_CONTAINER__SHARED' in names
            assert names['CHILD__CHILD_CONTAINER__SHARED']['type'] == 'unsigned'
            assert names['CHILD__CHILD_CONTAINER__SHARED']['bit_size'] == 8
        finally:
            os.remove(temp_file)

    def test_parse_xtce_command_dictionary_naming_and_arguments(self):
        """Test that XTCE command_stem is SpaceSystem__MetaCommand and that
        argument type/size/description are resolved via argumentTypeRef's
        shortDescription attribute."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:CommandMetaData>
    <xtce:ArgumentTypeSet>
      <xtce:IntegerArgumentType name="DO_THING_VERSION_Type" shortDescription="Test version arg" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerArgumentType>
    </xtce:ArgumentTypeSet>
    <xtce:MetaCommandSet>
      <xtce:MetaCommand name="DO_THING" shortDescription="Test command description">
        <xtce:ArgumentList>
          <xtce:Argument name="VERSION" argumentTypeRef="DO_THING_VERSION_Type" initialValue="0"/>
        </xtce:ArgumentList>
      </xtce:MetaCommand>
    </xtce:MetaCommandSet>
  </xtce:CommandMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            commands = parse_xtce_command_dictionary(temp_file)
            assert len(commands) == 1

            command = commands[0]
            assert command['command_stem'] == 'TESTSYS__DO_THING'
            assert command['cmd_description'] == 'Test command description'
            assert len(command['arguments']) == 1

            argument = command['arguments'][0]
            assert argument['argument_name'] == 'VERSION'
            assert argument['argument_type'] == 'UINT'
            assert argument['argument_size'] == 1
            assert argument['default_value'] == '0'
            assert argument['argument_description'] == 'Test version arg'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_command_dictionary_valid_range_set(self):
        """Test that ArgumentType ValidRangeSet/ValidRange elements are
        extracted into each argument's allowable_ranges as a list of
        {'min_value', 'max_value'} dicts, covering both inclusive and
        exclusive bound attributes and multiple ValidRange entries."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:CommandMetaData>
    <xtce:ArgumentTypeSet>
      <xtce:IntegerArgumentType name="RANGED_Type" signed="true">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="twosComplement"/>
        <xtce:ValidRangeSet>
          <xtce:ValidRange minInclusive="0" maxInclusive="100"/>
          <xtce:ValidRange minExclusive="200" maxExclusive="300"/>
        </xtce:ValidRangeSet>
      </xtce:IntegerArgumentType>
      <xtce:IntegerArgumentType name="NORANGE_Type" signed="true">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="twosComplement"/>
      </xtce:IntegerArgumentType>
    </xtce:ArgumentTypeSet>
    <xtce:MetaCommandSet>
      <xtce:MetaCommand name="DO_THING">
        <xtce:ArgumentList>
          <xtce:Argument name="RANGED_ARG" argumentTypeRef="RANGED_Type"/>
          <xtce:Argument name="PLAIN_ARG" argumentTypeRef="NORANGE_Type"/>
        </xtce:ArgumentList>
      </xtce:MetaCommand>
    </xtce:MetaCommandSet>
  </xtce:CommandMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            commands = parse_xtce_command_dictionary(temp_file)
            assert len(commands) == 1

            arguments_by_index = commands[0]['arguments']

            ranged_arg = arguments_by_index[0]
            assert ranged_arg['argument_name'] == 'RANGED_ARG'
            assert ranged_arg['allowable_ranges'] == [
                {'min_value': '0', 'max_value': '100'},
                {'min_value': '200', 'max_value': '300'},
            ]

            plain_arg = arguments_by_index[1]
            assert plain_arg['argument_name'] == 'PLAIN_ARG'
            assert 'allowable_ranges' not in plain_arg

            # Neither the Argument nor its type supplies a default or a
            # description, so both keys are omitted entirely.
            for argument in arguments_by_index:
                assert 'default_value' not in argument
                assert 'argument_description' not in argument
        finally:
            os.remove(temp_file)

    def test_parse_xtce_command_dictionary_multi_spacesystem(self):
        """Test that two SpaceSystems with same-named MetaCommands produce
        distinct command_stems and do not cross-resolve argumentTypeRefs."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="ROOT">
  <xtce:SpaceSystem name="SSA">
    <xtce:CommandMetaData>
      <xtce:ArgumentTypeSet>
        <xtce:IntegerArgumentType name="ARG_Type" shortDescription="SSA arg" signed="false">
          <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
        </xtce:IntegerArgumentType>
      </xtce:ArgumentTypeSet>
      <xtce:MetaCommandSet>
        <xtce:MetaCommand name="DO_THING" shortDescription="SSA do thing">
          <xtce:ArgumentList>
            <xtce:Argument name="ARG" argumentTypeRef="ARG_Type"/>
          </xtce:ArgumentList>
        </xtce:MetaCommand>
      </xtce:MetaCommandSet>
    </xtce:CommandMetaData>
  </xtce:SpaceSystem>
  <xtce:SpaceSystem name="SSB">
    <xtce:CommandMetaData>
      <xtce:ArgumentTypeSet>
        <xtce:FloatArgumentType name="ARG_Type" shortDescription="SSB arg">
          <xtce:FloatDataEncoding sizeInBits="32" encoding="IEEE754_1985"/>
        </xtce:FloatArgumentType>
      </xtce:ArgumentTypeSet>
      <xtce:MetaCommandSet>
        <xtce:MetaCommand name="DO_THING" shortDescription="SSB do thing">
          <xtce:ArgumentList>
            <xtce:Argument name="ARG" argumentTypeRef="ARG_Type"/>
          </xtce:ArgumentList>
        </xtce:MetaCommand>
      </xtce:MetaCommandSet>
    </xtce:CommandMetaData>
  </xtce:SpaceSystem>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            commands = parse_xtce_command_dictionary(temp_file)
            by_stem = {c['command_stem']: c for c in commands}

            assert 'SSA__DO_THING' in by_stem
            assert 'SSB__DO_THING' in by_stem

            ssa_arg = by_stem['SSA__DO_THING']['arguments'][0]
            ssb_arg = by_stem['SSB__DO_THING']['arguments'][0]

            # Each ARG_Type resolved within its own SpaceSystem's ArgumentTypeSet
            assert ssa_arg['argument_type'] == 'UINT'
            assert ssa_arg['argument_description'] == 'SSA arg'
            assert ssb_arg['argument_type'] == 'FLOAT'
            assert ssb_arg['argument_description'] == 'SSB arg'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_command_dictionary_argument_name_and_default_value(self):
        """Test argument_name extraction and the Argument-over-ArgumentType
        precedence for both default_value (initialValue) and
        argument_description (shortDescription)."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:CommandMetaData>
    <xtce:ArgumentTypeSet>
      <xtce:IntegerArgumentType name="PLAIN_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerArgumentType>
      <xtce:IntegerArgumentType name="TYPE_DEFAULT_Type" initialValue="7" shortDescription="Type level description" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerArgumentType>
    </xtce:ArgumentTypeSet>
    <xtce:MetaCommandSet>
      <xtce:MetaCommand name="DO_THING">
        <xtce:ArgumentList>
          <xtce:Argument name="ARG_ARGUMENT_DEFAULT" argumentTypeRef="PLAIN_Type" initialValue="1"/>
          <xtce:Argument name="ARG_TYPE_DEFAULT" argumentTypeRef="TYPE_DEFAULT_Type"/>
          <xtce:Argument name="ARG_BOTH_DEFAULTS" argumentTypeRef="TYPE_DEFAULT_Type" initialValue="9" shortDescription="Argument level description"/>
          <xtce:Argument name="ARG_NEITHER" argumentTypeRef="PLAIN_Type"/>
        </xtce:ArgumentList>
      </xtce:MetaCommand>
    </xtce:MetaCommandSet>
  </xtce:CommandMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            commands = parse_xtce_command_dictionary(temp_file)
            assert len(commands) == 1

            by_name = {a['argument_name']: a for a in commands[0]['arguments']}
            assert set(by_name) == {
                'ARG_ARGUMENT_DEFAULT', 'ARG_TYPE_DEFAULT',
                'ARG_BOTH_DEFAULTS', 'ARG_NEITHER',
            }

            # initialValue on the Argument only
            assert by_name['ARG_ARGUMENT_DEFAULT']['default_value'] == '1'

            # initialValue/shortDescription inherited from the ArgumentType
            assert by_name['ARG_TYPE_DEFAULT']['default_value'] == '7'
            assert by_name['ARG_TYPE_DEFAULT']['argument_description'] == 'Type level description'

            # Argument wins over the ArgumentType for both fields
            assert by_name['ARG_BOTH_DEFAULTS']['default_value'] == '9'
            assert by_name['ARG_BOTH_DEFAULTS']['argument_description'] == 'Argument level description'

            # Neither level supplies a default or description
            assert 'default_value' not in by_name['ARG_NEITHER']
            assert 'argument_description' not in by_name['ARG_NEITHER']
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_custom_algorithm_outputs(self):
        """Test that CustomAlgorithm OutputSet parameters become channels named
        after the SequenceContainer holding the algorithm's InputSet parameter,
        and that the raw input parameter's own channel is still emitted."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:StringParameterType name="RAW_Type" shortDescription="Opaque payload">
        <xtce:StringDataEncoding sizeInBits="64"/>
      </xtce:StringParameterType>
      <xtce:IntegerParameterType name="OUT_A_Type" shortDescription="Output A" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="unsigned"/>
      </xtce:IntegerParameterType>
      <xtce:FloatParameterType name="OUT_B_Type" shortDescription="Output B">
        <xtce:FloatDataEncoding sizeInBits="32" encoding="IEEE754_1985"/>
      </xtce:FloatParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="RAW_PAYLOAD" parameterTypeRef="RAW_Type"/>
      <xtce:Parameter name="OUT_A" parameterTypeRef="OUT_A_Type">
        <xtce:ParameterProperties dataSource="derived"/>
      </xtce:Parameter>
      <xtce:Parameter name="OUT_B" parameterTypeRef="OUT_B_Type">
        <xtce:ParameterProperties dataSource="derived"/>
      </xtce:Parameter>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="TEST_PKT" shortDescription="Test packet">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="RAW_PAYLOAD"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
    <xtce:AlgorithmSet>
      <xtce:CustomAlgorithm name="TransformTestPkt">
        <xtce:InputSet>
          <xtce:InputParameterInstanceRef parameterRef="RAW_PAYLOAD"/>
        </xtce:InputSet>
        <xtce:OutputSet>
          <xtce:OutputParameterRef parameterRef="OUT_A"/>
          <xtce:OutputParameterRef parameterRef="OUT_B"/>
        </xtce:OutputSet>
      </xtce:CustomAlgorithm>
    </xtce:AlgorithmSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            assert set(by_name) == {
                'TESTSYS__TEST_PKT__RAW_PAYLOAD',
                'TESTSYS__TEST_PKT__OUT_A',
                'TESTSYS__TEST_PKT__OUT_B',
            }

            # The raw input channel is still emitted
            raw = by_name['TESTSYS__TEST_PKT__RAW_PAYLOAD']
            assert raw['derived'] == 'No'

            out_a = by_name['TESTSYS__TEST_PKT__OUT_A']
            assert out_a['channel_id'] == 'TESTSYS__TEST_PKT__OUT_A'
            assert out_a['operations_category'] == 'TESTSYS'
            assert out_a['type'] == 'unsigned'
            assert out_a['bit_size'] == 16
            assert out_a['derived'] == 'Yes'
            assert out_a['description'] == 'Test packet - Output A'

            out_b = by_name['TESTSYS__TEST_PKT__OUT_B']
            assert out_b['type'] == 'float'
            assert out_b['bit_size'] == 32
            assert out_b['derived'] == 'Yes'
            assert out_b['description'] == 'Test packet - Output B'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_array_parameter_type(self):
        """Test that ArrayParameterType is resolved through arrayTypeRef to its
        element type, including when the element type is declared later in the
        ParameterTypeSet, and that a calibrator nested inside the element type's
        encoding sets eu_present."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:ArrayParameterType name="READINGS_ArrayType" shortDescription="Array description" arrayTypeRef="READING_Type">
        <xtce:DimensionList>
          <xtce:Dimension>
            <xtce:StartingIndex><xtce:FixedValue>0</xtce:FixedValue></xtce:StartingIndex>
            <xtce:EndingIndex><xtce:FixedValue>0</xtce:FixedValue></xtce:EndingIndex>
          </xtce:Dimension>
        </xtce:DimensionList>
      </xtce:ArrayParameterType>
      <xtce:ArrayParameterType name="INHERITED_ArrayType" arrayTypeRef="READING_Type"/>
      <!-- Element type is declared after the array types that reference it -->
      <xtce:IntegerParameterType name="READING_Type" shortDescription="Element description" signed="true">
        <xtce:IntegerDataEncoding sizeInBits="16" encoding="twosComplement">
          <xtce:DefaultCalibrator>
            <xtce:PolynomialCalibrator>
              <xtce:Term coefficient="0.001" exponent="1"/>
            </xtce:PolynomialCalibrator>
          </xtce:DefaultCalibrator>
        </xtce:IntegerDataEncoding>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="READINGS" parameterTypeRef="READINGS_ArrayType"/>
      <xtce:Parameter name="INHERITED" parameterTypeRef="INHERITED_ArrayType"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="TEST_PKT">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="READINGS"/>
          <xtce:ParameterRefEntry parameterRef="INHERITED"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            readings = by_name['TESTSYS__TEST_PKT__READINGS']
            assert readings['type'] == 'integer'
            assert readings['bit_size'] == 16
            # DefaultCalibrator is nested inside IntegerDataEncoding
            assert readings['eu_present'] == 'Yes'
            # The array type's own description wins over the element type's
            assert readings['description'] == 'Array description'

            # An array type without its own description inherits the element's
            inherited = by_name['TESTSYS__TEST_PKT__INHERITED']
            assert inherited['type'] == 'integer'
            assert inherited['bit_size'] == 16
            assert inherited['description'] == 'Element description'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_derived_data_source(self):
        """Test that the channel's derived flag comes from the Parameter's
        ParameterProperties dataSource attribute."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="COUNT_Type" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="DERIVED_PARAM" parameterTypeRef="COUNT_Type">
        <xtce:ParameterProperties dataSource="derived"/>
      </xtce:Parameter>
      <xtce:Parameter name="TELEMETERED_PARAM" parameterTypeRef="COUNT_Type">
        <xtce:ParameterProperties dataSource="telemetered"/>
      </xtce:Parameter>
      <xtce:Parameter name="UNSPECIFIED_PARAM" parameterTypeRef="COUNT_Type"/>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="TEST_PKT">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="DERIVED_PARAM"/>
          <xtce:ParameterRefEntry parameterRef="TELEMETERED_PARAM"/>
          <xtce:ParameterRefEntry parameterRef="UNSPECIFIED_PARAM"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            assert by_name['TESTSYS__TEST_PKT__DERIVED_PARAM']['derived'] == 'Yes'
            assert by_name['TESTSYS__TEST_PKT__TELEMETERED_PARAM']['derived'] == 'No'
            assert by_name['TESTSYS__TEST_PKT__UNSPECIFIED_PARAM']['derived'] == 'No'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_algorithm_output_shared_across_algorithms(self):
        """Test that an output parameter produced by several algorithms yields
        one channel per source container rather than being de-duplicated."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:StringParameterType name="RAW_Type">
        <xtce:StringDataEncoding sizeInBits="64"/>
      </xtce:StringParameterType>
      <xtce:IntegerParameterType name="SHARED_Type" shortDescription="Shared output" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="32" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="RAW_ONE" parameterTypeRef="RAW_Type"/>
      <xtce:Parameter name="RAW_TWO" parameterTypeRef="RAW_Type"/>
      <xtce:Parameter name="SHARED_OUT" parameterTypeRef="SHARED_Type">
        <xtce:ParameterProperties dataSource="derived"/>
      </xtce:Parameter>
    </xtce:ParameterSet>
    <xtce:ContainerSet>
      <xtce:SequenceContainer name="PKT_ONE" shortDescription="Packet one">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="RAW_ONE"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
      <xtce:SequenceContainer name="PKT_TWO" shortDescription="Packet two">
        <xtce:EntryList>
          <xtce:ParameterRefEntry parameterRef="RAW_TWO"/>
        </xtce:EntryList>
      </xtce:SequenceContainer>
    </xtce:ContainerSet>
    <xtce:AlgorithmSet>
      <xtce:CustomAlgorithm name="TransformOne">
        <xtce:InputSet>
          <xtce:InputParameterInstanceRef parameterRef="RAW_ONE"/>
        </xtce:InputSet>
        <xtce:OutputSet>
          <xtce:OutputParameterRef parameterRef="SHARED_OUT"/>
        </xtce:OutputSet>
      </xtce:CustomAlgorithm>
      <xtce:CustomAlgorithm name="TransformTwo">
        <xtce:InputSet>
          <xtce:InputParameterInstanceRef parameterRef="RAW_TWO"/>
        </xtce:InputSet>
        <xtce:OutputSet>
          <xtce:OutputParameterRef parameterRef="SHARED_OUT"/>
        </xtce:OutputSet>
      </xtce:CustomAlgorithm>
    </xtce:AlgorithmSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            assert 'TESTSYS__PKT_ONE__SHARED_OUT' in by_name
            assert 'TESTSYS__PKT_TWO__SHARED_OUT' in by_name

            assert by_name['TESTSYS__PKT_ONE__SHARED_OUT']['description'] == 'Packet one - Shared output'
            assert by_name['TESTSYS__PKT_TWO__SHARED_OUT']['description'] == 'Packet two - Shared output'
        finally:
            os.remove(temp_file)

    def test_parse_xtce_channel_dictionary_algorithm_input_not_in_container(self):
        """Test that when no SequenceContainer references an algorithm's input,
        its outputs fall back to being named after the algorithm."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<xtce:SpaceSystem xmlns:xtce="http://www.omg.org/spec/XTCE/20180204" name="TESTSYS">
  <xtce:TelemetryMetaData>
    <xtce:ParameterTypeSet>
      <xtce:IntegerParameterType name="VALUE_Type" shortDescription="Chained output" signed="false">
        <xtce:IntegerDataEncoding sizeInBits="8" encoding="unsigned"/>
      </xtce:IntegerParameterType>
    </xtce:ParameterTypeSet>
    <xtce:ParameterSet>
      <xtce:Parameter name="ORPHAN_INPUT" parameterTypeRef="VALUE_Type"/>
      <xtce:Parameter name="CHAINED_OUT" parameterTypeRef="VALUE_Type">
        <xtce:ParameterProperties dataSource="derived"/>
      </xtce:Parameter>
    </xtce:ParameterSet>
    <xtce:AlgorithmSet>
      <xtce:CustomAlgorithm name="ChainedTransform">
        <xtce:InputSet>
          <xtce:InputParameterInstanceRef parameterRef="ORPHAN_INPUT"/>
        </xtce:InputSet>
        <xtce:OutputSet>
          <xtce:OutputParameterRef parameterRef="CHAINED_OUT"/>
        </xtce:OutputSet>
      </xtce:CustomAlgorithm>
    </xtce:AlgorithmSet>
  </xtce:TelemetryMetaData>
</xtce:SpaceSystem>
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xtce', delete=False) as f:
            f.write(xml_content)
            temp_file = f.name

        try:
            channels = parse_xtce_channel_dictionary(temp_file)
            by_name = {c['channel_name']: c for c in channels}

            assert set(by_name) == {'TESTSYS__ChainedTransform__CHAINED_OUT'}

            channel = by_name['TESTSYS__ChainedTransform__CHAINED_OUT']
            assert channel['operations_category'] == 'TESTSYS'
            assert channel['derived'] == 'Yes'
            assert channel['type'] == 'unsigned'
            # No container, so the description is the ParameterType's alone
            assert channel['description'] == 'Chained output'
        finally:
            os.remove(temp_file)