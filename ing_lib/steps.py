'''
This library contains a set of functions and classes to assist in the creation of Ingenium steps.


Authors:
    * Chris Swan 
    * Hongman Kim 
'''
#################################################### Imports ####################################################

from collections import OrderedDict
import traceback
from datetime import datetime, timedelta
from enum import Enum
import json
import os
import sys
from ing_lib.logs import get_logger
logger = get_logger(__name__)

#################################################### Classes ####################################################

class BitMaskError(Exception):
    '''
    Error in applying a bit mask.
    '''
    pass

class InputError(Exception):
    """
    Error with inputs provided
    """
    pass

class ReturnOn(str, Enum):
    ANY = 'ANY'
    ALL = 'ALL'

#################################################### Constants ####################################################
# The amount of time in seconds the library will query after the query window
_TELEMETRY_QUERY_MARGIN = 5

#################################################### Functions ####################################################

def apply_bit_mask(input_value, bit_mask, bit_op):
    """
    This function will apply a bit_mask to a specified value (either AND or OR)
    Parameters
    ----------
    input_value: int
        Integer value to apply the bitmask to
    bit_mask: str
        Either binary (0b1100101), hex (0x23A3) or decimal (43) bitmask
    bit_op: str
        Either AND or OR
    Returns
    -------
    output_value: int
        Will either return the resulting bitmask'd value or False if the operation fails
    """

    # Make sure the input_value is an integer
    try:
        value = int(input_value)
    except ValueError:
        msg = f'Apply bitmask attempted on non-integer value: {input_value}'
        logger.error(msg)
        logger.error(traceback.format_exc())
        raise BitMaskError(msg)

    # If 0b/0B is in the start of the bitmask - it is binary
    if str(bit_mask)[:2].lower() == '0b':
        try:
            mask = int(bit_mask[2:], 2)
        except ValueError:
            msg = f'Unable to interpret bit_mask: {bit_mask}, input: {input_value}, bit_op: {bit_op}'
            logger.error(msg)
            logger.error(traceback.format_exc())
            raise BitMaskError(msg)

    # If 0x/0X is in the start of the bitmask - it is hex
    elif str(bit_mask)[:2].lower() == '0x':
        try:
            mask = int(bit_mask[2:], 16)
        except ValueError:
            msg = f'Unable to interpret bit_mask: {bit_mask}, input: {input_value}, bit_op: {bit_op}'
            logger.error(msg)
            logger.error(traceback.format_exc())
            raise BitMaskError(msg)
    # Otherwise it is decimal
    else:
        try:
            mask = int(bit_mask)
        except ValueError:
            msg = f'Unable to interpret bit_mask: {bit_mask}, input: {input_value}, bit_op: {bit_op}'
            logger.error(msg)
            logger.error(traceback.format_exc())
            raise BitMaskError(msg)

    # Now apply the bit mask to the value
    if bit_op == 'AND':
        output_value = value & mask
    elif bit_op == 'OR':
        output_value = value | mask
    else:
        msg = f"Non-supported bit_mask operation requested: {bit_op}, input: {input_value}, bit_mask: {bit_op}"
        logger.error(msg)
        raise BitMaskError(msg)

    logger.info(f'Applied bit-mask: {bit_mask}, bit-op: {bit_op} to input value: {input_value} which returns output value: {output_value}')
    # And return it
    return int(output_value)


def check_telemetry_query(query: list) -> None:
    """
    This function checks the provided telemetry query to ensure it is well formed

    Parameters
    ----------
    query: dict
        This is dictionary indexed by channel id with the provide

        Example:
                        {'telem_uuid' : 'CMD-3232',
                        'verify_wait' : 'WAIT',
                        'dn_eu': 'DN',
                        'verification_condition': 'GREATER_THAN',
                        'verification_values': ['12'],
                        'prior_value': 7,
                        'bit_mask': '0x13240123',
                        'bit_op': 'AND'}}
    Returns
    -------

    """

    for predict in query:

        # Check the Verification Condition and Verification Values

        # If the verification values are left empty - set to
        if predict['verification_condition'] in ['RECORD', 'NOT_PRESENT']:
            if len(predict.get('verification_values')) != 0:
                msg = f'Verification condition: {predict["verification_condition"]} requires no verification values. (Provided: {predict.get("verification_values")}'
                logger.error(msg)
                raise InputError(msg)
        elif predict['verification_condition'] in ['GREATER_THAN', 'GREATER_THAN_OR_EQUAL', 'LESS_THAN',
                                                   'LESS_THAN_OR_EQUAL', 'EQUAL', 'NOT_EQUAL']:
            if len(predict.get('verification_values')) != 1:
                msg = f'Verification condition: {predict["verification_condition"]} requires one verification value. (Provided: {predict.get("verification_values")}'
                logger.error(msg)
                raise InputError(msg)
        elif predict['verification_condition'] in ['INCLUSIVE_RANGE', 'EXCLUSIVE_RANGE']:
            if len(predict.get('verification_values')) != 2:
                msg = f'Verification condition: {predict["verification_condition"]} requires two verification values. (Provided: {predict.get("verification_values")}'
                logger.error(msg)
                raise InputError(msg)
        else:
            msg = f'Unknown Verification Condition: {predict["verification_condition"]}'
            logger.error(msg)
            raise InputError(msg)

        # Check DN vs. EU
        if predict['dn_eu'] not in ['DN', 'EU']:
            msg = f'Invalid DN_EU value ({predict.get("dn_eu")}. Allowable values: DN or EU.'
            logger.error(msg)
            raise InputError(msg)

        # Check Wait vs. Verify
        if predict['verify_wait'] not in ['WAIT', 'VERIFY']:
            msg = f'Invalid verify_wait value ({predict.get("verify_wait")}. Allowable values: WAIT or VERIFY.'
            logger.error(msg)
            raise InputError(msg)

        # If there is bit mask operation ensure a mask is provided and the verification values are numeric
        if predict.get('bit_op'):
            # Confirm correct types of bit operations
            if predict['bit_op'] not in ['AND', 'OR']:
                msg = f'Invalid bit_op value {predict["bit_op"]}. Allowable values: AND, OR.'
                logger.error(msg)
                raise InputError(msg)
            # Ensure that if a bit operation is present a mask is present
            if predict.get('bit_mask') is None:
                msg = f'Predicts with a bit operation require a bit mask.'
                logger.error(msg)
                raise InputError(msg)
            # Check that if a bit operation is being performed the verification values are numeric
            for verification_value in predict.get('verification_values'):
                if not confirm_numeric(verification_value):
                    msg = f'Predict {verification_value} is not numeric and can not be used with bitmask operations.'
                    logger.error(msg)
                    raise InputError(msg)

        if predict.get('bit_mask') and predict.get('bit_op') is None:
            msg = f'A bit mask f{predict.get("bit_mask")} without a bit operation is invalid.'
            logger.error(msg)
            raise InputError(msg)

        # If there is a prior value
        if predict.get('prior_value') is not None:

            # Confirm that the prior value is numeric
            if not confirm_numeric(predict.get('prior_value')):
                msg = f'Prior Value: {predict.get("prior_value")} is not numeric and can not be used.'
                logger.error(msg)
                raise InputError(msg)

            # And the verification values are numeric
            for verification_value in predict.get('verification_values'):
                if not confirm_numeric(verification_value):
                    msg = f'Predict {verification_value} is not numeric and can not be used with a prior value.'
                    logger.error(msg)
                    raise InputError(msg)


def confirm_numeric(value):
    """
    This function determines if a value is numeric (can be typecast to float)

    Parameters
    ----------
    value
        A variable of unknown type

    Returns
    -------
    True if numeric, False if not
    """
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def verify_wait_telemetry(query: dict, telemetry_query_func: callable, start_time: datetime = None, timeout: int = 60, lookback: int = 0) -> dict:
    """
    This function will query for telemetry and compare vs. a predict
    Parameters
    ----------
    query: dict
        Dictionary of dictionaries with the channel_id as the key, and the predict/bit_mask as values
        Example:
            {'CMD-1234' :
                        {'verify_wait' : 'WAIT',
                        'dn_eu': 'DN',
                        'verification_condition': 'GREATER_THAN',
                        'verification_values': ['12'],
                        'prior_value': 7,
                        'bit_mask': '0x13240123',
                        'bit_op': 'AND'},
             'CMD-6789  :
                        {'verify_wait': 'VERIFY,
                         'dn_eu': 'EU',
                         'verification_condition': 'RECORD'}
            }
    telemetry_query_func: callable
        A function that queries for telemetry data.
        Use functools.partial to pass any other required arguments to your query function (e.g. session_id).
    start_time: datetime object
        The start time of the query (use now if not provided)
    timeout: int
        How much time to look for the channels, from the start_time, before giving up (default 60)
    lookback: int
        How much time to "look back" from the start_time for the channel (default 0)
    Returns
    -------
    results: dict
        Dictionary of Dictionary of the results indexed by channel with an overall status of all values
        Example:
        {'query_matches_predict' : True,
         'channels' :  {'CMD-1234' : {'actual_value' : '43',
                                      'verification_status' : 'PASS',
                                      'channel_details' : dict},
                        'CMD-1235' : {'actual_value' : '43',
                                      'verification_status' : 'PASS',
                                      'channel_details' : dict}
                        }
        }
    """

    # Validate the query (will raise exception)
    check_telemetry_query(query)

    results = {'query_matches_predict': True,
               'channels': OrderedDict()}

    # Set the boundaries of the query
    if start_time is None:
        start_time = datetime.utcnow()

    query_end_time = start_time + timedelta(seconds=timeout)

    channels_to_query = []

    # Check the query structure for errors and collect the channels to query
    for channel, predicts in query.items():
        # Add the channel to a list
        channels_to_query.append(channel)

    # Query until the channel query is complete
    query_complete = False
    query_timeout = False

    time_out_time = query_end_time + timedelta(seconds=_TELEMETRY_QUERY_MARGIN)

    while not query_timeout and not query_complete:

        # If the timeout is in the past - set query_timeout to True
        # This feeds into the evaluation of WAIT and NOT_PRESENT conditions
        # It will also abort the loop in cases of timeouts
        if datetime.utcnow() > time_out_time:
            query_timeout = True

        # Query all the channels returning on collection of any data
        channel_results = telemetry_query_func(channels_to_query, timeout, lookback, start_time, ReturnOn.ANY)

        # Evaluate the results
        for channel, predicts in query.items():
            # Evaluate each channel per the predicts
            evaluated_channel = evaluate_verify_condition(channel_results['channels'].get(channel), channel, predicts,
                                                          query_timeout)

            # Include the full query history within the time frame
            evaluated_channel['history'] = channel_results['channels'].get(channel)

            # Append the channel results to results
            results['channels'][channel] = evaluated_channel


        # As we only want to exit when all channel queries / predicts have been satisfied set query_complete to True
        query_complete = True
        results['query_matches_predict'] = True

        # Check if the query has completed
        for channel_id, data in results['channels'].items():
            # If the verification_condition = NOT_PRESENT only exit on FAIL
            # Note that this also means that query_timeout = True
            if data['predicts']['verification_condition'] in ['NOT_PRESENT']:
                if data['verification_status'] not in ['PASS', 'ERROR']:
                    query_complete = False
                    results['query_matches_predict'] = False

            else:
                # If Waiting - mark the query complete if the status equals PASS or ERROR
                if data['predicts']['verify_wait'] == 'WAIT':
                    if data['verification_status'] in ['FAIL']:
                        query_complete = False
                        results['query_matches_predict'] = False


                # If not waiting - the query is already flagged complete
                elif data['predicts']['verify_wait'] == 'VERIFY':
                    if data['verification_status'] in ['FAIL', 'ERROR']:
                        results['query_matches_predict'] = False

    return results


def evaluate_verify_condition(telemetry, telem_uuid, predicts, query_timeout):
    """
    This function will apply the bit mask (if appropriate) and evaluate the results based on the predicts
    Parameters
    ----------
    telemetry: list
        List of channel objects. The last element is the latest.
    telem_uuid: str
        Channel id that is being evaluated
    predicts: dict
        A dictionary containing bit-masking information and predicts to evaluate against
    query_timeout: bool
        Whether the query has timed out (for Not Present evaluation)
    Returns
    -------
    result: dict
        Dictionary containing the results
    """

    # Debug: Log function entry and inputs
    logger.debug(f"evaluate_verify_condition called for {telem_uuid} with verification_condition: {predicts.get('verification_condition')}")
    logger.debug(f"query_timeout: {query_timeout}, telemetry present: {bool(telemetry)}")

    # Create a dictionary to captures the results (starting with the predicts)
    result = {'telem_uuid': telem_uuid,
              'predicts': predicts,
              'actual_value': None,
              'verification_status': None,
              'data_present': False,
              'telem_details': None}

    verification_condition = predicts['verification_condition']
    verification_values = predicts.get('verification_values')
    prior_value = predicts.get('prior_value')

    # Check if no telem values have been returned
    if not telemetry:
        # Debug: Log the no-telemetry case
        logger.debug(f"No telemetry found for {telem_uuid}, query_timeout: {query_timeout}")

        # Check if the query is complete (timed out) and the verification type is NOT_PRESENT
        if query_timeout and verification_condition == 'NOT_PRESENT':
            # If so - verification_status = 'PASS'
            result['verification_status'] = 'PASS'
            msg = f'Channel:{telem_uuid} not located within time range. Verification Type: {predicts["verification_condition"]} Result: {result["verification_status"]}'
            logger.info(msg)
            return result

        # If the verification type is not NOT_PRESENT the verification is FAIL
        elif query_timeout and verification_condition != 'NOT_PRESENT':
            result['verification_status'] = 'FAIL'
            msg = f'Channel:{telem_uuid} not located within time range. Verification Type: {predicts["verification_condition"]} Result: {result["verification_status"]}'
            logger.info(msg)
            return result
        # If no timeout yet, return PENDING status
        else:
            result['verification_status'] = 'PENDING'
            return result

    # If we get here, telemetry was found
    telem = telemetry[0]
    result['telem_details'] = telem
    result['data_present'] = True

    # Debug: Log that we found telemetry
    logger.debug(f"Found telemetry for {telem_uuid}: {telem}")

    # If the predict is targeting DN - set the evaluation value to that
    if predicts['dn_eu'] == 'DN':
        result['actual_value'] = telem.get('raw_value')

    # If the predict is targeting EU
    elif predicts['dn_eu'] == 'EU':
        result['actual_value'] = telem.get('eng_value')

    # Handle NOT_PRESENT case when telemetry is found
    if verification_condition == 'NOT_PRESENT':
        result['verification_status'] = 'FAIL'
        msg = (f'Channel:{telem_uuid} was found with value {result["actual_value"]} when NOT_PRESENT was expected. '
               f'Verification Status: FAIL')
        logger.info(msg)
        return result

    # If there is a bit mask present apply it
    if predicts.get('bit_mask') and predicts.get('bit_op'):
        msg = f'Applying bit_mask: {predicts.get("bit_mask")} bit_op: {predicts.get("bit_op")} to channel_id: {telem_uuid} (DN: {telem.get("raw_value")})'
        logger.debug(msg)

        # Try applying the bit mask
        try:
            masked_value = apply_bit_mask(telem.get('raw_value'), predicts['bit_mask'], predicts['bit_op'])
        except BitMaskError:
            msg = f'Error applying specified bit-mask: {predicts.get("bit_mask")}, bit-op: {predicts.get("bit_op")}, to channel: {telem_uuid}, value: {telem.get("eng_value")}'
            logger.error(msg)
            raise InputError(msg)

        # Set the evaluation value to the masked value
        result['actual_value'] = masked_value

    # Check if a prior value was provided
    # If so compute revised actual_value based on actual_value - prior_value
    if prior_value is not None:
        old_actual_value = result['actual_value']
        result['actual_value'] = old_actual_value - prior_value
        msg = f'Will evaluate based on the difference between measured value and prior value ({old_actual_value} - {prior_value} = {result["actual_value"]})'
        logger.debug(msg)

    # Now evaluate the actual_value against the provided predicts
    # Record is a special case (no predict)
    if verification_condition == 'RECORD':
        result['verification_status'] = 'PASS'
        msg = f'Found value for {telem_uuid}: {result["actual_value"]} (RECORD - no evaluation) - setting verification status to {result["verification_status"]}'
        logger.info(msg)
        return result

    # Otherwise is follows a standard pattern
    if verification_condition == 'GREATER_THAN':
        operator = '>'
        if result['actual_value'] > float(verification_values[0]):
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    elif verification_condition == 'LESS_THAN':
        operator = '<'
        if result['actual_value'] < float(verification_values[0]):
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    elif verification_condition == 'GREATER_THAN_OR_EQUAL':
        operator = '>='
        if result['actual_value'] >= float(verification_values[0]):
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    elif verification_condition == 'LESS_THAN_OR_EQUAL':
        operator = '<='
        if result['actual_value'] <= float(verification_values[0]):
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    elif verification_condition == 'EQUAL':
        operator = '=='
        if result['actual_value'] == verification_values[0]:
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    elif verification_condition == 'NOT_EQUAL':
        operator = '!='
        if result['actual_value'] != verification_values[0]:
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    elif verification_condition == 'INCLUSIVE_RANGE':
        operator = 'Inclusive Range'
        if result['actual_value'] >= float(verification_values[0]) and result['actual_value'] <= float(verification_values[1]):
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    elif verification_condition == 'EXCLUSIVE_RANGE':
        operator = 'Exclusive Range'
        if result['actual_value'] > float(verification_values[0]) and result['actual_value'] < (verification_values[1]):
            result['verification_status'] = 'PASS'
        else:
            result['verification_status'] = 'FAIL'

    msg = f'Evaluated predict for {telem_uuid} {result["actual_value"]} {operator} {verification_values} - setting verification status to {result["verification_status"]}'
    logger.info(msg)
    return result


def get_input_output_paths(error_msg):
    '''
    Get absolute paths of input and output files from command line arguments.

    Command line argument can be a relative path with respect to the current working directory.
    Relative paths will be translated to absolute paths.

    WARNING: If at least two input arguments are not provided, this function will exit the python process.

    Parameters
    --------
    error_msg: str
        error_msg Message will be printed before exit if not sufficient input arguments were provided.

    Returns
    --------
    input_file_abs_path: str
        Absoluate path of input json file
    output_file_abs_path: str
        Absoluate path of output json file        
    '''    
    if len(sys.argv) < 3:
        logger.error(error_msg)
        raise InputError(error_msg)

    input_file_abs_path = os.path.abspath(sys.argv[1])
    output_file_abs_path = os.path.abspath(sys.argv[2])

    return (input_file_abs_path, output_file_abs_path)   


def read_input_file(input_file_abs_path):
    '''
    Read input JSON file

    Parameters
    --------
    input_file_abs_path: str
        Absolute path of the input JSON file    

    Returns
    --------
    dict
        Content of the input json file
    '''

    try:
        with open(input_file_abs_path) as json_file:
            return json.load(json_file, object_pairs_hook=OrderedDict)
    except (FileNotFoundError, IOError, OSError) as e:
        msg = f"Unable to read input file: {input_file_abs_path}"
        logger.error(msg)
        logger.error(traceback.format_exc())
        raise InputError(msg) from e
    except json.JSONDecodeError as e:
        msg = f"Unable to parse JSON from file {input_file_abs_path}"
        logger.error(msg)
        logger.error(traceback.format_exc())
        raise InputError(msg) from e


def write_output_file(output_dict, output_file_abs_path):
    '''
    Write the output file

    If the output file exists, it will be overwritten.

    Parameters
    --------
    output_dict: dict
        Partial or full content of outputs
    output_file_abs_path: str
        Absolute path of the output JSON file    

    Returns
    --------
    None
    '''

    try:
        with open(output_file_abs_path, "w") as outfile:
            json.dump(output_dict, outfile, indent=4)
    except (IOError, OSError) as e:
        msg = f"Unable to write to output file: {output_file_abs_path}"
        logger.error(msg)
        logger.error(traceback.format_exc())
        raise InputError(msg) from e
    except TypeError as e:
        msg = f'Unable to serialize output to JSON for file {output_file_abs_path}'
        logger.error(msg)
        logger.error(traceback.format_exc())
        raise InputError(msg) from e


def write_series_file(series_data, output_dir):
    '''
    Write the series data to a file

    Parameters
    --------
    series_data: dict
        Partial or full content of outputs
    output_file_abs_path: str
        Absolute path of the output JSON file

    Returns
    --------
    None
    '''

    output_file_loc = os.path.join(output_dir, 'series.json')

    try:
        with open(output_file_loc, "w") as outfile:
            json.dump(series_data, outfile, indent=4)
    except (IOError, OSError) as e:
        msg = f"Unable to write to output file: {output_file_loc}"
        logger.error(msg)
        logger.error(traceback.format_exc())
        raise InputError(msg) from e
    except TypeError as e:
        msg = f'Unable to serialize output to JSON for file {output_file_loc}'
        logger.error(msg)
        logger.error(traceback.format_exc())
        raise InputError(msg) from e