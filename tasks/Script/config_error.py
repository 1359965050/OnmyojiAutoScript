# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger
from tasks.Component.config_base import MultiLine


class Error(BaseModel):
    handle_error: bool = Field(default=True,
                               description='handle_error_help')
    save_error: bool = Field(default=True,
                             description='')
    screenshot_length: int = Field(
        default=1,
        description='',
        ge=1,
    )
    notify_enable: bool = Field(default=False,
                                description='notify_enable_help')
    notify_config: MultiLine = Field(default='',
                                     description='notify_config_help')


