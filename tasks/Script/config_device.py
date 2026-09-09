# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from typing import Union, Any
from pydantic import BaseModel, ValidationError, Field, field_validator

from module.logger import logger
from tasks.Component.config_base import dynamic_hide


class PackageName(str, Enum):
    NETEASE_ONMYOJI = 'com.netease.onmyoji.wyzymnqsd_cps'  # 官方可扫码版
    WINDOWS_ONMYOJI = 'onmyoji.exe'  # Windows桌面版



class ScreenshotMethod(str, Enum):
    AUTO = 'auto'
    ADB = 'ADB'
    ADB_NC = 'ADB_nc'
    UIAUTOMATOR2 = 'uiautomator2'
    DROIDCAST = 'DroidCast'
    DROIDCAST_RAW = 'DroidCast_raw'
    SCRCPY = 'scrcpy'
    WINDOW_BACKGROUND = 'window_background'
    NEMU_IPC = 'nemu_ipc'


class ControlMethod(str, Enum):
    ADB = 'adb'
    UIAUTOMATOR2 = 'uiautomator2'
    MINITOUCH = 'minitouch'
    WINDOW_MESSAGE = 'window_message'



class EmulatorInfoType(str, Enum):
    # module.device.platform2.emulator_base.EmulatorBase
    WindowsClient = 'WindowsClient'
    MuMuPlayer12 = 'MuMuPlayer12'


class Device(BaseModel):
    serial: str = Field(default="auto", description='serial_help')

    @field_validator('serial', mode='before')
    @classmethod
    def validate_serial(cls, v: Any) -> str:
        if v is None:
            return 'auto'
        s = str(v).strip()
        if not s or s.lower() == 'auto':
            return 'auto'
        s = s.replace('：', ':')
        # 如果仅填写纯端口数字，例如 16448
        if s.isdigit():
            return f'127.0.0.1:{s}'
        # 如果是冒号开头的端口，例如 :16448
        if s.startswith(':') and s[1:].isdigit():
            return f'127.0.0.1{s}'
        # 如果以 localhost: 开头，转为 127.0.0.1:
        if s.lower().startswith('localhost:'):
            return f'127.0.0.1:{s[10:]}'
        return s
    handle: str = Field(default='', description='handle_help')
    package_name: PackageName = Field(title='Package Name', default=PackageName.NETEASE_ONMYOJI, description='package_name_help')
    screenshot_method: ScreenshotMethod = Field(default=ScreenshotMethod.AUTO, description='screenshot_method_help')
    control_method: ControlMethod = Field(default=ControlMethod.MINITOUCH, description='control_method_help')
    adb_restart: bool = Field(default=False, description='adb_restart_help')
    emulatorinfo_type: EmulatorInfoType = Field(default=EmulatorInfoType.MuMuPlayer12, description='emulatorinfo_type_help')

    @field_validator('emulatorinfo_type', mode='before')
    @classmethod
    def validate_emulatorinfo_type(cls, v: Any) -> EmulatorInfoType:
        if v is None:
            return EmulatorInfoType.MuMuPlayer12
        v_str = str(getattr(v, 'value', v)).strip()
        if v_str.lower() in ('windowsclient', 'windows_client', 'windows', 'pc'):
            return EmulatorInfoType.WindowsClient
        # 兼容旧配置中的 auto、NoxPlayer64、LDPlayer9、BlueStacks5、MEmuPlayer 等，全部安全回退至 MuMuPlayer12
        return EmulatorInfoType.MuMuPlayer12
    emulatorinfo_name: str = Field(default='', description='emulatorinfo_name_help')
    emulatorinfo_path: str = Field(default='', description='emulatorinfo_path_help')
    client_path: str = Field(default='', description='client_path_help')
    # 举例, E:\ProgramFiles\MuMuPlayer-12.0\shell\MuMuPlayer.exe
    # 模拟器启动时最小化
    emulator_window_minimize: bool = Field(default=False, description='模拟器静默启动并最小化')
    # 启动时纯后台运行模拟器，不显示窗口和任务栏
    run_background_only: bool = Field(default=False, description='模拟器无UI后台运行，关掉后重启脚本会重新显示（无需重启OAS）')

    hide_fields = dynamic_hide('emulatorinfo_name')


if __name__ == '__main__':
    d = Device()
    print(d.json())
    print(d.schema_json())
    try:
        d.control_method = 'adb'
    except ValidationError as e:
        print(e)
