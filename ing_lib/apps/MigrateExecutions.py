"""
This script migrates the executions or as-runs from one ingenium instance to another (via api).

Authors:
    * Chris Swan (christopher.a.swan@jpl.nasa.gov)
"""

##################################################### Imports ######################################################
import logging
from ing_lib.logs import init_console_logger,get_logger
init_console_logger()

import ing_lib.common as common
from ing_lib.executions import get_ingenium_executions,export_execution,import_execution
import argparse
import getpass
import datetime
import os
import posixpath
import urllib3

###### Constants
EXEC_STATUS_TO_MIGRATE = ['CLOSED', 'IN_REVIEW', 'FINALIZED'] # Only consider completed procedures

##################################################### Functions ######################################################

logger = get_logger(__name__)

def get_input(args=[]):
    """
    This function gathers inputs for the Migrate Execution Script

    Parameters
    --------
    args
        list of input arguments. Used when this is called from another Python module.

    Returns
    -------
        inputs: object
            Argparse input object
    """

    parser = argparse.ArgumentParser(description='This script migrates Ingenium executions (as-runs) between servers.',
                                     prog='MigrateExecutions.py',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('source_server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-psyche-atlo.fltops.jpl.nasa.gov')
    parser.add_argument('destination_server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-psyche.jpl.nasa.gov')
    parser.add_argument('execution_ids', type=str,
                        help='Comma separated list of Ingenium Execution IDs to limit the migration to or ALL to migrate all executions.(example: psyche-ingenium-10311,psyche-ingenium-10312)')
    parser.add_argument('--force', action='store_true',
                        help='Force migrates executions regardless if they exist in the destination Ingenium instance.')
    parser.add_argument('--debug', action='store_true', help='Enables debug logging.')
    parser.add_argument('--username', type=str,
                        help='Optional input to use a different username to login to Ingenium server.')
    parser.add_argument('--ignore_ssl_error', action='store_true', help='Ignore SSL verification error')
    parser.add_argument('--ssl_ca_bundle', type=str,
                        help='Path to the SSL CA bundle. If provided, this will override ignore_ssl_error.')
    parser.add_argument('--temp_dir', type=str,
                        help='Location in the file system where executions will be temporarily stored.',
                        default='/tmp')
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


def compare_executions(source_executions, destination_executions, inputs):
    """
    This function compares the source and destination executions and determines what is needed to be migrated.

    Parameters
    ----------
    source_executions: list
        List of executions (dict)
    destination_executions: list
        List of executions (dict)

    inputs: object
        Argparse input object

    Returns
    -------
    execution_ids_to_migrate: list
        List of source Ingenium execution ids to migrate
    """

    src_dict = {}
    dest_dict = {}

    execution_ids_to_migrate = []

    # Convert the provided exec_ids to a list
    try:
        execution_ids = inputs.execution_ids.split(',')
    except:
        msg = f"Could not process list of execution ids: {inputs.execution_ids}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    # Mine the source for their id and status
    for src_exec in source_executions:
        src_dict[src_exec['execution_id']] = src_exec['status']

    for user_exec_id in execution_ids:
        if not src_dict.get(user_exec_id):
            msg = f"User provided execution_id: {user_exec_id} not located in: {inputs.source_server}"
            logger.warning(msg)

    # Mine the destination for their id and status
    for dest_exec in destination_executions:
        dest_dict[dest_exec['execution_id']] = dest_exec['status']

    # Step through the source
    for execution_id, status in src_dict.items():

        # Check if the execution_id includes 'ALL' - if so skip because every execution will be migrated
        if 'ALL' not in execution_ids:
            # Otherwise check if the source execution_id is not in the list - skip it
            if execution_id not in execution_ids:
                continue

        # Check if the status can be migrated
        if status not in EXEC_STATUS_TO_MIGRATE:
            msg = f"Execution_id: {execution_id} has status: {status} which is not supported for migration - skipping. (Supported status: {EXEC_STATUS_TO_MIGRATE})"
            logger.warning(msg)
            # if not move to the next
            continue

        # Check if the execution is in the destination
        if dest_dict.get(execution_id):
            # If the destination execution is in a closed/in review/finalized status, don't migrate it (unless --force is used)
            if dest_dict[execution_id] not in EXEC_STATUS_TO_MIGRATE:
                execution_ids_to_migrate.append(execution_id)
            # If the force option is selected, add it to the list regardless of the status in the target instance
            elif inputs.force:
                msg = f"Execution: {execution_id} exists on destination with status: {status}, but force option was selected, so queuing for migration."
                logger.debug(msg)
                execution_ids_to_migrate.append(execution_id)

        # If not add it to the migration list
        else:
            execution_ids_to_migrate.append(execution_id)

    return sorted(execution_ids_to_migrate)


def migrate_executions(inputs, execution_ids_to_migrate, username, password):
    """
    This function exports executions for migration from the source and imports them to the destination.

    Parameters
    ----------
    inputs: object
        Argparse input object
    execution_ids_to_migrate:list
        List of  Ingenium execution ids to migrate
    username: str
        User name
    password: str
        Password

    Returns
    -------

    """

    # Create a temporary directory to save the execution tar.gz files
    tmp_folder = 'execution_migrate_tmp_' + datetime.datetime.strftime(datetime.datetime.now(datetime.timezone.utc), '%Y_%m_%d_%H%M%S%f')

    save_directory = posixpath.join(inputs.temp_dir, tmp_folder)

    try:
        os.mkdir(save_directory)
    except:
        msg = f"Could not create temp directory: {save_directory}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    for idx, execution in enumerate(execution_ids_to_migrate):

        # Login to the source server and export the execution
        login = common.authenticate(inputs.source_server, username=username, password=password, force=True, rsa=inputs.rsa)

        if not login:
            msg = f"Failure to Login to: {inputs.source_server} - Can not proceed. Exiting."
            logger.error(msg)
            raise common.IngeniumLibError(msg)

        filename = f"{execution}.tar.gz"
        file_path = posixpath.join(save_directory, filename)
        msg = f"Exporting execution {idx+1} of {len(execution_ids_to_migrate)} from: {inputs.source_server} to {file_path}"
        logger.info(msg)
        export_execution(inputs.source_server, execution, file_path)



        # Login to the destination server and import the execution
        login = common.authenticate(inputs.destination_server, username=username, password=password, force=True, rsa=inputs.rsa)

        if not login:
            msg = f"Failure to Login to: {inputs.destination_server} - Can not proceed. Exiting."
            logger.error(msg)
            raise common.IngeniumLibError(msg)

        msg = f"Importing execution {idx+1} of {len(execution_ids_to_migrate)} from: {file_path} to {inputs.destination_server}"
        logger.info(msg)

        results = import_execution(inputs.destination_server, file_path)
        msg = f"Successfully migrated execution: {results['execution_info'].get('execution_id')} to {inputs.destination_server}"
        logger.info(msg)



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

    logger.info(f"Migrating Executions ({inputs.execution_ids}) from: {inputs.source_server} to: {inputs.destination_server} - Force Enabled: {inputs.force}")

    if inputs.rsa:
        pw_prompt = f"Enter RSA Passcode for {username}:"
    else:
        pw_prompt = f"Enter LDAP Password for {username}:"

    # Need to capture the password separately from common.authenticate as the script needs to authenticate to two
    # different servers
    password = getpass.getpass(pw_prompt)

    # Login to source_execution
    login = common.authenticate(inputs.source_server, username=username, password=password, force=True, rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.source_server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    # Query source executions
    logger.info(f"Get the list of executions in source: {inputs.source_server}")
    source_executions = get_ingenium_executions(inputs.source_server)

    # Query destination executions

    logger.info(f"Get the list of executions in destination: {inputs.destination_server}")

    # Login to destination_server
    login = common.authenticate(inputs.destination_server, username=username, password=password, force=True, rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.destination_server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    # Query Destination
    destination_executions = get_ingenium_executions(inputs.destination_server)

    # Compare source and destination to determine what needs to be exported/imported
    executions_to_migrate = compare_executions(source_executions, destination_executions, inputs)

    if not executions_to_migrate:
        msg = 'No executions found to migrate. Exiting'
        logger.warning(msg)
    else:
        # Now for each execution to migrate - export it and import it
        logger.info(f"Migrating: {len(executions_to_migrate)} executions from: {inputs.source_server} to: {inputs.destination_server}.")
        migrate_executions(inputs, executions_to_migrate, username, password)
        logger.info(f"Migration of {len(executions_to_migrate)} executions from: {inputs.source_server} to: {inputs.destination_server} successful.")


if __name__ == '__main__':
    try:
        main()
    except common.IngeniumLibError:
        logger.error("Ingenium Migrate Executions encountered an error and needs to exit. Please check the log messages for the source of the error.")
