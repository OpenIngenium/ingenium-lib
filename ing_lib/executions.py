"""
This is a library of functions used to query and manage Ingenium executions (as-runs)
including execution export/import.

Authors:
    * Chris Swan

"""

##################################################################### Imports
import requests
from ing_lib.common import _auth_header,as_run_endpoint,get_ssl_verify
from ing_lib.common import IngeniumLibError,response_handler,ingenium_rest_get,ingenium_rest_get_paginated
from ing_lib.logs import get_logger

##################################################### Functions ######################################################

logger = get_logger(__name__)

def get_ingenium_execution_info(server, execution_id):
    """
    This function queries Ingenium for execution meta data

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Ingenium Execution ID

    Returns
    -------
    execution_info: dict
        JSON object containing execution meta data
    """

    endpoint = f"{server}{as_run_endpoint}/{execution_id}"

    msg = f"Querying Ingenium Execution Info: {execution_id} from: {server}"
    logger.info(msg)

    execution_info = ingenium_rest_get(endpoint)

    return execution_info


def get_ingenium_execution(server, execution_id):
    """
    This function queries Ingenium for an as-run and returns the execution summary and
    the element history in chronological order (for steps executed).

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Ingenium Execution ID

    Returns
    -------
    as_run_info: dict
        JSON object containing top level as-run information
    as_run_data: list
        JSON object containing all steps in the as-run in chronologic order
    """

    # Get the As-Run Information (top level)
    endpoint = f"{server}{as_run_endpoint}/{execution_id}"

    msg = f"Querying Ingenium Execution: {execution_id} from: {server}"
    logger.info(msg)

    as_run_info = ingenium_rest_get(endpoint)

    # Get the As-Run Contents
    endpoint = f"{server}{as_run_endpoint}/{execution_id}/history"

    as_run_data = ingenium_rest_get(endpoint, query_params={"limit": 10000})

    return as_run_info, as_run_data


def get_ingenium_procedure_sections(server, execution_id):
    """
    This function queries Ingenium for an as-run and returns the procedure sections that are
    contained in the execution.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Ingenium Execution ID

    Returns
    -------
    procedure_sections: list
        JSON object containing all procedure sections in an execution
    """

    endpoint = f"{server}{as_run_endpoint}/{execution_id}/procedure_sections"

    msg = f"Querying Procedure Sections from Ingenium Execution: {execution_id} from: {server}"
    logger.info(msg)

    procedure_sections = ingenium_rest_get(endpoint, query_params={"limit": 10000})

    return procedure_sections


def refresh_ingenium_execution(server, execution_id):
    """
    Refresh computed elements in the execution (example: step references in VI Status steps)

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Ingenium Execution ID

    Returns
    -------
    elements: list
        Updated elements
    """

    endpoint = f"{server}{as_run_endpoint}/{execution_id}/refresh"

    msg = f"Refreshing Ingenium Execution: {execution_id} on: {server}"
    logger.info(msg)

    try:
        res = requests.post(endpoint, headers=_auth_header(), json={}, verify=get_ssl_verify())
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        return res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def get_procedure_section_infos(ingenium_server, execution_id, procedure_section_infos, exclude_children):
    """
    This function recursively queries executions and extracts the procedure_sections information

    Parameters
    ----------
    ingenium_server: str
        Ingenium server

    execution_id: str
        Ingenium execution id

    procedure_section_infos: list
        List of dictionaries containing information on procedures.
        Note: Mutable and accessed via the recursively called collect_procedure_section_infos and the parent function.

    exclude_children: bool
        Whether to ignore child executions

    Returns
    -------

    """

    # Get the procedure information
    procedure_sections = get_ingenium_procedure_sections(ingenium_server, execution_id)

    # Collect procedure sections of the current execution
    for procedure_section in procedure_sections:
        procedure_section_infos.append(parse_procedure_section(procedure_section))

    # If the input flag exclude_child_executions is set, do not go into child executions
    if exclude_children:
        return

    # Now recursively investigate the children
    for child in procedure_sections:
        child_execution_id = child.get('child_execution_id')
        if child_execution_id:
            get_procedure_section_infos(ingenium_server,
                                        child['child_execution_id'],
                                        procedure_section_infos,
                                        exclude_children)

    return


def parse_procedure_section(procedure_section):
    """
    This function parses a single procedure section JSON object and returns a dictionary of procedure information

    Parameters
    ----------
    procedure_section: dict
        Dictionary of information about the procedure

    Returns
    -------
    procedure: dict
        Dictionary of information about the procedure

    """

    execution_user_input = procedure_section['execution_user_input']
    tags = []
    for tag in execution_user_input['tag_selections']:
        if tag['selected']:
            tags.append(tag['name'])

    procedure = {'execution_id': procedure_section.get('execution_id'),
                 'imported': procedure_section.get('imported'),
                 # Note imported is set if imported (called or otherwise)
                 'callable': execution_user_input.get('callable'),  # Indicates that there is a separate execution
                 'procedure_id': execution_user_input.get('reference_procedure_id'),
                 'procedure_title': execution_user_input.get('reference_procedure_title'),
                 'procedure_version': execution_user_input.get('reference_procedure_version'),
                 'institutional_id': execution_user_input.get('reference_procedure_institutional_id'),
                 'institutional_release_id': execution_user_input.get('reference_procedure_institutional_release_id'),
                 'run_for_score': execution_user_input.get('run_for_score', False),
                 'child_execution_id': procedure_section.get('child_execution_id'),
                 'step_number': procedure_section.get('number'),
                 'step_title': procedure_section.get('title'),
                 'tags': tags}

    return procedure


def halt_execution(server, execution):
    """
    This function halts a procedure execution.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution: str
        Execution ID

    Returns
    -------
    data: dict
        JSON response

    """

    endpoint = f"{server}{as_run_endpoint}/{execution}/halt"

    try:
        res = requests.post(endpoint, headers=_auth_header(), verify=get_ssl_verify(), json={})
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        data = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return data


def update_ingenium_execution(server, execution_id, execution_input):
    """
    This function updates the metadata of a particular execution

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Execution ID

    execution_input: dict
        Ingenium execution meta data

    Returns
    -------
    data: dict
        JSON response

    """

    endpoint = f"{server}{as_run_endpoint}/{execution_id}"

    try:
        res = requests.patch(endpoint, headers=_auth_header(), verify=get_ssl_verify(), json=execution_input)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        return res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def set_execution_mode(server, execution_id, mode):
    """
    This function sets the mode of a particular execution

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Execution ID

    mode: str
        Ingenium execution mode to set

    Returns
    -------
    data: dict
        JSON response

    """

    endpoint = f"{server}{as_run_endpoint}/{execution_id}"

    payload = {'mode': mode}

    try:
        res = requests.patch(endpoint, headers=_auth_header(), verify=get_ssl_verify(), json=payload)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        data = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return data


def update_execution_status(server, execution_id, status):
    """
    This function updates the status of an execution (either to CLOSED or SUSPENDED).

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Execution ID

    status: str
        Either "SUSPENDED", "CLOSED", "IN_REVIEW", "FINALIZED"

    Returns
    -------
    data: dict
        JSON response

    """

    CURRENT_STATUS_LIMITS = ['IDLE', 'SUSPENDED', 'CLOSED', 'IN_REVIEW', 'FINALIZED']
    DEST_STATUS_LIMITS = ['CLOSED', 'SUSPENDED', 'IN_REVIEW', 'FINALIZED']

    # Get the current status
    execution = get_ingenium_execution_info(server, execution_id)
    current_status = execution.get('status')

    # Check that the current status is supported
    if current_status not in CURRENT_STATUS_LIMITS:
        msg = f'Can not update the status of {execution_id} to {status} as the current status is {current_status}. ' \
              f'Current status has to be in {CURRENT_STATUS_LIMITS}.'
        logger.error(msg)
        raise IngeniumLibError(msg)

    # Check that the destination status is supported
    if status not in DEST_STATUS_LIMITS:
        msg = f'Can not set the status to: {status} (Limited to: {DEST_STATUS_LIMITS}).'
        logger.error(msg)
        raise IngeniumLibError(msg)

    # Check that the request doesn't attempt to "unclose" an execution
    if current_status in ['CLOSED', 'IN_REVIEW', 'FINALIZED'] and status in ['SUSPENDED']:
        msg = 'Can not suspend an execution that has been closed.'
        logger.error(msg)
        raise IngeniumLibError(msg)

    # If the desired status skips "CLOSED" - Close the execution - then set the status to the desired status
    # This is to ensure certain operations are performed (that happen only when an as-run is closed)
    if current_status in ['IDLE', 'SUSPENDED'] and status in ['IN_REVIEW', 'FINALIZED']:
        msg = f'Status of {execution_id} is {current_status}. Closing execution before setting to {status}.'
        logger.info(msg)

        update_execution_status(server, execution_id, 'CLOSED')

    endpoint = f"{server}{as_run_endpoint}/{execution_id}/status"

    payload = {'status': status,
               'comment': f'{status} via external script'}

    try:
        res = requests.post(endpoint, headers=_auth_header(), verify=get_ssl_verify(), json=payload)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        data = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return data

def get_ingenium_executions(server, query={}):
    """
    This function queries for the list of executions on the specified server.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    query: dict
        Query terms that correspond to the ExecutionInfo filters in the API

    Returns
    -------
    executions: list
        List of JSON objects containing the executions
    """

    endpoint = f"{server}{as_run_endpoint}"

    msg = f"Querying Ingenium Executions from: {server}"
    logger.info(msg)

    executions = ingenium_rest_get_paginated(endpoint, query_params=query)

    return executions


def get_ingenium_execution_elements(server, execution_id):
    """
    This function queries Ingenium for an as-run and returns the execution summary and element information.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Ingenium Execution ID (e.g. example-ingenium-10311)

    Returns
    -------
    as_run_info: dict
        JSON object containing top level as-run information
    as_run_data: list
        JSON object containing all elements in the as-run in step order
    """

    # Get the As-Run Information (top level)
    endpoint = f"{server}{as_run_endpoint}/{execution_id}"

    msg = f"Querying Ingenium Execution: {execution_id} from: {server}"
    logger.info(msg)

    as_run_info = ingenium_rest_get(endpoint)

    # Get the As-Run Elements
    endpoint = f"{server}{as_run_endpoint}/{execution_id}/elements/"

    as_run_data = ingenium_rest_get(endpoint, query_params={"limit": 10000})

    return as_run_info, as_run_data


def export_execution(server, execution_id, file_path):
    """
    This function exports a specific execution from Ingenium to a location in the file system

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    execution_id: str
        Ingenium Execution ID

    file_path: str
        Full path to save the exported execution file

    Returns
    -------

    """

    endpoint = f"{server}{as_run_endpoint}/{execution_id}/export"

    try:
        res = requests.get(endpoint, headers=_auth_header(), verify=get_ssl_verify(), stream=True)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        try:
            with open(file_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
        except:
            msg = f"Error when writing file to {file_path}"
            logger.error(msg)
            raise IngeniumLibError(msg)
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def import_execution(server, file_path):
    """
    This function imports an Ingenium execution into a specified Ingenium server

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    file_path: str
        Full path to the exported execution file

    Returns
    -------
    data: dict
        JSON object containing results
    """

    endpoint = f"{server}{as_run_endpoint}/import"

    try:
        with open(file_path, 'rb') as file:
            file_payload = {'execution_file': file}
            res = requests.post(endpoint, headers=_auth_header(),
                                verify=get_ssl_verify(),
                                files=file_payload)
    except FileNotFoundError:
        msg = f"Failed to open file: {file_path}"
        logger.error(msg, exc_info=True)
        raise IngeniumLibError(msg)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        data = res.json()
        if data.get('messages'):
            for message in data.get('messages'):
                logger.warning(f"Import Warning: {message}")
        return data
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)
