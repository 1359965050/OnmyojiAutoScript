# This Python file uses the following encoding: utf-8
# 本地单机版 — 更新功能已禁用

import subprocess

from deploy.utils import DEPLOY_CONFIG
from module.logger import logger
from module.server.config import DeployConfig


class Updater(DeployConfig):
    """精简版 Updater — 仅保留本地 git log 查询能力，禁用一切远程操作"""

    def __init__(self, file=DEPLOY_CONFIG):
        super().__init__(file=file)
        self.state = 0

    def execute_output(self, command) -> str:
        command = command.replace(r"\\", "/").replace("\\", "/").replace('"', '"')
        log = subprocess.run(
            command, capture_output=True, text=True, encoding="utf8", shell=True
        ).stdout
        return log

    def get_commit(self, revision="", n=1, short_sha1=False):
        """
        Return:
            (sha1, author, isotime, message,)
        """
        ph = "h" if short_sha1 else "H"
        git = getattr(self, 'git', 'git')

        log = self.execute_output(
            f'"{git}" log {revision} --pretty=format:"%{ph}---%an---%ad---%s" --date=iso -{n}'
        )

        if not log:
            return None, None, None, None

        logs = log.split("\n")
        logs = list(map(lambda log: tuple(log.split("---")), logs))

        if n == 1:
            return logs[0]
        else:
            return logs

    def current_branch(self) -> str:
        return getattr(self, 'Branch', 'local')

    def current_commit(self) -> str:
        return self.get_commit()

    def latest_commit(self) -> str:
        return self.current_commit()

    def check_update(self) -> bool:
        logger.info("Local mode: check_update bypassed")
        return False

    def execute_pull(self) -> bool:
        logger.info("Local mode: execute_pull bypassed")
        return False
