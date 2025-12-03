"""
This is a library of common functions, classes, and constants used to by the Ingenium Library to interact with Ingenium.

Authors:
    * Chris Swan

"""

##################################################################### Imports
from logs import get_logger
import datetime
import requests
import json
import getpass
import jwt
from urllib.parse import urlparse

##################################################################### Endpoints
# This lists the locations of all the Ingenium REST Endpoints (R15)
auth_endpoint = "/auth_server/api/v2/login"
refresh_endpoint = "/auth_server/api/v2/refresh_token"
venue_endpoint = "/core_server/api/v5/venues"
venue_group_endpoint = "/core_server/api/v5/venue_groups"
procedure_endpoint = "/core_server/api/v5/procedures"
as_run_endpoint = "/core_server/api/v5/executions"
dictionary_endpoint = "/dict_server/api/"

_store = {'token': None,
          'refresh_time': None,
          'ssl_verify': True}

############################################################# Constants
_TOKEN_REFRESH_DURATION = 3000
_TOKEN_DURATION = 3600

logger = get_logger(__name__)


class IngeniumLibError(Exception):
    """
    This exception indicates the Ingenium Library encountered an error and needs to abort

    """
    pass


def response_handler(response):
    """
    This function interprets the HTTP response from the Ingenium server and, depending on the endpoint, will indicate
    success or failure and log the results.

    Parameters
    ----------
    response
        The response (request object) from the Ingenium server

    Returns
    -------
        True (response OK) or False (response failed - for any reason)
    """

    good_responses = list(range(200,300))

    # Check if the status code successful - else log it
    if response.status_code in good_responses:
        msg = f"REST Call Successful Status: {response.status_code}"
        logger.debug(msg)
        response_ok = True
    else:
        msg = f"API call failed. url: {response.url} method: {response.request.method} status_code: {response.status_code} response: {response.text}"
        logger.error(msg)
        response_ok = False

    # For Bad Request responses loop through the response and log the problems with the request
    if response.status_code == 400:
        msg = f"Bad response: {response.text}"
        logger.error(msg)

    return response_ok


def ingenium_rest_get(endpoint):
    """
    This function encapsulates the restful get requests to the Ingenium servers

    Parameters
    ----------
    endpoint
        The REST endpoint to hit

    Returns
    -------
        Data (JSON)
    """

    # If needed, refresh the token
    if _stale_token():
        refresh_auth(_extract_server(endpoint), False)

    data = None

    data_req = requests.get(endpoint, headers=_auth_header(), verify=get_ssl_verify())

    if response_handler(data_req):
        data = data_req.json()
    else:
        msg = f"Response not completed successfully to {endpoint}"
        logger.error(msg)
        raise IngeniumLibError(msg)

    return data


def ingenium_rest_get_paginated(endpoint, query_params={}):
    """
    This function encapsulates the restful get requests for paginated endpoints to the Ingenium servers

    Parameters
    ----------
    endpoint
        The REST endpoint to hit

    query_params
        If there are already query parameters as part of this request

    Returns
    -------
        Data (JSON)
    """

    # If needed, refresh the token
    if _stale_token():
        refresh_auth(_extract_server(endpoint), False)

    _INITIAL_LIMIT = 1000
    _INITIAL_OFFSET = 0

    query_complete = False

    limit = _INITIAL_LIMIT
    offset = _INITIAL_OFFSET

    return_data = []

    while not query_complete:

        query_params['limit'] = limit
        query_params['offset'] = offset

        data_req = requests.get(endpoint, headers=_auth_header(), verify=get_ssl_verify(), params=query_params)

        if response_handler(data_req):
            data = data_req.json()
            header = data_req.headers
        else:
            msg = f"Response not completed successfully to {endpoint}"
            logger.error(msg)
            raise IngeniumLibError(msg)

        total = int(header['x-total-count'])

        if total <= limit + offset:
            query_complete = True
        else:
            offset = offset + _INITIAL_LIMIT

        return_data = return_data + data

    return return_data


def generate_token(private_pem, username=None, scopes=None, force=False):
    """
    This function generates an Ingenium JWT token based on a PEM located in an environment variable.

    Updates globals: token and refresh_time

    Parameters
    ----------
    pem: str
        PEM private key

    username: str
        Optional user name for the token

    scopes: list
        List of scopes to include in the token (if not provided - will include all)

    force: bool
        If the function will generate a token, even it one is present

    Returns
    -------

    """

    current_time = datetime.datetime.utcnow()

    if not _store.get('refresh_time'):
        _refresh_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=3600)

    # Check how much time is remaining on the current token
    token_time = (current_time - _store.get('refresh_time')).total_seconds()

    # Update the token if force = True or the token is older than the refresh duration
    if force or token_time > _TOKEN_REFRESH_DURATION:

        if force:
            msg = "Recreating token because force = True"
            logger.debug(msg)

        # Set the time range for the token
        # Start time = Current Time - 60 seconds
        # End time = Current Time + TOKEN_DURATION

        current_time_int = int(current_time.timestamp())
        start_time = current_time_int - 60
        end_time = current_time_int + _TOKEN_DURATION

        # If a username is provided - use it (otherwise set it to "script")
        if username:
            user_name = username
        else:
            user_name = "script"

        # If scopes are provided - use them (if not allow everything)
        if scopes:
            permissions = scopes
        else:  # TODO - Check and extract permissions
            permissions = ['basic', 'execute:wsts', 'execute:testbed', 'execute:sit', 'execute:other', 'redline',
                           'config_mgmt', 'test_lead', 'imcm', 'author', 'admin']

        # Create a token with the specified scopes
        try:
            encoded_token = jwt.encode({'scopes': permissions,
                                        'exp': end_time,
                                        'iat': start_time,
                                        'username': user_name},
                                       private_pem,
                                       algorithm='RS256')
        except:
            msg = 'Unable to generate JWT token. Likely due to an invalid input.'
            logger.error(msg, exc_info=True)
            raise IngeniumLibError(msg)

        # Convert the token to a string
        token_str = encoded_token.decode('utf-8')

        msg = f"Created token:{token_str} for user:{user_name}, scopes:{permissions}, valid from:{start_time} -{end_time}"
        logger.debug(msg)

        # Update the globals
        _store['token'] = f'Bearer {token_str}'
        _store['refresh_time'] = current_time

    # Other wise
    else:
        msg = f"Time remaining on token: {token_time} seconds is less than limit: {_TOKEN_REFRESH_DURATION}. No refresh needed."
        logger.debug(msg)


def authenticate(server, username=None, password=None, force=False, rsa=False):
    """
    This function attempts to login to the specified Ingenium server using the current user (and prompting for their
     password). If successful it stores the JWT in a dictionary. If token already exists, it will keep the token unless
     force if True.

    Parameters
    ----------
    server: str
        The Ingenium Server (without a trailing slash)

    username: str
        Optional input to specify username (will grab system username if not provided)

    password: str
        Optional input to specify password (LDAP) or passcode (RSA)

    force: bool
        If True, it will require log in regardless of existence of token

    rsa: bool
        If True, login will use RSA TFA username/passcode vs. LDAP username/password (driven by server settings)

    Returns True if successful
    -------

    """

    if get_token() is not None and not force:
        return True

    if not username:
        username = getpass.getuser()

    msg = f"Going to Authenticate as user: {username} with Server: {server}"
    logger.info(msg)

    if not password and not rsa:
        # Prompt for LDAP Password
        password = getpass.getpass('Enter Password for %s:' % username)

    if not password and rsa:
        # Prompt for RSA passcode
        password = getpass.getpass('Enter Passcode for %s:' % username)

    headers = {}
    if rsa:
        headers = {'X-AUTH-METHOD': 'rsa'}

    try:
        msg = f"Executing REST API Call to endpoint: {server}{auth_endpoint}"
        logger.debug(msg)
        logon = requests.get(server + auth_endpoint, auth=requests.auth.HTTPBasicAuth(username, password),
                             verify=get_ssl_verify(), headers=headers)
    except requests.ConnectionError as err:
        msg = f"Failed to communicate with: {server}."
        logger.error(msg)
        msg = f"Error: {repr(err)}"
        logger.error(msg)
        return False

    if response_handler(logon):
        _store['token'] = f"Bearer {json.loads(logon.text)['access_token']}"
        _store['refresh_time'] = datetime.datetime.utcnow()

        #_token = f"Bearer {json.loads(logon.text)['access_token']}"
        #_refresh_time = datetime.datetime.utcnow()
        msg = f"Successful login to {server} as {username} with token: {get_token()}"
        logger.debug(msg)
        return True
    else:
        msg = f"Login to {server} as {username} failed."
        logger.error(msg)
        return False


def refresh_auth(server, force=False):
    """
    This function refreshes the jwt token (assuming the existing token is still valid)

    Parameters
    ----------
    server: str
        Ingenium server to refresh the token

    force: bool
        Flag to force a token refresh (regardless of time)

    Returns
    -------

    """

    refresh_time = get_refresh_time()
    if refresh_time is None:
        raise IngeniumLibError("Cannot refresh token: No refresh time available. Please authenticate first.")

    token_time_remaining = (datetime.datetime.utcnow() - get_refresh_time()).total_seconds()

    if force or _stale_token():
        logger.debug('Forced refresh of token.')
        renew_header = {
            'Content-Type': 'application/json',
            'Authorization': get_token()
        }

        try:
            refresh = requests.post(server + refresh_endpoint, headers=renew_header, verify=get_ssl_verify())
        except requests.ConnectionError as err:
            msg = f"Failed to communicate with: {server}."
            logger.error(msg)
            msg = f"Error: {repr(err)}"
            logger.error(msg)
            raise IngeniumLibError(msg)
            

        if response_handler(refresh):
            _store['token'] = f"Bearer {json.loads(refresh.text)['access_token']}"
            _store['refresh_time'] = datetime.datetime.utcnow()
            msg = f"Successfully refreshed token with: {server}"
            logger.debug(msg)
            return 
        else:
            msg = "Failed to refresh token."
            logger.error(msg)
            raise IngeniumLibError(msg)

    else:
        msg = f"Time remaining on token: {token_time_remaining} seconds is less than limit: {_TOKEN_REFRESH_DURATION}. No refresh needed."
        logger.debug(msg)
        return 


def get_token():
    return _store.get('token')


def get_refresh_time():
    return _store.get('refresh_time')


def get_ssl_verify():
    return _store.get('ssl_verify')


def _auth_header():
    token = get_token()
    if not token:
        raise IngeniumLibError()
    return {"Authorization": token}


def _stale_token():
    token = get_token()
    if token is None or get_refresh_time() is None:
        return True
    elapsed = (datetime.datetime.utcnow() - get_refresh_time()).total_seconds()
    return elapsed > _TOKEN_REFRESH_DURATION


def _extract_server(endpoint):
    parsed = urlparse(endpoint)
    return f'{parsed.scheme}://{parsed.netloc}'
