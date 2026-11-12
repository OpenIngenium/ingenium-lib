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
