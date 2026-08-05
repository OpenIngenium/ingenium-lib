"""
This is a library related to the management of Ingenium venues.

Authors:
    * Chris Swan 

"""

##################################################################### Imports
import requests
from common import *
from logs import get_logger


##################################################### Functions ######################################################

logger = get_logger(__name__)

def create_venue_group(server, content):
    """
    This function creates a venue group in Ingenium.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    content: dict
        Dictionary of the venue group content per API

    Returns
    -------
    venue_group: dict
        Venue Group information of the group that was created.
    """

    endpoint = f"{server}{venue_group_endpoint}"

    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        venue_group = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return venue_group


def get_venue_groups(server, query={}):
    """
    This function queries Ingenium for venue groups based on filters (per API)
    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    query: dict
        Query parameters

    Returns
    -------
    venue_groups: list
        List of venue groups (dict)
    """

    endpoint = f"{server}{venue_group_endpoint}"
    logger.debug(f"Querying Ingenium ({server}) for venue groups.")
    venue_groups = ingenium_rest_get_paginated(endpoint,query_params = query)

    return venue_groups


def get_venue_group(server, venue_group_id):
    """
    This function queries Ingenium for a specific venue groups
    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    venue_group_id: str
        UUID of the venue group

    Returns
    -------
    venue_group: dict
        Dictionary of Venue Group information
    """

    endpoint = f"{server}{venue_group_endpoint}/{venue_group_id}"
    logger.debug(f"Querying Ingenium ({server}) for venue group {venue_group_id}.")
    venue_group = ingenium_rest_get(endpoint)

    return venue_group


def update_venue_group(server, venue_group_id, content):
    """
    This function updates the definition of a venue group in  Ingenium.

    Parameters
    ----------
    server: str
        The Ingenium server to create the venue on.

    venue_group_id: str
        UUID of the venue group

    content: dict
        The information to be changed (per API).

    Returns
    -------
    venue_group: dict
        Venue Group information (as specified)
    """

    endpoint = f"{server}{venue_group_endpoint}/{venue_group_id}"

    try:
        res = requests.patch(endpoint, headers=_auth_header(),
                             verify=get_ssl_verify(),
                             json=content)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        venue_info = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return venue_info


def update_ingenium_venue(server, venue_id, content):
    """
    This function updates a venue in Ingenium.

    Parameters
    ----------
    server: str
        The Ingenium server to create the venue on.

    venue_id: str
        The uuiid of the venue.

    content: dict
        The information to be changed (per API).

    Returns
    -------
    venue_info: dict
        Venue information (as specified)
    """

    endpoint = f"{server}{venue_endpoint}/{venue_id}"

    try:
        res = requests.patch(endpoint, headers=_auth_header(),
                             verify=get_ssl_verify(),
                             json=content)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        venue_info = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return venue_info


def create_ingenium_venue(server, content):
    """
    This function creates a new venue in Ingenium.

    Parameters
    ----------
    server: str
        The Ingenium server to create the venue on.

    content: dict
        The required information to create the venue per API

    Returns
    -------
    venue_info: dict
        Venue information (as specified)
    """

    endpoint = f"{server}{venue_endpoint}"


    try:
        res = requests.post(endpoint, headers=_auth_header(),
                                      verify=get_ssl_verify(),
                                      json=content)
    except requests.ConnectionError:
        msg = f"Failed to communicate with: {server}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    if response_handler(res):
        venue_info = res.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return venue_info


def get_ingenium_venues(server, query={}):
    """
    This function queries Ingenium for venues based on filters (per API)

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    query: dict
        Query parameters

    Returns
    -------
    venues: list
        List of venues (dict)
    """

    endpoint = f"{server}{venue_endpoint}"
    logger.debug(f"Querying Ingenium ({server}) for venues.")
    venues = ingenium_rest_get_paginated(endpoint,query_params = query)

    return venues


def get_ingenium_venue(server, venue_id):
    """
    This function queries Ingenium for an individual venue's information

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium-example.com) without a trailing slash

    venue_id: str
        Ingenium venue ID

    Returns
    -------
    venue_info: dict
        Unpacked JSON object containing venue information
    """

    endpoint = f"{server}{venue_endpoint}/{venue_id}"
    logger.debug(f"Querying Ingenium ({server}) for venue_id: {venue_id}.")
    venue_info = ingenium_rest_get(endpoint)

    return venue_info




