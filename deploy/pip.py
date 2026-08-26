import hashlib
from pathlib import Path
from urllib.parse import urlparse

from deploy.config import DeployConfig
from deploy.logger import logger
from deploy.utils import *


class PipManager(DeployConfig):
    @cached_property
    def python(self):
        return self.filepath("PythonExecutable")

    @cached_property
    def requirements_file(self):
        if self.RequirementsFile == 'requirements.txt':
            return 'requirements.txt'
        else:
            return self.filepath("RequirementsFile")

    @cached_property
    def pip(self):
        return f'"{self.python}" -m pip'

    def _get_requirements_hash(self) -> str:
        req_file = self.requirements_file
        if not os.path.exists(req_file):
            return ""
        try:
            with open(req_file, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def pip_install(self, force: bool = False):
        if not self.InstallDependencies:
            logger.info('InstallDependencies is disabled, skip')
            return

        hash_file = Path('config/.requirements_hash')
        current_hash = self._get_requirements_hash()

        if not force and current_hash and hash_file.exists():
            try:
                saved_hash = hash_file.read_text(encoding='utf-8').strip()
                if saved_hash == current_hash:
                    logger.info('Dependencies are up to date (hash matched), skipping pip install.')
                    return
            except Exception:
                pass

        logger.hr('Update Dependencies', 0)
        logger.hr('Check Python', 1)
        self.execute(f'"{self.python}" --version')

        arg = []
        if self.PypiMirror:
            mirror = self.PypiMirror
            arg += ['-i', mirror]
            # Trust http mirror or skip ssl verify
            if 'http:' in mirror or not self.SSLVerify:
                arg += ['--trusted-host', urlparse(mirror).hostname]
        elif not self.SSLVerify:
            arg += ['--trusted-host', 'pypi.org']
            arg += ['--trusted-host', 'files.pythonhosted.org']

        # Don't update pip, just leave it.
        # logger.hr('Update pip', 1)
        # self.execute(f'"{self.pip}" install --upgrade pip{arg}')
        arg += ['--disable-pip-version-check']

        logger.hr('Update Dependencies', 1)
        arg = ' ' + ' '.join(arg) if arg else ''
        self.execute(f'{self.pip} install -r {self.requirements_file}{arg}')

        # Save hash on success
        if current_hash:
            try:
                hash_file.parent.mkdir(parents=True, exist_ok=True)
                hash_file.write_text(current_hash, encoding='utf-8')
            except Exception as e:
                logger.warning(f'Failed to write requirements hash: {e}')

