# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from tasks.ActivityShikigami.activities.normal import NormalClimbAct


class ScriptTask(NormalClimbAct):
    """
    更新前请先看 ./README.md
    """
    pass


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()