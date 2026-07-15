# This Python file uses the following encoding: utf-8
# copy from alas https://github.com/LmeSzinc/AzurLaneAutoScript
import subprocess

from deploy.config import DeployConfig
from deploy.logger import logger
from deploy.utils import *


class GitManager(DeployConfig):
    @cached_property
    def git(self):
        return self.filepath('GitExecutable')

    @staticmethod
    def remove(file):
        try:
            os.remove(file)
            logger.info(f'Removed file: {file}')
        except FileNotFoundError:
            logger.info(f'File not found: {file}')

    def _git_revision(self, ref: str, timeout: int = 10) -> str | None:
        """
        获取指定 Git 引用的完整 SHA1。

        Returns:
            str: 完整 commit hash，失败时返回 None。
        """
        command = f'"{self.git}" rev-parse {ref}'
        command = command.replace(r"\\", "/").replace("\\", "/").replace('"', '"')
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.warning(f"Failed to get git revision for {ref}: {e}")
            return None

    def _git_fetch_with_timeout(self, source='origin', branch='master', timeout=3):
        """
        带超时的 git fetch，避免网络不可达时长时间阻塞。

        Returns:
            bool: True if fetch success, False if timeout or failed.
        """
        command = f'"{self.git}" fetch {source} {branch}'
        command = command.replace(r"\\", "/").replace("\\", "/").replace('"', '"')
        logger.info(command)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                logger.info('[ success ]')
                return True
            logger.info(f'[ allowed failure ], error_code: {result.returncode}')
            if result.stderr:
                logger.info(result.stderr.strip())
            return False
        except subprocess.TimeoutExpired:
            logger.info(f'[ timeout ] git fetch exceeded {timeout}s, skip network update')
            return False
        except Exception as e:
            logger.info(f'[ allowed failure ], error: {e}')
            return False

    def _git_pull_with_timeout(self, source='origin', branch='master', timeout=3):
        """
        带超时的 git pull，避免网络不可达时长时间阻塞。

        Returns:
            bool: True if pull success, False if timeout or failed.
        """
        command = f'"{self.git}" pull --ff-only {source} {branch}'
        command = command.replace(r"\\", "/").replace("\\", "/").replace('"', '"')
        logger.info(command)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                logger.info('[ success ]')
                return True
            logger.info(f'[ allowed failure ], error_code: {result.returncode}')
            if result.stderr:
                logger.info(result.stderr.strip())
            return False
        except subprocess.TimeoutExpired:
            logger.info(f'[ timeout ] git pull exceeded {timeout}s, skip network update')
            return False
        except Exception as e:
            logger.info(f'[ allowed failure ], error: {e}')
            return False

    def git_repository_init(
            self, repo, source='origin', branch='master',
            proxy='', ssl_verify=True, keep_changes=False, mirror=None
    ):
        if mirror:
            repo = f"{mirror.rstrip('/')}/{repo}"
            logger.info(f'Using GitHub mirror: {mirror}')
        logger.hr('Git Init', 1)
        if not self.execute(f'"{self.git}" init', allow_failure=True):
            self.remove('./.git/config')
            self.remove('./.git/index')
            self.remove('./.git/HEAD')
            self.execute(f'"{self.git}" init')

        logger.hr('Set Git Proxy', 1)
        if proxy:
            self.execute(f'"{self.git}" config --local http.proxy {proxy}')
            self.execute(f'"{self.git}" config --local https.proxy {proxy}')
        else:
            self.execute(f'"{self.git}" config --local --unset http.proxy', allow_failure=True)
            self.execute(f'"{self.git}" config --local --unset https.proxy', allow_failure=True)

        if ssl_verify:
            self.execute(f'"{self.git}" config --local http.sslVerify true', allow_failure=True)
        else:
            self.execute(f'"{self.git}" config --local http.sslVerify false', allow_failure=True)

        logger.hr('Set Git Repository', 1)
        if not self.execute(f'"{self.git}" remote set-url {source} {repo}', allow_failure=True):
            self.execute(f'"{self.git}" remote add {source} {repo}')

        logger.hr('Fetch Repository Branch', 1)
        fetch_success = self._git_fetch_with_timeout(source, branch, timeout=3)

        logger.hr('Check Version', 1)
        local_commit = self._git_revision('HEAD')
        remote_commit = self._git_revision(f'{source}/{branch}') if fetch_success else None

        if not remote_commit:
            if local_commit:
                logger.warning(
                    f'Cannot reach remote repository, using local version ({local_commit[:8]}), skip update'
                )
                logger.hr('Show Version', 1)
                self.execute(f'"{self.git}" --no-pager log --no-merges -1', allow_failure=True)
                return
            else:
                logger.error('No local code available and cannot fetch remote repository')
                self.show_error(f'"{self.git}" fetch {source} {branch}')
                raise ExecutionError

        if local_commit and local_commit == remote_commit:
            logger.info(f'Local version equals remote version ({local_commit[:8]}), skip update')
            logger.hr('Show Version', 1)
            self.execute(f'"{self.git}" --no-pager log --no-merges -1')
            return

        logger.hr('Pull Repository Branch', 1)
        # Remove git lock
        for lock_file in [
            './.git/index.lock',
            './.git/HEAD.lock',
            './.git/refs/heads/master.lock',
        ]:
            if os.path.exists(lock_file):
                logger.info(f'Lock file {lock_file} exists, removing')
                os.remove(lock_file)
        if keep_changes:
            if self.execute(f'"{self.git}" stash', allow_failure=True):
                self._git_pull_with_timeout(source, branch, timeout=3)
                if self.execute(f'"{self.git}" stash pop', allow_failure=True):
                    pass
                else:
                    # No local changes to existing files, untracked files not included
                    logger.info('Stash pop failed, there seems to be no local changes, skip instead')
            else:
                logger.info('Stash failed, this may be the first installation, drop changes instead')
                self.execute(f'"{self.git}" reset --hard {source}/{branch}')
                self._git_pull_with_timeout(source, branch, timeout=3)
        else:
            self.execute(f'"{self.git}" reset --hard {source}/{branch}')
            self._git_pull_with_timeout(source, branch, timeout=3)

        logger.hr('Show Version', 1)
        self.execute(f'"{self.git}" --no-pager log --no-merges -1')

    def git_install(self):
        logger.hr('Update Alas', 0)

        if not self.AutoUpdate:
            logger.info('AutoUpdate is disabled, skip')
            return

        self.git_repository_init(
            repo=self.Repository,
            source='origin',
            branch=self.Branch,
            proxy=self.GitProxy,
            ssl_verify=self.SSLVerify,
            keep_changes=self.KeepLocalChanges,
            mirror=self.GitMirror,
        )
