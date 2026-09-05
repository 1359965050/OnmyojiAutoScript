import os
import re
import typing as t

from module.device.platform2.handlers.base import EmulatorHandler
from module.logger import logger


class BlueStacksHandler(EmulatorHandler):
    BlueStacks5 = 'BlueStacks5'

    @staticmethod
    def type_names() -> list[str]:
        return ['BlueStacks5']

    @staticmethod
    def path_to_type(path: str, exe: str, dir1: str, dir2: str) -> str:
        if exe == 'bluestacks.exe':
            if dir1 in ['bluestacks_nxt', 'bluestacks_nxt_cn']:
                return 'BlueStacks5'
            else:
                # 默认识别为BS5，BS4已停更
                return 'BlueStacks5'
        if exe == 'hd-player.exe':
            if dir1 in ['bluestacks_nxt', 'bluestacks_nxt_cn']:
                return 'BlueStacks5'
            else:
                return 'BlueStacks5'
        return ''

    @staticmethod
    def multi_to_single(exe: str) -> list[str]:
        if 'HD-MultiInstanceManager.exe' in exe:
            return [
                exe.replace('HD-MultiInstanceManager.exe', 'HD-Player.exe'),
                exe.replace('HD-MultiInstanceManager.exe', 'Bluestacks.exe'),
            ]
        return []

    @staticmethod
    def single_to_console(exe: str) -> t.Optional[str]:
        if 'Bluestacks.exe' in exe:
            return exe.replace('Bluestacks.exe', 'bsconsole.exe')
        return None

    def iter_instances(self, emulator) -> t.Iterable:
        from module.device.platform2.emulator_windows import EmulatorInstance

        yield from self._iter_bluestacks5(emulator)

    @staticmethod
    def _iter_bluestacks5(emulator) -> t.Iterable:
        import winreg
        from module.device.platform2.emulator_windows import EmulatorInstance

        folder = None
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt") as reg:
                folder = winreg.QueryValueEx(reg, 'UserDefinedDir')[0]
        except FileNotFoundError:
            logger.debug(r'Registry not found: HKLM\SOFTWARE\BlueStacks_nxt')
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt_cn") as reg:
                folder = winreg.QueryValueEx(reg, 'UserDefinedDir')[0]
        except FileNotFoundError:
            logger.debug(r'Registry not found: HKLM\SOFTWARE\BlueStacks_nxt_cn')
        if not folder:
            return

        try:
            conf_path = os.path.abspath(os.path.join(folder, 'bluestacks.conf')).replace('\\', '/')
            with open(conf_path, encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            return

        emulators = re.findall(r'bst.instance.(\w+).status.adb_port="(\d+)"', content)
        for emu in emulators:
            yield EmulatorInstance(
                serial=f'127.0.0.1:{emu[1]}',
                name=emu[0],
                path=emulator.path,
            )


    def iter_adb_binaries(self, emulator) -> t.Iterable[str]:
        yield from self._iter_common_adb(emulator)

    def build_start_command(self, instance) -> t.Optional[str]:
        exe = instance.emulator.path
        # HD-Player.exe --instance Pie64
        return f'"{exe}" --instance {instance.name}'

    def stop_by_kill(self, instance) -> t.Optional[str]:
        if instance.type == self.BlueStacks5:
            return (
                rf'('
                rf'HD-Player.exe.*"--instance" "{instance.name}"'
                rf')'
            )
        return None
