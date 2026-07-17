# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.exception import TaskEnd
from module.logger import logger

from tasks.GameUi.game_ui import GameUi


class ScriptTask(GameUi):
    def run(self):
        logger.info('SoulsTidy task has been migrated to DailyTrifles, skip execution')
        self.set_next_run(task='SoulsTidy', success=True, finish=True)
        raise TaskEnd('SoulsTidy')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    #t.greed_maneki()
    t.run()


