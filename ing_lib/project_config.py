"""
This is a library of functions used to query and manage Ingenium's project configuration information including
cmd/tlm dictionaries, V&V information, and custom scripts.

Authors:
    * Chris Swan 

"""

##################################################################### Imports
import requests
from ing_lib.common import _auth_header,dictionary_endpoint,get_ssl_verify
from ing_lib.common import IngeniumLibError,response_handler,ingenium_rest_get,ingenium_rest_get_paginated
from ing_lib.logs import get_logger

##################################################### Functions ######################################################

logger = get_logger(__name__)

def get_dictionary_versions(server, flight_sse, query={}, api_version='v4'):
    """
    This function queries the dictionary service for a list of versions (Flight and SSE)

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    flight_sse
        flight or sse

    query
        Optional query parameter for searching dictionary content

    api_version
        Currently supports v3 and v4

    Returns
    -------
        Two Lists of JSON objects
    """

    endpoint = f"{server}{dictionary_endpoint}{api_version}/dictionaries/{flight_sse}/versions"

    msg = f"Querying Ingenium Flight Dictionary Versions from: {endpoint}"
    logger.info(msg)

    versions = ingenium_rest_get_paginated(endpoint,query_params = query)

    return versions


def delete_dictionary_version(server, flight_sse, dictionary_version):
    """
    Deletes a Dictionary Version. Note only compatible with V4 of the API

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    flight_sse: str
        Either sse or flight

    dictionary_version: str
        Dictionary version to update

    Returns
    -------
    data
        JSON object containing dictionary details
    """

    endpoint = f'{server}{dictionary_endpoint}v4/dictionaries/{flight_sse}/versions/{dictionary_version}'

    try:
        res = requests.delete(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify())
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        pass
        # Note no action is required if 204 is received (empty JSON)
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def get_dictionary(server, dictionary, flight_sse, dict_type, query={}, api_version='v4'):
    """
    This function queries the dictionary service for dictionary content

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    api_version
        Currently supports v3 and v4

    dictionary
        Name of the dictionary (per Ingenium)

    flight_sse
        flight or sse (which dictionary to query)

    dict_type
        cmds/evrs/channels/mil1553

    query
        Dictionary of query parameters (refer to API for details)

    api_version
        Currently supports v3 and v4

    Returns
    -------
    dictionary_content
        JSON object containing the dictionary content
    """

    if dict_type not in ['cmds', 'evrs', 'channels', 'mil1553']:
        msg = f"Unknown dictionary type: {dict_type}. Supported options: cmds, evrs, channels, mil1553."
        logger.error(msg)
        raise IngeniumLibError(msg)
    # Channels used to be called "ehas" (JPL specific name for channels)
    if api_version == 'v3' and dict_type == 'channels':
        dict_type = 'ehas'

    endpoint = f'{server}{dictionary_endpoint}{api_version}/dictionaries/{flight_sse}/versions/{dictionary}/{dict_type}'

    msg = f"Querying Ingenium Dictionary Versions: {dictionary} ({flight_sse}) from: {endpoint}"
    logger.info(msg)

    dictionary_content = ingenium_rest_get_paginated(endpoint, query_params = query)

    return dictionary_content


def get_dictionary_element(server, dictionary, flight_sse, dict_type, element_name, api_version='v4'):
    """
    This function queries a single dictionary element by version,flight/sse, type, and name.

    Parameters
    ----------
    server: str
        The Ingenium server
    dictionary:str
        The dictionary version to query
    flight_sse: str
        Either flight or sse
    dict_type:str
        One of the dictionary types supports (cmds, evrs, channels, mil1553)
    element_name:str
        The name of the dictionary element
    api_version: str
        Either v3 (Ingenium 14.3.x) or v4 (Ingenium 15.x)

    Returns
    -------
    element_content: dict
        Dictionary containing the details of the dictionary element
    """

    if dict_type not in ['cmds', 'evrs', 'channels', 'mil1553']:
        msg = f"Unknown dictionary type: {dict_type}. Supported options: cmds, evrs, channels, mil1553."
        logger.error(msg)
        raise IngeniumLibError(msg)
    # Channels used to be called "ehas" (JPL specific name for channels)
    if api_version == 'v3' and dict_type == 'channels':
        dict_type = 'ehas'

    endpoint = f'{server}{dictionary_endpoint}{api_version}/dictionaries/{flight_sse}/versions/{dictionary}/{dict_type}/{element_name}'

    msg = f"Querying Ingenium Dictionary: {dictionary} ({flight_sse}) for: {element_name}"
    logger.debug(msg)

    element_content = ingenium_rest_get(endpoint)

    return element_content


def get_custom_scripts(server, query={}, api_version='v3'):
    """
    This function queries the dictionary service for custom scripts

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    query
        Dictionary of query parameters for filtering

    api_version
        Currently supports v3 and v4

    Returns
    -------
    custom_scripts
        JSON object containing an array of custom scripts
    """
    endpoint = f'{server}{dictionary_endpoint}{api_version}/custom_scripts'

    msg = f"Querying Ingenium ({server}) for custom scripts."
    logger.info(msg)
    custom_scripts = ingenium_rest_get_paginated(endpoint, query_params=query)

    return custom_scripts


def get_vnv_vis(server, query={}, api_version='v3'):
    """
    This function queries the dictionary service for V&V Verification Items

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    api_version
        Currently supports v3 and v4

    Returns
    -------
    vis
        JSON object containing an array of Verification Items
    """

    endpoint = f'{server}{dictionary_endpoint}{api_version}/vnv/vis'

    msg = f"Querying Ingenium({server}) for Verification Items."
    logger.info(msg)

    vis = ingenium_rest_get_paginated(endpoint, query_params = query)

    return vis


def get_vnv_vis_bulk(server, bulk_list, api_version='v3'):
    """
    This function queries the dictionary service for V&V Verification Items

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    bulk_list
        List of VI IDs to return the results

    api_version
        Currently supports v3 and v4

    Returns
    -------
    vis
        JSON object containing an array of Verification Items
    """

    endpoint = f'{server}{dictionary_endpoint}{api_version}/vnv/vis/bulk_query'

    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=bulk_list)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        vis = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return vis


def create_dictionary_version(server, flight_sse, content):
    """
    Creates a Dictionary Version. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    flight_sse
        Either sse or flight

    content
        dictionary following the format {dictionary_description: <description>,
                                         dictionary_version: <version>,
                                         state:<state>}

    Returns
    -------
    data
        JSON object containing dictionary details
    """

    endpoint = f'{server}{dictionary_endpoint}v4/dictionaries/{flight_sse}/versions'

    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg, exc_info=True)
        raise IngeniumLibError(msg)

    if response_handler(res):
        data = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return data


def update_dictionary_version(server, flight_sse, dictionary_version, content):
    """
    Creates a Dictionary Version. Note only compatible with V4 of the API

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    flight_sse: str
        Either sse or flight

    dictionary_version: str
        Dictionary version to update

    content: dict
        dictionary following the format {dictionary_description: <description>,
                                         state:<state>}

    Returns
    -------
    data
        JSON object containing dictionary details
    """

    endpoint = f'{server}{dictionary_endpoint}v4/dictionaries/{flight_sse}/versions/{dictionary_version}'

    try:
        res = requests.patch(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
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


def create_dictionary_content(server, flight_sse, content, dictionary_version, dictionary_type):
    """
    Creates dictionary content of a particular type. Note only compatible with V4 of the API

        Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    flight_sse
        Either sse or flight

    content
        An array of dictionary content (per the dictionary type)

    dictionary_version
        Dictionary version to update

    dictionary_type
        cmds, evrs, channels, mil1553

    Returns
    -------
    data
        JSON object containing arrays of dictionary content
    """

    endpoint = f'{server}{dictionary_endpoint}v4/dictionaries/{flight_sse}/versions/{dictionary_version}/{dictionary_type}'

    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
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


def update_dictionary_element(server, dictionary, flight_sse, dict_type, element_name, content, api_version='v4'):
    """
    Updates a single dictionary element. Note only compatible with V4 of the API

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    dictionary: str
        The dictionary version to update

    flight_sse: str
        Either sse or flight

    dict_type: str
        cmds, evrs, channels, mil1553

    element_name: str
        The name of the dictionary element to update

    content: dict
        Dictionary element content following the appropriate schema

    Returns
    -------
    data: dict
        JSON object containing the updated dictionary element
    """

    if dict_type not in ['cmds', 'evrs', 'channels', 'mil1553']:
        msg = f"Unknown dictionary type: {dict_type}. Supported options: cmds, evrs, channels, mil1553."
        logger.error(msg)
        raise IngeniumLibError(msg)

    endpoint = f'{server}{dictionary_endpoint}{api_version}/dictionaries/{flight_sse}/versions/{dictionary}/{dict_type}/{element_name}'

    try:
        res = requests.patch(endpoint, headers=_auth_header(),
                             verify=get_ssl_verify(),
                             json=content)
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


def delete_dictionary_element(server, dictionary, flight_sse, dict_type, element_name, api_version='v4'):
    """
    Deletes a single dictionary element. Note only compatible with V4 of the API

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    dictionary: str
        The dictionary version to update

    flight_sse: str
        Either sse or flight

    dict_type: str
        cmds, evrs, channels, mil1553

    element_name: str
        The name of the dictionary element to delete

    Returns
    -------
    None
    """

    if dict_type not in ['cmds', 'evrs', 'channels', 'mil1553']:
        msg = f"Unknown dictionary type: {dict_type}. Supported options: cmds, evrs, channels, mil1553."
        logger.error(msg)
        raise IngeniumLibError(msg)

    endpoint = f'{server}{dictionary_endpoint}{api_version}/dictionaries/{flight_sse}/versions/{dictionary}/{dict_type}/{element_name}'

    try:
        res = requests.delete(endpoint, headers=_auth_header(),
                              verify=get_ssl_verify())
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        pass
        # Note no action is required if 204 is received (empty JSON)
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def create_custom_script(server, content):
    """
    Creates custom scripts. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    content
        An array of custom scripts

    Returns
    -------
    data
        JSON object containing an array of custom scripts
    """

    endpoint = f'{server}{dictionary_endpoint}v4/custom_scripts'

    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
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


def update_custom_script(server, script_id, content):
    """
    Updates a custom script. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    script_id
        Unique ID of the script

    content
        An array of custom scripts

    Returns
    -------
    data
        JSON object containing an array of custom scripts
    """

    endpoint = f'{server}{dictionary_endpoint}v4/custom_scripts/{script_id}'

    try:
        res = requests.patch(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
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


def delete_custom_script(server, script_id):
    """
    Deletes a custom script. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    script_id
        Unique ID of the script

    Returns
    -------
    """

    endpoint = f'{server}{dictionary_endpoint}v4/custom_scripts/{script_id}'
    logger.info(f"Deleting custom script with ID: {script_id}")
    try:
        res = requests.delete(endpoint, headers=_auth_header(),
                              verify=get_ssl_verify())
        if res.status_code == 404:
            logger.warning(f"Custom script with ID {script_id} not found on server, nothing to delete.")
        elif response_handler(res):
            logger.info(f"Successfully deleted custom script with ID: {script_id}")
        else:
            msg = f"Failed to delete custom script with ID {script_id}"
            logger.error(msg)
            raise IngeniumLibError(msg)
    except requests.ConnectionError as e:
        msg = f"Failed to communicate with {server}: {e}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def create_vnv_vis(server, content):
    """
    Creates Verification Items. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    content
        An array of verification items

    Returns
    -------
    data
        JSON object containing dictionary details
    """

    endpoint = f'{server}{dictionary_endpoint}v4/vnv/vis'

    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        data = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    return data


def update_vnv_vi(server, vi_id, content):
    """
    Creates Verification Items. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    vi_id
        Dictionary containing updates

    content
        An array of verification items

    Returns
    -------
    data
        JSON object containing dictionary details
    """

    endpoint = f'{server}{dictionary_endpoint}v4/vnv/vis/{vi_id}'

    try:
        res = requests.patch(endpoint, headers=_auth_header(), verify=get_ssl_verify(), json=content)
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


def delete_vnv_vi(server, vi_id):
    """
    Deletes Verification Items. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    vi_id
        Dictionary containing updates

    Returns
    -------
    """

    endpoint = f'{server}{dictionary_endpoint}v4/vnv/vis/{vi_id}'

    try:
        res = requests.delete(endpoint, headers=_auth_header(), verify=get_ssl_verify())
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        pass
        # Note no action is required if 204 is received (empty JSON)
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)


def get_built_in_palette(server, query={}):
    """
    Gets all built-in step palette settings

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash

    query
        Dictionary containing query parameters (step_type, display_name, enable_disable)

    Returns
    -------
    steps
        List of built-in step palette settings

    """

    endpoint = f"{server}{dictionary_endpoint}v4/step_palette/built_in"

    msg = f"Querying Ingenium Built-in Step Palette from: {endpoint}"
    logger.info(msg)

    steps = ingenium_rest_get(endpoint, query_params = query)

    return steps


def update_built_in_palette(server, step_type, content):
    """
    Updates a specific built-in step_type palette settings.

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash

    step_type
        Built-in step to modify palette settings for. Includes:
            - MANUAL_INPUT
            - MANUAL_EIP
            - VENUE_CONFIG_MANUAL
            - ENVIRONMENT_MANUAL
            - GDS_MANUAL
            - QUERY_EVR
            - VERIFY_EHA     
            - WAIT_EHA
            - BUS_1553
            - WAIT_EVR
            - LIST_DATA_PRODUCTS
            - WAIT_DATA_PRODUCTS
            - CMD
            - CMD_FILE
            - CMD_SCMF     
            - CMD_SSE  
            - MANUAL_VERIFICATION
            - CUSTOM_SCRIPT
            - WAIT  
            - TIME_REFERENCE

    content
        Dictionary containing updates (step_display_name, palette_catagory, enable_disable)

    Returns
    -------
    step
        Built-in step palette setting
    """

    endpoint = f'{server}{dictionary_endpoint}v4/step_palette/built_in/{step_type}'

    try:
        res = requests.patch(endpoint, headers=_auth_header(),
                                       verify=get_ssl_verify(),
                                       json=content)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        step = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return step


def get_custom_palette(server, query={}):
    """
    This function queries the dictionary service for custom step palettes

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash

    query
        Optional query parameter for searching palette content (display_name, sort, limit, offset, wild)

    Returns
    -------
        JSON object containing custom palette data
    """

    endpoint = f"{server}{dictionary_endpoint}v4/step_palette/custom"

    msg = f"Querying Ingenium Custom Step Palette from: {endpoint}"
    logger.info(msg)

    palette_data = ingenium_rest_get_paginated(endpoint, query_params = query)

    return palette_data


def create_custom_palette(server, content):
    """
    Creates custom step palette entries. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash

    content
        An array of custom step palette entries following PaletteCustomStep schema

    Returns
    -------
    data
        JSON object containing an array of created custom step palette entries
    """

    endpoint = f'{server}{dictionary_endpoint}v4/step_palette/custom'

    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
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


def update_custom_palette(server, step_id, content):
    """
    Updates a custom step palette entry. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash

    step_id
        Unique ID of the custom step palette entry

    content
        Dictionary containing updates following PaletteCustomStepPatch schema

    Returns
    -------
    data
        JSON object containing the updated custom step palette entry
    """

    endpoint = f'{server}{dictionary_endpoint}v4/step_palette/custom/{step_id}'

    try:
        res = requests.patch(endpoint, headers=_auth_header(),
                                       verify=get_ssl_verify(),
                                       json=content)
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


def delete_custom_palette(server, step_id):
    """
    Deletes a custom step palette entry. Note only compatible with V4 of the API

    Parameters
    ----------
    server
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash

    step_id
        Unique ID of the custom step palette entry

    Returns
    -------
    """

    endpoint = f'{server}{dictionary_endpoint}v4/step_palette/custom/{step_id}'

    try:
        res = requests.delete(endpoint, headers=_auth_header(),
                                        verify=get_ssl_verify())
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        pass
        # Note no action is required if 204 is received (empty JSON)
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)