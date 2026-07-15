# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta

from module.logger import logger
from module.exception import TaskEnd
from tasks.base_task import BaseTask


class ScriptTask(BaseTask):

    def run(self):
        logger.info('Pets task has been migrated to DailyTrifles, skip execution')
        self.set_next_run(task='Pets', success=True, finish=True)
        raise TaskEnd('Pets')
