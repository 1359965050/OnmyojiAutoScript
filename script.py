# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.base.dpi import enable_dpi_awareness
enable_dpi_awareness()

import zerorpc
import zmq
import re
import cv2
import time
import os
import inflection
import json
import copy

from datetime import date
import threading
from module.device.device import Device
from typing import Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
from functools import cached_property
from pydantic import BaseModel, ValidationError
from threading import Thread
from multiprocessing.queues import Queue
from module.config.utils import convert_to_underscore
from module.config.config import Config
from module.config.anti_ban import AntiBanGuard
from module.device.env import IS_WINDOWS
from module.base.utils import load_module
from module.base.decorator import del_cached_property
from module.logger import logger
from module.exception import *
from module.server.i18n import I18n
from module.image.rpc import ensure_image_server_ready
from module.ocr.rpc import ensure_ocr_server_ready
from module.script import ScriptRuntimeController, ScriptRuntimeDecision
from module.utils.power_manager import PowerManager
from tasks.Restart.server_update import delay_pending_tasks_for_server_update, is_server_update_window
from module.server.log_service import build_error_log_dir_name

_log_switch_lock = threading.Lock()#线程锁


class Script:
    def __init__(self, config_name: str ='oas') -> None:
        logger.hr('启动', level=0)
        self.server = None
        self.state_queue: Queue = None
        self._emulator_down = False
        self.runtime = ScriptRuntimeController(self)
        self.gui_update_task: Callable = None  # 回调函数, gui进程注册当每次config更新任务的时候更新gui的信息
        self.config_name = config_name
        # Skip first restart
        self.is_first_task = True
        # Failure count of tasks
        # Key: str, task name, value: int, failure count
        self.failure_record = {}
        self.last_task_runtime_outcome: dict[str, Any] | None = None
        self.task_hoarding_until: datetime | None = None
        self.task_hoarding_released = False
        # 运行loop的线程
        self.loop_thread: Thread = None
        self.anti_ban_guard: AntiBanGuard = AntiBanGuard(config_name=self.config_name)

    def _reload_config(self) -> Config:
        """重新加载配置并同步更新已初始化设备的 config 引用。"""
        del_cached_property(self, 'config')
        new_config = self.config
        dev = self.__dict__.get('device')
        if dev is not None:
            dev.config = new_config
        return new_config

    @cached_property
    def config(self) -> "Config":
        try:
            from module.config.config import Config
            config = Config(config_name=self.config_name)
            return config
        except RequestHumanTakeover:
            logger.critical('Request human takeover')
            exit(1)
        except Exception as e:
            logger.exception(e)
            exit(1)

    @cached_property
    def device(self) -> Device | None:
        try:
            from module.device.device import Device
            device = Device(config=self.config)
            return device
        except RequestHumanTakeover:
            logger.critical('Request human takeover')
            exit(1)
        except Exception as e:
            logger.exception(e)
            exit(1)

    @cached_property
    def checker(self):
        """
        占位函数，在alas中是检查服务器是否正常的
        :return:
        """
        return None

    def save_error_log(self, e: Exception | None = None):
        """
        保存错误现场到 ./log/error/<script_name>_<timestamp_ms>。

        保存内容包括:
        - 最近一段截图, 文件名为时间戳 PNG。
        - 当前脚本日志的截取内容, 文件名为 log.txt。
        - 错误上下文快照: 任务名、页面状态、设备信息、配置。
        - 完整 traceback（如果传入异常对象）。

        说明:
        - 新错误目录名会带上脚本名, 便于前端区分不同脚本产生的错误。
        - 目录名和脚本名都会经过统一净化, 避免路径注入。
        """
        from module.base.utils import save_image
        from module.handler.sensitive_info import (handle_sensitive_image,
                                                   handle_sensitive_logs)
        import traceback
        if self.config.script.error.save_error:
            folder_name = build_error_log_dir_name(self.config_name, int(time.time() * 1000))
            folder = f'./log/error/{folder_name}'
            logger.warning(f'Saving error: {folder}')
            os.makedirs(folder, exist_ok=True)

            dev = self.__dict__.get('device')
            if dev is not None:
                try:
                    for data in getattr(dev, 'screenshot_deque', ()):
                        image_time = datetime.strftime(data['time'], '%Y-%m-%d_%H-%M-%S-%f')
                        image = handle_sensitive_image(data['image'])
                        save_image(image, f'{folder}/{image_time}.png')
                except Exception:
                    pass

                try:
                    latest = dev.screenshot()
                    image_time = datetime.strftime(datetime.now(), '%Y-%m-%d_%H-%M-%S-%f')
                    image = handle_sensitive_image(latest)
                    save_image(image, f'{folder}/{image_time}.png')
                except Exception:
                    pass

            lines = []
            log_file = getattr(logger, 'log_file', None)
            if log_file and os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    raw_lines = f.readlines()
                start = None
                for index, line in enumerate(raw_lines):
                    stripped = line.strip(' \r\t\n')
                    if re.match('^═{15,}$', stripped):
                        start = index
                sliced = raw_lines[-200:] if start is None else raw_lines[max(0, start - 2):]
                lines = handle_sensitive_logs(sliced)

            context_lines = []
            context_lines.append('=' * 60 + '\n')
            context_lines.append('ERROR CONTEXT SNAPSHOT\n')
            context_lines.append('=' * 60 + '\n')
            context_lines.append(f'Time: {datetime.now().isoformat()}\n')
            context_lines.append(f'Script: {self.config_name}\n')
            context_lines.append(f'Running Task: {self.config.model.running_task}\n')
            context_lines.append(f'Next Task: {self.config.task.command if self.config.task else "None"}\n')
            try:
                context_lines.append(f'Device: {dev.__class__.__name__ if dev is not None else "Uninitialized"}\n')
            except Exception:
                context_lines.append('Device: Unknown\n')
            try:
                context_lines.append(f'Package: {getattr(dev, "package", "Unknown") if dev is not None else "Unknown"}\n')
            except Exception:
                context_lines.append('Package: Unknown\n')
            try:
                screen_size = getattr(dev, "screen_size", getattr(dev, "screenshot_size", "Unknown")) if dev is not None else "Unknown"
                context_lines.append(f'Screen Size: {screen_size}\n')
            except Exception:
                context_lines.append('Screen Size: Unknown\n')
            try:
                context_lines.append(f'Error Count: {self.config.script.error.error_count}\n')
            except Exception:
                context_lines.append('Error Count: Unknown\n')
            try:
                context_lines.append(f'Failure Record: {json.dumps(self.failure_record, ensure_ascii=False)}\n')
            except Exception:
                context_lines.append('Failure Record: Unknown\n')
            context_lines.append('=' * 60 + '\n')

            if e:
                try:
                    context_lines.append('\n=== FULL TRACEBACK ===\n')
                    context_lines.append(traceback.format_exc())
                    context_lines.append('=' * 60 + '\n')
                except Exception:
                    context_lines.append('\n=== TRACEBACK FAILED ===\n')

            with open(f'{folder}/log.txt', 'w', encoding='utf-8') as f:
                f.writelines(context_lines)
                f.writelines(lines)

    def init_server(self, port: int) -> int:
        """
        初始化zerorpc服务，返回端口号
        :return:
        """
        self.server = zerorpc.Server(self)
        try:
            self.server.bind(f'tcp://127.0.0.1:{port}')
            return port
        except zmq.error.ZMQError:
            logger.error(f"Ocr server cannot bind on port {port}")
            return None

    def run_server(self) -> None:
        """
        启动zerorpc服务
        :return:
        """
        self.server.run()

    def gui_args(self, task: str) -> str:
        """
        获取给gui显示的参数
        :return:
        """
        return self.config.gui_args(task=task)

    def gui_menu(self) -> str:
        """
        获取给gui显示的菜单
        :return:
        """
        return self.config.gui_menu

    def gui_task(self, task: str) -> str:
        """
        获取给gui显示的任务 的参数的具体值
        :return:
        """
        return self.config.model.gui_task(task=task)

    def gui_set_task(self, task: str, group: str, argument: str, value) -> bool:
        """
        设置给gui显示的任务 的参数的具体值
        :return:
        """
        # 验证参数
        task = convert_to_underscore(task)
        group = convert_to_underscore(group)
        argument = convert_to_underscore(argument)
        # pandtic验证
        if isinstance(value, str):
            if len(value) == 8:
                try:
                    value = datetime.strptime(value, '%H:%M:%S').time()
                except ValueError:
                    pass


        path = f'{task}.{group}.{argument}'
        task_object = getattr(self.config.model, task, None)
        group_object = getattr(task_object, group, None)
        argument_object = getattr(group_object, argument, None)

        if argument_object is None:
            logger.error(f'Set arg {task}.{group}.{argument}.{value} failed')
            return False

        try:
            setattr(group_object, argument, value)
            argument_object = getattr(group_object, argument, None)
            logger.info(f'Set arg {task}.{group}.{argument}.{argument_object}')
            self.config.save()  # 我是没有想到什么方法可以使得属性改变自动保存的
            return True
        except ValidationError as e:
            logger.error(e)
            return False

    @zerorpc.stream
    def gui_mirror_image(self):
        """
        获取给gui显示的镜像
        :return: cv2的对象将 numpy 数组转换为字节串。接下来MsgPack 进行序列化发送方将图像数据转换为字节串
        """
        # return msgpack.packb(cv2.imencode('.jpg', self.device.screenshot())[1].tobytes())
        img = cv2.cvtColor(self.device.screenshot(), cv2.COLOR_RGB2BGR)
        self.device.stuck_record_clear()
        ret, buffer = cv2.imencode('.jpg', img)
        yield buffer.tobytes()

    def _gui_update_tasks(self) -> None:
        """
        获取更新任务后 pending waiting 的任务 和 当前的任务的数据。打包给gui显示
        :return:
        """
        data = {}
        pending = []
        waiting = []
        task = {}
        if self.config.task is not None and self.config.task.next_run < datetime.now():
            task["name"] = self.config.task.command
            task["next_run"] = str(self.config.task.next_run)
        data["task"] = task

        for p in self.config.pending_task[1:]:
            item = {"name": p.command, "next_run": str(p.next_run)}
            pending.append(item)

        for w in self.config.waiting_task:
            item = {"name": w.command, "next_run": str(w.next_run)}
            waiting.append(item)


        data["pending"] = pending
        data["waiting"] = waiting

        if self.gui_update_task is not None:
            self.gui_update_task(data)

    def _gui_set_status(self, status: str) -> None:
        """
        设置给gui显示的状态
        :param status: 可以在gui中显示的状态 有 "Init", "Empty"(不显示), "Run"(运行中), "Error", "Free"(空闲)
        :return:
        """
        data = {"status": status}
        if self.gui_update_task is not None:
            self.gui_update_task(data)

    def gui_task_list(self) -> str:
        """
        获取给gui显示的任务列表
        :return:
        """
        result = {}
        for key, value in self.config.model.dict().items():
            if isinstance(value, str):
                continue
            if key == "restart":
                continue
            if "scheduler" not in value:
                continue

            scheduler = value["scheduler"]
            item = {"enable": scheduler["enable"],
                    "next_run": str(scheduler["next_run"])}
            key = self.config.model.type(key)
            result[key] = item
        return json.dumps(result)

    def wait_until(self, future):
        """
        Wait until a specific time.

        Args:
            future (datetime):

        Returns:
            bool: True if wait finished, False if config changed.
        """
        future = future + timedelta(seconds=1)
        self.config.start_watching()
        while 1:
            if datetime.now() > future:
                return True
            # if self.stop_event is not None:
            #     if self.stop_event.is_set():
            #         logger.info("Update event detected")
            #         logger.info(f"[{self.config_name}] exited. Reason: Update")
            #         exit(0)

            time.sleep(5)

            if self.config.should_reload():
                return False

    def _hoard_next_task(self, task, now: datetime):
        """在空闲时延迟首个到期任务，窗口内到达的任务一并等待。"""
        duration = self.config.script.optimization.task_hoarding_duration
        if duration <= 0 or not self.config.pending_task:
            self.task_hoarding_until = None
            self.task_hoarding_released = False
            return task

        if (self.config.model.running_task or self.task_hoarding_released
                or (self.is_first_task and task.command == 'Restart')
                or (task.next_run > now and self.task_hoarding_until is None)):
            return task

        if self.task_hoarding_until is None:
            self.task_hoarding_until = now + timedelta(minutes=duration)
            logger.info(
                f"Task hoarding started for {duration:g} minutes, "
                f"release at {self.task_hoarding_until.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        if now < self.task_hoarding_until:
            task = copy.deepcopy(task)
            task.next_run = max(self.task_hoarding_until, task.next_run)
            logger.info(
                f"Task hoarding active, defer pending tasks until "
                f"{self.task_hoarding_until.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return task

        self.task_hoarding_until = None
        self.task_hoarding_released = True
        logger.info('Task hoarding window ended, resume scheduled task execution')
        return task

    def get_next_task(self) -> str:
        """
        获取下一个任务的名字, 大驼峰。
        :return:
        """
        while True:
            task = self.config.get_next()
            now = datetime.now()
            antiban_wake = self.anti_ban_guard.wake_time(now, self.config.script.anti_ban)
            if antiban_wake is not None:
                task.next_run = max(task.next_run, antiban_wake)
            task = self._hoard_next_task(task, now)
            self.config.task = task
            if self.state_queue:
                self.state_queue.put({'schedule': self.config.get_schedule_data()})
            # 任务时间到了返回任务名称
            if task.next_run <= now:
                return task.command
            # 根据策略执行等待逻辑
            wait_until = task.next_run
            if self.task_hoarding_until and self.config.waiting_task:
                wait_until = min(wait_until, self.config.waiting_task[0].next_run)
            decision = self.runtime.handle_wait_during_idle(wait_until)
            if decision == ScriptRuntimeDecision.RESCHEDULE:
                logger.info('Idle wait requested scheduler refresh, reload config and reschedule')
                self._reload_config()
            elif decision == ScriptRuntimeDecision.FAILED:
                logger.warning('Idle wait preparation failed, reload config and retry scheduling')
                self._reload_config()

    def exception_handler(self, e: Exception, command: str) -> None:
        # 处理御魂溢出
        from tasks.Utils.post_diagnotor import PostDiagnotor, AnalyzeType
        dev = self.__dict__.get('device')
        image = getattr(dev, 'image', None) if dev is not None else None
        # image为None则不做处理
        if image is None:
            return
        analyse_type = PostDiagnotor().handle(e=e, command=command, image=image)
        if analyse_type == AnalyzeType.SoulOverflow:
            self.config.task_call('SoulsTidy')
            time.sleep(1)

    def _reset_task_runtime_outcome(self) -> None:
        self.last_task_runtime_outcome = None
        if 'config' in self.__dict__:
            self.config.task_runtime_outcome = None

    def _set_task_runtime_outcome(self, task: str, status: str, wait_until: datetime | None = None) -> None:
        outcome = {
            'task': task,
            'status': status,
        }
        if wait_until is not None:
            outcome['wait_until'] = wait_until
        self.last_task_runtime_outcome = outcome
        if 'config' in self.__dict__:
            self.config.task_runtime_outcome = outcome

    def _capture_task_runtime_outcome(self, command: str) -> None:
        outcome = getattr(self.config, 'task_runtime_outcome', None)
        self.last_task_runtime_outcome = outcome if isinstance(outcome, dict) else None
        if self.last_task_runtime_outcome is None:
            return
        status = self.last_task_runtime_outcome.get('status')
        if status == 'server_update_delayed':
            wait_until = self.last_task_runtime_outcome.get('wait_until')
            logger.info(f'{command} runtime outcome: server_update_delayed (wait_until={wait_until})')
            if isinstance(wait_until, datetime):
                self.runtime.server_update_wait_until = wait_until
                self.runtime.server_update_wait_log_until = None
            return
        if command != 'Restart':
            return
        if status == 'recovered':
            logger.info('Restart runtime outcome: recovered')
            return
        logger.info(f'Restart runtime outcome: {status}')

    def _delay_tasks_for_server_update(self, task: str, reason: str) -> bool:
        if not is_server_update_window():
            return False

        delay_target = delay_pending_tasks_for_server_update(self.config, reason=reason)
        self._set_task_runtime_outcome(task=task, status='server_update_delayed', wait_until=delay_target)
        return True

    def run(self, command: str) -> bool:
        """
        :param command:  大写驼峰命名的任务名字
        :return:
        """
        if command == 'start' or command == 'goto_main':
            logger.error(f'Invalid command `{command}`')

        self._reset_task_runtime_outcome()
        try:
            if command == 'Restart':
                logger.info('Skip screenshot before Restart task')
            else:
                if getattr(self.device, 'is_windows_client', False) and hasattr(self.device, 'desktop_window_set_size'):
                    self.device.desktop_window_set_size(1280, 720, log_if_matched=False)
                self.device.screenshot()
            module_name = 'script_task'
            module_path = str(Path.cwd() / 'tasks' / command / (module_name + '.py'))
            logger.info(f'module_path: {module_path}, module_name: {module_name}')
            task_module = load_module(module_name, module_path)
            task_module.ScriptTask(config=self.config, device=self.device).run()
        except Exception as e:
            return self._handle_task_exception(e, command)
        return False

    @staticmethod
    def _resolve_target_window_name(raw_handle, is_win_client: bool = False, resolved_title: str = '') -> str:
        """
        解析用于置顶或最小化的目标窗口名称，避免将 'auto' 或数字句柄直接传入标题查找。
        """
        target = '' if raw_handle is None else str(raw_handle).strip()
        title = str(resolved_title or '').strip()
        is_placeholder = (
            not target
            or target.lower() == 'auto'
            or target.isdigit()
            or (
                is_win_client
                and 'mumu' in target.lower()
                and '阴阳师' not in target
                and 'onmyoji' not in target.lower()
            )
        )
        if is_placeholder:
            if title:
                return title
            return '阴阳师' if is_win_client else ''
        return target

    def loop(self):
        """
        Main loop of scheduler.
        :return:
        """
        with _log_switch_lock:
            logger.set_file_logger(self.config_name, do_cleanup=True)
        start_day = date.today()
        logger.info(f'Start scheduler loop: {self.config_name}')
        self.config.model.running_task = ''

        # Update GUI 防呆, 读取设置并立刻显示后台模拟器到前台
        if not self.config.script.device.run_background_only and IS_WINDOWS:
            from module.device.platform2.platform_windows import minimize_by_name, show_window_by_name
            raw_handle = self.config.script.device.handle  # 在这里输入你的具体窗口名称
            has_device = hasattr(self, 'device')
            is_win_client = getattr(self.device, 'is_windows_client', False) if has_device else False
            resolved_title = getattr(self.device, 'root_handle_title', '') if has_device else ''
            target_window_name = self._resolve_target_window_name(
                raw_handle,
                is_win_client=is_win_client,
                resolved_title=resolved_title,
            )
            if target_window_name:
                if self.config.script.device.emulator_window_minimize:
                    minimize_by_name(target_window_name)
                    logger.info(f'重新显示: {target_window_name}')
                else:
                    show_window_by_name(target_window_name)
                
        while 1:
            if date.today() > start_day:
                with _log_switch_lock:
                    logger.set_file_logger(self.config_name, do_cleanup=True)
                start_day = date.today()

            task = ""
            try:
                # Get task
                task = self.get_next_task()
                # Skip first restart
                if self.is_first_task and task == 'Restart':
                    logger.info('Skip task `Restart` at scheduler start')
                    self.config.task_delay(task='Restart', success=True, server=True)
                    self._reload_config()
                    continue
                decision = self.runtime.prepare_task_execution(task)
            except Exception as e:
                self._handle_task_exception(e, task)
                # 本轮 prepare 失败,重新调度
                self._reload_config()
                continue

            if decision == ScriptRuntimeDecision.RESCHEDULE:
                logger.info(f'Runtime preparation for `{task}` requested reschedule, reload config and retry scheduling')
                self._reload_config()
                continue
            if decision == ScriptRuntimeDecision.FAILED:
                logger.warning(f'Runtime preparation for `{task}` failed, reload config and retry scheduling')
                self._reload_config()
                continue

            # Run
            logger.info(f'Scheduler: Start task `{task}`')
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            task_cn = I18n.trans_zh_cn(task)
            logger.hr(f'{task_cn} [{task}]' if task_cn != task else task, level=0)
            self.config.model.running_task = task
            _task_start = datetime.now()
            PowerManager.acquire()
            try:
                success = self.run(inflection.camelize(task))
            finally:
                PowerManager.release()
                self.config.model.running_task = ''
            logger.info(f'Scheduler: End task `{task}`')
            self.is_first_task = False
            self.anti_ban_guard.record_active((datetime.now() - _task_start).total_seconds())

            # Check failures
            # failed = deep_get(self.failure_record, keys=task, default=0)
            failed = self.failure_record[task] if task in self.failure_record else 0
            failed = 0 if success else failed + 1
            # deep_set(self.failure_record, keys=task, value=failed)
            self.failure_record[task] = failed
            if failed >= 3:
                logger.critical(f"Task `{task}` failed 3 or more times.")
                logger.critical("Possible reason #1: You haven't used it correctly. "
                                "Please read the help text of the options.")
                logger.critical("Possible reason #2: There is a problem with this task. "
                                "Please contact developers or try to fix it yourself.")
                logger.critical('Request human takeover')
                # 添加失败三次的推送通知
                self.config.notifier.push(
                    title=f'{I18n.trans_zh_cn(task)}{task}',
                    content=f"<{self.config_name}> 任务连续失败三次，请上线查看"
                )
                exit(1)

            if success:
                self._reload_config()
                continue
            elif self.config.script.error.handle_error:
                # self.config.task_delay(success=False)
                self._reload_config()
                # self.checker.check_now()
                continue
            else:
                break
        PowerManager.release_all()
        logger.info(f'Scheduler loop exited: {self.config_name}')

    def _handle_task_exception(self, e: Exception, command: str) -> bool:
        """
        统一处理任务执行 / 准备阶段抛出的异常。
        Returns:
            True  -> 视为正常结束, 调度器继续推进
            False -> 视为失败（触发失败计数累积）, 脚本继续尝试重启恢复
        对致命异常 (ScriptError / RequestHumanTakeover / 未识别 Exception)
        在内部直接 exit(1)。
        """
        if isinstance(e, TaskEnd):
            self._capture_task_runtime_outcome(command)
            return True

        dev = self.__dict__.get('device')
        pkg_name = getattr(dev, 'package', 'Unknown') if dev is not None else 'Unknown'
        sleep_fn = dev.sleep if dev is not None else time.sleep

        if isinstance(e, GameNotRunningError):
            logger.warning(e)
            self.exception_handler(e=e, command=command)
            self.config.task_call('Restart')
            return False

        if isinstance(e, (GameStuckError, GameTooManyClickError)):
            logger.error(e)
            self.save_error_log(e=e)
            self.exception_handler(e=e, command=command)
            logger.warning(f'Game stuck, {pkg_name} will be restarted in 10 seconds')
            logger.warning('If you are playing by hand, please stop Alas')
            self.config.notifier.push(title=f'{I18n.trans_zh_cn(command)}{command}',
                                      content=f"<{self.config_name}> GameStuckError or GameTooManyClickError")
            self.config.task_call('Restart')
            sleep_fn(10)
            return False

        if isinstance(e, GameBugError):
            logger.warning(e)
            self.save_error_log(e=e)
            self.exception_handler(e=e, command=command)
            logger.warning('An error has occurred in Azur Lane game client, Alas is unable to handle')
            logger.warning(f'Restarting {pkg_name} to fix it')
            self.config.task_call('Restart')
            sleep_fn(10)
            return False

        if isinstance(e, GamePageUnknownError):
            logger.info('Game server may be under maintenance or network may be broken, check server status now')
            if command == 'GotoMain' and self._delay_tasks_for_server_update(
                    task=command,
                    reason='failed to goto main during morning server update window',
            ):
                logger.info('GotoMain failed during server update window, delayed pending tasks and reschedule')
                return False
            logger.critical('Game page unknown')
            self.save_error_log(e=e)
            self.exception_handler(e=e, command=command)
            self.config.notifier.push(
                title=f'{I18n.trans_zh_cn(command)}{command}',
                content=f"<{self.config_name}> GamePageUnknownError",
            )
            self.config.task_call('Restart')
            sleep_fn(10)
            return False

        if isinstance(e, ScriptError):
            logger.critical(e)
            self.exception_handler(e=e, command=command)
            logger.critical('This is likely to be a mistake of developers, but sometimes just random issues')
            self.config.notifier.push(
                title=f'{I18n.trans_zh_cn(command)}{command}',
                content=f"<{self.config_name}> ScriptError",
            )
            exit(1)

        if isinstance(e, RequestHumanTakeover):
            logger.critical(e)
            self.exception_handler(e=e, command=command)
            logger.critical('Request human takeover')
            self.config.notifier.push(
                title=f'{I18n.trans_zh_cn(command)}{command}',
                content=f"<{self.config_name}> RequestHumanTakeover",
            )
            exit(1)

        # generic
        logger.exception(e)
        self.exception_handler(e=e, command=command)
        self.save_error_log(e=e)
        self.config.notifier.push(
            title=f'{I18n.trans_zh_cn(command)}{command}',
            content=f"<{self.config_name}> Exception occured",
        )
        exit(1)
        return False

    def start_loop(self) -> None:
        """
        创建一个线程，运行loop
        :return:
        """
        if self.loop_thread is None:
            self.loop_thread = Thread(target=self.loop, name='Script_loop')
            self.loop_thread.start()


if __name__ == "__main__":
    ensure_image_server_ready()
    ensure_ocr_server_ready()
    script = Script("oas1")
    script.loop()
