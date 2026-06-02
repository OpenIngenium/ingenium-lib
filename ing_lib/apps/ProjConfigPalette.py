"""
This script reads and writes to a MS Excel File that contains the settings for the Step Palette.

It has three modes of operation:
1. Query the Ingenium Server for built-in and custom steps in the step palette and write that information to an Excel File.
2. Diff the contents of an Excel File with the Ingenium Server for the step palette
3. Update the Ingenium Server with the contents of an Excel File

Authors:
    * Chris Swan
"""

##################################################### Imports ######################################################
import sys
import os

import logging
from ing_lib.logs import init_console_logger, get_logger

init_console_logger()

import ing_lib.common as common
from ing_lib.project_config import get_custom_scripts, create_custom_script, update_custom_script
from ing_lib.project_config import get_built_in_palette, get_custom_palette
from ing_lib.project_config import update_built_in_palette, create_custom_palette, update_custom_palette, delete_custom_palette
import argparse
import getpass
import urllib3
import openpyxl
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet


##################################################### Functions ######################################################

logger = get_logger(__name__)


def get_input(args=[]):
    """
    This function gathers inputs for the Palette script

    Parameters
    --------
    args
        list of input arguments. Used when this is called from another Python module.

    Returns
    -------
        inputs: object
            Argparse input object
    """

    parser = argparse.ArgumentParser(
        description='This script helps manage the step palette for an Ingenium Server',
        prog='Ingenium Palette Script',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-sample_project.jpl.nasa.gov)')
    parser.add_argument('function', type=str, choices=['query', 'diff', 'update', 'delete'],
                        help='Function to perform. Can be one of: query, diff, update, delete.')
    parser.add_argument('excel', type=str,
                        help='Path to the Excel file to use for diff or update.')
    parser.add_argument('--debug', action='store_true', help='Enables debug logging.')
    parser.add_argument('--username', type=str,
                        help='Optional input to use a different username to login to Ingenium server.')
    parser.add_argument('--ignore_ssl_error', action='store_true', help='Ignore SSL verification error')
    parser.add_argument('--ssl_ca_bundle', type=str,
                        help='Path to the SSL CA bundle. If provided, this will override ignore_ssl_error.')
    parser.add_argument('--rsa', action='store_true',
                        help='Uses RSA Two Factor Authentication (username/passcode) to authenticate.')
    parser.add_argument('--confirm', action='store_true',
                        help='Automatically confirm all actions without prompting user.')


    if len(args) > 0:
        inputs = parser.parse_args(args)
    else:
        inputs = parser.parse_args()

    # Setup debug logging (if desired)
    if inputs.debug:
        for handler in logger.root.handlers:
            handler.setLevel(logging.DEBUG)
            logger.debug("Logging set to Debug.")

    return inputs

def get_palette_info(server):
    """
    This function queries the Ingenium server for both built-in and custom step palette information

    Parameters
    ----------
    server : str
        Ingenium Server (e.g. https://ingenium-sample_project.jpl.nasa.gov) without a trailing slash

    Returns
    -------
    dict
        Dictionary containing built-in and custom palette information
    """
    logger.info(f"Querying palette information from server: {server}")
    
    try:
        # Get built-in palette information
        built_in_palette = get_built_in_palette(server)
        logger.info(f"Retrieved {len(built_in_palette)} built-in steps")
        
        # Get custom palette information
        custom_palette = get_custom_palette(server)
        logger.info(f"Retrieved {len(custom_palette)} custom steps")
        
        palette_info = {
            'built_in': built_in_palette,
            'custom': custom_palette
        }
        
        return palette_info
        
    except Exception as e:
        msg = f"Error getting palette information from server: {e}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

def read_palette_excel(excel_path):
    """
    This function reads palette information from an Excel file with separate worksheets for built-in and custom steps

    Parameters
    ----------
    excel_path : str
        Path to the Excel file

    Returns
    -------
    dict
        Dictionary containing built-in and custom palette information
    """
    logger.info(f"Reading palette information from Excel file: {excel_path}")
    
    try:
        # Load the workbook
        workbook = openpyxl.load_workbook(excel_path)
        
        palette_info = {}
        
        # Read built-in steps worksheet
        if 'Built-in Steps' in workbook.sheetnames:
            built_in_ws = workbook['Built-in Steps']
            built_in_steps = []
            
            # Get headers from first row
            headers = []
            for cell in built_in_ws[1]:
                headers.append(cell.value)
            
            # Read data rows
            for row in built_in_ws.iter_rows(min_row=2, values_only=True):
                if any(cell is not None for cell in row):  # Skip empty rows
                    step_data = dict(zip(headers, row))
                    built_in_steps.append(step_data)
            
            palette_info['built_in'] = built_in_steps
            logger.info(f"Read {len(built_in_steps)} built-in steps from Excel")
        else:
            logger.warning("No 'Built-in Steps' worksheet found in Excel file")
            palette_info['built_in'] = []
        
        # Read custom steps worksheet
        if 'Custom Steps' in workbook.sheetnames:
            custom_ws = workbook['Custom Steps']
            custom_steps = []
            
            # Get headers from first row
            headers = []
            for cell in custom_ws[1]:
                headers.append(cell.value)
            
            # Read data rows
            for row in custom_ws.iter_rows(min_row=2, values_only=True):
                if any(cell is not None for cell in row):  # Skip empty rows
                    step_data = dict(zip(headers, row))
                    # Only add if this looks like real data (not just a placeholder message)
                    if not (len(step_data) == 1 and list(step_data.values())[0] in ["No custom steps found", "No custom steps data provided"]):
                        custom_steps.append(step_data)

            palette_info['custom'] = custom_steps
            logger.info(f"Read {len(custom_steps)} custom steps from Excel")
        else:
            logger.warning("No 'Custom Steps' worksheet found in Excel file")
            palette_info['custom'] = []
        
        workbook.close()
        return palette_info
        
    except FileNotFoundError:
        msg = f"Excel file not found: {excel_path}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)
    except Exception as e:
        msg = f"Error reading Excel file: {e}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

def write_palette_excel(excel_path, palette_info):
    """
    This function writes palette information to an Excel file with separate worksheets for built-in and custom steps

    Parameters
    ----------
    excel_path : str
        Path to the Excel file to create/overwrite
    palette_info : dict
        Dictionary containing built-in and custom palette information
    """
    logger.info(f"Writing palette information to Excel file: {excel_path}")
    
    try:
        # Create a new workbook
        workbook = Workbook()
        
        # Remove the default sheet
        if 'Sheet' in workbook.sheetnames:
            workbook.remove(workbook['Sheet'])
        
        # Write built-in steps worksheet
        if palette_info.get('built_in'):
            built_in_ws = workbook.create_sheet('Built-in Steps')
            
            # Get all possible keys from built-in steps for headers
            built_in_steps = palette_info['built_in']
            if built_in_steps:
                headers = set()
                for step in built_in_steps:
                    if isinstance(step, dict):
                        headers.update(step.keys())
                headers = sorted(list(headers))
                
                # Write headers
                for col_idx, header in enumerate(headers, 1):
                    built_in_ws.cell(row=1, column=col_idx, value=header)
                
                # Write data
                for row_idx, step in enumerate(built_in_steps, 2):
                    if isinstance(step, dict):
                        for col_idx, header in enumerate(headers, 1):
                            value = step.get(header, '')
                            built_in_ws.cell(row=row_idx, column=col_idx, value=value)
                
                logger.info(f"Wrote {len(built_in_steps)} built-in steps to Excel")
            else:
                built_in_ws.cell(row=1, column=1, value="No built-in steps found")
        else:
            # Create empty sheet with message
            built_in_ws = workbook.create_sheet('Built-in Steps')
            built_in_ws.cell(row=1, column=1, value="No built-in steps data provided")
        
        # Write custom steps worksheet
        custom_ws = workbook.create_sheet('Custom Steps')
        
        if palette_info.get('custom'):
            # Get all possible keys from custom steps for headers
            custom_steps = palette_info['custom']
            if custom_steps:
                headers = set()
                for step in custom_steps:
                    if isinstance(step, dict):
                        headers.update(step.keys())
                headers = sorted(list(headers))
                
                # Write headers
                for col_idx, header in enumerate(headers, 1):
                    custom_ws.cell(row=1, column=col_idx, value=header)
                
                # Write data
                for row_idx, step in enumerate(custom_steps, 2):
                    if isinstance(step, dict):
                        for col_idx, header in enumerate(headers, 1):
                            value = step.get(header, '')
                            custom_ws.cell(row=row_idx, column=col_idx, value=value)
                
                logger.info(f"Wrote {len(custom_steps)} custom steps to Excel")
        else:
            # Write default headers even when no custom steps data provided
            default_headers = ['step_id','step_hash', 'step_path', 'palette_category', 'step_display_name']
            for col_idx, header in enumerate(default_headers, 1):
                custom_ws.cell(row=1, column=col_idx, value=header)
            logger.info("Created custom steps worksheet with default headers")
        
        # Save the workbook
        workbook.save(excel_path)
        workbook.close()
        
        logger.info(f"Successfully wrote palette information to {excel_path}")
        
    except Exception as e:
        msg = f"Error writing Excel file: {e}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

def diff_palette_info(current_palette, excel_palette):
    """
    This function compares the current palette information from the server with the Excel palette data

    Parameters
    ----------
    current_palette : dict
        Dictionary containing current built-in and custom palette information from server
    excel_palette : dict
        Dictionary containing built-in and custom palette information from Excel file
    """
    logger.info("Comparing current palette with Excel palette data")
    
    try:
        # Compare built-in steps
        current_built_in = current_palette.get('built_in', [])
        excel_built_in = excel_palette.get('built_in', [])
        
        logger.info("=== Built-in Steps Comparison ===")
        logger.info(f"Current server built-in steps: {len(current_built_in)}")
        logger.info(f"Excel built-in steps: {len(excel_built_in)}")
        
        # Create dictionaries for easier comparison (using step_type as key)
        current_built_in_dict = {}
        for step in current_built_in:
            if isinstance(step, dict) and 'step_type' in step:
                current_built_in_dict[step['step_type']] = step
        
        excel_built_in_dict = {}
        for step in excel_built_in:
            if isinstance(step, dict) and 'step_type' in step:
                excel_built_in_dict[step['step_type']] = step
        
        # Find differences in built-in steps
        built_in_only_in_server = set(current_built_in_dict.keys()) - set(excel_built_in_dict.keys())
        built_in_only_in_excel = set(excel_built_in_dict.keys()) - set(current_built_in_dict.keys())
        built_in_common = set(current_built_in_dict.keys()) & set(excel_built_in_dict.keys())
        
        if built_in_only_in_server:
            logger.info(f"Built-in steps only in server: {len(built_in_only_in_server)}")
            for step_type in sorted(built_in_only_in_server):
                logger.info(f"  - {step_type}")
        
        if built_in_only_in_excel:
            logger.info(f"Built-in steps only in Excel: {len(built_in_only_in_excel)}")
            for step_type in sorted(built_in_only_in_excel):
                logger.info(f"  - {step_type}")
        
        # Check for differences in common built-in steps
        built_in_differences = []
        for step_type in built_in_common:
            current_step = current_built_in_dict[step_type]
            excel_step = excel_built_in_dict[step_type]
            
            # Compare key fields
            fields_to_compare = ['step_display_name', 'palette_category', 'enable_disable']
            for field in fields_to_compare:
                if current_step.get(field) != excel_step.get(field):
                    built_in_differences.append({
                        'step_type': step_type,
                        'field': field,
                        'current': current_step.get(field),
                        'excel': excel_step.get(field)
                    })
        
        if built_in_differences:
            logger.info(f"Built-in steps with differences: {len(built_in_differences)}")
            for diff in built_in_differences:
                logger.info(f"  - {diff['step_type']}.{diff['field']}: "
                           f"Server='{diff['current']}' vs Excel='{diff['excel']}'")
        
        # Compare custom steps
        current_custom = current_palette.get('custom', [])
        excel_custom = excel_palette.get('custom', [])
        
        logger.info("\n=== Custom Steps Comparison ===")
        logger.info(f"Current server custom steps: {len(current_custom)}")
        logger.info(f"Excel custom steps: {len(excel_custom)}")
        
        # Create dictionaries for easier comparison (using step_id as key)
        current_custom_dict = {}
        for step in current_custom:
            if isinstance(step, dict):
                key = step.get('step_id')
                current_custom_dict[key] = step
        
        excel_custom_dict = {}
        for step in excel_custom:
            if isinstance(step, dict):
                key = step.get('step_id')
                excel_custom_dict[key] = step

        # Find differences in custom steps
        custom_only_in_server = set(current_custom_dict.keys()) - set(excel_custom_dict.keys())
        custom_only_in_excel = set(excel_custom_dict.keys()) - set(current_custom_dict.keys())
        custom_common = set(current_custom_dict.keys()) & set(excel_custom_dict.keys())
        
        if custom_only_in_server:
            logger.info(f"Custom steps only in server: {len(custom_only_in_server)}")
            for key in sorted(custom_only_in_server):
                logger.info(f"  - {current_custom_dict[key]['step_display_name']}{key}")
        
        if custom_only_in_excel:
            logger.info(f"Custom steps only in Excel: {len(custom_only_in_excel)}")
            for key in sorted(custom_only_in_excel):
                logger.info(f"  - {excel_custom_dict[key]['step_display_name']}({key})")
        
        # Check for differences in common custom steps
        custom_differences = []
        for key in custom_common:
            current_step = current_custom_dict[key]
            excel_step = excel_custom_dict[key]
            
            # Compare key fields
            fields_to_compare = ['step_display_name', 'palette_category', 'script_id', 'step_path', 'step_hash']
            for field in fields_to_compare:
                if current_step.get(field) != excel_step.get(field):
                    custom_differences.append({
                        'key': key,
                        'field': field,
                        'current': current_step.get(field),
                        'excel': excel_step.get(field)
                    })
        
        if custom_differences:
            logger.info(f"Custom steps with differences: {len(custom_differences)}")
            for diff in custom_differences:
                logger.info(f"  - {diff['key']}.{diff['field']}: "
                           f"Server='{diff['current']}' vs Excel='{diff['excel']}'")
        
        # Summary
        total_differences = (len(built_in_only_in_server) + len(built_in_only_in_excel) + 
                           len(built_in_differences) + len(custom_only_in_server) + 
                           len(custom_only_in_excel) + len(custom_differences))
        
        logger.info(f"\n=== Summary ===")
        logger.info(f"Total differences found: {total_differences}")
        
        if total_differences == 0:
            logger.info("No differences found between server and Excel palette data")
        else:
            logger.info("Differences found. Review the details above and consider using 'update' function if needed")
        
    except Exception as e:
        msg = f"Error comparing palette information: {e}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

def update_palette_info(server, current_palette, excel_palette, confirm=False):
    """
    This function updates the Ingenium server with palette information from Excel data

    Parameters
    ----------
    server : str
        Ingenium Server (e.g. https://ingenium-sample_project.jpl.nasa.gov) without a trailing slash

    current_palette : dict
        Dictionary containing built-in and custom palette information from server

    excel_palette : dict
        Dictionary containing built-in and custom palette information from Excel file
    
    confirm : bool
        If True, automatically confirm all updates without prompting user
    """
    logger.info("Updating server palette with Excel data")
    
    try:
        # Show detailed differences before proceeding
        logger.info("=== Update Summary ===")
        logger.info("Displaying differences between server and Excel data:")
        diff_palette_info(current_palette, excel_palette)
        
        # Count potential changes
        excel_built_in = excel_palette.get('built_in', [])
        current_built_in = current_palette.get('built_in', [])
        excel_custom = excel_palette.get('custom', [])
        current_custom = current_palette.get('custom', [])
        
        logger.info(f"\nBasic counts:")
        logger.info(f"Built-in steps in Excel: {len(excel_built_in)}")
        logger.info(f"Built-in steps on server: {len(current_built_in)}")
        logger.info(f"Custom steps in Excel: {len(excel_custom)}")
        logger.info(f"Custom steps on server: {len(current_custom)}")
        
        if not confirm:
            # Ask for user confirmation before proceeding
            while True:
                response = input(f"\nDo you want to proceed with updating the server palette? (y/n): ").strip().lower()
                if response in ['y', 'yes']:
                    break
                elif response in ['n', 'no']:
                    logger.info("Update cancelled by user")
                    return
                else:
                    print("Please enter 'y' or 'n'")
        else:
            logger.info("Auto-confirmation enabled, proceeding with updates")

        # Update built-in steps
        excel_built_in = excel_palette.get('built_in', [])
        current_built_in = current_palette.get('built_in', [])
        
        logger.info("=== Updating Built-in Steps ===")
        
        # Create current built-in steps dictionary
        current_built_in_dict = {}
        for step in current_built_in:
            if isinstance(step, dict) and 'step_type' in step:
                current_built_in_dict[step['step_type']] = step
        
        # Update each built-in step from Excel (only if different)
        built_in_updates = 0
        built_in_skipped = 0
        for excel_step in excel_built_in:
            if isinstance(excel_step, dict) and 'step_type' in excel_step:
                step_type = excel_step['step_type']
                current_step = current_built_in_dict.get(step_type)
                
                if not current_step:
                    logger.warning(f"Built-in step {step_type} not found on server, skipping")
                    built_in_skipped += 1
                    continue
                
                # Check for differences
                differences = {}
                fields_to_check = ['step_display_name', 'palette_category', 'enable_disable']
                for field in fields_to_check:
                    if excel_step.get(field) != current_step.get(field):
                        differences[field] = {
                            'current': current_step.get(field),
                            'excel': excel_step.get(field)
                        }
                
                if differences:
                    # Prepare update content with only different fields
                    update_content = {}
                    for field in differences:
                        update_content[field] = excel_step.get(field)
                    
                    try:
                        result = update_built_in_palette(server, step_type, update_content)
                        logger.info(f"Updated built-in step: {step_type}")
                        for field, diff in differences.items():
                            logger.info(f"  {field}: '{diff['current']}' -> '{diff['excel']}'")
                        built_in_updates += 1
                    except Exception as e:
                        logger.warning(f"Failed to update built-in step {step_type}: {e}")
                else:
                    logger.debug(f"No differences found for built-in step {step_type}, skipping")
                    built_in_skipped += 1
        
        logger.info(f"Built-in steps updated: {built_in_updates}")
        logger.info(f"Built-in steps skipped (no differences): {built_in_skipped}")
        
        # Update custom steps
        excel_custom = excel_palette.get('custom', [])
        current_custom = current_palette.get('custom', [])
        
        logger.info("\n=== Updating Custom Steps ===")
        
        # Create current custom steps dictionary
        current_custom_dict = {}
        for step in current_custom:
            if isinstance(step, dict):
                key = step.get('step_id') or step.get('step_display_name') or str(hash(str(step)))
                current_custom_dict[key] = step
        
        # Process custom steps from Excel (only if different)
        custom_creates = 0
        custom_updates = 0
        custom_skipped = 0
        
        for excel_step in excel_custom:
            if isinstance(excel_step, dict):
                display_name = excel_step.get('step_display_name', '')
                step_id = excel_step.get('step_id')
                
                # Check if this is a new step or an update
                existing_step = None
                if step_id:
                    # Try to find by step_id
                    for current_step in current_custom:
                        if isinstance(current_step, dict) and current_step.get('step_id') == step_id:
                            existing_step = current_step
                            break
                
                if existing_step:
                    # Check for differences in existing custom step
                    differences = {}
                    fields_to_check = ['step_display_name', 'palette_category', 'step_id', 'step_path', 'step_hash']
                    for field in fields_to_check:
                        if excel_step.get(field) != existing_step.get(field):
                            differences[field] = {
                                'current': existing_step.get(field),
                                'excel': excel_step.get(field)
                            }
                    
                    if differences and existing_step.get('step_id'):
                        # Update only different fields
                        update_content = {}
                        for field in differences:
                            update_content[field] = excel_step.get(field)
                        
                        try:
                            result = update_custom_palette(server, existing_step['step_id'], update_content)
                            logger.info(f"Updated custom step: {display_name}")
                            for field, diff in differences.items():
                                logger.info(f"  {field}: '{diff['current']}' -> '{diff['excel']}'")
                            custom_updates += 1
                        except Exception as e:
                            logger.warning(f"Failed to update custom step {display_name}: {e}")
                    else:
                        logger.debug(f"No differences found for custom step {display_name}, skipping")
                        custom_skipped += 1
                else:
                    # Create new custom step (always create new steps)
                    required_fields = ['step_display_name', 'palette_category', 'step_id', 'step_path', 'step_hash']
                    if all(field in excel_step for field in required_fields):
                        create_content = {}
                        fields_to_create = ['step_display_name', 'palette_category', 'step_id', 'step_path', 'step_hash']
                        for field in fields_to_create:
                            if field in excel_step:
                                create_content[field] = excel_step[field]
                        
                        try:
                            result = create_custom_palette(server, [create_content])
                            logger.info(f"Created new custom step: {display_name}")
                            custom_creates += 1
                        except Exception as e:
                            logger.warning(f"Failed to create custom step {display_name}: {e}")
                    else:
                        logger.warning(f"Skipping custom step creation - missing required fields: {display_name}")
        
        logger.info(f"Custom steps created: {custom_creates}")
        logger.info(f"Custom steps updated: {custom_updates}")
        logger.info(f"Custom steps skipped (no differences): {custom_skipped}")
        
        # Summary
        total_updates = built_in_updates + custom_updates + custom_creates
        total_skipped = built_in_skipped + custom_skipped
        logger.info(f"\n=== Update Summary ===")
        logger.info(f"Total updates performed: {total_updates}")
        logger.info(f"Total steps skipped (no differences): {total_skipped}")
        logger.info(f"  - Built-in steps updated: {built_in_updates}")
        logger.info(f"  - Built-in steps skipped: {built_in_skipped}")
        logger.info(f"  - Custom steps created: {custom_creates}")
        logger.info(f"  - Custom steps updated: {custom_updates}")
        logger.info(f"  - Custom steps skipped: {custom_skipped}")
        
        if total_updates == 0:
            if total_skipped == 0:
                logger.info("No steps found to process")
            else:
                logger.info("No updates needed - all steps are already up to date")
        else:
            logger.info("Palette update completed successfully")
        
    except Exception as e:
        msg = f"Error updating palette information: {e}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

def delete_custom_steps(server, current_palette, excel_palette, confirm=False):
    """
    This function deletes custom steps from the Ingenium server based on Excel data with user confirmation

    Parameters
    ----------
    server : str
        Ingenium Server (e.g. https://ingenium-sample_project.jpl.nasa.gov) without a trailing slash

    current_palette : dict
        Dictionary containing custom palette information from server to delete

    excel_palette : dict
        Dictionary containing custom palette information from Excel file to delete
    
    confirm : bool
        If True, automatically confirm all deletions without prompting user
    """
    logger.info("Processing custom step deletions from Excel data")
    
    try:
        current_custom = current_palette.get('custom', [])
        
        # Create current custom steps dictionary for lookup
        current_custom_dict = {}
        for step in current_custom:
            if isinstance(step, dict) and step.get('step_id'):
                current_custom_dict[step['step_id']] = step
        
        excel_custom = excel_palette.get('custom', [])
        
        if not excel_custom:
            logger.info("No custom steps found in Excel file to delete")
            return
        
        logger.info("=== Custom Steps Deletion ===")
        logger.info(f"Found {len(excel_custom)} custom steps in Excel file for deletion")
        
        # Process each custom step from Excel for deletion
        deletions_confirmed = 0
        deletions_skipped = 0
        deletions_failed = 0
        
        for excel_step in excel_custom:
            if isinstance(excel_step, dict):
                step_id = excel_step.get('step_id')
                display_name = excel_step.get('step_display_name', 'Unknown')
                
                if not step_id:
                    logger.warning(f"Skipping custom step deletion - missing step_id: {display_name}")
                    deletions_skipped += 1
                    continue
                
                # Check if step exists on server
                if step_id not in current_custom_dict:
                    logger.warning(f"Custom step '{display_name}' ({step_id}) not found on server, skipping")
                    deletions_skipped += 1
                    continue
                
                existing_step = current_custom_dict[step_id]
                
                # Display step information and ask for confirmation
                logger.info(f"\nCustom step found for deletion:")
                logger.info(f"  Step ID: {step_id}")
                logger.info(f"  Display Name: {display_name}")
                logger.info(f"  Palette Category: {existing_step.get('palette_category', 'N/A')}")
                
                # Prompt user for confirmation unless auto-confirm is enabled
                confirmed = False
                if confirm:
                    confirmed = True
                    logger.info(f"Auto-confirmation enabled, deleting custom step: {display_name} ({step_id})")
                else:
                    while True:
                        response = input(f"\nDo you want to delete custom step '{display_name}' ({step_id})? (y/n): ").strip().lower()
                        if response in ['y', 'yes']:
                            confirmed = True
                            break
                        elif response in ['n', 'no']:
                            confirmed = False
                            break
                        else:
                            print("Please enter 'y' or 'n'")
                
                if confirmed:
                    try:
                        delete_custom_palette(server, step_id)
                        logger.info(f"Successfully deleted custom step: {display_name} ({step_id})")
                        deletions_confirmed += 1
                    except Exception as e:
                        logger.error(f"Failed to delete custom step {display_name} ({step_id}): {e}")
                        deletions_failed += 1
                else:
                    logger.info(f"Deletion cancelled by user for custom step: {display_name} ({step_id})")
                    deletions_skipped += 1
        
        # Summary
        logger.info(f"\n=== Deletion Summary ===")
        logger.info(f"Total steps processed: {len(excel_custom)}")
        logger.info(f"Steps deleted: {deletions_confirmed}")
        logger.info(f"Steps skipped: {deletions_skipped}")
        logger.info(f"Deletions failed: {deletions_failed}")
        
        if deletions_confirmed > 0:
            logger.info("Custom step deletion completed successfully")
        elif deletions_skipped > 0:
            logger.info("No custom steps were deleted (all skipped or cancelled)")
        else:
            logger.info("No custom steps found to process")
        
    except Exception as e:
        msg = f"Error deleting custom steps: {e}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)


##################################################### Main ###########################################################
def main(args=[]):
    """
    This is the main function of the Ingenium Create/Update Custom Script utility.

    Processes a single custom script definition from either XML or JSON format.
    Supports both XML (custom_script_schema.rnc format) and JSON (v4 OpenAPI CustomScript format) input files.
    Each input file is expected to contain exactly one custom script definition.
    File type is automatically detected and the appropriate parser is used.

    Parameters
    ----------
    args
        Array of input arguments. Used when this function is called from another Python module.

    Returns
    -------
        None
    """
    # Gets initial input
    inputs = get_input(args)

    # if ssl_ca_bundle is specified, it will take precedence over ignore_ssl_error
    if inputs.ssl_ca_bundle is not None:
        common.ssl_verify = inputs.ssl_ca_bundle
    else:
        common.ssl_verify = not inputs.ignore_ssl_error
        if not common.ssl_verify:
            # To suppress SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.debug(f"Ingenium.ssl_verify:{common.ssl_verify}")

    if inputs.username:
        username = inputs.username
    else:
        username = getpass.getuser()

    if inputs.rsa:
        pw_prompt = f"Enter RSA Passcode for {username}:"
    else:
        pw_prompt = f"Enter LDAP Password for {username}:"

    # Login to server
    login = common.authenticate(inputs.server, username=username, password=getpass.getpass(pw_prompt), force=True,
                                rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    # Get the current palette
    current_palette = get_palette_info(inputs.server)

    # If the function is query, write the current palette to an Excel File
    if inputs.function in ['query']:

        # Write the current palette to an Excel File
        write_palette_excel(inputs.excel, current_palette)

    # If the function is diff or update, read the Excel File Contents
    if inputs.function in ['diff', 'update', 'delete']:

        # Read the Excel File Contents
        excel_palette = read_palette_excel(inputs.excel)

        if inputs.function in ['diff']:
            diff_palette_info(current_palette, excel_palette)
        elif inputs.function in ['update']:
            update_palette_info(inputs.server, current_palette, excel_palette, inputs.confirm)
        elif inputs.function in ['delete']:
            delete_custom_steps(inputs.server, current_palette, excel_palette, inputs.confirm)

    logger.info("Step Palette processing completed successfully")


if __name__ == '__main__':
    try:
        main()
    except common.IngeniumLibError:
        logger.error(
            "Ingenium Create/Update Custom Script has encountered an error and needs to exit. Please check the log messages for the source of the error.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error("Ingenium Create/Update Custom Script has encountered an error and needs to exit.")

