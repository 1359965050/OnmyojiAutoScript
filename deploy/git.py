# This Python file uses the following encoding: utf-8
# copy from alas https://github.com/LmeSzinc/AzurLaneAutoScript
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

    @staticmethod
    def _has_conflict_markers(text: str) -> bool:
        """检查文本中是否包含 Git 冲突标记。"""
        return any(marker in text for marker in ('<<<<<<<', '=======', '>>>>>>>'))

    def _check_working_tree_conflicts(self) -> list[str]:
        """
        扫描工作区中是否存在未解决的 Git 冲突标记。

        Returns:
            包含冲突标记的文件路径列表。
        """
        conflict_files = []
        for root, _, files in os.walk('.'):
            # 跳过依赖目录和虚拟环境，避免误报
            if any(skip in root for skip in ['.git', 'toolkit', 'node_modules', '.venv', '__pycache__']):
                continue
            for file in files:
                if not file.endswith(('.py', '.json', '.xml', '.yaml', '.yml', '.md', '.dart', '.txt')):
                    continue
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        if self._has_conflict_markers(f.read()):
                            conflict_files.append(path)
                except Exception:
                    continue
        return conflict_files

    def git_repository_init(
            self, repo, source='origin', branch='master',
            proxy='', ssl_verify=True, keep_changes=False
    ):
        logger.hr('Pre-update Check', 1)
        conflict_files = self._check_working_tree_conflicts()
        if conflict_files:
            logger.error('Unresolved Git conflict markers detected, abort update to prevent syntax errors:')
            for path in conflict_files:
                logger.error(f'  {path}')
            logger.error('Please resolve conflicts manually before updating.')
            return

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
        self.execute(f'"{self.git}" fetch {source} {branch}')

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
                    conflict_files = self._check_working_tree_conflicts()
                    if conflict_files:
                        logger.error('Stash pop produced conflicts, abort merge and restore stash to protect local changes:')
                        for path in conflict_files:
                            logger.error(f'  {path}')
                        # Abort the in-progress merge to restore a clean working tree
                        self.execute(f'"{self.git}" merge --abort', allow_failure=True)
                        self.execute(f'"{self.git}" reset --merge', allow_failure=True)
                        logger.warning('Please resolve conflicts manually. The local changes are still in the stash.')
                        return
                    # No local changes to existing files, untracked files not included
                    logger.info('Stash pop failed, there seems to be no local changes, skip instead')
            else:
                logger.warning('Stash failed due to unresolved merges or conflicts, abort update to preserve local changes')
                return
        else:
            logger.info('KeepLocalChanges is disabled, skip pull to protect local modifications')
            logger.info('If you want to force update, please resolve local changes manually first')
            return

        logger.hr('Show Version', 1)
        self.execute(f'"{self.git}" --no-pager log --no-merges -1')

    def git_install(self):
        logger.hr('Update OAS', 0)

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
        )
