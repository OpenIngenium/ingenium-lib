"""
This script migrates the procedures from one ingenium instance to another (via api).

Authors:
    * Chris Swan (christopher.a.swan@jpl.nasa.gov)
"""

##################################################### Imports ######################################################
import logging
from ing_lib.logs import init_console_logger,get_logger
init_console_logger()

import ing_lib.common as common
from ing_lib.procedures import get_procedure_versions,export_procedure_version,import_procedure_versions
import argparse
import getpass
import datetime
import os
import posixpath
import urllib3

##################################################### Functions ######################################################

logger = get_logger(__name__)

def get_input(args=[]):
    """
    This function gathers inputs for the Migrate Procedures Script

    Parameters
    --------
    args
        list of input arguments. Used when this is called from another Python module.

    Returns
    -------
        inputs: object
            Argparse input object
    """

    parser = argparse.ArgumentParser(description='This script migrates Ingenium procedures between servers.',
                                     prog='MigrateProcedures.py',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('source_server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-psyche-atlo.fltops.jpl.nasa.gov')
    parser.add_argument('destination_server', type=str,
                        help='Full Path to Ingenium Server (e.g. https://ingenium-psyche.jpl.nasa.gov')
    parser.add_argument('procedures_to_migrate', type=str,
                        help='Full Path to file containing a list of procedures to migrate.')
    parser.add_argument('--force', action='store_true',
                        help='Skips comparing the source and destination and pushes all identified procedures to destination.')
    parser.add_argument('--ignore_warnings', action='store_true',
                        help='If this flag is set the script will ignore warnings for unreleased procedures and unsupported operations (removal).')
    parser.add_argument('--debug', action='store_true', help='Enables debug output (raw JSON and csv files)')
    parser.add_argument('--username', type=str,
                        help='Optional input to use a different username to login to Ingenium server.')
    parser.add_argument('--ignore_ssl_error', action='store_true', help='Ignore SSL verification error')
    parser.add_argument('--ssl_ca_bundle', type=str,
                        help='Path to the SSL CA bundle. If provided, this will override ignore_ssl_error.')
    parser.add_argument('--temp_dir', type=str,
                        help='Location in the file system where procedures will be temporarily stored.',
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


def query_proc_ver(server, migrate_data):
    """
    This function queries the Ingenium server for a list of procedures/versions and then formats the results to focus
    on the procedure/version only.

    Parameters
    ----------
    server: str
        Ingenium Server (e.g. https://ingenium.europa.jpl.nasa.gov) without a trailing slash

    migrate_data: dict
         Dictionary (indexed by procedure id) of a list of versions to migrate

    Returns
    -------
    proc_ver_info: dict
        Dictionary (indexed by procedure_id) of dictionary of versions (indexed by version #)
    """

    proc_vers = []

    # Query for the list of procedure_ids within the input migrate_data
    for procedure_id, migrate_versions in migrate_data.items():

        versions = get_procedure_versions(server, procedure_id)

        for version in versions:
            data = {'procedure_id': procedure_id,
                    'version': version}
            proc_vers.append(data)

    # Define the return structure
    proc_ver_info = {}

    # Now build a data structure to enable easy reference

    for proc_ver in proc_vers:

        version = str(proc_ver['version']['version'])
        status = proc_ver['version']['status']
        release_id = proc_ver['version']['institutional_release_id']
        procedure_id = proc_ver['procedure_id']

        version_dict = {version: {'status': status,
                                  'release_id': release_id}}

        # If the procedure doesn't exist add it
        if proc_ver_info.get(procedure_id):
            proc_ver_info[procedure_id][version] = {'status': status,
                                                    'release_id': release_id}
        else:
            proc_ver_info[procedure_id] = version_dict

    return proc_ver_info


def read_migrate_input(filename):
    """
    This function reads an input file that lists procedure-ids and versions to migrate.

    Expect format:
    <procedure-id>,<version-num>,<version-num>,<version-num>,.... # <comment>

    Parameters
    ----------
    filename: str
        Full path to the file to open and parse

    Returns
    -------
    to_migrate: dict
        Dictionary (indexed by procedure id) of a list of versions to migrate
    """

    to_migrate = {}

    try:
        input_file = open(filename, 'r')
    except:
        msg = f"Could not open input file ({filename}). Can not continue. Exiting"
        logger.error(msg, exc_info=True)
        raise common.IngeniumLibError(msg)

    lines = input_file.read().splitlines()

    for line in lines:
        versions = []
        # Split by '#' to allow for commenting and then by comments
        segs = line.split('#')[0].split(',')
        procedure_id = segs[0].strip()
        for seg in segs[1:]:
            version = seg.strip()
            # Check if any versions were repeated
            if version not in versions:
                versions.append(version)

        # Make sure the procedure id is a real id (vs. empty line etc.)
        if 'procedure' not in procedure_id:
            continue

        # If the procedure-id has already been found merge the version information
        if to_migrate.get(procedure_id):
            merged_versions = list(set(to_migrate[procedure_id]+versions))
            to_migrate[procedure_id] = merged_versions
        else:
            to_migrate[procedure_id] = versions

    return to_migrate


def compare_procedures(source, destination, migrate_input, inputs):
    """
    This function looks at the procedures in the source, the destination, and the migrate list.

    It will check:
        - If there are procedures or version that are in the migrate list but not in the source (abort)
        - If there are versions that are in the migrate list but are not released (warn / optionally halt)
        - If there are difference in versions available from source -> destination (queue for migrate)
        - If there are no differences - log (info)

    As the import will be performed at the procedure level all versions specified in the migrate import will be included.

    Parameters
    ----------
    source: dict
        Dictionary (indexed by procedure_id) of dictionary of versions (indexed by version #)
    destination: dict
        Dictionary (indexed by procedure_id) of dictionary of versions (indexed by version #)
    migrate_input: dict
        Dictionary (indexed by procedure_id) of a list of versions to migrate
    inputs: object
        Argparse object with the inputs

    Returns
    -------
    procedures_to_migrate: dict
        Dictionary (indexed by procedure_id) of a list of versions to migrate
    """

    procedures_to_migrate = {}

    for proc_id, versions in migrate_input.items():
        # If the source exists
        if source.get(proc_id):
            # Check that the versions exist and are released
            for version in versions:
                if not source[proc_id].get(version):
                    msg = f"{proc_id} ({version}) can not be located in the Ingenium Source. Can not continue - exiting."
                    logger.error(msg)
                    raise common.IngeniumLibError(msg)

                if source[proc_id].get(version)['status'] != 'RELEASED':
                    msg = f"{proc_id} ({version}) status is NOT RELEASED (status: {source[proc_id].get(version)['status']} / Release Id: {source[proc_id].get(version)['release_id']})."
                    logger.warning(msg)
                    if not inputs.ignore_warnings:
                        msg = 'Warnings not ignored. Halting'
                        logger.error(msg)
                        raise common.IngeniumLibError(msg)
        else:
            msg = f"Procedure ID: {proc_id} can not be located in the Ingenium Source. Can not continue - exiting."
            logger.error(msg)
            raise common.IngeniumLibError(msg)

        # If the procedure exists
        if destination.get(proc_id):
            # Check if the destination has all the versions (if not add the version to the migration list)
            versions_to_migrate = []
            for version in versions:
                # If the version is not present in the destination server - queue for migration
                if not destination[proc_id].get(version):
                    msg = f"Procedure: {proc_id} , Version: {version} not located on the destination server. Queuing for migrate."
                    logger.info(msg)
                    versions_to_migrate.append(version)
                # Or if the "--force" option was selected - queue it regarding of the destination
                elif inputs.force:
                    msg = f"Procedure: {proc_id} , Version: {version} located on the destination server. Force option selected. Queuing for migration."
                    logger.info(msg)
                    versions_to_migrate.append(version)

            # Now add all versions to migrate
            procedures_to_migrate[proc_id] = versions_to_migrate

        # If the procedure is not on the destination queue all versions for migration
        else:
            procedures_to_migrate[proc_id] = versions
            msg = f"Procedure: {proc_id} not located on on the destination server. Queuing for migrate."
            logger.info(msg)

    return procedures_to_migrate


def migrate_procedures(inputs, procedures_to_migrate, username, password):
    """
    This function exports a list of procedures from the source and the imports them to the destination

    Parameters
    ----------
    inputs: object
        Argparse input object
    procedures_to_migrate: dict
        Dictionary (indexed by procedure_id) of a list of versions to migrate
    username: str
        username (to log back into the source and destination)
    password: str
        Password (to log back into the source and destination)

    Returns
    -------
    """

    # Create a temporary directory to save the execution tar.gz files
    tmp_folder = 'procedure_migrate_tmp_' + datetime.datetime.strftime(datetime.datetime.now(datetime.timezone.utc), '%Y_%m_%d_%H%M%S%f')

    save_directory = posixpath.join(inputs.temp_dir, tmp_folder)

    try:
        os.mkdir(save_directory)
    except:
        msg = f"Could not create temp directory: {save_directory}"
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    # Login to the source server and export everything
    login = common.authenticate(inputs.source_server, username=username, password=password, force=True, rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.source_server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    msg = f"Exporting {len(procedures_to_migrate)} procedures from: {inputs.source_server}"
    logger.info(msg)

    files_to_import = []

    for procedure, versions in procedures_to_migrate.items():
        for version in versions:
            filename = f"{procedure}_v{version}.tar.gz"
            file_path = posixpath.join(save_directory, filename)
            msg = f"Exporting procedure/version from: {inputs.source_server} to {file_path}"
            logger.info(msg)
            export_procedure_version(inputs.source_server, procedure, version, file_path)
            files_to_import.append(file_path)

    # Login to the destination server and import everything
    login = common.authenticate(inputs.destination_server, username=username, password=password, force=True, rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.destination_server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    msg = f"Importing {len(procedures_to_migrate)} procedures to: {inputs.destination_server}"
    logger.info(msg)

    for idx, file in enumerate(files_to_import):
        msg = f"Importing {file} to {inputs.destination_server}. ({idx+1} / {len(files_to_import)})"
        logger.info(msg)
        results = import_procedure_versions(inputs.destination_server, file)
        msg = f"Successfully imported: {results['procedure_info'].get('procedure_id')} ({results['version_infos'][0].get('version')}) to {inputs.destination_server}"
        logger.info(msg)


def update_input_for_released(migrate_input, source_procedures):
    """
    This function updates the migrate_input data by replacing "Released" with the versions that are actually released

    Parameters
    ----------
    migrate_input: dict
        Dictionary (indexed by procedure id) of a list of versions to migrate (Updated in place)
    source_procedures: dict
        Dictionary (indexed by procedure_id) of dictionary of versions (indexed by version #)

    Returns
    -------
    """



    # Step through the inputs and look for "RELEASED"
    for procedure, versions in migrate_input.items():
        if 'RELEASED' in versions:
            released_versions = []
            # Check if the procedure exists
            if source_procedures.get(procedure):
                # Then look at the source for "status" == "RELEASED"
                for source_ver in source_procedures.get(procedure):
                    if source_procedures[procedure][source_ver].get('status') == 'RELEASED':
                        released_versions.append(source_ver)
                # Now remove the 'Released' from the versions and merge the lists
                versions.pop(versions.index('RELEASED'))
                msg = f"Found {len(released_versions)} released versions for Procedure: {procedure}. Adding them ({released_versions}) to the list."
                logger.info(msg)
                migrate_input[procedure] = list(set(versions + released_versions))
            else:
                msg = f"Procedure ID: {procedure} can not be located in the Ingenium Source. Can not continue - exiting."
                logger.error(msg)
                raise common.IngeniumLibError(msg)


##################################################### Main ###########################################################


def main(args=[]):
    """
    This is the main function of the Ingenium Migrate Procedures script

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

    # Read external file to build a list of procedures/versions to migrate
    migrate_input = read_migrate_input(inputs.procedures_to_migrate)

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

    logger.info(f"Migrating Procedures ({len(migrate_input)}) from: {inputs.source_server} to: {inputs.destination_server} - Force Enabled: {inputs.force}, Ignore Warning: {inputs.ignore_warnings}")

    if inputs.rsa:
        pw_prompt = f"Enter RSA Passcode for {username}:"
    else:
        pw_prompt = f"Enter LDAP Password for {username}:"

    # Need to capture the password separately from common.authenticate as the script needs to authenticate to two
    # different servers
    password = getpass.getpass(pw_prompt)

    # Login to the source server
    login = common.authenticate(inputs.source_server, username=username, password=password, force=True, rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.source_server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    # Need to query the source information for the procedures flagged for migratation
    source_procedures = query_proc_ver(inputs.source_server, migrate_input)

    update_input_for_released(migrate_input, source_procedures)

    # And again for the destination server
    logger.info(f"Querying list of procedure/versions from: {inputs.destination_server}")

    # Login to the destination server
    login = common.authenticate(inputs.destination_server, username=username, password=password, force=True, rsa=inputs.rsa)

    if not login:
        msg = f"Failure to Login to: {inputs.destination_server} - Can not proceed. Exiting."
        logger.error(msg)
        raise common.IngeniumLibError(msg)

    destination_procedures = query_proc_ver(inputs.destination_server, migrate_input)


    # Compare source and destination to determine what needs to be exported/imported
    procedures_to_migrate = compare_procedures(source_procedures,
                                            destination_procedures,
                                            migrate_input,
                                            inputs)

    # Get total counts
    versions_to_migrate = 0
    for procedure, versions in procedures_to_migrate.items():
        for version in versions:
            versions_to_migrate = versions_to_migrate + 1

    # Now for each procedure to migrate - export it and import it
    logger.info(f"Migrating: {len(procedures_to_migrate)} procedures and {versions_to_migrate} versions. From: {inputs.source_server} To: {inputs.destination_server}.")

    migrate_procedures(inputs, procedures_to_migrate, username, password)

    logger.info(f"Migration of {len(procedures_to_migrate)} procedures and {versions_to_migrate} versions successful. From: {inputs.source_server} To: {inputs.destination_server}")


if __name__ == '__main__':
    try:
        main()
    except common.IngeniumLibError:
        logger.error("Ingenium Migrate Procedures encountered an error and needs to exit. Please check the log messages for the source of the error.")
