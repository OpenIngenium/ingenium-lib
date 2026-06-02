"""
This script deletes all project configuration information from an Ingenium server.

Authors:
    * Chris Swan (christopher.a.swan@jpl.nasa.gov)
"""

##################################################### Imports ######################################################
import logging
from ing_lib.logs import init_console_logger
init_console_logger(logging.INFO)

import ing_lib.common as common
from ing_lib.project_config import get_dictionary_versions, delete_dictionary_version, get_vnv_vis, get_custom_scripts
from ing_lib.project_config import delete_vnv_vi, delete_custom_script
import argparse
import getpass
import urllib3



##################################################### Functions ######################################################

logger = logging.getLogger(__name__)

def get_input(args=[]):
    """
    This function gathers inputs for the Project Configuration Clear Script

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
        description='This script deletes Ingenium project configuration information.',
        prog='Ingenium Clear Project Config',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-sample_project.jpl.nasa.gov')
    parser.add_argument('--types', nargs='+', choices=['flight', 'sse', 'vis', 'custom-scripts'],
                        help='Specify which types of project configuration to delete. '
                             'Choices are flight, sse, vis, and custom-scripts. '
                             'If not specified, all project configuration information will be deleted.')
    parser.add_argument('--debug', action='store_true', help='Enables debug logging.')
    parser.add_argument('--username', type=str,
                        help='Optional input to use a different username to login to Ingenium server.')
    parser.add_argument('--ignore_ssl_error', action='store_true', help='Ignore SSL verification error')
    parser.add_argument('--ssl_ca_bundle', type=str,
                        help='Path to the SSL CA bundle. If provided, this will override ignore_ssl_error.')
    parser.add_argument('--rsa', action='store_true',
                        help='Uses RSA Two Factor Authentication (username/passcode) to authenticate.')

    if len(args) > 0:
        inputs = parser.parse_args(args)
    else:
        inputs = parser.parse_args()

    # Setup debug logging (if desired)
    if inputs.debug:
        for handler in logger.root.handlers:
            handler.setLevel(logging.DEBUG)
            logger.debug("Logging set to Debug.")
    return inputs


def clear_project_configuration(server, types_to_delete):
    """
    Clears specified project configuration information from an Ingenium server.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium.project_name.jpl.nasa.gov) without a trailing slash
    types_to_delete: list
        A list of strings of types to delete.
        Valid types are: 'flight', 'sse', 'vis', 'custom-scripts'.

    Returns
    -------
    """

    dict_types_to_delete = [t for t in types_to_delete if t in ['flight', 'sse']]
    for dict_type in dict_types_to_delete:
        versions = get_dictionary_versions(server, dict_type, api_version='v4')
        logger.info(f"Deleting {len(versions)} versions of {dict_type} dictionaries.")
        for version in versions:
            logger.debug(f"Deleting Version: {version.get('dictionary_version')}")
            try:
                delete_dictionary_version(server, dict_type, version.get('dictionary_version'))
            except:
                continue

    if 'vis' in types_to_delete:
        vis = get_vnv_vis(server, api_version='v4')
        logger.info(f"Deleting {len(vis)} VIs.")
        count = 0
        for vi in vis:
            count = count + 1
            if count >= 1000:
                logger.info(f"Deleted 1000 VIs")
                count = 0
            delete_vnv_vi(server, vi.get('vi_id'))

    if 'custom-scripts' in types_to_delete:
        custom_scripts = get_custom_scripts(server, api_version='v4')
        logger.info(f"Deleting {len(custom_scripts)} Scripts.")
        for script in custom_scripts:
            delete_custom_script(server, script.get('script_id'))

    return

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
        common.ssl_verify = inputs.ssl_ca_bundle
    else:
        common.ssl_verify = not inputs.ignore_ssl_error
        if not common.ssl_verify:
            # To suppress SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.debug(f"Ingenium.ssl_verify:{common.ssl_verify}")

    if inputs.username:
        username = inputs.username
    else:
        username = getpass.getuser()

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

    types_to_delete = inputs.types
    if not types_to_delete:
        types_to_delete = ['flight', 'sse', 'vis', 'custom-scripts']
        confirm_message = f"Are you sure you want to clear all project configuration information from {inputs.server}? This operation can not be undone. (yes/no): "
    else:
        confirm_message = f"Are you sure you want to clear the following project configuration types: {', '.join(types_to_delete)} from {inputs.server}? This operation can not be undone. (yes/no): "

    confirm = input(confirm_message).lower()

    while confirm not in ["yes", "no"]:
        confirm = input("Please enter 'yes' or 'no': ").lower()

    if confirm == "yes":
        logger.info(f"Clearing project configuration from {inputs.server}.")
        clear_project_configuration(inputs.server, types_to_delete)
        logger.info("Project configuration cleared successfully.")
    else:
        logger.info("Operation cancelled by user.")


if __name__ == '__main__':
    try:
        main()
    except common.IngeniumLibError:
        logger.error("Ingenium Project Configuration clear script has encountered and error and needs to exit. Please check the log messages for the source of the error.")

