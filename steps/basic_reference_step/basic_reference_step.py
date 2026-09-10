#!/home/swanchr/ing-venv/bin/python3
'''
This is reference Ingenium Custom Script it intended as a demo of the capabilities in a custom script
 and as a template to follow for implementation.


Authors:
    * Chris Swan 
    * Hongman Kim 

'''


import time
from datetime import datetime, timedelta
import copy
import os
import random
from ing_lib.logs import init_console_logger, get_logger
from pathlib import Path
import string
init_console_logger()
logger = get_logger(__name__)

from ing_lib.steps import *

def random_text(num_chars: int) -> str:
    # You can tailor the charset; here we include letters, digits, punctuation, space
    charset = string.ascii_letters + string.digits + string.punctuation + " "
    return ''.join(random.choice(charset) for _ in range(num_chars))

if __name__ == '__main__':


    # Locate the custom script input file
    error_msg = 'USAGE: python reference_step.py input_file_path output_file_path'
    input_file_abs_path, output_file_abs_path = get_input_output_paths(error_msg)
    logger.info(f'input_file_abs_path: {input_file_abs_path}')
    logger.info(f'output_file_abs_path: {output_file_abs_path}')

    # Read the input file
    logger.info('Reading custom script inputs')
    input_dict = read_input_file(input_file_abs_path)

    # Initialize the Output Data
    '''
    Users should construct the output data structure as a python dictionary and initialize the status to "PENDING"
    Later the script will update this dictionary as results are produced and it can be easily saved to the outputs.json
    
    Note that this varies per script (as the outputs vary)
    '''


    # Initialize output data
    inputs = copy.deepcopy(input_dict.get('inputs', []))
    variables = input_dict.get('variables', {})
    telemetry= copy.deepcopy(variables.get('telemetry', {}))
    parameters=copy.deepcopy(variables.get('parameters', {}))    
    entries = copy.deepcopy(input_dict.get('entries', {}))
    outputs = {
        'start_time_date_time': '',
        'query_start': '',
        'query_end': ''
    }
    my_output_array = []

    output_dict = {
        'custom_script_status': 'PENDING',
        'inputs': inputs,
        'entries': entries,
        'outputs': outputs,
        'output_summary': ''
    }

    # Step through each entry and initialize the outputs
    for i, entry in enumerate(entries):
        entry['verification_status'] = 'PENDING'
        entry['entry_outputs'] = {
            'entry_output_1': 0,   # INT
            'entry_output_2': 0.0, # FLOAT
            'entry_output_3': 0,   # INT
            'entry_output_4': 0.0, # FLOAT
            'entry_output_5': 0.0, # FLOAT
            'entry_output_6': 0,   # INT
        }
        entry['entry_output_array'] = []

    # Write initial output
    write_output_file(output_dict, output_file_abs_path)
    logger.info('Output file was initialized')

    '''
    Add the custom script logic here
    Remember to:
        - Program defensibly (use try/except, think about what happens if actions fail)
        - Update the output_dict as you go and save it when new results are available (this will provide visibility while it is executing)
        - Log the actions - it helps with visibility and troubleshooting
        - Remember that the script will likley be running as an application user - not as you
    '''

    '''
    The following code builds random ouputs for the script
    '''

    # Convert the start_time to a datetime object
    start_time = datetime.strptime(inputs['start_time'], '%Y-%jT%H:%M:%S')
    
    # Compute the query range
    query_start = start_time - timedelta(seconds=inputs['lookback'])
    query_end = start_time + timedelta(seconds=inputs['timeout'])
    
    # Update the query range in the outputs
    outputs['start_time_date_time'] = start_time.strftime('%Y-%jT%H:%M:%S.%f')
    outputs['query_start'] = query_start.strftime('%Y-%jT%H:%M:%S.%f')
    outputs['query_end'] = query_end.strftime('%Y-%jT%H:%M:%S.%f')

    # Populate output values
    for i, entry in enumerate(entries):
        entry['verification_status'] = 'PASS'
        entry['entry_outputs']['entry_output_1'] = '' + str(i)
        entry['entry_outputs']['entry_output_2'] = '' + str(10*i)
        write_output_file(output_dict, output_file_abs_path)
        logger.info(f'Entry was added: {i}')

    start_time_seconds = start_time.timestamp()

    '''
    If your script has entries - evaluate them to determine overall status.
    '''
    # Review entries to generate overall status
    custom_script_status = 'PASS'
    for entry in entries:
        if entry['verification_status'] != 'PASS':
            custom_script_status = 'FAIL'
            break

    '''
    Log the successful completion and Push the final status (PASS/FAIL/ERROR) to the output_dict - 
    Ingenium watches for the status to be Not equal to PENDING 
    
    Note that you will likely have some logic to determine pass/fail (or will base it off entry verification_status)
    '''
    msg = f'basic_reference_step.py has run to completion with overall status: {custom_script_status}'
    logger.info(msg)
    output_dict['custom_script_status'] = custom_script_status

    '''
    Build a text compatible representation of the step output.
    Ingenium steps are complicated JSON objects which don't translate well into reporting tools like Excel.
    
    Custom Scripts should produce a text compatible translation of the step contents for use in these situations.
    (obviously this can not include things like images/series/etc.)
    '''

    text_representation = f'Sending Flight CMD: {output_dict["inputs"]["flight_cmd"].split(",")[0]} and Sim CMD: {output_dict["inputs"]["sim_cmd"].split(",")[0]} at {output_dict["inputs"]["start_time"]}\n'
    for entry in entries:
        text_representation = text_representation + f'Querying Flight Channel:{entry["entry_inputs"]["flight_channel"].split(",")[0]} Sim Channel:{entry["entry_inputs"]["sim_channel"].split(",")[0]} (EVRs:{entry["entry_inputs"]["flight_evr"]}, {entry["entry_inputs"]["sim_evr"]}) - Value:{entry["entry_outputs"]["entry_output_1"]}\n'

    text_representation = text_representation + f'Generated: No files because this is the basic version'

    output_dict['output_summary'] = text_representation

    # Write any series or image data
    output_dir = os.path.dirname(output_file_abs_path)

    # Report Final custom_script_status
    write_output_file(output_dict, output_file_abs_path)

