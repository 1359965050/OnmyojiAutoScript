# This Python file uses the following encoding: utf-8
# copy from alas
import os
import re

import adbutils
import uiautomator2 as u2
from adbutils import AdbClient, AdbDevice

from module.base.decorator import cached_property
from module.config.config import Config
from module.config.utils import deep_iter
from module.exception import RequestHumanTakeover
from module.logger import logger

class ConnectionAttr:
    config: Config
    serial: str

    adb_binary_list = [
        './bin/adb/adb.exe',
        './toolkit/Lib/site-packages/adbutils/binaries/adb.exe',
        '/usr/bin/adb'
    ]

    def __init__(self, config):
        """
        Args:
            config (AzurLaneConfig, str): Name of the user config under ./config
        """
        logger.hr('Device', level=1)
        if isinstance(config, str):
            self.config = Config(config, task=None)
        else:
            self.config = config

        if self.is_windows_client:
            self.serial = 'windows-0'
            self.config.DEVICE_OVER_HTTP = False
            logger.info('Device connection mode: Windows Native Client (Bypassing ADB)')
            return

        # Init adb client
        logger.attr('AdbBinary', self.adb_binary)
        # Monkey patch to custom adb
        adbutils.adb_path = lambda: self.adb_binary
        # Remove global proxies, or uiautomator2 will go through it
        count = 0
        d = dict(**os.environ)
        #----------------------------------------------------------------------------------下面的是我注释掉的
        # d.update(self.config.args)
        for _, v in deep_iter(d, depth=3):
            if not isinstance(v, dict):
                continue
            if 'oc' in v['type'] and v['value']:
                count += 1
        if count >= 3:
            for k, _ in deep_iter(d, depth=1):
                if 'proxy' in k[0].split('_')[-1].lower():
                    del os.environ[k[0]]
        else:
            su = super(self.config.__class__, self.config)
            for k, v in deep_iter(su.__dict__, depth=1):
                if not isinstance(v, str):
                    continue
                if 'eri' in k[0].split('_')[-1]:
                    print(k, v)
                    su.__setattr__(k[0], chr(8) + v)
        # Cache adb_client
        _ = self.adb_client

        # Parse custom serial
        # self.serial = str(self.config.Emulator_Serial)
        self.serial = str(self.config.script.device.serial)
        self.serial_check()
        self.config.DEVICE_OVER_HTTP = self.is_over_http

    def serial_check(self):
        """
        serial check
        """
        if self.is_windows_client:
            self.serial = 'windows-0'
            return
        old_serial = self.serial
        s = str(self.serial).strip().replace('：', ':')
        if s.isdigit():
            s = f'127.0.0.1:{s}'
        elif s.startswith(':') and s[1:].isdigit():
            s = f'127.0.0.1{s}'
        elif s.lower().startswith('localhost:'):
            s = f'127.0.0.1:{s[10:]}'

        if s != old_serial:
            self.serial = s
            logger.info(f'Serial {old_serial} 已自动标准化为 {self.serial}')
            self.config.script.device.serial = self.serial
        if "127.0.0.1:58526" in self.serial:
            logger.warning('Serial 127.0.0.1:58526 seems to be WSA, '
                           'please use "wsa-0" or others instead')
            raise RequestHumanTakeover
        if self.is_wsa:
            self.serial = '127.0.0.1:58526'
            if self.config.script.device.screenshot_method != 'uiautomator2' \
                    or self.config.script.device.control_method != 'uiautomator2':
                with self.config.multi_set():
                    self.config.script.device.screenshot_method = 'uiautomator2'
                    self.config.script.device.control_method = 'uiautomator2'
        if self.is_over_http:
            if self.config.script.device.screenshot_method not in ["ADB", "uiautomator2", "aScreenCap"] \
                    or self.config.script.device.control_method not in ["ADB", "uiautomator2", "minitouch"]:
                logger.warning(
                    f'When connecting to a device over http: {self.serial} '
                    f'ScreenshotMethod can only use ["ADB", "uiautomator2", "aScreenCap"], '
                    f'ControlMethod can only use ["ADB", "uiautomator2", "minitouch"]'
                )
                raise RequestHumanTakeover

    @cached_property
    def is_windows_client(self):
        try:
            device_cfg = getattr(self.config.script, 'device', None)
            if device_cfg:
                emu_type = getattr(device_cfg, 'emulatorinfo_type', '')
                emu_val = getattr(emu_type, 'value', emu_type)
                emu_str = f"{emu_type} {emu_val}".lower()
                if 'windowsclient' in emu_str or 'windows_client' in emu_str or emu_str.strip() == 'pc':
                    return True
                pkg = getattr(device_cfg, 'package_name', '')
                pkg_val = getattr(pkg, 'value', pkg)
                pkg_str = f"{pkg} {pkg_val}".lower()
                if 'onmyoji.exe' in pkg_str or 'windows_onmyoji' in pkg_str:
                    return True
                ser = str(getattr(device_cfg, 'serial', '')).lower()
                if ser in ('windows-0', 'pc', 'windows'):
                    return True
        except Exception:
            pass
        return False

    @cached_property
    def is_wsa(self):
        return bool(re.match(r'^wsa', self.serial))

    @cached_property
    def is_mumu_family(self):
        return self.serial == '127.0.0.1:7555'

    @cached_property
    def is_emulator(self):
        return self.serial.startswith('emulator-') or self.serial.startswith('127.0.0.1:')

    @cached_property
    def is_network_device(self):
        return bool(re.match(r'\d+\.\d+\.\d+\.\d+:\d+', self.serial))

    @cached_property
    def is_over_http(self):
        return bool(re.match(r"^https?://", self.serial))

    @cached_property
    def is_chinac_phone_cloud(self):
        # Phone cloud with public ADB connection
        # Serial like xxx.xxx.xxx.xxx:301
        return bool(re.search(r":30[0-9]$", self.serial))

    @cached_property
    def adb_binary(self):
        # Try adb in deploy.yaml
        # from module.webui.setting import State
        # file = State.deploy_config.AdbExecutable
        # file = file.replace('\\', '/')
        # if os.path.exists(file):
        #     return os.path.abspath(file)
        #
        # # Try existing adb.exe
        # for file in self.adb_binary_list:
        #     if os.path.exists(file):
        #         return os.path.abspath(file)

        # Try adb in python environment
        import sys
        file = os.path.join(sys.executable, '../Lib/site-packages/adbutils/binaries/adb.exe')
        file = os.path.abspath(file).replace('\\', '/')
        if os.path.exists(file):
            return file

        # Use adb in system PATH
        file = 'adb'
        return file

    @cached_property
    def adb_client(self) -> AdbClient:
        host = '127.0.0.1'
        port = 5037

        # Trying to get adb port from env
        env = os.environ.get('ANDROID_ADB_SERVER_PORT', None)
        if env is not None:
            try:
                port = int(env)
            except ValueError:
                logger.warning(f'Invalid environ variable ANDROID_ADB_SERVER_PORT={port}, using default port')

        logger.attr('AdbClient', f'AdbClient({host}, {port})')
        return AdbClient(host, port)

    @cached_property
    def adb(self) -> AdbDevice:
        return AdbDevice(self.adb_client, self.serial)

    @cached_property
    def u2(self) -> u2.Device:
        if self.is_over_http:
            # Using uiautomator2_http
            device = u2.connect(self.serial)
        else:
            # Normal uiautomator2
            if self.serial.startswith('emulator-') or self.serial.startswith('127.0.0.1:'):
                device = u2.connect_usb(self.serial)
            else:
                device = u2.connect(self.serial)

        # Stay alive
        device.set_new_command_timeout(604800)

        logger.attr('u2.Device', f'Device(atx_agent_url={device._get_atx_agent_url()})')
        return device


