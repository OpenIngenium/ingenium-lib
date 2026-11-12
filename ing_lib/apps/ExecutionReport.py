"""
This script creates an execution report output (XLSX) from Ingenium Procedure Executions
and optional external data sources.

Authors:
    * Chris Swan (open-ingenium@jpl.nasa.gov)
"""

##################################################### Imports ######################################################
import logging
from ing_lib.logs import init_console_logger,get_logger
init_console_logger()

import ing_lib.common as common
from ing_lib.executions import get_procedure_section_infos,get_ingenium_execution
from ing_lib.elements import parse_ingenium_steps
import argparse
import copy
import csv
import datetime
import getpass
import traceback
import urllib3
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation


##################################################### Constants ######################################################

# Statuses for steps that actually executed
EXECUTED_STATUSES = ['PASS', 'FAIL', 'ERROR', 'OVERRIDE_PASS', 'OVERRIDE_FAIL']

# The limit of the number of rows in Excel (or OpenOffice) is 1,048,576
# Here we will use 1,000,000 as the limit
ROW_LIMIT = 1000000

_DISPOSITION_OPTIONS = ['',
                        'EXPECTED_PER_DESIGN',
                        'EXPECTED_WARNING',
                        'EXPECTED_VENUE_IDIO',
                        'EXPECTED_EXISTING_PROBLEM',
                        'EXPECTED_PROCEDURE_ERROR',
                        'UNEXPECTED_INVESTIGATING',
                        'UNEXPECTED_NEW_PROBLEM',
                        'UNEXPECTED_PROCEDURE_ERROR']

_HEADER_COMMENTS = {
    'A1': 'Earth Return Time / Current System Time (DOY format). Reflect the time telemetry was received, '
          'commands were sent, logs were written. Available for all data sources.',
    'B1': 'Spacecraft Event Time (DOY format). Reflects the time telemetry occurred on the vehicle '
          '(is effectively SCLK in UTC format).',
    'C1': 'Spacecraft Clock Time. Reflects the time telemetry occurred on the vehicle in seconds from a known epoch.',
    'D1': 'Source of Data. Includes the type of data and any unique id (execution id, etc.)',
    'E1': 'Type of data. Includes Ingenium Step Type.',
    'F1': 'Ingenium Step name/number.',
    'G1': 'ID of data.',
    'H1': 'Data content. Includes Ingenium results and other step information.',
    'I1': 'Other data. Includes Ingenium Pass/Fail status.',
    'J1': 'Category of disposition for off-nominal events.',
    'K1': 'Notes regarding the details of the disposition.'
}


##################################################### Functions ######################################################

logger = get_logger(__name__)


def get_input(args=[]):
    """
    This function gathers inputs for the Execution Report Script

    Parameters
    --------
    args
        list of input arguments. Used when this is called from another Python module.

    Returns
    -------
        inputs: object
            Argparse input object
    """

    parser = argparse.ArgumentParser(description='This script creates an execution report',
        prog='ExecutionReport.py',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('ingenium_server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-psyche.jpl.nasa.gov)')
    parser.add_argument('execution_ids', type=str,
                        help='Comma separated list of Ingenium Execution IDs (e.g. psyche-ingenium-10311,psyche-ingenium-10312')
    parser.add_argument('output_file', type=str, help='Output Excel File.')
    parser.add_argument('--ignore_ssl_error', action='store_true', help='Ignore SSL verification error')
    parser.add_argument('--ssl_ca_bundle', type=str,
                        help='Path to the SSL CA bundle. If provided, this will override ignore_ssl_error.')
    parser.add_argument('--debug', action='store_true', help='Enables debug output (raw JSON files)')
    parser.add_argument('--username', type=str,
                        help='Optional input to use a different username to login to Ingenium server.')
    parser.add_argument('--begin_time', type=str,
                        help='Will limit the report to events after the provided time. Performed against ERT Time. Use DOY format in UTC (e.g. 2021-123T21:32:33).')
    parser.add_argument('--end_time', type=str,
                        help='Will limit the report to events before the provided time. Performed against ERT Time. Use DOY format in UTC (e.g. 2021-123T21:32:33).')
    parser.add_argument('--exclude_child_executions', action='store_true',
                        help='Do not attempt to determine child executions (limit query to user provided executions).')
    parser.add_argument('--external_data_files', nargs='+',
                        help='Space delimited list of external data files (assumed to be in csv format. <ert in DOY format>, <scet>, <sclk>, <source>, <type>, <id>, <data>, <sequence_id>) ')
    parser.add_argument('--rsa', action='store_true',
                        help='Uses RSA Two Factor Authentication (username/passcode) to authenticate.')

    if len(args) > 0:
        inputs = parser.parse_args(args)
    else:
        inputs = parser.parse_args()

    # Setup debug logging (if desired)
    if inputs.debug:
        get_logger().setLevel(logging.DEBUG)
        for handler in get_logger().handlers:
            handler.setLevel(logging.DEBUG)
            logger.debug("Logging set to Debug.")

    # If begin/end time is provided check that it is in DOY format (if not warn the user and ignore the limitation)
    # Note that we will leave the time as a string as the majority of functions need a string
    if inputs.begin_time:
        try:
            datetime.datetime.strptime(inputs.begin_time, '%Y-%jT%H:%M:%S')
        except:
            msg = f"Begin time of : {inputs.begin_time} does not follow DOY format (e.g. 2021-123T21:32:33)."
            logger.error(msg)
            raise common.IngeniumLibError(msg)
    if inputs.end_time:
        try:
            datetime.datetime.strptime(inputs.end_time, '%Y-%jT%H:%M:%S')
        except:
            msg = f"End time of : {inputs.end_time} does not follow DOY format (e.g. 2021-123T21:32:33)."
            logger.error(msg)
            raise common.IngeniumLibError(msg)

    return inputs


def query_ingenium_execution(inputs):
    """
    This function queries the Ingenium Executions and extracts a variety of information.

    Parameters
    ----------
    inputs
        Object of inputs

    Returns
    -------
    as_run_infos: list
        This is a list of JSON structs that contain the execution information
    report_entries: list
        This is a list of dictionaries that contains the ingenium steps in a format that can be written to the
        execution report.
    procedure_sections_infos: list
        This is a list of dictionaries that contain the procedure section information of the executions
    """

    # If data/time ranges are provided use them, otherwise set the limits to the min/max values of datetime.
    if inputs.begin_time:
        begin_time = datetime.datetime.strptime(inputs.begin_time, '%Y-%jT%H:%M:%S')
    else:
        begin_time = datetime.datetime.min
    if inputs.end_time:
        end_time = datetime.datetime.strptime(inputs.end_time, '%Y-%jT%H:%M:%S')
    else:
        end_time = datetime.datetime.max

    report_entries = []
    venues = []
    as_run_infos = []
    execution_ids = []
    procedure_sections_infos = []

    # Convert the csv list of executions into a list
    if inputs.execution_ids:
        for execution_id in inputs.execution_ids.split(','):
            if execution_id not in execution_ids:
                execution_ids.append(execution_id)

    # First we will walk the user provided executions, looking for child executions, and grabbing tags
    for execution_id in execution_ids:
        # This will recursively query a execution for all its children (and children's children, etc.)
        get_procedure_section_infos(inputs.ingenium_server,
                                    execution_id,
                                    procedure_sections_infos,
                                    inputs.exclude_child_executions)

    # Ensure that all the child executions are on the list to be queried
    for procedure in procedure_sections_infos:
        # procedure_sections_infos may contain procedure sections of the current execution, which
        # are used to report used procedures of the current execution in Excel report.
        # Include child executions only when exclude_child_executions is false.
        if not inputs.exclude_child_executions:
            if procedure['child_execution_id'] not in execution_ids and procedure['child_execution_id'] != '':
                execution_ids.append(procedure['child_execution_id'])

    execution_ids.sort()
    logger.info(f"Included executions: {','.join(execution_ids)}")

    # Now that we have the full list of executions we can query the steps
    for execution_id in execution_ids:
        as_run_info, as_run_data = get_ingenium_execution(inputs.ingenium_server, execution_id)

        if not as_run_info:
            msg = 'Failure to query Ingenium Data - Can not proceed. Exiting.'
            logger.error(msg)
            raise common.IngeniumLibError(msg)

        as_run_infos.append(as_run_info)

        if as_run_info['venue_name'] not in venues:
            venues.append(as_run_info['venue_name'])

        # Output the raw json (if debug = True)
        if inputs.debug:
            debug_file_name_data = common.get_debug_file_path(inputs.output_file,
                                                              f'_{execution_id}_execution_data.json')
            debug_file_name_info = common.get_debug_file_path(inputs.output_file,
                                                              f'_{execution_id}_execution_info.json')
            common.debug_output(debug_file_name_data, as_run_data)
            common.debug_output(debug_file_name_info, as_run_info)

        # Parse the steps of the procedure
        steps = parse_ingenium_steps(as_run_data, 'as-run')

        # Step through each Ingenium Element
        for step in steps:
            # If the step is an Ingenium Step (not section,etc)
            if step.elem_type == 'STEP':

                # If the status is NONE the step did not execute (so it can be skipped)
                if step.meta_data['status'] in EXECUTED_STATUSES and step.step_type != 'VERIFICATION_ITEM_STATUS':

                    # If the step is not part of a procedure use the execution id
                    if step.procedure_id == '':
                        source = step.execution_id
                    else:
                        source = step.procedure_id + ' ' + step.procedure_title

                    # Showing the start and end of each step
                    step_started = datetime.datetime.strptime(step.meta_data['time_started'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    try:
                        step_ended = datetime.datetime.strptime(step.meta_data['time_completed'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except:
                        logger.warning(f"Can not parse time for time: {step.meta_data['time_completed']}")
                        step_ended = step_started

                    override_note = None
                    modification_note = None

                    # Capture redline notes
                    if step.procedure_modification_status in ['MODIFYING', 'ADDED', 'MODIFYING_OLD']:
                        mod_type = step.procedure_modification['justification'].get('modification_type')
                        mod_requestor = step.procedure_modification['justification'].get('user_name')
                        mod_justification = step.procedure_modification['justification'].get('content')
                        mod_approver = step.procedure_modification['approval'].get('user_name')
                        mod_app_justification = step.procedure_modification['approval'].get('content')
                        modification_note = f'{mod_type}: Requestor: {mod_requestor} Justification: {mod_justification}. \n Approver: {mod_approver} Justification: {mod_app_justification}'

                    # Construct the notes
                    if step.meta_data['status'] in ['OVERRIDE_PASS', 'OVERRIDE_FAIL']:
                        override_note = f'Overriden by {step.meta_data.get("overridden_by")} - Justification: {step.meta_data.get("override_justification")}.'

                    step_start = {'ert': step_started,
                                  'scet': '',
                                  'sclk': '',
                                  'source': source,
                                  'type': step.step_type,
                                  'id': step.number + ' ' + step.title,
                                  'data': step.print_format,
                                  'sequence_id': step.meta_data['status'],
                                  'start_end': 'START',
                                  'ingenium': True,
                                  'override_note': override_note,
                                  'modification_note': modification_note}

                    step_end = copy.deepcopy(step_start)
                    step_end['ert'] = step_ended
                    step_end['start_end'] = 'END'

                    # Apply the time filter. Note that it will include any start that either starts or
                    # ends in the provided time range
                    if (step_started > begin_time and step_started < end_time) or \
                            (step_ended > begin_time and step_ended < end_time):

                        report_entries.append(step_start)
                        report_entries.append(step_end)

    if len(venues) > 1:
        logger.warning(f"Executions span more than one venue ({venues}) - Execution report can not currently handle this.")

    return as_run_infos, report_entries, procedure_sections_infos


def ingest_external_data_sources(inputs):
    """
    This function will read and format external data sources for inclusion in the Execution report.

    Parameters
    ----------
    inputs: object
    Argparse input object

    Returns
    -------
    report_entries: list
        List of dictionaries

    """

    report_entries = []

    if inputs.external_data_files:
        for external_file in inputs.external_data_files:
            logger.info(f"Reading External file: {external_file} for inclusion in the execution report.")
            try:
                with open(external_file, 'r') as file:
                    reader = csv.reader(file)
                    for row in reader:
                        try:
                            data = {'ert': datetime.datetime.strptime(row[0], '%Y-%jT%H:%M:%S.%f'),
                                    'scet': row[1],
                                    'sclk': row[2],
                                    'source': 'External Data: %s' % row[3],
                                    'type': row[4],
                                    'id': row[5],
                                    'data': row[6],
                                    'sequence_id': row[7],
                                    'ingenium': False}
                        except:
                            logger.warning(f"Unable to parse external data file: {external_file}, row: {row}")
                            logger.warning(f"Traceback: {traceback.format_exc()}")
                            continue
                        report_entries.append(data)
            except IOError:
                logger.warning(f"Unable to open or access {external_file}")
                logger.warning(f"Traceback: {traceback.format_exc()}")
                continue
    return report_entries


def _report_formats(workbook):
    """
    This function builds the cell formats used in the execution report.

    Parameters
    ----------
    workbook
        The openpyxl workbook (unused, present for symmetry)

    Returns
    -------
        Dictionary of (font, fill, alignment) tuples indexed by format name
    """

    border = Border(left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin'))
    wrap = Alignment(wrap_text=True)
    wrap_center = Alignment(wrap_text=True, horizontal='center')

    def fmt(font_color, bold, bg_color, alignment=None, italic=False):
        return (Font(color=font_color, bold=bold, italic=italic),
                PatternFill(fill_type='solid', start_color=bg_color, end_color=bg_color),
                alignment or wrap,
                border)

    formats = {
        'header': fmt('FF000000', True, 'FFBFBFBF'),
        'ingenium_step_start_pass': fmt('FF000000', True, 'FF00FF00'),
        'ingenium_step_end_pass': fmt('FF000000', True, 'FF99FF99'),
        'ingenium_step_start_fail': fmt('FF000000', True, 'FFFF8000'),
        'ingenium_step_end_fail': fmt('FF000000', True, 'FFFFB266'),
        'ingenium_step_start_error': fmt('FF000000', True, 'FFFF0000'),
        'ingenium_step_end_error': fmt('FF000000', True, 'FFFF6666'),
        'external_data': fmt('FF000000', True, 'FF36EBFF'),
        'unknown': fmt('FFFFA500', False, 'FF000000'),
        'summary_title': fmt('FF000000', True, 'FFBFBFBF'),
        'summary_pass': fmt('FFFFFFFF', True, 'FF008000'),
        'summary_fail': fmt('FFFFFFFF', True, 'FFFF6600'),
        'summary_error': fmt('FFFFFFFF', True, 'FFFF0000'),
        'summary_info': fmt('FF000000', False, 'FFFFFFFF', alignment=wrap_center),
    }

    return formats


def _write_cell(sheet, row, col, value, cell_format):
    """
    This function writes a formatted cell.

    Parameters
    ----------
    sheet
        openpyxl worksheet
    row: int
        Row number (1 indexed)
    col: int
        Column number (1 indexed)
    value
        Cell content
    cell_format
        (font, fill, alignment, border) tuple

    Returns
    -------
        The written cell
    """
    font, fill, alignment, border = cell_format
    cell = sheet.cell(row=row, column=col, value=value)
    cell.font = font
    cell.fill = fill
    cell.alignment = alignment
    cell.border = border
    return cell


def _write_summary_sheet(summary, execution_info, procedures, inputs, formats):
    """
    This function writes the Summary worksheet.

    Parameters
    ----------
    summary
        openpyxl worksheet
    execution_info: list
        List of dictionaries of general execution information
    procedures: list
        List of dictionaries that capture all the procedures invoked in all the associated executions
    inputs: object
        Argparse object of inputs
    formats: dict
        Cell formats

    Returns
    -------
        None
    """

    _ROW_WIDTH_PER_PROCEDURE = 45

    summary.column_dimensions['A'].width = 20

    summary_labels = ['Ingenium Executions',
                      'Execution Description',
                      'Start Time',
                      'End Time',
                      'Total Duration',
                      'Execution Duration',
                      'Venue Name',
                      'Test Conductors',
                      'Ingenium Version',
                      'Flight Dictionary',
                      'SSE Dictionary',
                      'Steps Executed',
                      'Steps Pass',
                      'Steps Fail',
                      'Steps Error',
                      'Procedure Information']

    for idx, label in enumerate(summary_labels, 1):
        _write_cell(summary, idx, 1, label, formats['summary_title'])

    summary_column = 1

    max_row = len(summary_labels)
    for execution in execution_info:
        summary_column = summary_column + 1
        summary.column_dimensions[get_column_letter(summary_column)].width = 65

        _write_cell(summary, 1, summary_column, execution['execution_id'], formats['summary_info'])
        _write_cell(summary, 2, summary_column, execution['description'], formats['summary_info'])

        # Convert the Times
        try:
            dt_time_started = datetime.datetime.strptime(execution['time_started'], '%Y-%m-%dT%H:%M:%S.%fZ')
            dt_time_completed = datetime.datetime.strptime(execution['time_completed'], '%Y-%m-%dT%H:%M:%S.%fZ')
            delta = dt_time_completed - dt_time_started
            hours, remainder = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            duration = '{:0>2d}:{:0>2d}:{:0>2d}'.format(int(hours), int(minutes), int(seconds))
        except:
            duration = "Unknown"

        # Compute the execution duration

        # If there are no transitions - then the duration = execution_duration
        if not execution['transitions']:
            exec_duration = duration
        # Otherwise we need to step through the transitions adding up the actual run time.
        else:
            start_time = dt_time_started
            total_exec_time = 0
            for transition in execution['transitions']:
                if transition['to_status'] in ['SUSPENDED', 'CLOSED']:
                    end_time = datetime.datetime.strptime(transition['time_updated'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    total_exec_time = total_exec_time + (end_time - start_time).total_seconds()
                if transition['to_status'] in ['IDLE']:
                    start_time = datetime.datetime.strptime(transition['time_updated'], '%Y-%m-%dT%H:%M:%S.%fZ')

            hours, remainder = divmod(total_exec_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            exec_duration = '{:0>2d}:{:0>2d}:{:0>2d}'.format(int(hours), int(minutes), int(seconds))

        _write_cell(summary, 3, summary_column, execution['time_started'], formats['summary_info'])
        _write_cell(summary, 4, summary_column, execution['time_completed'], formats['summary_info'])
        _write_cell(summary, 5, summary_column, duration, formats['summary_info'])
        _write_cell(summary, 6, summary_column, exec_duration, formats['summary_info'])
        _write_cell(summary, 7, summary_column, execution['venue_name'], formats['summary_info'])
        list_of_tcs = '\n'.join(execution['test_conductors'])
        _write_cell(summary, 8, summary_column, list_of_tcs, formats['summary_info'])
        _write_cell(summary, 9, summary_column, execution.get('version'), formats['summary_info'])
        _write_cell(summary, 10, summary_column, execution['flight_dictionary_version'], formats['summary_info'])
        _write_cell(summary, 11, summary_column, execution['sse_dictionary_version'], formats['summary_info'])
        _write_cell(summary, 12, summary_column, execution['num_steps_executed'], formats['summary_info'])
        _write_cell(summary, 13, summary_column, execution['num_steps_passed'], formats['summary_pass'])
        _write_cell(summary, 14, summary_column, execution['num_steps_failed'], formats['summary_fail'])
        _write_cell(summary, 15, summary_column, execution['num_steps_errored'], formats['summary_error'])

        row = 15
        for procedure in procedures:
            string_format = 'Step: %s (Called: %s)  %s - Ingenium (%s, %s) - PBAT (%s, %s) - Run for Score: %s with TAGs: %s' \
                            % (procedure['step_number'],
                               procedure['callable'],
                               procedure['procedure_title'],
                               procedure['procedure_id'],
                               procedure['procedure_version'],
                               procedure['institutional_id'],
                               procedure['institutional_release_id'],
                               procedure['run_for_score'],
                               ','.join(procedure['tags']))
            if procedure['execution_id'] == execution['execution_id']:
                # If the procedure has been Imported - it was "executed" so write the contents
                if procedure['imported']:
                    row = row + 1
                    if row > max_row:
                        max_row = row
                    _write_cell(summary, row, 1, 'Procedure Information', formats['summary_title'])
                    _write_cell(summary, row, summary_column, string_format, formats['summary_info'])
                    summary.row_dimensions[row].height = _ROW_WIDTH_PER_PROCEDURE

    # If a begin/end time filter was used - note it in the summary page
    time_filter_row = max_row + 2
    # If either a begin/end time provided - note that the content is filtered
    if inputs.begin_time or inputs.end_time:
        summary.row_dimensions[time_filter_row].height = 30
        _write_cell(summary, time_filter_row, 1,
                    'Execution Report content has been filtered by the follow time ranges. '
                    'Note this does not filter execution summary information.',
                    formats['summary_title'])
        summary.merge_cells(start_row=time_filter_row, start_column=1, end_row=time_filter_row, end_column=2)
    # If there is a begin time filter add it
    if inputs.begin_time:
        time_filter_row = time_filter_row + 1
        _write_cell(summary, time_filter_row, 1, 'Begin Time Filter', formats['summary_title'])
        _write_cell(summary, time_filter_row, 2, inputs.begin_time, formats['summary_info'])
    # If there is an end time filter add it
    if inputs.end_time:
        time_filter_row = time_filter_row + 1
        _write_cell(summary, time_filter_row, 1, 'End Time Filter', formats['summary_title'])
        _write_cell(summary, time_filter_row, 2, inputs.end_time, formats['summary_info'])


def output_report(report, execution_info, inputs, procedures):
    """
    This function takes a sorted list and outputs an XLSX file.

    Parameters
    ----------
    report: list
        Sorted List of report dictionary items

    execution_info: list
        List of dictionaries of General Execution Information

    inputs: object
        Argparse object of inputs.

    procedures: list
        List of dictionaries that capture all the procedures invoked in all the associated executions

    Returns
    -------
        None
    """

    # Create a workbook and add a worksheet.
    try:
        workbook = Workbook()
    except:
        msg = f"Failure to open XLSX workbook ({inputs.output_file}). Can not proceed. Exiting."
        logger.error(msg, exc_info=True)
        raise common.IngeniumLibError(msg)

    formats = _report_formats(workbook)

    ###################### Summary

    summary = workbook.active
    summary.title = 'Summary'

    _write_summary_sheet(summary, execution_info, procedures, inputs, formats)

    ###################### Execution Report

    num_data = len(report)
    logger.info(f"Total number of rows in the report: {num_data}")

    if num_data == 0:
        logger.warning('No entries found for the execution report. Please check your inputs. (Time Range?)')

    # Note that // is used for integer division
    total_worksheets = max(num_data - 1, 0) // ROW_LIMIT + 1

    excel_output_start = datetime.datetime.now(datetime.timezone.utc)

    for index, element in enumerate(report):
        # row is row index in worksheet.
        # 1 is for the header and data starts from row 2
        row = index % ROW_LIMIT + 2
        # current_worksheet is 1-based index of worksheet
        # Note that // is used for integer division
        current_worksheet = index // ROW_LIMIT + 1

        # create header before adding the first data row
        if row == 2:
            logger.info(f"Building execution report worksheet {current_worksheet} of {total_worksheets}")

            # Creating the worksheet
            worksheet = workbook.create_sheet(f'Execution_Report_{current_worksheet}')
            worksheet.freeze_panes = 'A2'

            # Setup Initial Column Widths
            for idx, width in enumerate([22, 22, 18, 42, 16, 40, 40, 80, 9, 30, 60], 1):
                worksheet.column_dimensions[get_column_letter(idx)].width = width

            # Write the headers
            for col_idx, header_text in enumerate(['ERT', 'SCET', 'SCLK', 'SOURCE', 'TYPE', 'STEP', 'ID', 'DATA',
                                                   'OTHER', 'DISPOSITION', 'DISPOSITION NOTES'], 1):
                _write_cell(worksheet, 1, col_idx, header_text, formats['header'])

            # Write comments to headers
            for cell_ref, comment_text in _HEADER_COMMENTS.items():
                comment = Comment(comment_text, 'Ingenium')
                worksheet[cell_ref].comment = comment

            # Add the disposition data validation
            disposition_dv = DataValidation(type='list', formula1='"' + ','.join(_DISPOSITION_OPTIONS) + '"',
                                            allow_blank=True)
            worksheet.add_data_validation(disposition_dv)

        # Add data row

        # Determine the formatting to apply to each row (based on element type and source)
        if element.get('ingenium'):
            if element['start_end'] == 'START':
                if element['sequence_id'] == 'PASS' or element['sequence_id'] == 'OVERRIDE_PASS':
                    cell_format = formats['ingenium_step_start_pass']
                elif element['sequence_id'] == 'FAIL' or element['sequence_id'] == 'OVERRIDE_FAIL':
                    cell_format = formats['ingenium_step_start_fail']
                else:
                    cell_format = formats['ingenium_step_start_error']
            else:
                if element['sequence_id'] == 'PASS' or element['sequence_id'] == 'OVERRIDE_PASS':
                    cell_format = formats['ingenium_step_end_pass']
                elif element['sequence_id'] == 'FAIL' or element['sequence_id'] == 'OVERRIDE_FAIL':
                    cell_format = formats['ingenium_step_end_fail']
                else:
                    cell_format = formats['ingenium_step_end_error']
        elif 'External Data' in element['source']:
            cell_format = formats['external_data']
        else:
            logger.warning(f"Encountered Unexpected execution report content: {element['source']} - {element['type']}")
            cell_format = formats['unknown']

        # Note ERT is to 3 decimal places (so not displaying all decimal places)
        _write_cell(worksheet, row, 1, element['ert'].strftime('%Y-%jT%H:%M:%S.%f')[:-3], cell_format)
        _write_cell(worksheet, row, 2, element['scet'], cell_format)
        # Attempt to convert all SCLKs to float so that sorting works as expected
        try:
            floating_sclk = float(element['sclk'])
        except (ValueError, TypeError):
            floating_sclk = element['sclk']
        _write_cell(worksheet, row, 3, floating_sclk, cell_format)
        _write_cell(worksheet, row, 4, element['source'], cell_format)
        _write_cell(worksheet, row, 5, element['type'], cell_format)
        # If the source is from Ingenium write the step # input column 6, other write it in column 7
        # (we write a blank string to the other column so the formatting is applied
        if element.get('ingenium'):
            step_cell = _write_cell(worksheet, row, 6, '%s:%s' % (element['start_end'], element['id']), cell_format)
            _write_cell(worksheet, row, 7, '', cell_format)

            # If an Ingenium step was added via redline/blue - capture the justification/approval in a comment
            # (But only the start element)
            if element['start_end'] == 'START':
                if element['modification_note']:
                    step_cell.comment = Comment(element['modification_note'], 'Ingenium')
                    step_cell.comment.width = 300
                    step_cell.comment.height = 150
        else:
            _write_cell(worksheet, row, 6, '', cell_format)
            _write_cell(worksheet, row, 7, element['id'], cell_format)
        _write_cell(worksheet, row, 8, element['data'], cell_format)
        other_cell = _write_cell(worksheet, row, 9, element['sequence_id'], cell_format)
        # If an Ingenium step was override - write the override justification via a comment
        if element.get('override_note'):
            other_cell.comment = Comment(element['override_note'], 'Ingenium')
            other_cell.comment.width = 300
            other_cell.comment.height = 150
        # Write blank content to disposition columns (are populated by the users)
        _write_cell(worksheet, row, 10, '', cell_format)
        _write_cell(worksheet, row, 11, '', cell_format)

        # If this is the last entry in the report or the last row in a worksheet
        # apply the filters and data validity options
        if row == ROW_LIMIT + 1 or (index + 1) == num_data:
            logger.debug(f"set filter index: {index} row: {row}")
            # Add a Filter
            worksheet.auto_filter.ref = f"A1:K{row}"

            # Add the data validation
            disposition_dv.add(f"J2:J{row}")

    excel_output_end = datetime.datetime.now(datetime.timezone.utc)
    total_time = (excel_output_end - excel_output_start).total_seconds()
    if total_time > 0:
        row_per_sec = num_data / total_time
    else:
        row_per_sec = num_data

    logger.info(f"Completed writing Excel File. {num_data} rows in {total_time} seconds. ({row_per_sec} rows/sec).")

    try:
        workbook.save(inputs.output_file)
        workbook.close()
    except:
        msg = 'Unable to save Execution Report.'
        logger.error(msg, exc_info=True)
        raise common.IngeniumLibError(msg)

    return


##################################################### Main ###########################################################


def main(args=[]):
    """
    This is the main function of the Ingenium Execution Report Generator

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
        common.set_ssl_verify(inputs.ssl_ca_bundle)
    else:
        common.set_ssl_verify(not inputs.ignore_ssl_error)
        if not common.get_ssl_verify():
            # To suppress SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.debug(f"Ingenium.ssl_verify:{common.get_ssl_verify()}")

    if inputs.username:
        username = inputs.username
    else:
        username = getpass.getuser()

    if inputs.rsa:
        pw_prompt = f"Enter RSA Passcode for {username}:"
    else:
        pw_prompt = f"Enter LDAP Password for {username}:"

    # Login to Ingenium
    login = common.authenticate(inputs.ingenium_server, username=username,
                                password=getpass.getpass(pw_prompt), force=True,
                                rsa=inputs.rsa)
    if not login:
        msg = 'Failure to Login - Can not proceed. Exiting.'
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    # Query the Ingenium execution
    execution_infos, steps, procedures = query_ingenium_execution(inputs)

    # Include external inputs (if provided)
    report_entries = steps + ingest_external_data_sources(inputs)

    # Sort the merged list by ERT
    logger.info('Merging and sorting data sources')
    report_entries.sort(key=lambda x: x['ert'])

    # Write the Report to a File
    logger.info(f"Building Execution Report in XLXS format: {inputs.output_file}")
    output_report(report_entries, execution_infos, inputs, procedures)


if __name__ == '__main__':
    try:
        main()
    except common.IngeniumLibError:
        logger.error("Ingenium Execution Report encountered an error and needs to exit. Please check the log messages for the source of the error.")
