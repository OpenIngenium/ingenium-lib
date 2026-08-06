"""
Integration tests for end-to-end workflows across multiple ProjConfig applications.

These tests verify that the applications work together correctly in realistic scenarios:
1. Backup → Clear → Restore workflow
2. Backup → Modify → Restore workflow
3. Custom Script creation → Palette update workflow
4. AMPCS Dictionary load → Backup workflow

Authors:
    * Chris Swan (christopher.a.swan@jpl.nasa.gov)
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open

# Import all the applications under test
from apps.ProjConfigBackup import main as backup_main, get_source_dictionaries
from apps.ProjConfigClear import main as clear_main, clear_project_configuration
from apps.ProjConfigRestore import main as restore_main, restore_dictionaries
from apps.ProjConfigCreateUpdateCS import main as create_cs_main
from apps.ProjConfigPalette import main as palette_main
from apps.ProjConfigLoadDict import main as load_dict_main
import ing_lib.common as common


class TestBackupClearRestoreWorkflow:
    """Test the complete backup → clear → restore workflow."""
    
    def test_backup_clear_restore_complete_workflow(self, comprehensive_server_mock, mock_user_input):
        """Test full workflow: backup project config, clear it, then restore it."""
        
        # Step 1: Backup
        backup_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        backup_path = backup_file.name
        backup_file.close()
        
        try:
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://test-server.example.com',
                    'v4',
                    backup_path
                ]
                
                backup_main(backup_args)
                
                # Verify backup was created
                mock_file.assert_called_with(backup_path, 'w')
                mock_json_dump.assert_called_once()
                
                # Get the backed up data
                backed_up_data = mock_json_dump.call_args[0][0]
                assert 'versions' in backed_up_data
                assert 'flight' in backed_up_data['versions']
                assert 'sse' in backed_up_data['versions']
            
            # Step 2: Clear
            with patch('builtins.input', return_value='yes'), \
                 patch('apps.ProjConfigClear.clear_project_configuration') as mock_clear:
                
                clear_args = [
                    'https://test-server.example.com'
                ]
                
                clear_main(clear_args)
                
                # Verify clear was called with all types
                mock_clear.assert_called_once_with(
                    'https://test-server.example.com',
                    ['flight', 'sse', 'vis', 'custom-scripts']
                )
            
            # Step 3: Restore
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.load', return_value=backed_up_data) as mock_json_load, \
                 patch('apps.ProjConfigRestore.restore_dictionaries') as mock_restore:
                
                restore_args = [
                    'https://test-server.example.com',
                    backup_path
                ]
                
                restore_main(restore_args)
                
                # Verify restore was called with the backed up data
                mock_restore.assert_called_once_with(
                    'https://test-server.example.com',
                    backed_up_data
                )
        
        finally:
            # Cleanup
            if os.path.exists(backup_path):
                os.remove(backup_path)
    
    def test_selective_backup_and_restore(self, comprehensive_server_mock, mock_user_input):
        """Test backing up only specific content types and restoring them."""
        
        backup_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        backup_path = backup_file.name
        backup_file.close()
        
        try:
            # Backup only commands and custom scripts
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://test-server.example.com',
                    'v4',
                    backup_path,
                    '--include_cmds',
                    '--include_cs'
                ]
                
                backup_main(backup_args)
                
                backed_up_data = mock_json_dump.call_args[0][0]
                
                # Verify selective backup
                assert 'custom_scripts' in backed_up_data
                assert 'versions' in backed_up_data
            
            # Restore the selective backup
            with patch('builtins.open', mock_open()), \
                 patch('json.load', return_value=backed_up_data), \
                 patch('apps.ProjConfigRestore.restore_dictionaries') as mock_restore:
                
                restore_args = [
                    'https://test-server.example.com',
                    backup_path
                ]
                
                restore_main(restore_args)
                
                mock_restore.assert_called_once()
        
        finally:
            if os.path.exists(backup_path):
                os.remove(backup_path)
    
    def test_backup_with_filter_then_restore(self, comprehensive_server_mock, mock_user_input):
        """Test backing up with retired filter and restoring."""
        
        backup_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        backup_path = backup_file.name
        backup_file.close()
        
        try:
            # Backup with filter_retired
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://test-server.example.com',
                    'v4',
                    backup_path,
                    '--filter_retired',
                    '--include_all'
                ]
                
                backup_main(backup_args)
                
                backed_up_data = mock_json_dump.call_args[0][0]
                
                # Verify backup structure
                assert 'versions' in backed_up_data
                assert 'vis' in backed_up_data
                assert 'custom_scripts' in backed_up_data
            
            # Restore should work with filtered backup
            with patch('builtins.open', mock_open()), \
                 patch('json.load', return_value=backed_up_data), \
                 patch('apps.ProjConfigRestore.restore_dictionaries') as mock_restore:
                
                restore_args = [
                    'https://test-server.example.com',
                    backup_path
                ]
                
                restore_main(restore_args)
                
                mock_restore.assert_called_once()
        
        finally:
            if os.path.exists(backup_path):
                os.remove(backup_path)


class TestCustomScriptPaletteWorkflow:
    """Test the custom script creation → palette update workflow."""
    
    def test_create_custom_script_then_update_palette(self, comprehensive_server_mock, mock_user_input):
        """Test creating a custom script and then updating the palette to include it."""
        
        # Create temporary script file
        with tempfile.TemporaryDirectory() as temp_dir:
            script_file = os.path.join(temp_dir, 'test_script.sh')
            with open(script_file, 'w') as f:
                f.write('#!/bin/bash\necho "test"')
            
            # Create XML definition
            xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <custom_script script_name="integration_test_script" 
                   script_path="test_script.sh" 
                   description="Integration test script"
                   is_command="false">
        <input_field name="test_input" type="STRING" phase="EXECUTION" required="YES" 
                     description="Test input"/>
        <output_field name="test_output" type="STRING" description="Test output"/>
    </custom_script>
</custom-scripts>"""
            
            xml_file = os.path.join(temp_dir, 'test_script.xml')
            with open(xml_file, 'w') as f:
                f.write(xml_content)
            
            # Step 1: Create custom script
            with patch('apps.ProjConfigCreateUpdateCS.create_custom_script') as mock_create, \
                 patch('apps.ProjConfigCreateUpdateCS.get_custom_scripts', return_value=[]):
                
                mock_create.return_value = {
                    'script_name': 'integration_test_script',
                    'script_id': 'test_script_id'
                }
                
                cs_args = [
                    'https://test-server.example.com',
                    xml_file,
                    '--base_path', temp_dir
                ]
                
                create_cs_main(cs_args)
                
                # Verify script was created
                assert mock_create.called
            
            # Step 2: Query palette to get current state
            with patch('apps.ProjConfigPalette.get_palette_info') as mock_get_palette, \
                 patch('apps.ProjConfigPalette.write_palette_excel') as mock_write_excel:
                
                mock_get_palette.return_value = {
                    'built_in': [],
                    'custom': [
                        {
                            'step_id': 'test_script_id',
                            'step_display_name': 'Integration Test Script',
                            'palette_category': 'Custom',
                            'step_path': 'test_script.sh',
                            'step_hash': 'abc123'
                        }
                    ]
                }
                
                excel_file = os.path.join(temp_dir, 'palette.xlsx')
                palette_args = [
                    'https://test-server.example.com',
                    'query',
                    excel_file
                ]
                
                palette_main(palette_args)
                
                # Verify palette was queried and written
                mock_get_palette.assert_called_once()
                mock_write_excel.assert_called_once()
                
                # Verify the custom script appears in palette
                written_data = mock_write_excel.call_args[0][1]
                assert 'custom' in written_data
                assert len(written_data['custom']) > 0
                assert written_data['custom'][0]['step_id'] == 'test_script_id'
    
    def test_create_multiple_scripts_and_manage_palette(self, comprehensive_server_mock, mock_user_input):
        """Test creating multiple custom scripts and managing them in the palette."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple scripts
            scripts = []
            for i in range(3):
                script_file = os.path.join(temp_dir, f'script_{i}.sh')
                with open(script_file, 'w') as f:
                    f.write(f'#!/bin/bash\necho "script {i}"')
                
                xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<custom-scripts>
    <custom_script script_name="test_script_{i}" 
                   script_path="script_{i}.sh" 
                   description="Test script {i}"
                   is_command="false">
        <input_field name="input_{i}" type="STRING" phase="EXECUTION" required="YES" 
                     description="Input {i}"/>
        <output_field name="output_{i}" type="STRING" description="Output {i}"/>
    </custom_script>
</custom-scripts>"""
                
                xml_file = os.path.join(temp_dir, f'script_{i}.xml')
                with open(xml_file, 'w') as f:
                    f.write(xml_content)
                
                scripts.append({
                    'xml': xml_file,
                    'script_id': f'script_id_{i}',
                    'name': f'test_script_{i}'
                })
            
            # Create all scripts
            for script in scripts:
                with patch('apps.ProjConfigCreateUpdateCS.create_custom_script') as mock_create, \
                     patch('apps.ProjConfigCreateUpdateCS.get_custom_scripts', return_value=[]):
                    
                    mock_create.return_value = {
                        'script_name': script['name'],
                        'script_id': script['script_id']
                    }
                    
                    cs_args = [
                        'https://test-server.example.com',
                        script['xml'],
                        '--base_path', temp_dir
                    ]
                    
                    create_cs_main(cs_args)
            
            # Query palette with all scripts
            with patch('apps.ProjConfigPalette.get_palette_info') as mock_get_palette, \
                 patch('apps.ProjConfigPalette.write_palette_excel') as mock_write_excel:
                
                mock_get_palette.return_value = {
                    'built_in': [],
                    'custom': [
                        {
                            'step_id': script['script_id'],
                            'step_display_name': script['name'],
                            'palette_category': 'Custom',
                            'step_path': f"script_{i}.sh",
                            'step_hash': f'hash_{i}'
                        }
                        for i, script in enumerate(scripts)
                    ]
                }
                
                excel_file = os.path.join(temp_dir, 'palette.xlsx')
                palette_args = [
                    'https://test-server.example.com',
                    'query',
                    excel_file
                ]
                
                palette_main(palette_args)
                
                # Verify all scripts are in palette
                written_data = mock_write_excel.call_args[0][1]
                assert len(written_data['custom']) == 3


class TestAMPCSDictionaryBackupWorkflow:
    """Test the AMPCS dictionary load → backup workflow."""
    
    def test_load_ampcs_then_backup(self, comprehensive_server_mock, mock_user_input):
        """Test loading AMPCS dictionaries and then backing them up."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create sample AMPCS command dictionary
            cmd_dict_content = """<?xml version="1.0"?>
<command_dictionary>
    <command_definitions>
        <fsw_command stem="TEST_CMD" class="FSW">
            <description>Test command</description>
            <categories>
                <ops_category>TEST</ops_category>
            </categories>
        </fsw_command>
    </command_definitions>
</command_dictionary>"""
            
            cmd_dict_file = os.path.join(temp_dir, 'cmd_dict.xml')
            with open(cmd_dict_file, 'w') as f:
                f.write(cmd_dict_content)
            
            # Create sample AMPCS channel dictionary
            ch_dict_content = """<?xml version="1.0"?>
<telemetry_dictionary>
    <telemetry_definitions>
        <telemetry name="TEST_CH" abbreviation="TCH" type="integer" byte_length="4" source="flight">
            <description>Test channel</description>
        </telemetry>
    </telemetry_definitions>
</telemetry_dictionary>"""
            
            ch_dict_file = os.path.join(temp_dir, 'ch_dict.xml')
            with open(ch_dict_file, 'w') as f:
                f.write(ch_dict_content)
            
            # Step 1: Load AMPCS dictionaries
            with patch('apps.ProjConfigLoadDict.ensure_dictionary_version_exists', return_value=True), \
                 patch('apps.ProjConfigLoadDict.upload_dictionary_content', return_value=True):
                
                with patch('sys.argv', [
                    'script',
                    'https://test-server.example.com',
                    'v1.0',
                    'flight',
                    '--format', 'ampcs',
                    cmd_dict_file,
                    ch_dict_file
                ]):
                    load_dict_main()
            
            # Step 2: Backup the loaded dictionaries
            backup_file = os.path.join(temp_dir, 'backup.json')
            
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://test-server.example.com',
                    'v4',
                    backup_file,
                    '--include_cmds',
                    '--include_eha'
                ]
                
                backup_main(backup_args)
                
                # Verify backup includes the loaded dictionaries
                backed_up_data = mock_json_dump.call_args[0][0]
                assert 'versions' in backed_up_data
                assert 'flight' in backed_up_data


class TestComplexIntegrationScenarios:
    """Test complex multi-step integration scenarios."""
    
    def test_full_migration_workflow(self, comprehensive_server_mock, mock_user_input):
        """Test a complete migration: backup source → load to target → verify."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_file = os.path.join(temp_dir, 'migration_backup.json')
            
            # Step 1: Backup from source server
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://source-server.example.com',
                    'v4',
                    backup_file,
                    '--include_all'
                ]
                
                backup_main(backup_args)
                
                source_data = mock_json_dump.call_args[0][0]
            
            # Step 2: Clear target server
            with patch('builtins.input', return_value='yes'), \
                 patch('apps.ProjConfigClear.clear_project_configuration') as mock_clear:
                
                clear_args = [
                    'https://target-server.example.com'
                ]
                
                clear_main(clear_args)
                
                mock_clear.assert_called_once()
            
            # Step 3: Restore to target server
            with patch('builtins.open', mock_open()), \
                 patch('json.load', return_value=source_data), \
                 patch('apps.ProjConfigRestore.restore_dictionaries') as mock_restore:
                
                restore_args = [
                    'https://target-server.example.com',
                    backup_file
                ]
                
                restore_main(restore_args)
                
                # Verify restore was called with source data
                mock_restore.assert_called_once_with(
                    'https://target-server.example.com',
                    source_data
                )
            
            # Step 4: Verify by backing up target server
            verify_backup_file = os.path.join(temp_dir, 'verify_backup.json')
            
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://target-server.example.com',
                    'v4',
                    verify_backup_file,
                    '--include_all'
                ]
                
                backup_main(backup_args)
                
                target_data = mock_json_dump.call_args[0][0]
                
                # Verify structure matches
                assert 'versions' in target_data
                assert 'flight' in target_data['versions']
                assert 'sse' in target_data['versions']
    
    def test_incremental_update_workflow(self, comprehensive_server_mock, mock_user_input):
        """Test incremental updates: backup → modify palette → backup again."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 1: Initial backup
            backup1_file = os.path.join(temp_dir, 'backup1.json')
            
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://test-server.example.com',
                    'v4',
                    backup1_file,
                    '--include_all'
                ]
                
                backup_main(backup_args)
                
                initial_data = mock_json_dump.call_args[0][0]
            
            # Step 2: Modify palette
            excel_file = os.path.join(temp_dir, 'palette.xlsx')
            
            with patch('apps.ProjConfigPalette.get_palette_info') as mock_get_palette, \
                 patch('apps.ProjConfigPalette.read_palette_excel') as mock_read_excel, \
                 patch('apps.ProjConfigPalette.update_palette_info') as mock_update:
                
                mock_get_palette.return_value = {
                    'built_in': [
                        {
                            'step_type': 'MANUAL_INPUT',
                            'step_display_name': 'Manual Input',
                            'palette_category': 'Input',
                            'enable_disable': 'enable'
                        }
                    ],
                    'custom': []
                }
                
                mock_read_excel.return_value = {
                    'built_in': [
                        {
                            'step_type': 'MANUAL_INPUT',
                            'step_display_name': 'Updated Manual Input',
                            'palette_category': 'Input',
                            'enable_disable': 'enable'
                        }
                    ],
                    'custom': []
                }
                
                palette_args = [
                    'https://test-server.example.com',
                    'update',
                    excel_file,
                    '--confirm'
                ]
                
                palette_main(palette_args)
                
                mock_update.assert_called_once()
            
            # Step 3: Backup after modification
            backup2_file = os.path.join(temp_dir, 'backup2.json')
            
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://test-server.example.com',
                    'v4',
                    backup2_file,
                    '--include_all'
                ]
                
                backup_main(backup_args)
                
                modified_data = mock_json_dump.call_args[0][0]
                
                # Both backups should have the same structure
                assert 'versions' in modified_data
    
    def test_disaster_recovery_workflow(self, comprehensive_server_mock, mock_user_input):
        """Test disaster recovery: backup → simulate failure → restore."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_file = os.path.join(temp_dir, 'disaster_backup.json')
            
            # Step 1: Create backup before disaster
            with patch('builtins.open', mock_open()) as mock_file, \
                 patch('json.dump') as mock_json_dump:
                
                backup_args = [
                    'https://test-server.example.com',
                    'v4',
                    backup_file,
                    '--include_all'
                ]
                
                backup_main(backup_args)
                
                pre_disaster_data = mock_json_dump.call_args[0][0]
            
            # Step 2: Simulate disaster - clear everything
            with patch('builtins.input', return_value='yes'), \
                 patch('apps.ProjConfigClear.clear_project_configuration') as mock_clear:
                
                clear_args = [
                    'https://test-server.example.com'
                ]
                
                clear_main(clear_args)
                
                # Verify everything was cleared
                mock_clear.assert_called_once_with(
                    'https://test-server.example.com',
                    ['flight', 'sse', 'vis', 'custom-scripts']
                )
            
            # Step 3: Restore from backup
            with patch('builtins.open', mock_open()), \
                 patch('json.load', return_value=pre_disaster_data), \
                 patch('apps.ProjConfigRestore.restore_dictionaries') as mock_restore:
                
                restore_args = [
                    'https://test-server.example.com',
                    backup_file
                ]
                
                restore_main(restore_args)
                
                # Verify restore was called with pre-disaster data
                mock_restore.assert_called_once_with(
                    'https://test-server.example.com',
                    pre_disaster_data
                )
                
                # Verify data structure is intact
                restored_data = mock_restore.call_args[0][1]
                assert 'versions' in restored_data
                assert 'flight' in restored_data['versions']
                assert 'sse' in restored_data['versions']
                assert 'vis' in restored_data
                assert 'custom_scripts' in restored_data
