from lxml import etree

from module.device.method.adb import Adb
from module.device.method.uiautomator_2 import Uiautomator2
from module.device.method.utils import HierarchyButton
# from module.device.method.wsa import WSA
from module.logger import logger


class AppControl(Adb, Uiautomator2):
    hierarchy: etree._Element
    _app_u2_family = ['uiautomator2', 'minitouch', 'scrcpy']

    def app_is_alive(self, package_name=None) -> bool:
        """
        判断目标应用进程是否仍然存活，不要求当前位于前台。

        这用于区分“应用被切到后台”和“应用已经被真正杀掉”两种情况。
        """
        if getattr(self, 'is_windows_client', False):
            import psutil
            target = (package_name or self.package or 'onmyoji.exe').lower()
            for p in psutil.process_iter(['name', 'pid']):
                try:
                    pname = p.info['name']
                    if pname and 'onmyoji' in pname.lower():
                        logger.attr('Package_pid', str(p.info['pid']))
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            logger.attr('Package_pid', 'None')
            return False

        if not package_name:
            package_name = self.package

        try:
            result = self.adb_shell(['pidof', package_name])
        except Exception as e:
            logger.info(f'Check app alive by pidof failed: {e}')
            return False

        result = result.strip(' \t\r\n')
        logger.attr('Package_pid', result if result else 'None')
        return bool(result)

    def app_is_running(self) -> bool:
        if getattr(self, 'is_windows_client', False):
            hwnd = getattr(self, 'screenshot_handle_num', 0)
            if hwnd:
                from win32gui import IsWindow, IsWindowVisible
                if IsWindow(hwnd) and IsWindowVisible(hwnd):
                    return True
            return self.app_is_alive()

        method = self.config.script.device.control_method
        # if self.is_wsa:
        #     package = self.app_current_wsa()
        if method in AppControl._app_u2_family:
            package = self.app_current_uiautomator2()
        else:
            package = self.app_current_adb()

        package = package.strip(' \t\r\n')
        logger.attr('Package_name', package)
        return package == self.package

    def app_start(self):
        if getattr(self, 'is_windows_client', False):
            logger.info('App start (Windows): onmyoji.exe')
            import subprocess, os
            path = getattr(self.config.script.device, 'client_path', '')
            path = str(path).strip().strip('"\'') if path else ''

            if not path:
                logger.info('client_path is empty. Skip automatic launch of desktop client (manual launch mode).')
                return

            if os.path.isdir(path):
                for candidate in ['Launch.exe', os.path.join('bin', 'onmyoji.exe'), 'onmyoji.exe']:
                    c_path = os.path.join(path, candidate)
                    if os.path.exists(c_path):
                        path = c_path
                        break

            if not os.path.exists(path) or os.path.isdir(path):
                logger.warning(f'Onmyoji desktop executable not found at client_path: {path}. Please check configuration or start the game manually.')
                return

            cwd = os.path.dirname(path)
            logger.info(f'Launching Onmyoji client: {path} (cwd: {cwd})')
            try:
                subprocess.Popen([path], cwd=cwd, shell=False)
            except OSError as e:
                logger.warning(f'Failed to launch {path} directly ({e}). Trying shell launch or bin/onmyoji.exe fallback...')
                # 尝试使用 Windows Shell 打开（可唤起系统的 UAC 提示）
                try:
                    os.startfile(path)
                    return
                except Exception:
                    pass

                bin_path = os.path.join(cwd, 'bin', 'onmyoji.exe') if not path.endswith('onmyoji.exe') else path
                root_dir = cwd if not path.endswith('onmyoji.exe') else os.path.dirname(cwd)
                if os.path.exists(bin_path):
                    try:
                        subprocess.Popen([bin_path], cwd=root_dir, shell=False)
                    except OSError as e2:
                        logger.warning(f'Automatic client launch requires UAC elevation: {e2}. Please start Onmyoji PC client manually.')
                else:
                    logger.warning('Please start Onmyoji PC client manually.')
            return

        method = self.config.script.device.screenshot_method
        logger.info(f'App start: {self.package}')
        # if self.config.Emulator_Serial == 'wsa-0':
        #     self.app_start_wsa(display=0)
        if method in AppControl._app_u2_family:
            self.app_start_uiautomator2()
        else:
            self.app_start_adb()

    def app_stop(self):
        if getattr(self, 'is_windows_client', False):
            logger.info('App stop (Windows): onmyoji.exe')
            import psutil
            stopped = False
            for p in psutil.process_iter(['name', 'pid']):
                try:
                    pname = p.info['name']
                    if pname and 'onmyoji' in pname.lower():
                        p.terminate()
                        stopped = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if stopped:
                logger.info('Terminated onmyoji.exe process')
            return

        method = self.config.script.device.screenshot_method
        logger.info(f'App stop: {self.package}')
        if method in AppControl._app_u2_family:
            self.app_stop_uiautomator2()
        else:
            self.app_stop_adb()

    def dump_hierarchy(self) -> etree._Element:
        """
        Returns:
            etree._Element: Select elements with `self.hierarchy.xpath('//*[@text="Hermit"]')` for example.
        """
        method = self.config.script.device.screenshot_method
        if method in AppControl._app_u2_family:
            self.hierarchy = self.dump_hierarchy_uiautomator2()
        else:
            self.hierarchy = self.dump_hierarchy_adb()
        return self.hierarchy

    def xpath_to_button(self, xpath: str) -> HierarchyButton:
        """
        Args:
            xpath (str):

        Returns:
            HierarchyButton:
                An object with methods and properties similar to Button.
                If element not found or multiple elements were found, return None.
        """
        return HierarchyButton(self.hierarchy, xpath)
