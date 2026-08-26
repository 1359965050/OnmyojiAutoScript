import sys
from deploy.patch import pre_checks

pre_checks()

from deploy.adb import AdbManager
from deploy.process import ProcessManager
from deploy.fluentui import FluentuiManager
from deploy.config import ExecutionError
from deploy.git import GitManager
from deploy.pip import PipManager


class Installer(GitManager, PipManager, AdbManager, FluentuiManager, ProcessManager):
    def install(self, force: bool = False):
        try:
            self.git_install()
            self.process_kill()
            self.pip_install(force=force)
            self.adb_install()
        except ExecutionError:
            exit(1)


if __name__ == '__main__':
    force_update = '--force' in sys.argv or '--update' in sys.argv
    Installer().install(force=force_update)

