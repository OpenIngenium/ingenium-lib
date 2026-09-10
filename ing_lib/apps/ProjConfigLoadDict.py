"""
This script reads XML dictionary files and uploads them to a specified Ingenium Server.

The script supports multiple dictionary formats:
- AMPCS: Command, Channel/Telemetry, EVR, and MIL-STD-1553 dictionaries
- XTCE: XML Telemetric and Command Exchange standard (commands and telemetry)

The dictionary type is automatically detected based on the XML structure.

Usage Examples:
    # Upload a single AMPCS command dictionary
    python ProjConfigLoadDict.py https://ingenium.project.jpl.nasa.gov my_dict_v1.0 flight --format ampcs command_dict.xml
    
    # Upload multiple AMPCS dictionaries 
    python ProjConfigLoadDict.py https://ingenium.project.jpl.nasa.gov my_dict_v1.0 sse --format ampcs cmd_dict.xml channel_dict.xml evr_dict.xml
    
    # Upload XTCE dictionary (may contain both commands and telemetry)
    python ProjConfigLoadDict.py https://ingenium.project.jpl.nasa.gov my_dict_v1.0 flight --format xtce spacecraft.xml
    
    # With custom description for the dictionary version
    python ProjConfigLoadDict.py https://ingenium.project.jpl.nasa.gov my_dict_v1.0 flight --format ampcs cmd_dict.xml --description "Flight software v2.3.1 command dictionary"
    
    # With debug logging and RSA authentication
    python ProjConfigLoadDict.py https://ingenium.project.jpl.nasa.gov my_dict_v1.0 flight --format ampcs cmd_dict.xml --debug --rsa

Authors:
    * Chris Swan (christopher.a.swan@jpl.nasa.gov)
"""

##################################################### Imports ######################################################
import logging
from ing_lib.logs import init_console_logger
init_console_logger(logging.INFO)

import ing_lib.common as common
from ing_lib.project_config import get_dictionary_versions, create_dictionary_version, create_dictionary_content
import argparse
import getpass
import urllib3
import xml.etree.ElementTree as ET
import os
import sys
from typing import List, Dict, Any, Optional

# Suppress SSL warnings if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

##################################################### Helper Functions ##############################################

def _strip_ns(tag: str) -> str:
    """
    Strip namespace from XML tag.
    
    Args:
        tag: Tag name, possibly with namespace like {http://...}LocalName
        
    Returns:
        Local name without namespace
    """
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def _find_with_ns(element: ET.Element, path: str, namespaces: Optional[Dict[str, str]] = None) -> Optional[ET.Element]:
    """
    Find child element handling namespaces.
    
    Args:
        element: Parent element
        path: Path to find (without namespace prefix)
        namespaces: Optional namespace dict
        
    Returns:
        Found element or None
    """
    if namespaces:
        return element.find(path, namespaces)
    
    # Try without namespace first
    result = element.find(path)
    if result is not None:
        return result
    
    # Try to find by local name
    for child in element:
        if _strip_ns(child.tag) == path:
            return child
    return None


def _findall_with_ns(element: ET.Element, path: str, namespaces: Optional[Dict[str, str]] = None) -> List[ET.Element]:
    """
    Find all child elements handling namespaces.
    
    Args:
        element: Parent element
        path: Path to find (without namespace prefix)
        namespaces: Optional namespace dict
        
    Returns:
        List of found elements
    """
    if namespaces:
        return element.findall(path, namespaces)
    
    # Try without namespace first
    results = element.findall(path)
    if results:
        return results
    
    # Try to find by local name
    return [child for child in element if _strip_ns(child.tag) == path]


##################################################### AMPCS Functions ###############################################

def detect_ampcs_type(xml_file: str) -> Optional[str]:
    """
    Detect the AMPCS dictionary type based on XML root element.
    
    Args:
        xml_file: Path to XML file
        
    Returns:
        Dictionary type: 'commands', 'channels', 'evrs', 'mil1553', or None if unknown
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        if root.tag == 'command_dictionary':
            return 'commands'
        elif root.tag == 'telemetry_dictionary':
            return 'channels' 
        elif root.tag == 'evr_dictionary':
            return 'evrs'
        elif root.tag == 'mil1553_dictionary':
            return 'mil1553'
        else:
            logger.warning(f"Unknown AMPCS dictionary type for root element: {root.tag}")
            return None
            
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML file {xml_file}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error detecting AMPCS dictionary type for {xml_file}: {e}")
        return None


def parse_command_dictionary(xml_file: str) -> List[Dict[str, Any]]:
    """
    Parse AMPCS command dictionary XML and convert to OpenAPI format.
    
    Args:
        xml_file: Path to command dictionary XML file
        
    Returns:
        List of command objects in OpenAPI format
    """
    commands = []
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find command definitions
        cmd_defs = root.find('command_definitions')
        if cmd_defs is None:
            logger.warning(f"No command_definitions found in {xml_file}")
            return commands
            
        # Process FSW commands
        for fsw_cmd in cmd_defs.findall('fsw_command'):
            command = {}
            
            # Required attributes
            command['command_stem'] = fsw_cmd.get('stem')
            
            # Optional attributes
            if fsw_cmd.get('class'):
                command['cmd_type'] = fsw_cmd.get('class')
                
            # Description
            desc_elem = fsw_cmd.find('description')
            if desc_elem is not None and desc_elem.text:
                command['cmd_description'] = desc_elem.text.strip()
                
            # Categories -> operations_category
            categories = fsw_cmd.find('categories')
            if categories is not None:
                cat_elem = categories.find('ops_category')
                if cat_elem is not None and cat_elem.text:
                    command['operations_category'] = cat_elem.text.strip()
                    
            # Arguments
            args_elem = fsw_cmd.find('arguments')
            if args_elem is not None:
                arguments = []
                
                for arg in args_elem:
                    argument = {}
                    
                    # Map AMPCS argument types to OpenAPI types
                    if arg.tag in ['int_argument', 'integer_argument']:
                        argument['argument_type'] = 'INT'
                    elif arg.tag in ['unsigned_argument']:
                        argument['argument_type'] = 'UINT'
                    elif arg.tag in ['float_argument']:
                        argument['argument_type'] = 'FLOAT'
                    elif arg.tag in ['string_argument', 'var_string_argument', 'fixed_string_argument']:
                        argument['argument_type'] = 'STRING'
                    elif arg.tag in ['boolean_argument']:
                        argument['argument_type'] = 'BOOL'
                    elif arg.tag in ['time_argument']:
                        argument['argument_type'] = 'TIME'
                    elif arg.tag in ['enum_argument']:
                        argument['argument_type'] = 'ENUM'
                    else:
                        # Default for unknown types
                        argument['argument_type'] = 'STRING'
                        
                    # Argument size (bit length converted to bytes)
                    bit_length = arg.get('bit_length')
                    if bit_length:
                        argument['argument_size'] = int(bit_length) // 8
                        
                    # Description
                    if arg.text and arg.text.strip():
                        argument['argument_description'] = arg.text.strip()
                        
                    # Repeat argument
                    repeat = arg.get('repeat') 
                    if repeat and repeat.lower() == 'true':
                        argument['repeat_arg'] = 'Yes'
                    else:
                        argument['repeat_arg'] = 'No'
                        
                    # Handle enumerations for ENUM type
                    if argument['argument_type'] == 'ENUM':
                        enum_table = arg.get('enum_table_name')
                        if enum_table:
                            # Note: Would need to parse enum_definitions section for full enum values
                            # For now, just note the enum table reference
                            argument['enumerations'] = []
                            
                    arguments.append(argument)
                    
                if arguments:
                    command['arguments'] = arguments
                    
            # Handle repeat arguments min/max
            # This would require more complex parsing of repeat argument structures
            
            commands.append(command)
            
        # Process HW commands 
        for hw_cmd in cmd_defs.findall('hw_command'):
            command = {}
            command['command_stem'] = hw_cmd.get('stem')
            command['cmd_type'] = 'HW'
            
            # Description
            desc_elem = hw_cmd.find('description')
            if desc_elem is not None and desc_elem.text:
                command['cmd_description'] = desc_elem.text.strip()
                
            # Categories
            categories = hw_cmd.find('categories')
            if categories is not None:
                cat_elem = categories.find('ops_category')
                if cat_elem is not None and cat_elem.text:
                    command['operations_category'] = cat_elem.text.strip()
                    
            commands.append(command)
            
    except ET.ParseError as e:
        logger.error(f"Failed to parse command dictionary {xml_file}: {e}")
    except Exception as e:
        logger.error(f"Error processing command dictionary {xml_file}: {e}")
        
    return commands


def parse_channel_dictionary(xml_file: str) -> List[Dict[str, Any]]:
    """
    Parse AMPCS channel/telemetry dictionary XML and convert to OpenAPI format.
    
    Args:
        xml_file: Path to channel dictionary XML file
        
    Returns:
        List of channel objects in OpenAPI format
    """
    channels = []
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find telemetry definitions
        tlm_defs = root.find('telemetry_definitions')
        if tlm_defs is None:
            logger.warning(f"No telemetry_definitions found in {xml_file}")
            return channels
            
        for tlm in tlm_defs.findall('telemetry'):
            channel = {}
            
            # Required attributes
            channel['channel_name'] = tlm.get('name')
            channel['channel_id'] = tlm.get('abbreviation')
            
            # Data type mapping
            ampcs_type = tlm.get('type')
            if ampcs_type == 'integer':
                channel['type'] = 'integer'
            elif ampcs_type == 'unsigned':
                channel['type'] = 'unsigned'
            elif ampcs_type == 'float':
                channel['type'] = 'float'
            elif ampcs_type == 'string':
                channel['type'] = 'string'
            elif ampcs_type == 'boolean':
                channel['type'] = 'boolean'
            elif ampcs_type == 'time':
                channel['type'] = 'time'
            elif ampcs_type == 'enum':
                channel['type'] = 'enum'
            else:
                channel['type'] = 'string'  # Default
                
            # Bit size
            byte_length = tlm.get('byte_length')
            if byte_length:
                channel['bit_size'] = int(byte_length) * 8
                
            # Source -> derived mapping
            source = tlm.get('source')
            if source == 'sse' or source == 'simulation':
                channel['derived'] = 'Yes'
            else:
                channel['derived'] = 'No'
                
            # Description  
            desc_elem = tlm.find('description')
            if desc_elem is not None and desc_elem.text:
                channel['description'] = desc_elem.text.strip()
                
            # Categories -> operations_category
            categories = tlm.find('categories')
            if categories is not None:
                cat_elem = categories.find('ops_category')
                if cat_elem is not None and cat_elem.text:
                    channel['operations_category'] = cat_elem.text.strip()
                    
            # EU present - check for derivation or conversion elements
            eu_present = "No"
            if (tlm.find('eu_conversion') is not None or 
                tlm.find('derivation') is not None or 
                tlm.find('raw_to_eng') is not None):
                eu_present = "Yes"
            channel['eu_present'] = eu_present
            
            # Handle enumerations for enum type
            if channel['type'] == 'enum':
                enum_table = tlm.get('enum_table_name')
                if enum_table:
                    # Note: Would need to parse enum_definitions section for full enum values
                    channel['enumerations'] = []
                    
            channels.append(channel)
            
    except ET.ParseError as e:
        logger.error(f"Failed to parse channel dictionary {xml_file}: {e}")
    except Exception as e:
        logger.error(f"Error processing channel dictionary {xml_file}: {e}")
        
    return channels


def parse_evr_dictionary(xml_file: str) -> List[Dict[str, Any]]:
    """
    Parse AMPCS EVR dictionary XML and convert to OpenAPI format.
    
    Args:
        xml_file: Path to EVR dictionary XML file
        
    Returns:
        List of EVR objects in OpenAPI format
    """
    evrs = []
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find EVR definitions
        evr_defs = root.find('evrs')
        if evr_defs is None:
            logger.warning(f"No evrs found in {xml_file}")
            return evrs
            
        for evr in evr_defs.findall('evr'):
            evr_obj = {}
            
            # Required attributes
            evr_obj['evr_name'] = evr.get('name')
            
            # EVR ID - handle both decimal and hex formats
            evr_id = evr.get('id')
            if evr_id:
                if evr_id.startswith('0x'):
                    # Convert hex to decimal string
                    evr_obj['evr_id'] = str(int(evr_id, 16))
                else:
                    evr_obj['evr_id'] = evr_id
                    
            # Level
            level = evr.get('level')
            if level:
                evr_obj['evr_level'] = level
                
            # Format message -> evr_message
            format_elem = evr.find('format_message')
            if format_elem is not None and format_elem.text:
                evr_obj['evr_message'] = format_elem.text.strip()
                
            # Description (if available)
            desc_elem = evr.find('description')
            if desc_elem is not None and desc_elem.text:
                evr_obj['evr_description'] = desc_elem.text.strip()
                
            # Categories -> operations_category
            categories = evr.find('categories')
            if categories is not None:
                cat_elem = categories.find('ops_category')
                if cat_elem is not None and cat_elem.text:
                    evr_obj['operations_category'] = cat_elem.text.strip()
                    
            evrs.append(evr_obj)
            
    except ET.ParseError as e:
        logger.error(f"Failed to parse EVR dictionary {xml_file}: {e}")
    except Exception as e:
        logger.error(f"Error processing EVR dictionary {xml_file}: {e}")
        
    return evrs


def parse_mil1553_dictionary(xml_file: str) -> List[Dict[str, Any]]:
    """
    Parse AMPCS 1553 dictionary XML and convert to OpenAPI format.
    
    Args:
        xml_file: Path to 1553 dictionary XML file
        
    Returns:
        List of mil1553 objects in OpenAPI format
    """
    mil1553_signals = []
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Find mil1553 signal definitions
        signal_defs = root.find('mil1553_signals')
        if signal_defs is None:
            logger.warning(f"No mil1553_signals found in {xml_file}")
            return mil1553_signals
            
        for signal in signal_defs.findall('mil1553_signal'):
            mil1553_obj = {}
            
            # Required attributes
            mil1553_obj['mil1553_name'] = signal.get('name')
            
            # Description
            description = signal.get('description')
            if description:
                mil1553_obj['description'] = description
                
            # Operations category
            ops_cat = signal.get('ops_cat')
            if ops_cat:
                mil1553_obj['operations_category'] = ops_cat
                
            # Output type mapping
            signal_type = signal.get('type')
            if signal_type:
                mil1553_obj['output_type'] = signal_type
                
            # Parse mil1553_map element
            mil1553_map = signal.find('mil1553_map')
            if mil1553_map is not None:
                # Sub address
                sub_address = mil1553_map.get('sub_address')
                if sub_address:
                    mil1553_obj['sub_address'] = int(sub_address)
                    
                # Remote terminal
                remote_terminal = mil1553_map.get('remote_terminal')
                if remote_terminal:
                    mil1553_obj['remote_terminal'] = int(remote_terminal)
                    
                # Transmit/Receive mapping
                transmit_receive = mil1553_map.get('transmit_receive')
                if transmit_receive:
                    if transmit_receive == 'T':
                        mil1553_obj['transmit_receive'] = 'TRANSMIT'
                    elif transmit_receive == 'R':
                        mil1553_obj['transmit_receive'] = 'RECEIVE'
                        
            # EU present - check for polynomial conversion
            eu_present = "No"
            if signal.find('poly') is not None:
                eu_present = "Yes"
            mil1553_obj['eu_present'] = eu_present
            
            # Handle enumerations if present
            enums_elem = signal.find('enums')
            if enums_elem is not None:
                enumerations = []
                for enum in enums_elem.findall('enum'):
                    enum_obj = {}
                    symbol = enum.get('symbol')
                    numeric = enum.get('numeric')
                    
                    if symbol:
                        enum_obj['symbol'] = symbol
                    if numeric:
                        try:
                            enum_obj['numeric'] = int(numeric)
                        except ValueError:
                            logger.warning(f"Invalid numeric value for enum in signal {mil1553_obj.get('mil1553_name')}: {numeric}")
                            continue
                    
                    if enum_obj:  # Only add if has symbol or numeric
                        enumerations.append(enum_obj)
                        
                if enumerations:
                    mil1553_obj['enumerations'] = enumerations
                    
            mil1553_signals.append(mil1553_obj)
            
    except ET.ParseError as e:
        logger.error(f"Failed to parse 1553 dictionary {xml_file}: {e}")
    except Exception as e:
        logger.error(f"Error processing 1553 dictionary {xml_file}: {e}")
        
    return mil1553_signals


##################################################### XTCE Functions ################################################

def detect_xtce_type(xml_file: str) -> Optional[str]:
    """
    Detect the XTCE dictionary content types based on SpaceSystem structure.
    
    Args:
        xml_file: Path to XTCE XML file
        
    Returns:
        'commands', 'channels', 'both', or None if not XTCE or error
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Check if root is SpaceSystem
        if _strip_ns(root.tag) != 'SpaceSystem':
            return None
        
        has_commands = False
        has_telemetry = False
        
        # Check for CommandMetaData and TelemetryMetaData
        # These can be in root or nested SpaceSystems
        def check_space_system(elem):
            nonlocal has_commands, has_telemetry
            
            for child in elem:
                local_tag = _strip_ns(child.tag)
                if local_tag == 'CommandMetaData':
                    has_commands = True
                elif local_tag == 'TelemetryMetaData':
                    has_telemetry = True
                elif local_tag == 'SpaceSystem':
                    check_space_system(child)
        
        check_space_system(root)
        
        if has_commands and has_telemetry:
            return 'both'
        elif has_commands:
            return 'commands'
        elif has_telemetry:
            return 'channels'
        else:
            logger.warning(f"XTCE file {xml_file} has no CommandMetaData or TelemetryMetaData")
            return None
            
    except ET.ParseError as e:
        logger.error(f"Failed to parse XTCE file {xml_file}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error detecting XTCE dictionary type for {xml_file}: {e}")
        return None


def _get_element_description(element: ET.Element) -> Optional[str]:
    """
    Get a description for an XTCE element, preferring the `shortDescription`
    attribute, and falling back to `LongDescription`/`ShortDescription`
    child elements (used by some other XTCE dictionaries).

    Args:
        element: XTCE element (e.g. MetaCommand, Parameter, *ParameterType, *ArgumentType)

    Returns:
        Description string or None
    """
    short_desc_attr = element.get('shortDescription')
    if short_desc_attr:
        return short_desc_attr

    long_desc_text = None
    short_desc_text = None
    for child in element:
        local_tag = _strip_ns(child.tag)
        if local_tag == 'LongDescription' and child.text:
            long_desc_text = child.text.strip()
        elif local_tag == 'ShortDescription' and child.text:
            short_desc_text = child.text.strip()

    return long_desc_text or short_desc_text


def parse_xtce_command_dictionary(xml_file: str) -> List[Dict[str, Any]]:
    """
    Parse XTCE command dictionary and convert to OpenAPI format.

    Command names are built as f"{SpaceSystem_leaf_name}__{MetaCommand_name}"
    (e.g. "SPACESYSTEM__COMMAND_NAME"). Argument types are resolved via each
    MetaCommand's own SpaceSystem's ArgumentTypeSet (argumentTypeRef). The
    operations_category is set to the owning SpaceSystem's leaf name.
    ArgumentType ValidRangeSet/ValidRange elements are extracted into each
    argument's allowable_ranges as a list of {'min_value', 'max_value'}
    dicts (values taken from minInclusive/minExclusive and
    maxInclusive/maxExclusive, per the Ingenium OpenAPI schema which has no
    inclusive/exclusive distinction). Each argument's description is built
    as f"{Argument name} - ({ArgumentType short description})", falling
    back to just the Argument name if the ArgumentType has no description.

    Args:
        xml_file: Path to XTCE XML file

    Returns:
        List of command objects in OpenAPI format
    """
    commands = []

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        if _strip_ns(root.tag) != 'SpaceSystem':
            logger.error(f"Not an XTCE SpaceSystem: {xml_file}")
            return commands

        # Phase A: collect ArgumentTypeSet scoped per-SpaceSystem (keyed by SpaceSystem path)
        arg_types_by_ss: Dict[str, Dict[str, Dict[str, Any]]] = {}

        def collect_arg_types(space_system, ss_path):
            type_map = {}

            for cmd_meta in space_system:
                if _strip_ns(cmd_meta.tag) != 'CommandMetaData':
                    continue

                for child in cmd_meta:
                    if _strip_ns(child.tag) == 'ArgumentTypeSet':
                        for arg_type in child:
                            type_name = arg_type.get('name')
                            if not type_name:
                                continue

                            type_info = {'element': arg_type}
                            local_tag = _strip_ns(arg_type.tag)

                            # Map XTCE types to Ingenium types
                            if local_tag == 'IntegerArgumentType':
                                signed = arg_type.get('signed', 'true').lower() == 'true'
                                type_info['argument_type'] = 'INT' if signed else 'UINT'
                            elif local_tag == 'FloatArgumentType':
                                type_info['argument_type'] = 'FLOAT'
                            elif local_tag == 'StringArgumentType':
                                type_info['argument_type'] = 'STRING'
                            elif local_tag == 'BooleanArgumentType':
                                type_info['argument_type'] = 'BOOL'
                            elif local_tag == 'EnumeratedArgumentType':
                                type_info['argument_type'] = 'ENUM'
                                # Extract enumerations
                                enums = []
                                for enum_list in arg_type:
                                    if _strip_ns(enum_list.tag) == 'EnumerationList':
                                        for enum in enum_list:
                                            if _strip_ns(enum.tag) == 'Enumeration':
                                                enum_obj = {}
                                                if enum.get('label'):
                                                    enum_obj['symbol'] = enum.get('label')
                                                if enum.get('value'):
                                                    try:
                                                        enum_obj['numeric'] = int(enum.get('value'))
                                                    except ValueError:
                                                        pass
                                                if enum_obj:
                                                    enums.append(enum_obj)
                                if enums:
                                    type_info['enumerations'] = enums
                            else:
                                type_info['argument_type'] = 'STRING'

                            # Get size in bits
                            for encoding in arg_type:
                                encoding_tag = _strip_ns(encoding.tag)
                                if 'Encoding' in encoding_tag:
                                    size_in_bits = encoding.get('sizeInBits')
                                    if size_in_bits:
                                        try:
                                            type_info['argument_size'] = int(size_in_bits) // 8
                                        except ValueError:
                                            pass

                            # ValidRangeSet -> allowable_ranges
                            allowable_ranges = []
                            for range_set in arg_type:
                                if _strip_ns(range_set.tag) != 'ValidRangeSet':
                                    continue
                                for valid_range in range_set:
                                    if _strip_ns(valid_range.tag) != 'ValidRange':
                                        continue
                                    range_obj = {}

                                    min_value = valid_range.get('minInclusive')
                                    if min_value is None:
                                        min_value = valid_range.get('minExclusive')
                                    if min_value is not None:
                                        range_obj['min_value'] = min_value

                                    max_value = valid_range.get('maxInclusive')
                                    if max_value is None:
                                        max_value = valid_range.get('maxExclusive')
                                    if max_value is not None:
                                        range_obj['max_value'] = max_value

                                    if range_obj:
                                        allowable_ranges.append(range_obj)

                            if allowable_ranges:
                                type_info['allowable_ranges'] = allowable_ranges

                            # Description (shortDescription attribute preferred)
                            arg_type_desc = _get_element_description(arg_type)
                            if arg_type_desc:
                                type_info['argument_description'] = arg_type_desc

                            type_map[type_name] = type_info

            arg_types_by_ss[ss_path] = type_map

            # Recurse into nested SpaceSystems
            for child in space_system:
                if _strip_ns(child.tag) == 'SpaceSystem':
                    subsys_name = child.get('name', '')
                    child_ss_path = f"{ss_path}/{subsys_name}" if ss_path else subsys_name
                    collect_arg_types(child, child_ss_path)

        root_ss_name = root.get('name', '')
        collect_arg_types(root, root_ss_name)

        # Phase B: collect MetaCommands, keyed by owning SpaceSystem path + name
        # meta_commands entries: (ss_path, ss_leaf_name, meta_cmd_element)
        meta_commands: List[tuple] = []

        def collect_meta_commands(space_system, ss_path, ss_leaf_name):
            for cmd_meta in space_system:
                if _strip_ns(cmd_meta.tag) != 'CommandMetaData':
                    continue

                for child in cmd_meta:
                    if _strip_ns(child.tag) == 'MetaCommandSet':
                        for meta_cmd in child:
                            if _strip_ns(meta_cmd.tag) == 'MetaCommand':
                                cmd_name = meta_cmd.get('name')
                                if cmd_name:
                                    meta_commands.append((ss_path, ss_leaf_name, meta_cmd))

            # Recurse into nested SpaceSystems
            for child in space_system:
                if _strip_ns(child.tag) == 'SpaceSystem':
                    subsys_name = child.get('name', '')
                    child_ss_path = f"{ss_path}/{subsys_name}" if ss_path else subsys_name
                    collect_meta_commands(child, child_ss_path, subsys_name)

        collect_meta_commands(root, root_ss_name, root_ss_name)

        # Parse MetaCommands
        seen_command_stems = set()
        for ss_path, ss_leaf_name, meta_cmd in meta_commands:
            # Skip abstract commands
            if meta_cmd.get('abstract', 'false').lower() == 'true':
                continue

            cmd_name = meta_cmd.get('name')
            command_stem = f"{ss_leaf_name}__{cmd_name}"

            if command_stem in seen_command_stems:
                logger.warning(f"Duplicate command_stem generated: {command_stem} (SpaceSystem path: {ss_path})")
            seen_command_stems.add(command_stem)

            command = {}
            command['command_stem'] = command_stem
            command['operations_category'] = ss_leaf_name

            # Description (shortDescription attribute preferred, falls back to child elements)
            cmd_description = _get_element_description(meta_cmd)
            if cmd_description:
                command['cmd_description'] = cmd_description

            # Parse arguments from ArgumentList
            arg_types = arg_types_by_ss.get(ss_path, {})
            arguments = []
            for child in meta_cmd:
                if _strip_ns(child.tag) == 'ArgumentList':
                    for arg_elem in child:
                        if _strip_ns(arg_elem.tag) == 'Argument':
                            arg_name = arg_elem.get('name')
                            arg_type_ref = arg_elem.get('argumentTypeRef')

                            if arg_type_ref and arg_type_ref in arg_types:
                                type_info = arg_types[arg_type_ref]
                                argument = {
                                    'argument_type': type_info.get('argument_type', 'STRING'),
                                    'repeat_arg': 'No'
                                }

                                if 'argument_size' in type_info:
                                    argument['argument_size'] = type_info['argument_size']

                                if 'enumerations' in type_info:
                                    argument['enumerations'] = type_info['enumerations']

                                if 'allowable_ranges' in type_info:
                                    argument['allowable_ranges'] = type_info['allowable_ranges']

                                # Description: f"{Argument name} - ({ArgumentType short description})",
                                # falling back to just the Argument name if the ArgumentType has
                                # no description.
                                type_description = type_info.get('argument_description')
                                if type_description:
                                    argument['argument_description'] = f"{arg_name} - ({type_description})"
                                else:
                                    argument['argument_description'] = arg_name

                                arguments.append(argument)
                            else:
                                logger.warning(
                                    f"Could not resolve argumentTypeRef '{arg_type_ref}' for argument "
                                    f"'{arg_name}' in command '{command_stem}' (SpaceSystem path: {ss_path}); "
                                    f"defaulting to STRING type"
                                )
                                arguments.append({
                                    'argument_type': 'STRING',
                                    'repeat_arg': 'No'
                                })

            if arguments:
                command['arguments'] = arguments

            commands.append(command)

    except ET.ParseError as e:
        logger.error(f"Failed to parse XTCE command dictionary {xml_file}: {e}")
    except Exception as e:
        logger.error(f"Error processing XTCE command dictionary {xml_file}: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return commands


def _resolve_xtce_ref(ref: str, own_ss_path: str, all_ss_paths: List[str]) -> Optional[str]:
    """
    Resolve an XTCE NameReferenceType-style reference (e.g. parameterRef) to
    the SpaceSystem path that owns the referenced element, following XTCE
    path syntax:
      - Absolute path ("/Root/Sub/Name"): resolved from the document root.
      - Relative path with "../" segments: walked up from own_ss_path.
      - Relative path with "Child/Name" segments: walked down from own_ss_path.
      - Bare name (no "/"): resolved in own_ss_path first.

    Args:
        ref: The raw ref string (e.g. "PARAM", "../Sibling/PARAM", "/ROOT/PARAM")
        own_ss_path: SpaceSystem path of the referencing element (e.g. "ROOT" or "ROOT/Sub")
        all_ss_paths: All known SpaceSystem paths in the document (for validation/fallback)

    Returns:
        The resolved SpaceSystem path that should contain the bare name, or None if
        the ref could not be resolved to a known SpaceSystem path.
    """
    if '/' not in ref:
        # Bare name: same-scope lookup
        return own_ss_path if own_ss_path in all_ss_paths else None

    if ref.startswith('/'):
        # Absolute path: strip leading slash, split off the bare name, rest is the SS path
        parts = ref.lstrip('/').split('/')
        ss_path = '/'.join(parts[:-1])
        return ss_path if ss_path in all_ss_paths else None

    # Relative path: may start with one or more "../" segments
    own_parts = own_ss_path.split('/') if own_ss_path else []
    ref_parts = ref.split('/')

    while ref_parts and ref_parts[0] == '..':
        if own_parts:
            own_parts.pop()
        ref_parts.pop(0)

    # Remaining ref_parts[:-1] are child SpaceSystem names to descend into, last is the bare name
    ss_parts = own_parts + ref_parts[:-1]
    ss_path = '/'.join(ss_parts)
    return ss_path if ss_path in all_ss_paths else None


def parse_xtce_channel_dictionary(xml_file: str) -> List[Dict[str, Any]]:
    """
    Parse XTCE telemetry/channel dictionary and convert to OpenAPI format.

    Channel names are built from the SequenceContainer structure, as
    f"{SpaceSystem_leaf_name}__{SequenceContainer_name}__{parameterRef}"
    (e.g. "SPACESYSTEM__CONTAINER_NAME__PARAM_NAME"). Types/descriptions are resolved via
    ParameterRefEntry -> Parameter -> parameterTypeRef -> ParameterType.
    channel_id is set to the same value as channel_name. The
    operations_category is set to the owning SpaceSystem's leaf name (the
    SpaceSystem that owns the SequenceContainer). The description is built as
    f"{SequenceContainer short description} - {ParameterType short description}",
    falling back to whichever of the two is available if only one is present.

    Args:
        xml_file: Path to XTCE XML file

    Returns:
        List of channel objects in OpenAPI format
    """
    channels = []

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        if _strip_ns(root.tag) != 'SpaceSystem':
            logger.error(f"Not an XTCE SpaceSystem: {xml_file}")
            return channels

        # Phase A: collect per-SpaceSystem registries of parameter types and parameters,
        # plus the SequenceContainers owned by each SpaceSystem.
        param_types_by_ss: Dict[str, Dict[str, Dict[str, Any]]] = {}
        parameters_by_ss: Dict[str, Dict[str, str]] = {}
        # containers_by_ss[ss_path] -> list of (leaf_ss_name, SequenceContainer element)
        containers_by_ss: Dict[str, List[tuple]] = {}

        def collect_registries(space_system, ss_path, ss_leaf_name):
            param_types: Dict[str, Dict[str, Any]] = {}
            parameters: Dict[str, str] = {}
            containers: List[ET.Element] = []

            for tlm_meta in space_system:
                if _strip_ns(tlm_meta.tag) != 'TelemetryMetaData':
                    continue

                for child in tlm_meta:
                    local_tag = _strip_ns(child.tag)

                    if local_tag == 'ParameterTypeSet':
                        for param_type in child:
                            type_name = param_type.get('name')
                            if not type_name:
                                continue

                            type_info = {'element': param_type}
                            type_local_tag = _strip_ns(param_type.tag)

                            # Map XTCE types to Ingenium types
                            if type_local_tag == 'IntegerParameterType':
                                signed = param_type.get('signed', 'true').lower() == 'true'
                                type_info['type'] = 'integer' if signed else 'unsigned'
                            elif type_local_tag == 'FloatParameterType':
                                type_info['type'] = 'float'
                            elif type_local_tag == 'StringParameterType':
                                type_info['type'] = 'string'
                            elif type_local_tag == 'BooleanParameterType':
                                type_info['type'] = 'boolean'
                            elif type_local_tag == 'EnumeratedParameterType':
                                type_info['type'] = 'enum'
                                # Extract enumerations
                                enums = []
                                for enum_list in param_type:
                                    if _strip_ns(enum_list.tag) == 'EnumerationList':
                                        for enum in enum_list:
                                            if _strip_ns(enum.tag) == 'Enumeration':
                                                enum_obj = {}
                                                if enum.get('label'):
                                                    enum_obj['symbol'] = enum.get('label')
                                                if enum.get('value'):
                                                    try:
                                                        enum_obj['numeric'] = int(enum.get('value'))
                                                    except ValueError:
                                                        pass
                                                if enum_obj:
                                                    enums.append(enum_obj)
                                if enums:
                                    type_info['enumerations'] = enums
                            else:
                                type_info['type'] = 'string'

                            # Get size in bits and check for EU
                            eu_present = False
                            for encoding in param_type:
                                encoding_tag = _strip_ns(encoding.tag)
                                if 'Encoding' in encoding_tag:
                                    size_in_bits = encoding.get('sizeInBits')
                                    if not size_in_bits:
                                        for encoding_child in encoding:
                                            if _strip_ns(encoding_child.tag) == 'SizeInBits':
                                                # SizeInBits may be a plain text value, contain a
                                                # FixedValue child directly (integerValue attr or
                                                # text), or nest it under a Fixed element (as used
                                                # by StringDataEncoding: SizeInBits -> Fixed ->
                                                # FixedValue).
                                                if encoding_child.text and encoding_child.text.strip():
                                                    size_in_bits = encoding_child.text.strip()
                                                else:
                                                    for size_child in encoding_child:
                                                        size_child_tag = _strip_ns(size_child.tag)
                                                        if size_child_tag == 'FixedValue':
                                                            size_in_bits = size_child.get('integerValue') or size_child.text
                                                        elif size_child_tag == 'Fixed':
                                                            for fixed_child in size_child:
                                                                if _strip_ns(fixed_child.tag) == 'FixedValue':
                                                                    size_in_bits = fixed_child.get('integerValue') or fixed_child.text
                                                                    break
                                                        if size_in_bits:
                                                            size_in_bits = size_in_bits.strip()
                                                            break
                                                break
                                    if size_in_bits:
                                        try:
                                            type_info['bit_size'] = int(size_in_bits)
                                        except ValueError:
                                            pass
                                elif encoding_tag in ['DefaultCalibrator', 'ContextCalibrationList']:
                                    eu_present = True

                            type_info['eu_present'] = 'Yes' if eu_present else 'No'

                            # Description (shortDescription attribute preferred)
                            type_desc = _get_element_description(param_type)
                            if type_desc:
                                type_info['description'] = type_desc

                            param_types[type_name] = type_info

                    elif local_tag == 'ParameterSet':
                        for param in child:
                            if _strip_ns(param.tag) == 'Parameter':
                                param_name = param.get('name')
                                if not param_name:
                                    continue
                                param_type_ref = param.get('parameterTypeRef')
                                parameters[param_name] = param_type_ref

                    elif local_tag == 'ContainerSet':
                        for container in child:
                            if _strip_ns(container.tag) == 'SequenceContainer':
                                containers.append(container)

            param_types_by_ss[ss_path] = param_types
            parameters_by_ss[ss_path] = parameters
            if containers:
                containers_by_ss[ss_path] = [(ss_leaf_name, c) for c in containers]

            # Recurse into nested SpaceSystems
            for child in space_system:
                if _strip_ns(child.tag) == 'SpaceSystem':
                    subsys_name = child.get('name', '')
                    child_ss_path = f"{ss_path}/{subsys_name}" if ss_path else subsys_name
                    collect_registries(child, child_ss_path, subsys_name)

        root_ss_name = root.get('name', '')
        collect_registries(root, root_ss_name, root_ss_name)

        all_ss_paths = list(param_types_by_ss.keys())

        # Phase B: walk SequenceContainers per SpaceSystem, resolving each
        # ParameterRefEntry to its owning SpaceSystem/Parameter/ParameterType.
        seen_channel_names = set()

        for ss_path, container_entries in containers_by_ss.items():
            for ss_leaf_name, container in container_entries:
                container_name = container.get('name')
                if not container_name:
                    continue

                container_description = _get_element_description(container)

                entry_list = None
                for child in container:
                    if _strip_ns(child.tag) == 'EntryList':
                        entry_list = child
                        break

                if entry_list is None:
                    continue

                for entry in entry_list:
                    entry_tag = _strip_ns(entry.tag)
                    if entry_tag != 'ParameterRefEntry':
                        # Other entry kinds (ContainerRefEntry, ArrayParameterRefEntry,
                        # ParameterSegmentRefEntry, IndirectParameterRefEntry,
                        # StreamSegmentEntry) are not channels; skip with a debug log.
                        logger.debug(
                            f"Skipping unsupported EntryList entry kind '{entry_tag}' in "
                            f"container '{container_name}' (SpaceSystem: {ss_leaf_name})"
                        )
                        continue

                    parameter_ref = entry.get('parameterRef')
                    if not parameter_ref:
                        continue

                    owning_ss_path = _resolve_xtce_ref(parameter_ref, ss_path, all_ss_paths)
                    bare_param_name = parameter_ref.rstrip('/').split('/')[-1]

                    if owning_ss_path is None:
                        logger.warning(
                            f"Could not resolve owning SpaceSystem for parameterRef "
                            f"'{parameter_ref}' in container '{container_name}' "
                            f"(SpaceSystem: {ss_leaf_name}); skipping"
                        )
                        continue

                    parameters = parameters_by_ss.get(owning_ss_path, {})
                    param_type_ref = parameters.get(bare_param_name)

                    if param_type_ref is None:
                        logger.warning(
                            f"parameterRef '{parameter_ref}' not found in ParameterSet "
                            f"(resolved SpaceSystem scope: '{owning_ss_path}'); skipping "
                            f"entry in container '{container_name}' (SpaceSystem: {ss_leaf_name})"
                        )
                        continue

                    param_types = param_types_by_ss.get(owning_ss_path, {})
                    type_info = param_types.get(param_type_ref)

                    channel_name = f"{ss_leaf_name}__{container_name}__{bare_param_name}"
                    if channel_name in seen_channel_names:
                        logger.warning(f"Duplicate channel_name generated: {channel_name}")
                    seen_channel_names.add(channel_name)

                    channel = {
                        'channel_name': channel_name,
                        'channel_id': channel_name,
                        'derived': 'No',
                        'operations_category': ss_leaf_name
                    }

                    if type_info:
                        channel['type'] = type_info.get('type', 'string')

                        if 'bit_size' in type_info:
                            channel['bit_size'] = type_info['bit_size']

                        if 'enumerations' in type_info:
                            channel['enumerations'] = type_info['enumerations']

                        channel['eu_present'] = type_info.get('eu_present', 'No')

                        type_description = type_info.get('description')
                        if container_description and type_description:
                            channel['description'] = f"{container_description} - {type_description}"
                        elif container_description:
                            channel['description'] = container_description
                        elif type_description:
                            channel['description'] = type_description
                    else:
                        logger.warning(
                            f"parameterTypeRef '{param_type_ref}' not found for parameter "
                            f"'{bare_param_name}' (SpaceSystem scope: '{owning_ss_path}'); "
                            f"defaulting to string type"
                        )
                        channel['type'] = 'string'
                        channel['eu_present'] = 'No'
                        if container_description:
                            channel['description'] = container_description

                    channels.append(channel)

    except ET.ParseError as e:
        logger.error(f"Failed to parse XTCE channel dictionary {xml_file}: {e}")
    except Exception as e:
        logger.error(f"Error processing XTCE channel dictionary {xml_file}: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return channels


##################################################### Common Functions ##############################################

def detect_dictionary_type(xml_file: str, fmt: str) -> Optional[str]:
    """
    Detect dictionary type based on format.
    
    Args:
        xml_file: Path to XML file
        fmt: Format ('ampcs' or 'xtce')
        
    Returns:
        Dictionary type string or None
    """
    if fmt == 'ampcs':
        return detect_ampcs_type(xml_file)
    elif fmt == 'xtce':
        return detect_xtce_type(xml_file)
    else:
        logger.error(f"Unknown format: {fmt}")
        return None


def ensure_dictionary_version_exists(server: str, flight_sse: str, dictionary_version: str, 
                                    description: str = "Imported from XML dictionary") -> bool:
    """
    Ensure the dictionary version exists, create if it doesn't.
    
    Args:
        server: Ingenium server URL
        flight_sse: 'flight' or 'sse'
        dictionary_version: Version identifier
        description: Description for new dictionary version
        
    Returns:
        True if version exists or was created successfully
    """
    try:
        # Check if version already exists
        existing_versions = get_dictionary_versions(server, flight_sse)
        for version in existing_versions:
            if version.get('dictionary_version') == dictionary_version:
                logger.info(f"Dictionary version {dictionary_version} already exists")
                return True
                
        # Create new version
        logger.info(f"Creating new dictionary version: {dictionary_version}")
        content = {
            'dictionary_version': dictionary_version,
            'dictionary_description': description,
            'state': 'NOT_PUBLISHED'
        }
        
        result = create_dictionary_version(server, flight_sse, content)
        logger.info(f"Successfully created dictionary version: {dictionary_version}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to ensure dictionary version exists: {e}")
        return False


def upload_dictionary_content(server: str, flight_sse: str, dictionary_version: str, 
                            dict_type: str, content: List[Dict[str, Any]]) -> bool:
    """
    Upload dictionary content to Ingenium server.
    
    Args:
        server: Ingenium server URL
        flight_sse: 'flight' or 'sse'
        dictionary_version: Version identifier
        dict_type: 'cmds', 'channels', or 'evrs'
        content: List of dictionary objects
        
    Returns:
        True if upload successful
    """
    if not content:
        logger.warning(f"No {dict_type} content to upload")
        return True
        
    try:
        # Map dictionary types to API endpoints
        api_type_map = {
            'commands': 'cmds',
            'channels': 'channels', 
            'evrs': 'evrs',
            'mil1553': 'mil1553'
        }
        
        api_type = api_type_map.get(dict_type, dict_type)
        
        logger.info(f"Uploading {len(content)} {dict_type} to {server}")
        result = create_dictionary_content(server, flight_sse, content, dictionary_version, api_type)
        
        logger.info(f"Successfully uploaded {len(content)} {dict_type}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to upload {dict_type}: {e}")
        return False


def process_xml_file(xml_file: str, server: str, flight_sse: str, dictionary_version: str, fmt: str) -> bool:
    """
    Process a single XML file and upload its content.
    
    Args:
        xml_file: Path to XML file
        server: Ingenium server URL
        flight_sse: 'flight' or 'sse'
        dictionary_version: Version identifier
        fmt: Format ('ampcs' or 'xtce')
        
    Returns:
        True if processing successful
    """
    if not os.path.exists(xml_file):
        logger.error(f"XML file not found: {xml_file}")
        return False
        
    logger.info(f"Processing {fmt.upper()} XML file: {xml_file}")
    
    # Detect dictionary type
    dict_type = detect_dictionary_type(xml_file, fmt)
    if not dict_type:
        logger.error(f"Could not detect dictionary type for: {xml_file}")
        return False
        
    logger.info(f"Detected dictionary type: {dict_type}")
    
    # Handle XTCE 'both' case - file contains both commands and channels
    if dict_type == 'both':
        logger.info("File contains both commands and telemetry")
        
        # Parse and upload commands
        commands = parse_xtce_command_dictionary(xml_file)
        if commands:
            success = upload_dictionary_content(server, flight_sse, dictionary_version, 'commands', commands)
            if not success:
                return False
        
        # Parse and upload channels
        channels = parse_xtce_channel_dictionary(xml_file)
        if channels:
            success = upload_dictionary_content(server, flight_sse, dictionary_version, 'channels', channels)
            if not success:
                return False
        
        return True
    
    # Parse content based on type and format
    content = []
    if fmt == 'ampcs':
        if dict_type == 'commands':
            content = parse_command_dictionary(xml_file)
        elif dict_type == 'channels':
            content = parse_channel_dictionary(xml_file)
        elif dict_type == 'evrs':
            content = parse_evr_dictionary(xml_file)
        elif dict_type == 'mil1553':
            content = parse_mil1553_dictionary(xml_file)
    elif fmt == 'xtce':
        if dict_type == 'commands':
            content = parse_xtce_command_dictionary(xml_file)
        elif dict_type == 'channels':
            content = parse_xtce_channel_dictionary(xml_file)
        
    if not content:
        logger.warning(f"No content found in {xml_file}")
        return True
        
    # Upload content
    success = upload_dictionary_content(server, flight_sse, dictionary_version, dict_type, content)
    return success


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Load XML dictionary files (AMPCS or XTCE format) into Ingenium',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('server', 
                       help='Ingenium server URL (e.g., https://ingenium.project.jpl.nasa.gov)')
    parser.add_argument('dictionary_version',
                       help='Dictionary version identifier')
    parser.add_argument('flight_sse',
                       choices=['flight', 'sse'],
                       help='Dictionary type: flight or sse')
    parser.add_argument('--format',
                       choices=['ampcs', 'xtce'],
                       required=True,
                       help='Dictionary format: ampcs or xtce')
    parser.add_argument('xml_files', 
                       nargs='+',
                       help='One or more XML dictionary files')
    parser.add_argument('--debug', 
                       action='store_true',
                       help='Enable debug logging')
    parser.add_argument('--rsa',
                       action='store_true', 
                       help='Use RSA token for authentication instead of LDAP')
    parser.add_argument('--username', 
                       type=str,
                       help='Optional input to use a different username to login to Ingenium server.')
    parser.add_argument('--ignore_ssl_error', 
                       action='store_true', 
                       help='Ignore SSL verification error')
    parser.add_argument('--ssl_ca_bundle', 
                       type=str,
                       help='Path to the SSL CA bundle. If provided, this will override ignore_ssl_error.')
    parser.add_argument('--description',
                       type=str,
                       default='Imported from XML dictionary',
                       help='Description for the dictionary version (default: "Imported from XML dictionary")')
    
    return parser.parse_args()


def main():
    """Main function."""
    inputs = parse_arguments()
    
    # Setup debug logging (if desired)
    if inputs.debug:
        for handler in logger.root.handlers:
            handler.setLevel(logging.DEBUG)
            logger.debug("Logging set to Debug.")
    
    
    # Validate XML files exist
    missing_files = [f for f in inputs.xml_files if not os.path.exists(f)]
    if missing_files:
        logger.error(f"XML files not found: {missing_files}")
        sys.exit(1)
    
    # Configure SSL settings
    # if ssl_ca_bundle is specified, it will take precedence over ignore_ssl_error
    if inputs.ssl_ca_bundle is not None:
        common.set_ssl_verify(inputs.ssl_ca_bundle)
    else:
        common.set_ssl_verify(not inputs.ignore_ssl_error)
        if not common.get_ssl_verify():
            # To suppress SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.debug(f"Ingenium.ssl_verify:{common.get_ssl_verify()}")
        
    # Get username
    if inputs.username:
        username = inputs.username
    else:
        username = os.getenv('USER') or os.getenv('USERNAME')
        if not username:
            username = input("Enter username: ")
        
    logger.info(f"Connecting to {inputs.server} as {username}")
    
    # Authenticate
    if inputs.rsa:
        pw_prompt = f"Enter RSA Passcode for {username}:"
    else:
        pw_prompt = f"Enter LDAP Password for {username}:"
        
    login = common.authenticate(inputs.server, username=username, 
                              password=getpass.getpass(pw_prompt), force=True, rsa=inputs.rsa)
    
    if not login:
        logger.error(f"Failed to authenticate with {inputs.server}")
        sys.exit(1)
        
    logger.info("Successfully authenticated")
    
    # Ensure dictionary version exists
    if not ensure_dictionary_version_exists(inputs.server, inputs.flight_sse, 
                                          inputs.dictionary_version, inputs.description):
        logger.error("Failed to ensure dictionary version exists")
        sys.exit(1)
        
    # Process each XML file
    success_count = 0
    for xml_file in inputs.xml_files:
        if process_xml_file(xml_file, inputs.server, inputs.flight_sse, inputs.dictionary_version, inputs.format):
            success_count += 1
        else:
            logger.error(f"Failed to process {xml_file}")
            
    logger.info(f"Successfully processed {success_count}/{len(inputs.xml_files)} XML files")
    
    if success_count == len(inputs.xml_files):
        logger.info("All XML files processed successfully")
    else:
        logger.warning(f"{len(inputs.xml_files) - success_count} files failed to process")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except common.IngeniumLibError as e:
        logger.error(f"Ingenium error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
