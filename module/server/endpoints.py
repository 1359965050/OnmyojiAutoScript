# This Python file uses the following encoding: utf-8
"""
OAS web service endpoint path and API contract constants.
This module contains only pure constants to avoid circular imports.
"""


class HomeEndpoints:
    TEST = '/test'
    HOME_MENU = '/home_menu'
    KILL_SERVER = '/kill_server'
    UPDATE_INFO = '/update_info'
    EXECUTE_UPDATE = '/execute_update'
    CHINESE_TRANSLATE = '/chinese_translate'
    ADDITIONAL_TRANSLATE = '/additional_translate'
    # Currently consumed by the frontend but not implemented on the backend.
    NOTIFY_TEST = '/notify_test'


class ScriptEndpoints:
    TEST = '/test'
    SCRIPT_MENU = '/script_menu'

    # Config management
    CONFIG_LIST = '/config_list'
    CONFIG_COPY = '/config_copy'
    CONFIG_NEW_NAME = '/config_new_name'
    CONFIG_ALL = '/config_all'
    CONFIG = '/config'
    CONFIG_TASK_COPY = '/config/task/copy'
    CONFIG_TASK_GROUP_COPY = '/config/task/group/copy'

    # Script instance management (parameterized)
    SCRIPT_START = '/{script_name}/start'
    SCRIPT_STOP = '/{script_name}/stop'
    SCRIPT_LOGGER_LEVEL = '/{script_name}/logger/level'
    SCRIPT_TASK_ARGS = '/{script_name}/{task}/args'
    SCRIPT_TASK_ARG_VALUE = '/{script_name}/{task}/{group}/{argument}/value'
    SCRIPT_SYNC_NEXT_RUN = '/{script_name}/{task}/sync_next_run'

    # WebSocket
    SCRIPT_WS = '/ws/{script_name}'


class ScriptWsCommands:
    GET_STATE = 'get_state'
    GET_SCHEDULE = 'get_schedule'
    START = 'start'
    STOP = 'stop'


class ScriptValidation:
    VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}


class DateTimeFormats:
    DATETIME = '%Y-%m-%d %H:%M:%S'
    TIME = '%H:%M:%S'


