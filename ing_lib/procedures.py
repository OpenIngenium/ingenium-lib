"""
This is a library of functions used to query and manage Ingenium procedures and procedure versions
including version export/import.

Authors:
    * Chris Swan

"""

##################################################################### Imports
import requests
from ing_lib.common import _auth_header,procedure_endpoint,get_ssl_verify
from ing_lib.common import IngeniumLibError,response_handler,ingenium_rest_get_paginated
from ing_lib.logs import get_logger

##################################################### Functions ######################################################

logger = get_logger(__name__)

def get_procedures(server, query={}):
    """
    This function queries the Ingenium Server for a list of procedures

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    query: dict
        Optional query parameters

    Returns
    -------
    procedure_content: list
        List of JSON objects containing the procedures
    """

    endpoint = f"{server}{procedure_endpoint}"

    msg = f"Querying Ingenium Procedures from: {server}"
    logger.info(msg)

    procedure_content = ingenium_rest_get_paginated(endpoint, query_params=query)

    return procedure_content


def get_procedure_versions(server, procedure_id, query={}):
    """
    This function queries the Ingenium Server for a list of versions (for a given procedure)

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    procedure_id: str
        Ingenium Procedure ID

    query: dict
        Optional query parameters

    Returns
    -------
    procedure_version_content: list
        List of JSON objects containing the procedure versions
    """

    endpoint = f"{server}{procedure_endpoint}/{procedure_id}/versions"

    msg = f"Querying Ingenium Procedures from: {server} for: {procedure_id}"
    logger.info(msg)

    procedure_version_content = ingenium_rest_get_paginated(endpoint, query_params=query)

    return procedure_version_content


def get_procedures_and_versions(server):
    """
    This function queries for a list of procedures on the specified Ingenium server and then loops through each one,
    collecting the version information.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    Returns
    -------
    proc_vers: list
        List of dictionaries containing the procedure and version information
    """

    proc_vers = []

    # Query for a list of procedures
    procedures = get_procedures(server)

    # Query for a list of versions for each procedure
    for procedure in procedures:
        versions = get_procedure_versions(server, procedure['procedure_id'])
        for version in versions:
            data = {'procedure': procedure,
                    'version': version}
            proc_vers.append(data)

    return proc_vers


def export_procedure_version(server, procedure_id, version, filepath):
    """
    This function exports a specific procedure and version to a file in the file system.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    procedure_id: str
        Ingenium Procedure ID

    version: str
        Version to export

    filepath: str
        Location in the file system to save the exported procedure.

    Returns
    -------

    """

    endpoint = f"{server}{procedure_endpoint}/{procedure_id}/export_versions"

    query_params = {'version': version}

    try:
        res = requests.get(endpoint, headers=_auth_header(), verify=get_ssl_verify(), params=query_params,
                           stream=True)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        try:
            with open(filepath, 'wb') as f:
                for chunk in res.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
        except:
            msg = f"Error when writing file to {filepath}"
            logger.error(msg)
            raise IngeniumLibError(msg)
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def import_procedure_versions(server, source_file):
    """
    This function allows a procedure to be imported from an exported tar.gz file

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    source_file: str
        Full path to a compatible tar.gz file

    Returns
    -------
    data: dict
        Dictionary/Json response
    """

    endpoint = f"{server}{procedure_endpoint}/import"

    try:
        with open(source_file, 'rb') as file:
            file_payload = {'procedure_versions_file': file}
            res = requests.post(endpoint, headers=_auth_header(),
                                verify=get_ssl_verify(),
                                files=file_payload)
    except FileNotFoundError:
        msg = f"Failed to open file: {source_file}"
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
