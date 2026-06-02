"""
This script restores project configuration content from a backup file to an Ingenium server.

Authors:
    * Chris Swan (christopher.a.swan@jpl.nasa.gov)
"""

##################################################### Imports ######################################################
import logging
from ing_lib.logs import init_console_logger,get_logger
init_console_logger()

import ing_lib.common as common
from ing_lib.project_config import create_dictionary_version,create_dictionary_content,create_custom_script,create_vnv_vis
import argparse
import getpass
import urllib3
import json


##################################################### Functions ######################################################

logger = get_logger(__name__)

def get_input(args=[]):
    """
    This function gathers inputs for the Project Configuration Restore Script

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
        description='This script restores Ingenium project configuration information.',
        prog='Ingenium Restore Project Config',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-sample_project.jpl.nasa.gov')
    parser.add_argument('file_input', type=str,
                        help='Full path and file name of the project configuration file to restore.')
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
        get_logger().setLevel(logging.DEBUG)
        for handler in get_logger().handlers:
            handler.setLevel(logging.DEBUG)
            logger.debug("Logging set to Debug.")
    return inputs


def restore_dictionaries(server, dictionary_content):
    """
    Restores all Dictionary content to the source server

    Parameters
    ----------
    server
        Ingenium server
    
    dictionary_content
        Python dictionary of all dictionary content from backup
    
    Returns
    -------
        Python dictionary of all dictionary content
    """

    # Restore dictionary versions and content
    for dict_type in ['flight', 'sse']:
        for version, content in dictionary_content['versions'][dict_type].items():
            try:
                logger.info(f"Creating {dict_type} dictionary version: {version}")
                create_dictionary_version(server, dict_type, content)

                for sub_dict in ['cmds', 'evrs', 'channels', 'mil1553']:
                    if sub_dict in dictionary_content[dict_type][version] and len(dictionary_content[dict_type][version][sub_dict]) > 0:
                        logger.info(f"Creating {dict_type} {sub_dict} dictionary content for version {version}")
                        create_dictionary_content(server, dict_type, dictionary_content[dict_type][version][sub_dict], version, sub_dict)
            except Exception as e:
                logger.error(f"Error restoring {dict_type} dictionary version {version}: {str(e)}.")

    # Restore verification items
    if 'vis' in dictionary_content and dictionary_content['vis']:
        try:
            logger.info(f"Creating {len(dictionary_content['vis'])} verification items")
            create_vnv_vis(server, dictionary_content['vis'])
        except Exception as e:
            logger.error(f"Error restoring verification items: {str(e)}")

    # Restore custom scripts
    if 'custom_scripts' in dictionary_content and dictionary_content['custom_scripts']:
        try:
            logger.info(f"Creating {len(dictionary_content['custom_scripts'])} custom scripts")
            create_custom_script(server, dictionary_content['custom_scripts'])
        except Exception as e:
            logger.error(f"Error restoring custom scripts: {str(e)}")

    logger.info("Project configuration restore completed")
    return dictionary_content


##################################################### Main ###########################################################


def main(args=[]):
    """
    This is the main function of the Ingenium Project Configuration Restore script

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

    logger.info(f"Restoring project configuration from {inputs.file_input} to {inputs.server}.")

    if inputs.rsa:
        pw_prompt = f"Enter RSA Passcode for {username}:"
    else:
        pw_prompt = f"Enter LDAP Password for {username}:"

    # Login to server
    login = common.authenticate(inputs.server, username=username, password=getpass.getpass(pw_prompt), force=True,
                                  rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    logging.debug(f"Loading {inputs.file_input} into memory.")
    with open(inputs.file_input, "r") as file:
        dictionary_content = json.load(file)
    logging.debug(f"File {inputs.file_input} loaded into memory.")


    restore_dictionaries(inputs.server, dictionary_content)


if __name__ == '__main__':
    try:
        main()
    except common.IngeniumLibError:
        logger.error("Ingenium Project Configuration Restore script has encountered and error and needs to exit. Please check the log messages for the source of the error.")

