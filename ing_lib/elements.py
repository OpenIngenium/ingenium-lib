"""
This library parses Ingenium elements (procedures and as-run executions) into objects
that contain a text representation (print_format) suitable for reports and spreadsheets.

Authors:
    * Chris Swan

"""

##################################################################### Imports
from ing_lib.logs import get_logger

############################################################# Classes

logger = get_logger(__name__)


class IngeniumElement(object):
    def __init__(self, data):
        """
        This class parses all Ingenium Elements

        Parameters
        ----------
        data
            The raw Ingenium element
        """

        self.title = data['title']
        self.number = data['number']
        self.description = data['description']
        self.procedure_title = data['procedure_title']
        self.procedure_id = data['procedure_id']
        self.execution_id = data['execution_id']
        self.conversations = data['conversations']
        self.tags = data['tag_ids']
        self.run_for_score = data['run_for_score']
        self.elem_id = data['elem_id']
        self.procedure_modification = data['procedure_modification']
        self.procedure_modification_status = data['procedure_modification_status']

        # self.executable = data['executable']
        self.elem_type = data['elem_type']
        if data['elem_type'] == "STEP":
            self.step = True
        else:
            self.step = False
        if self.step:
            self.step_type = data['step_type']
        else:
            self.step_type = False


class ProcedureStep(IngeniumElement):
    def __init__(self, data, state):
        """
        This class refines Ingenium Elements for "ProcedureSteps"

        Parameters
        ----------
        data
            Ingenium Element
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """
        # Invoke the parent element
        super().__init__(data)

        # Get the Inputs
        if state == 'procedure':
            self.inputs = data['authoring_user_input']
            format_string = "Reference Procedure: %s (%s) Version: %s" \
                            % (self.inputs['reference_procedure_title'],
                               self.inputs['reference_procedure_id'],
                               self.inputs['reference_procedure_version'])
        elif state == 'as-run':
            self.inputs = data['execution_user_input']
            format_string = "Reference Procedure: %s (%s) Version: %s R4S: %s" \
                            % (self.inputs['reference_procedure_title'],
                               self.inputs['reference_procedure_id'],
                               self.inputs['reference_procedure_version'],
                               self.inputs['run_for_score'])

        self.tag_selections = self.inputs['tag_selections']
        self.elements = self.inputs['elements']
        self.print_format = format_string.rstrip()


class IngeniumStep(IngeniumElement):
    def __init__(self, data):
        """
        This Class refines the IngeniumElement Class for Ingenium Elements that are Executable Steps

        Parameters
        ----------
        data
            Ingenium Element Object
        """
        # Invoke the parent element
        super().__init__(data)

        # Get the Inputs
        self.authoring_user_input = data['authoring_user_input']
        self.execution_user_input = data['execution_user_input']
        self.meta_data = data['execution']['meta_data']
        self.results = data['execution']['results']


class VIDeclareStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the VERIFICATION_ITEM step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        vis = []
        format_string = ""
        if state == "procedure":
            vis = self.execution_user_input['vis']
        elif state == "as-run":
            vis = self.execution_user_input['vis']
        for vi in vis:
            string = "%s:%s - %s \n" % (vi['vi_type'], vi['vi_id'], vi['vi_name'])
            format_string = format_string + string

        self.print_format = format_string.rstrip()


class VIStatusStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class parses the VERIFICATION_ITEM_STATUS step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """
        # Invoke the parent element
        super().__init__(data)

        format_string = "The Verification Status of the following vis: \n"
        if state == "procedure":
            vis = self.authoring_user_input['vis']
            steps = self.authoring_user_input['steps']
        elif state == "as-run":
            vis = self.results['vis']
            steps = self.results['steps']

        for vi in vis:
            string = "%s:%s - %s \n" % (vi['vi_type'], vi['vi_id'], vi['vi_name'])
            format_string = format_string + string

        string = "Are verified by the following steps: \n"

        for step in steps:
            if state == 'procedure':
                string = "%s %s \n" % (step['number'], step['title'])
            elif state == 'as-run':
                string = "%s %s  Result: %s \n" % (step['number'], step['title'], step['status'])
            format_string = format_string + string

        self.print_format = format_string.rstrip()


class GetConfigStep(IngeniumStep):

    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the GET_CONFIG step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """
        # Invoke the parent element
        super().__init__(data)

        format_string = 'Get configurations for the following elements on the venue: \n'
        if state == "procedure":
            if self.authoring_user_input['get_all']:
                format_string = format_string + "All Elements"
            else:
                venue_config_items = self.authoring_user_input['entries']
                for vc in venue_config_items:
                    string = "%s \n" % vc['config_elem_name']
                    format_string = format_string + string
        elif state == 'as-run':
            if self.execution_user_input['get_all']:
                format_string = format_string + "All Elements \n"
            venue_config_items = self.results['entries']
            for vc in venue_config_items:
                string = "Name: %s Type: %s Status: %s Serial: %s\n" \
                         % (vc['config_elem_name'], vc['type'], vc['status'], vc['serial'])
                format_string = format_string + string

        self.print_format = format_string.rstrip()


class UpdateConfigStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the UPDATE_CONFIG step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """
        # Invoke the parent element
        super().__init__(data)

        format_string = "Update venue configuration for the following elements: \n"

        if state == 'procedure':
            config_items = self.authoring_user_input['entries']
            serial = 'serial'
        elif state == 'as-run':
            config_items = self.results['entries']
            serial = 'serial_number'

        for config_item in config_items:
            string = "Element: %s, Type: %s, Status: %s, Serial: %s, Notes: %s \n" % (config_item['config_elem_name'],
                                                                                      config_item['type'],
                                                                                      config_item['status'],
                                                                                      config_item['serial'],
                                                                                      config_item['notes'],)
            format_string = format_string + string

        self.print_format = format_string.rstrip()


class CheckConfigStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the CHECK_CONFIG step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        format_string = "Checking venue configuration for the following elements: \n"

        if state == 'procedure':
            config_items = self.authoring_user_input['entries']
            for config_item in config_items:
                string = "%s %s \n" % (config_item['config_elem_name'],
                                       VerificationCondition(config_item['field_name'],
                                                             config_item['verification_condition'],
                                                             [config_item['verification_value']]).printformat)
                format_string = format_string + string
        elif state == 'as-run':
            config_items = self.results['entries']
            for config_item in config_items:
                string = "%s %s Results: %s Status: %s \n" % (config_item['config_elem_name'],
                                                              VerificationCondition(
                                                                  config_item['field_name'],
                                                                  config_item['verification_condition'],
                                                                  [config_item['verification_value']]).printformat,
                                                              config_item['actual_value'],
                                                              config_item['verification_status'])
                format_string = format_string + string

        self.print_format = format_string.rstrip()


class VerificationCondition:
    def __init__(self, value, condition, verification_values):
        """
        This class translates the various Ingenium Verification Conditions into text

        Parameters
        ----------
        value
            The value to compare against
        condition
            The condition to evaluate against
        verification_values
            The verification values (which vary per the condition)
        """
        try:
            if condition == "EQUAL":
                self.printformat = "%s = %s" % (value, verification_values[0])
            elif condition == "NOT_EQUAL":
                self.printformat = "%s != %s" % (value, verification_values[0])
            elif condition == "RECORD":
                self.printformat = "Record: %s" % value
            elif condition == "GREATER_THAN":
                self.printformat = "%s > %s" % (value, verification_values[0])
            elif condition == "LESS_THAN":
                self.printformat = "%s < %s" % (value, verification_values[0])
            elif condition == "GREATER_THAN_OR_EQUAL":
                self.printformat = "%s >= %s" % (value, verification_values[0])
            elif condition == "LESS_THAN_OR_EQUAL":
                self.printformat = "%s <= %s" % (value, verification_values[0])
            elif condition == "NOT_PRESENT":
                self.printformat = "%s Not Present" % value
            elif condition == "CONTAINS":
                self.printformat = "%s Contains %s" % (value, verification_values[0])
            elif condition == "INCLUSIVE_RANGE":
                self.printformat = "%s <= %s <= %s" % (verification_values[0], value, verification_values[1])
            elif condition == "EXCLUSIVE_RANGE":
                self.printformat = "%s < %s < %s" % (verification_values[0], value, verification_values[1])
        except IndexError:
            self.printformat = "Missing predicts"


class ManualConfig(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the MANUAL_CONFIG step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """
        # Invoke the parent element
        super().__init__(data)

        if state == 'procedure':
            format_string = 'fsw_dictionary: \nfsw_version: \ngds_version: \nsse_dictionary: \nsse_version: \n'
        elif state == 'as-run':
            format_string = 'fsw_dictionary: %s \nfsw_version: %s\ngds_version: %s\nsse_dictionary: %s\nsse_version: %s \n' \
                            % (self.results['fsw_dictionary'],
                               self.results['fsw_version'],
                               self.results['gds_version'],
                               self.results['sse_dictionary'],
                               self.results['sse_version'])

        self.print_format = format_string.rstrip()


class QueryEVRStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the QUERY_EVR step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """
        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            value = "EVRS"
        if state == "as-run":
            inputs = self.results
            value = inputs['total_count']

        if inputs['duration'] == "":
            format_string = "Querying for EVRs between %s and %s via %s \n" % (inputs['start_time'], inputs['end_time'],
                                                                               inputs['data_path'])
        elif inputs['start_time'] == "":
            format_string = "Querying for EVRs ending at %s for %s seconds via %s \n" % (inputs['end_time'],
                                                                                         inputs['duration'],
                                                                                         inputs['data_path'])
        elif inputs['end_time'] == "":
            format_string = "Querying for EVRs starting at %s for %s seconds via %s \n" % (inputs['start_time'],
                                                                                           inputs['duration'],
                                                                                           inputs['data_path'])
        else:
            format_string = "Querying for EVRs starting at %s for %s seconds until %s via %s \n" % (inputs['start_time'],
                                                                                                    inputs['duration'],
                                                                                                    inputs['end_time'],
                                                                                                    inputs['data_path'])

        # Note that Verification Condition takes a list of verification values (hence the list)
        format_string = format_string + "Evaluating the number of EVRs that meet the filter criteria are: %s \n" \
                        % VerificationCondition(value, inputs['verification_condition'],
                                                [inputs['verification_value']]).printformat

        format_string = format_string + "EVR ID: %s EVR Name:%s EVR Level: %s EVR Type: %s EVR Message %s" \
                        % (inputs['evr_id'],
                           inputs['evr_name'],
                           inputs['evr_level'],
                           inputs['evr_type'],
                           inputs['message_filter'])

        self.print_format = format_string.rstrip()


class WaitEVRStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the WAIT_EVR step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            evrs = inputs['entries']
        elif state == "as-run":
            inputs = self.execution_user_input
            evrs = self.results['entries']

        format_string = "Waiting for EVRs on %s starting:%s (timeout:%s lookback:%s \n" % (inputs['data_path'],
                                                                                           inputs['start_time'],
                                                                                           inputs['timeout'],
                                                                                           inputs['lookback'])
        for evr in evrs:
            string = "EVR Name: %s EVR ID: %s EVR Type: %s EVR Level:%s EVR Message:%s - %s" \
                     % (evr['evr_name'],
                        evr['evr_id'],
                        evr['evr_type'],
                        evr['evr_level'],
                        evr['message_filter'],
                        evr['verification_condition'])
            if state == 'as-run':
                string = string + " Found: %s EVRs - %s \n" % (evr['total_count'], evr['verification_status'])
            if state == 'procedure':
                string = string + "\n"
            format_string = format_string + string

        self.print_format = format_string.rstrip()


class VerifyEhaStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the VERIFY_EHA step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            channels = inputs['entries']
        elif state == 'as-run':
            inputs = self.execution_user_input
            channels = self.results['entries']

        format_string = "Querying EHA Channels from: %s lookback: %s timeout: %s \n" % (inputs['start_time'],
                                                                                        inputs['lookback'],
                                                                                        inputs['timeout'],)

        for channel in channels:
            channel_name = channel.get('channel_name', 'Not Available')
            if state == 'procedure':
                value = "%s (%s)" % (channel['verify_on'], channel['dn_eu'])
            elif state == 'as-run':
                value = "%s - %s" % (channel['verify_on'], channel['dn_eu'])
            string = "Via: %s - %s (%s) Predict: %s" % (channel['data_path'],
                                                        channel_name,
                                                        channel['channel_id'],
                                                        VerificationCondition(
                                                            value,
                                                            channel['verification_condition'],
                                                            channel['verification_values']).printformat)
            if state == 'procedure':
                string = string + "\n"
            elif state == 'as-run':
                string = string + " Actual: %s - %s \n" % (channel['actual_value'], channel['verification_status'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class WaitEHAStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the WAIT_EHA step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            channels = inputs['entries']
        elif state == 'as-run':
            inputs = self.execution_user_input
            channels = self.results['entries']

        format_string = "Waiting for EHA Channels to match from: %s lookback: %s timeout: %s \n" \
                        % (inputs['start_time'],
                           inputs['lookback'],
                           inputs['timeout'],)

        for channel in channels:
            channel_name = channel.get('channel_name', 'Not Available')

            value = "%s (%s)" % (channel['verify_on'], channel['dn_eu'])
            string = "Via: %s - %s (%s) Predict: %s" % (channel['data_path'],
                                                        channel_name,
                                                        channel['channel_id'],
                                                        VerificationCondition(
                                                            value,
                                                            channel['verification_condition'],
                                                            channel['verification_values']).printformat)
            if state == 'procedure':
                string = string + "\n"
            elif state == 'as-run':
                string = string + " Actual: %s - %s \n" % (channel['actual_value'], channel['verification_status'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class BUS1553Step(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the BUS1553 step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            Bus1553Vars = inputs['entries']
        elif state == 'as-run':
            inputs = self.execution_user_input
            Bus1553Vars = self.results['entries']

        wait_or_verify = ''
        if inputs['verify_wait'] == "VERIFY":
            wait_or_verify = "Verifying"
        elif inputs['verify_wait'] == 'WAIT':
            wait_or_verify = 'Waiting for'

        format_string = "%s 1553 Data Channels from: %s lookback: %s timeout: %s \n" % (wait_or_verify,
                                                                                        inputs['start_time'],
                                                                                        inputs['lookback'],
                                                                                        inputs['timeout'],)

        for Bus1553Var in Bus1553Vars:
            value = "%s (%s)" % (Bus1553Var['verify_on'], Bus1553Var['raw_convert'])
            string = "1553 Var: %s Predict: %s" % (Bus1553Var['bus_1553_var'],
                                                   VerificationCondition(
                                                        value,
                                                        Bus1553Var['verification_condition'],
                                                        Bus1553Var['verification_values']).printformat)

            if state == 'procedure':
                string = string + "\n"
            elif state == 'as-run':
                string = string + " Actual: %s - %s \n" % (Bus1553Var['actual_value'],
                                                           Bus1553Var['verification_status'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class CMDStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the CMD step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            commands = inputs['entries']
        elif state == 'as-run':
            inputs = self.results
            commands = inputs['entries']

        format_string = "Sending commands via: %s \n" % inputs['data_path']

        for command in commands:
            # Grab the string selection if available (otherwise insert the default for pre-R11 procedures)
            if command.get('string_selection'):
                string_selection = command.get('string_selection')
            else:
                string_selection = 'DEFAULT'

            if state == 'procedure':
                string = "Sending: %s (%s) String: %s (timeout: %s, verify:%s) \n" % (command['cmd_string'],
                                                                                      command['hw_fsw'],
                                                                                      string_selection,
                                                                                      command['timeout'],
                                                                                      command['verify'])
            elif state == 'as-run':
                string = "Sending: %s (%s) String: %s (timeout: %s, verify:%s) - Sent: %s (%s) \n" \
                         % (command['cmd_string'],
                            command['hw_fsw'],
                            string_selection,
                            command['timeout'],
                            command['verify'],
                            command['radiated'],
                            command['radiated_time'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class TimeReferenceStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the Time Reference step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
        elif state == 'as-run':
            inputs = self.results

        if state == 'procedure':
            self.print_format = 'Time Reference: %s.' % inputs.get('name')
        elif state == 'as-run':
            self.print_format = 'Time Reference: %s recorded at: %s' % (inputs.get('name'),
                                                                        inputs.get('time_value'))


class SSECMDStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the SSECMD step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            commands = inputs['entries']
        elif state == 'as-run':
            inputs = self.results
            commands = inputs['entries']

        format_string = "Sending SSE commands via: %s \n" % inputs['data_path']

        for command in commands:
            if state == 'procedure':
                string = "Sending: %s (timeout: %s) \n" % (command['cmd_string'], command['timeout'])
            elif state == 'as-run':
                string = "Sending: %s (timeout: %s) - Sent: %s (%s) \n" % (command['cmd_string'],
                                                                           command['timeout'],
                                                                           command['radiated'],
                                                                           command['radiated_time'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class CMDFileStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the CMDFile step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            files = inputs['entries']

        elif state == 'as-run':
            inputs = self.results
            files = inputs['entries']

        format_string = "Sending Files via: %s \n" % inputs['data_path']

        for file in files:
            # Grab the string selection if available (otherwise insert the default for pre-R11 procedures)
            if file.get('string_selection'):
                string_selection = file.get('string_selection')
            else:
                string_selection = 'DEFAULT'

            if state == 'procedure':
                string = "Sending: %s to %s (string: %s filetype: %s timeout: %s, overwrite: %s, verify: %s) \n" \
                         % (file['file_path'],
                            file['onboard_path'],
                            string_selection,
                            file['file_type'],
                            file['timeout'],
                            file['overwrite'],
                            file['verify'])
            elif state == 'as-run':
                string = "Sending: %s to %s (string: %s filetype: %s timeout: %s, overwrite: %s, verify: %s)- Sent: %s (%s) \n" \
                         % (file['file_path'],
                            file['onboard_path'],
                            string_selection,
                            file['file_type'],
                            file['timeout'],
                            file['overwrite'],
                            file['verify'],
                            file['radiated'],
                            file['radiated_time'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class CMDSCMFStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the CMDSCMF step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            scmfs = inputs['entries']
        elif state == 'as-run':
            inputs = self.results
            scmfs = inputs['entries']

        format_string = "Sending SCMFs via: %s \n" % inputs['data_path']

        for scmf in scmfs:
            if state == 'procedure':
                string = "Sending: %s (filetype: %s timeout: %s, disable_checks: %s, verify: %s) \n" % (
                    scmf['file_path'],
                    scmf['file_type'],
                    scmf['timeout'],
                    scmf['disable_checks'],
                    scmf['verify'])
            elif state == 'as-run':
                string = "Sending: %s (filetype: %s timeout: %s, disable_checks: %s, verify: %s) - Sent: %s (%s) \n" % (
                    scmf['file_path'],
                    scmf['file_type'],
                    scmf['timeout'],
                    scmf['disable_checks'],
                    scmf['verify'],
                    scmf['radiated'],
                    scmf['radiated_time']
                )

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class ManualGDSStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the MANUAL_GDS step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
        elif state == "as-run":
            inputs = self.results

        # Grab the string selection if available (otherwise insert the default for pre-R11 procedures)
        if inputs.get('default_cmd_string'):
            default_cmd_string = inputs.get('default_cmd_string')
        else:
            default_cmd_string = 'AB'

        format_string = "Initializing MTAK with default command string: %s and the following datapaths: \n" \
                        % default_cmd_string

        datapaths = inputs['entries']

        for datapath in datapaths:
            if state == 'procedure':
                string = "Initializing datapath: %s \n" % (datapath['data_path'])
            elif state == 'as-run':
                string = "Initializing datapath: %s to session:%s \n" % (datapath['data_path'],
                                                                         datapath['session_id'])
            format_string = format_string + string

        self.print_format = format_string.rstrip()


class ManualInputStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the MANUAL_INPUT step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
        elif state == 'as-run':
            inputs = self.results
        format_string = "Checking the following Manual Inputs: \n"

        manual_inputs = inputs['entries']

        for manual_input in manual_inputs:
            if state == 'procedure':
                value = "%s" % (manual_input.get('verify_on'))
            elif state == 'as-run':
                value = "%s" % (manual_input.get('verify_on'))

            string = "Variable: %s Predict: %s" % (manual_input['name'],
                                                   VerificationCondition(
                                                       value,
                                                       manual_input.get('verification_condition'),
                                                       manual_input.get('verification_values')).printformat)
            if state == 'procedure':
                string = string + " \n"
            elif state == 'as-run':
                string = string + " Actual: %s - %s \n" % (manual_input.get('actual_value'),
                                                           manual_input.get('verification_status'))
            format_string = format_string + string

        self.print_format = format_string.rstrip()


class ManualVerificationStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the MANUAL_VERIFICATION step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        IngeniumStep.__init__(self, data)

        if state == "procedure":
            inputs = self.authoring_user_input
        elif state == 'as-run':
            inputs = self.results

        format_string = "Confirm the following is completed/true: \n"
        if state == "procedure":
            format_string = format_string + inputs['verification_text']
        elif state == 'as-run':
            format_string = format_string + inputs['verification_text'] + "\n Status: %s" % \
                            inputs['verification_status']

        self.print_format = format_string.rstrip()


class EnvironmentalStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the ENVIRONMENT step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        format_string = ""

        if state == "procedure":
            inputs = self.authoring_user_input
            string = "Checking Temperature : %s \n" % (VerificationCondition(
                                                        inputs['temperature']['verify_on'],
                                                        inputs['temperature']['verification_condition'],
                                                        inputs['temperature']['verification_values']).printformat)
            format_string = format_string + string
            string = "Checking Humidity : %s \n" % (VerificationCondition(
                                                    inputs['humidity']['verify_on'],
                                                    inputs['humidity']['verification_condition'],
                                                    inputs['humidity']['verification_values']).printformat)
            format_string = format_string + string
        elif state == "as-run":
            inputs = self.results
            string = "Checking Temperature : %s - Status: %s \n" % \
                                            (VerificationCondition("%s (%s)"
                                                % (inputs['temperature']['actual_value'],
                                                   inputs['temperature']['verify_on']),
                                                   inputs['temperature']['verification_condition'],
                                                   inputs['temperature']['verification_values']).printformat,
                                                   inputs['temperature']['verification_status'])
            format_string = format_string + string
            string = "Checking Humidity : %s - Status: %s \n" % \
                                            (VerificationCondition("%s (%s)"
                                                % (inputs['humidity']['actual_value'],
                                                   inputs['humidity']['verify_on']),
                                                   inputs['humidity']['verification_condition'],
                                                   inputs['humidity']['verification_values']).printformat,
                                                   inputs['temperature']['verification_status'])
            format_string = format_string + string

        self.print_format = format_string.rstrip()


class ManualEIPStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the EIP step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        format_string = "Electrical Integration Procedure Step \n"

        if state == "procedure":
            inputs = self.authoring_user_input
            for entry in inputs['entries']:
                format_string = format_string + "Signal: %s ICDS: %s from: %s to: %s Predict: %s < Value (%s) < %s \n" % (
                entry['signal_name'],
                entry['icds'],
                entry['from'],
                entry['to'],
                entry['min_value'],
                entry['unit'],
                entry['max_value'])
        elif state == "as-run":
            inputs = self.results
            for entry in inputs['entries']:
                format_string = format_string + "Signal: %s ICDS: %s from: %s to: %s Actual: %s < %s (%s) < %s - %s \n" % (
                entry.get('signal_name'),
                entry.get('icds'),
                entry.get('from'),
                entry.get('to'),
                entry.get('min_value'),
                entry.get('actual_value'),
                entry.get('unit'),
                entry.get('max_value'),
                entry.get('verification_status'))

        self.print_format = format_string.rstrip()


class CustomScriptStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the Customer Script step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            format_string = "Running Custom Script: %s (timeout: %s) \n" % (inputs['script_name'], inputs['timeout'])
            format_string = format_string + "Script Path: %s \n" % (inputs['script_path'])
        elif state == "as-run":
            inputs = self.results
            # Custom scripts populate their own text representation in the output_summary field.
            # Use it when available, otherwise fall back to the generated format.
            if inputs.get('output_summary'):
                self.print_format = inputs['output_summary'].rstrip()
                return
            format_string = "Ran Custom Script: %s (timeout: %s) Status: %s \n" % (inputs['script_name'],
                                                                                   inputs['timeout'],
                                                                                   inputs['custom_script_status'])
            format_string = format_string + "Script Path: %s \n" % (inputs['script_path'])

        self.print_format = format_string.rstrip()


class WaitStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the WAIT step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
        elif state == 'as-run':
            inputs = self.results
        if inputs['wait_type'] == "DURATION":
            format_string = "Waiting for %s seconds" % inputs['time_value']
        elif inputs['wait_type'] == "UNTIL":
            format_string = "Waiting until: %s" % inputs['time_value']

        self.print_format = format_string.rstrip()


class ListDataProductStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the LIST_DP step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            products = inputs['entries']
        elif state == 'as-run':
            inputs = self.execution_user_input
            products = self.results['entries']

        if inputs['duration'] == "":
            format_string = "Querying for Data Products between %s and %s via %s \n" % (inputs['start_time'],
                                                                                        inputs['end_time'],
                                                                                        inputs['data_path'])
        elif inputs['start_time'] == "":
            format_string = "Querying for Data Products ending at %s for %s seconds via %s \n" % (inputs['end_time'],
                                                                                                  inputs['duration'],
                                                                                                  inputs['data_path'])
        elif inputs['end_time'] == "":
            format_string = "Querying for Data Products starting at %s for %s seconds via %s \n" % (
            inputs['start_time'],
            inputs['duration'],
            inputs['data_path'])
        else:
            format_string = "Issue with parsing step: %s" % inputs

        # Note that Verification Condition takes a list of verification values (hence the list)
        for product in products:
            if state == 'procedure':
                string = "Looking for APID: %s, Criteria: %s \n" % \
                         (product['apid'],
                          VerificationCondition('Value',
                                                product['verification_condition'],
                                                [product['verification_value']]).printformat)
            elif state == 'as-run':
                string = "Looking for APID: %s, Criteria: %s, Status: %s \n" % \
                         (product['apid'],
                          VerificationCondition(product['total_count'],
                                                product['verification_condition'],
                                                [product['verification_value']]).printformat,
                                                product['verification_status'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


class WaitDataProductStep(IngeniumStep):
    def __init__(self, data, state):
        """
        This class refines the IngeniumStep class to specifically parse the WAIT_DP step

        Parameters
        ----------
        data
            Ingenium Step Object
        state
            Whether to parse the procedure version ('procedure') or the executed version ('as-run')
        """

        # Invoke the parent element
        super().__init__(data)

        if state == "procedure":
            inputs = self.authoring_user_input
            products = inputs['entries']
        elif state == 'as-run':
            inputs = self.execution_user_input
            products = self.results['entries']

        format_string = "Waiting for Data Products via: %s (from: %s, timeout: %s)\n" % (inputs['data_path'],
                                                                                         inputs['start_time'],
                                                                                         inputs['timeout'])

        for product in products:
            if state == 'procedure':
                string = "Waiting for APID: %s, Criteria: %s \n" \
                         % (product['apid'],
                            VerificationCondition('Value',
                                                  product['verification_condition'],
                                                  [product['verification_value']]).printformat)
            elif state == 'as-run':
                string = "Waiting for APID: %s, Criteria: %s, Status: %s \n" \
                         % (product['apid'],
                            VerificationCondition(product['total_count'],
                                                  product['verification_condition'],
                                                  [product['verification_value']]).printformat,
                                                  product['verification_status'])

            format_string = format_string + string

        self.print_format = format_string.rstrip()


def IngeniumStepParser(step, state):
    """
    This function determines the step type of a paticular step and then creates the appropriate object

    Parameters
    ----------
    step
        JSON definition of an Ingenium Step
    state
        Whether to parse the procedure version ('procedure') or the executed version ('as-run')
    """

    step_data = IngeniumElement(step)

    if step_data.elem_type:
        if step_data.elem_type == "PROCEDURE_SECTION":
            step_data = ProcedureStep(step, state)
        if step_data.elem_type == "STEP":
            if step_data.step_type == 'VERIFICATION_ITEM':
                step_data = VIDeclareStep(step, state)
            elif step_data.step_type == 'VERIFICATION_ITEM_STATUS':
                step_data = VIStatusStep(step, state)
            elif step_data.step_type == 'VENUE_CONFIG_GET':
                step_data = GetConfigStep(step, state)
            elif step_data.step_type == 'VENUE_CONFIG_MANUAL':
                step_data = ManualConfig(step, state)
            elif step_data.step_type == 'VENUE_CONFIG_UPDATE':
                step_data = UpdateConfigStep(step, state)
            elif step_data.step_type == 'VENUE_CONFIG_CHECK':
                step_data = CheckConfigStep(step, state)
            elif step_data.step_type == 'VERIFY_EHA':
                step_data = VerifyEhaStep(step, state)
            elif step_data.step_type == 'BUS_1553':
                step_data = BUS1553Step(step, state)
            elif step_data.step_type == 'WAIT_EHA':
                step_data = WaitEHAStep(step, state)
            elif step_data.step_type == 'WAIT_EVR':
                step_data = WaitEVRStep(step, state)
            elif step_data.step_type == 'QUERY_EVR':
                step_data = QueryEVRStep(step, state)
            elif step_data.step_type == 'CMD':
                step_data = CMDStep(step, state)
            elif step_data.step_type == 'CMD_FILE':
                step_data = CMDFileStep(step, state)
            elif step_data.step_type == 'CMD_SSE':
                step_data = SSECMDStep(step, state)
            elif step_data.step_type == 'CMD_SCMF':
                step_data = CMDSCMFStep(step, state)
            elif step_data.step_type == 'GDS_MANUAL':
                step_data = ManualGDSStep(step, state)
            elif step_data.step_type == 'MANUAL_INPUT':
                step_data = ManualInputStep(step, state)
            elif step_data.step_type == 'MANUAL_VERIFICATION':
                step_data = ManualVerificationStep(step, state)
            elif step_data.step_type == 'ENVIRONMENT_MANUAL':
                step_data = EnvironmentalStep(step, state)
            elif step_data.step_type == 'WAIT':
                step_data = WaitStep(step, state)
            elif step_data.step_type == 'MANUAL_EIP':
                step_data = ManualEIPStep(step, state)
            elif step_data.step_type == 'CUSTOM_SCRIPT':
                step_data = CustomScriptStep(step, state)
            elif step_data.step_type == 'LIST_DATA_PRODUCTS':
                step_data = ListDataProductStep(step, state)
            elif step_data.step_type == 'WAIT_DATA_PRODUCTS':
                step_data = WaitDataProductStep(step, state)
            elif step_data.step_type == 'TIME_REFERENCE':
                step_data = TimeReferenceStep(step, state)

    return step_data


def parse_ingenium_steps(data, state):
    """
    This function parses a JSON response from Ingenium into a list of Ingenium Step Objects.

    Parameters
    ----------
    data
        JSON object containing detailed procedure or as-run steps
    state
        Whether the data is a "procedure" or an executed "as-run"

    Returns
    -------
        List of steps
    """

    steps = []

    for step in data:
        step_data = IngeniumStepParser(step, state)
        steps.append(step_data)

    return steps
