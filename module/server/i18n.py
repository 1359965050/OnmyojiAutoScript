import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import List, Optional

from module.logger import logger


class Addition:
    @classmethod
    def load_additions(cls) -> dict:
        """Load additional translations from the backend-managed i18n directory.

        zh-CN is always read from the generated runtime file so that it matches
        the single source of truth (i18n_cn.dart). en-US is optional and falls
        back to an empty map when the generated file is absent.
        """
        result = {}
        i18n_dir = Path.cwd() / 'module' / 'config' / 'i18n'
        files = ['zh-CN', 'en-US']
        for file in files:
            file_path = i18n_dir / f'{file}.json'
            result[file] = {}
            if not file_path.exists():
                continue
            try:
                with open(str(file_path), 'r', encoding='utf-8') as f:
                    result[file] = json.load(f)
            except Exception as e:
                result[file] = {}
        return result


class I18n(Addition):
    file_zh_cn = Path.cwd() / 'module' / 'config' / 'i18n' / 'zh-CN.json'

    @classmethod
    def trans_zh_cn(cls, text) -> str:
        cn_zh_data = cls.load_zh_cn()
        return cn_zh_data[text] if text in cn_zh_data else text

    @classmethod
    def save_zh_cn(cls, data) -> None:
        """Persist Chinese translations without runtime overrides.

        The single source of truth is OASX-master/lib/config/translation/i18n_cn.dart
        and the generated module/config/i18n/zh-CN.json. This method only writes
        the data it receives; it must not inject hard-coded keys.
        """
        I18n.file_zh_cn.parent.mkdir(parents=True, exist_ok=True)
        with open(str(I18n.file_zh_cn), 'w', encoding='utf-8') as f:
            s = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=str)
            f.write(s)

    @classmethod
    def _candidate_cache_dirs(cls) -> List[Path]:
        """Return possible Flutter application cache directories on Windows.

        path_provider's getApplicationCacheDirectory() on Windows maps to
        %LOCALAPPDATA%/<CompanyName>/<ProductName>/cache for desktop builds.
        For OASX the resource info is CompanyName="com.oas", ProductName="oasx",
        so the real path is ``.../com.oas/oasx/cache``. We list the known paths
        plus loose globs so repackaged builds are still found.
        """
        candidates: List[Path] = []
        local_app_data = os.environ.get('LOCALAPPDATA')
        if not local_app_data:
            return candidates

        base = Path(local_app_data)
        for app_name in ['oasx', 'OASX', 'OnmyojiAutoScript']:
            candidates.append(base / app_name / 'cache')

        # Known Windows desktop build layout: <CompanyName>/<ProductName>/cache.
        candidates.append(base / 'com.oas' / 'oasx' / 'cache')

        # Loose match for variants such as "OASX_<version>", package IDs, or
        # other company names that still use "oasx" as the product name.
        try:
            for matched in base.glob('*oasx*/cache'):
                if matched not in candidates:
                    candidates.append(matched)
            for matched in base.glob('*Onmyoji*/cache'):
                if matched not in candidates:
                    candidates.append(matched)
            for matched in base.glob('*/oasx/cache'):
                if matched not in candidates:
                    candidates.append(matched)
            for matched in base.glob('com.*/oasx/cache'):
                if matched not in candidates:
                    candidates.append(matched)
        except Exception:
            pass

        return candidates

    @classmethod
    def _find_frontend_cache_dir(cls) -> Optional[Path]:
        """Locate the OASX frontend cache directory.

        Prefer a directory that already contains i18n files (the frontend has
        run and created it). If none exists, fall back to an application cache
        directory that already exists or looks like the right one, so the sync
        can create the i18n sub-directory on first run.
        """
        candidates = cls._candidate_cache_dirs()

        # 1. Directory that already has i18n files written by the frontend.
        for cache_dir in candidates:
            i18n_dir = cache_dir / 'i18n'
            if i18n_dir.exists() and any(i18n_dir.iterdir()):
                return i18n_dir

        # 2. Existing cache directory (frontend created it but no i18n yet).
        for cache_dir in candidates:
            if cache_dir.exists():
                return cache_dir / 'i18n'

        # 3. Existing app directory with a known marker (e.g. logs) but no
        # cache sub-directory yet. Create the cache/i18n path on sync.
        for cache_dir in candidates:
            app_dir = cache_dir.parent
            if app_dir.exists() and any(app_dir.iterdir()):
                return cache_dir / 'i18n'

        return None

    @classmethod
    def sync_to_frontend_cache(cls) -> None:
        """Copy the latest generated translations to the frontend cache directory.

        This lets OASX pick up new translations without restarting, because
        LocaleService watches the cache directory for changes.
        """
        i18n_dir = Path.cwd() / 'module' / 'config' / 'i18n'
        target_dir = cls._find_frontend_cache_dir()
        if target_dir is None:
            logger.warning(
                'Could not locate OASX frontend cache directory; '
                'translations will be served through the API instead.'
            )
            return

        target_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        for file_name in ['zh-CN.json', 'en-US.json']:
            source = i18n_dir / file_name
            if not source.exists():
                continue
            try:
                target = target_dir / file_name
                target.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
                copied.append(file_name)
            except Exception as e:
                logger.warning(f'Failed to sync translation to frontend cache: {file_name}: {e}')
        if copied:
            logger.info(f'Synced translations to frontend cache: {target_dir} ({", ".join(copied)})')

    # ------------------------------------------------------------------
    # Background watcher: keep the frontend cache in sync when the
    # generated translation files change at runtime (e.g. user edits
    # i18n_cn.dart and runs i18n_sync.py while the backend is running).
    # ------------------------------------------------------------------
    _watch_stop_event: Optional[threading.Event] = None
    _watch_thread: Optional[threading.Thread] = None

    @classmethod
    def _file_hash(cls, path: Path) -> str:
        """Return a hex SHA-256 of the file, or an empty string if unreadable."""
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return ''

    @classmethod
    def _watch_loop(cls, interval: int) -> None:
        """Poll the generated zh-CN.json and sync to frontend cache on change."""
        source = I18n.file_zh_cn
        previous_hash = cls._file_hash(source)
        while cls._watch_stop_event and not cls._watch_stop_event.is_set():
            try:
                time.sleep(interval)
                current_hash = cls._file_hash(source)
                if current_hash and current_hash != previous_hash:
                    previous_hash = current_hash
                    logger.info('Detected translation file change; syncing to frontend cache.')
                    cls.sync_to_frontend_cache()
            except Exception as e:
                logger.warning(f'Translation watcher error: {e}')

    @classmethod
    def start_watching(cls, interval: int = 30) -> None:
        """Start a daemon thread that syncs translations when they change.

        The initial sync is performed immediately so the frontend cache is up
        to date before the first polling interval elapses.
        """
        if cls._watch_thread is not None and cls._watch_thread.is_alive():
            return
        cls.sync_to_frontend_cache()
        cls._watch_stop_event = threading.Event()
        cls._watch_thread = threading.Thread(
            target=cls._watch_loop,
            args=(interval,),
            daemon=True,
            name='i18n-sync-watcher',
        )
        cls._watch_thread.start()
        logger.info(f'Started translation file watcher (interval={interval}s).')

    @classmethod
    def stop_watching(cls) -> None:
        """Stop the background translation watcher."""
        if cls._watch_stop_event is not None:
            cls._watch_stop_event.set()
        cls._watch_thread = None

    @classmethod
    def load_zh_cn(cls) -> dict:
        if not I18n.file_zh_cn.exists():
            return {}
        with open(str(I18n.file_zh_cn), 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == '__main__':
    print(I18n.load_zh_cn())
