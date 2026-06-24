# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.logger import logger


class Notifier:
    """通知器空壳实现 — 所有推送通知已禁用（本地单机版）"""

    def __init__(self, _config: str = '', enable: bool = False) -> None:
        self.config_name: str = ""
        self.enable: bool = False

    def push(self, **kwargs) -> bool:
        """推送通知（已禁用，仅记录日志）"""
        title = kwargs.get('title', '')
        content = kwargs.get('content', '')
        if title or content:
            logger.info(f'[Notifier disabled] title={title}, content={content}')
        return False
