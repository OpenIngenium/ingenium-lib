"""
This script backs up the project configuration content from an Ingenium server to a local file

Authors:
    * Chris Swan (christopher.a.swan@jpl.nasa.gov)
"""

##################################################### Imports ######################################################
import logging
from ing_lib.logs import init_console_logger,get_logger
init_console_logger()

import ing_lib.common as common
from ing_lib.project_config import get_dictionary_versions,get_dictionary,get_custom_scripts,get_vnv_vis,get_dictionary_element
import argparse
import getpass
import urllib3
import json


##################################################### Functions ######################################################

logger = get_logger(__name__)

def csv_list(value: str):
    """Convert a comma‑separated string to a list of stripped items."""
    return [item.strip() for item in value.split(',') if item.strip()]

def get_input(args=[]):
    """
    This function gathers inputs for the Project Configuration Backup Script

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
        description='This script backs up Ingenium project configuration information.',
        prog='Ingenium Backup Project Config',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-sample_project.jpl.nasa.gov')
    parser.add_argument('api_version', type=str,
                        help='Version of the API in use by the server', choices=['v3','v4'])
    parser.add_argument('file_output', type=str,
                        help='Full path and file name of the backup project configuration file.')
    parser.add_argument('--debug', action='store_true', help='Enables debug logging.')
    parser.add_argument('--username', type=str,
                        help='Optional input to use a different username to login to Ingenium server.')
    parser.add_argument('--ignore_ssl_error', action='store_true', help='Ignore SSL verification error')
    parser.add_argument('--ssl_ca_bundle', type=str,
                        help='Path to the SSL CA bundle. If provided, this will override ignore_ssl_error.')
    parser.add_argument('--rsa', action='store_true',
                        help='Uses RSA Two Factor Authentication (username/passcode) to authenticate.')
    parser.add_argument('--filter_retired', action='store_true',
                        help='Filters dictionaries based on status and ignores RETIRED dictionaries.')
    parser.add_argument('--flight_sse', type=str, choices=['flight', 'sse'],
                        help='Limits the backup to either flight or sse dictionaries')
    parser.add_argument('--specific_versions', type=csv_list,
                        help='Limits the backup to specific versions (csv list).')
    parser.add_argument('--include_vis', action='store_true',
                        help='Whether to include V&V information in the backup')
    parser.add_argument('--include_cs', action='store_true',
                        help='Whether to include Custom Scripts information in the backup')
    parser.add_argument('--include_cmds', action='store_true',
                        help='Whether to include CMDs in the backup')
    parser.add_argument('--include_eha', action='store_true',
                        help='Whether to include EHA (channels) in the backup')
    parser.add_argument('--include_evr', action='store_true',
                        help='Whether to include EVRs in the backup')
    parser.add_argument('--include_mil1553', action='store_true',
                        help='Whether to include MIL1553 in the backup')
    parser.add_argument('--include_all', action='store_true',
                        help='Include all dictionary content (cmds, eha, evr, mil1553, vis, custom scripts)')

    if len(args) > 0:
        inputs = parser.parse_args(args)
    else:
        inputs = parser.parse_args()

    # If include_all is set, enable all include flags
    if inputs.include_all:
        inputs.include_cmds = True
        inputs.include_eha = True
        inputs.include_evr = True
        inputs.include_mil1553 = True
        inputs.include_vis = True
        inputs.include_cs = True

    # Setup debug logging (if desired)
    if inputs.debug:
        get_logger().setLevel(logging.DEBUG)
        for handler in get_logger().handlers:
            handler.setLevel(logging.DEBUG)
            logger.debug("Logging set to Debug.")
    return inputs


def get_source_dictionaries(server, api_version, inputs):
    """
    Queries all dictionaries from a source server

    Note that querying the dictionary from an older (v3) project configuration service will take some time (hours).

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash

    api_version: str
        Either v3 or v4 (slight differences between the project configuration api)

    inputs: object
        Input object

    Returns
    -------
    dictionary_content: dict
        Python dictionary of all dictionary content
    """

    # Setting up a dictionary to hold all the information

    dictionary_content = {'versions': {'flight': {}, 'sse': {}},
                          'flight': {},
                          'sse': {},
                          'vis': [],
                          'custom_scripts': []}

    for dict_type in ['sse', 'flight']:

        # If a flight/sse limit filter was provided, apply it
        if inputs.flight_sse:
            if dict_type not in inputs.flight_sse:
                continue

        versions = get_dictionary_versions(server, dict_type, api_version=api_version)

        for version in versions:

            # If a version filter was provided, apply it
            if inputs.specific_versions:
                if version.get('dictionary_version') not in inputs.specific_versions:
                    continue

            # If the list of dictionaries is long you may want to skip the Retired ones. (it takes a long time to dump all of them)
            if inputs.filter_retired:
                if version.get('state') == 'RETIRED':
                    continue
            dictionary_content['versions'][dict_type][version.get('dictionary_version')] = {
                'dictionary_description': version.get('dictionary_description'),
                'dictionary_version': version.get('dictionary_version'),
                'state': version.get('state')}
            dictionary_content[dict_type][version.get('dictionary_version')] = {'cmds': [], 'channels': [], 'evrs': [],
                                                                               'mil1553': []}

            for sub_dict in ['cmds', 'evrs', 'channels', 'mil1553']:
                # Check if this sub-dictionary type should be included based on flags
                if sub_dict == 'cmds' and not inputs.include_cmds:
                    continue
                if sub_dict == 'channels' and not inputs.include_eha:
                    continue
                if sub_dict == 'evrs' and not inputs.include_evr:
                    continue
                if sub_dict == 'mil1553' and not inputs.include_mil1553:
                    continue

                # First grab the master list of dictionary elements
                # This is only required in v3 of the PC API
                if api_version == 'v3':
                    # Query the dictionary content in the specific dictionary version (note that the try except is because if there are no elements a 400 error is thrown)
                    try:
                        elements = get_dictionary(server, version.get('dictionary_version'), dict_type,
                                                  sub_dict, api_version=api_version)
                    except:
                        logger.warning(f"Could not read {version.get('dictionary_version')} - type:{sub_dict}. Skipping", exc_info=True)
                        continue

                    # Now extract all the individual elements
                    for element in elements:
                        if sub_dict == 'cmds':
                            element_name = element.get('command_stem')
                        if sub_dict == 'evrs':
                            element_name = element.get('evr_name')
                        if sub_dict == 'channels':
                                element_name = element.get('eha_name')
                        if sub_dict == 'mil1553':
                            element_name = element.get('mil1553_name')

                        element_details =  get_dictionary_element(server,version.get('dictionary_version'),dict_type,sub_dict,element_name, api_version=api_version)
                        # Need to refresh the token because this takes awhile
                        common.refresh_auth(server)
                        dictionary_content[dict_type][version.get('dictionary_version')][sub_dict].append(element_details)

                else:
                    # Query the dictionary content in the specific dictionary version (note that the try except is because if there are no elements a 400 error is thrown)
                    try:
                        dictionary_content[dict_type][version.get('dictionary_version')][sub_dict] = get_dictionary(
                            server,
                            version.get('dictionary_version'),
                            dict_type,
                            sub_dict, api_version=api_version)
                    except:
                        logger.warning(
                            f"Could not read {version.get('dictionary_version')} - type:{sub_dict}. Skipping",
                            exc_info=True)
    if inputs.include_vis:
        dictionary_content['vis'] = get_vnv_vis(server,api_version=api_version)

    if inputs.include_cs:
        dictionary_content['custom_scripts'] = get_custom_scripts(server,api_version=api_version)

    return dictionary_content


##################################################### Main ###########################################################


def main(args=[]):
    """
    This is the main function of the Ingenium Migrate Execution script

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

    logger.info(f"Backing up project configuration from {inputs.server} to {inputs.file_output}.")

    if inputs.rsa:
        pw_prompt = f"Enter RSA Passcode for {username}:"
    else:
        pw_prompt = f"Enter LDAP Password for {username}:"

    # Login to source_execution
    login = common.authenticate(inputs.server, username=username, password=getpass.getpass(pw_prompt), force=True,
                                  rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    source_dict = get_source_dictionaries(inputs.server, inputs.api_version, inputs)

    with open(inputs.file_output, "w") as file:
        json.dump(source_dict, file)

if __name__ == '__main__':
    try:
        main()
    except common.IngeniumLibError:
        logger.error("Ingenium Project Configuration backup script has encountered and error and needs to exit. Please check the log messages for the source of the error.")

