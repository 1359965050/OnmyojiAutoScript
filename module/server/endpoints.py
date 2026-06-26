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


class ToolEndpoints:
    ANNOTATOR = '/annotator'

    # Session
    ANNOTATOR_SESSION = '/annotator/api/session'
    ANNOTATOR_SESSION_DETAIL = '/annotator/api/session/{session_id}'
    ANNOTATOR_SESSION_CLOSE_BEACON = '/annotator/api/session/{session_id}/close'

    # Images
    ANNOTATOR_IMAGES_UPLOAD = '/annotator/api/images/upload'
    ANNOTATOR_IMAGES = '/annotator/api/images'
    ANNOTATOR_IMAGE_FILE = '/annotator/api/images/{session_id}/{image_id}'
    ANNOTATOR_IMAGES_DELETE_BATCH = '/annotator/api/images/delete-batch'
    ANNOTATOR_IMAGES_CLEAR = '/annotator/api/images/clear'

    # Configs / tasks
    ANNOTATOR_CONFIGS = '/annotator/api/configs'
    ANNOTATOR_TASKS = '/annotator/api/tasks'
    ANNOTATOR_TASK_JSON_FILES = '/annotator/api/tasks/{task_name}/json'

    # Rules
    ANNOTATOR_RULE_SCHEMA = '/annotator/api/rules/schema'
    ANNOTATOR_RULE_LOAD = '/annotator/api/rules/load'
    ANNOTATOR_RULE_SOURCE = '/annotator/api/rules/source'
    ANNOTATOR_RULE_SOURCE_CREATE = '/annotator/api/rules/source/create'
    ANNOTATOR_RULE_SOURCE_DELETE = '/annotator/api/rules/source/delete'
    ANNOTATOR_RULE_IMAGE_PREVIEW = '/annotator/api/rules/image-preview'
    ANNOTATOR_RULE_IMAGE_DELETE = '/annotator/api/rules/image/delete'
    ANNOTATOR_RULE_TEST = '/annotator/api/rules/test'
    ANNOTATOR_RULE_SAVE = '/annotator/api/rules/save'

    # Emulator
    ANNOTATOR_EMULATOR_START = '/annotator/api/emulator/start'
    ANNOTATOR_EMULATOR_STOP = '/annotator/api/emulator/stop'
    ANNOTATOR_EMULATOR_STATUS = '/annotator/api/emulator/status'
    ANNOTATOR_EMULATOR_CAPTURE = '/annotator/api/emulator/capture'

    # Misc
    ANNOTATOR_CROP_SAVE = '/annotator/api/images/crop-save'

    # WebSocket
    ANNOTATOR_WS = '/annotator/ws/{session_id}'


class ToolErrorCodes:
    PAGE_NOT_FOUND = 'page_not_found'
    INVALID_SESSION = 'invalid_session'
    EMULATOR_ERROR = 'emulator_error'


class ToolCloseReasons:
    CLIENT_CLOSE = 'client_close'
    PAGEHIDE = 'pagehide'
