# This Python file uses the following encoding: utf-8
"""防风控作息看守器: 睡眠窗 / 每日活跃上限 / 强制长休息, 由 Script 持有。"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class AntiBanGuard:
    def __init__(
        self,
        config_name: str | None = None,
        state_file: Path | str | None = None,
    ) -> None:
        self._config_name = (config_name or "").strip()
        if state_file is not None:
            self._state_file: Path | None = Path(state_file)
        elif self._config_name:
            safe_name = self._config_name.replace("/", "_").replace("\\", "_")
            self._state_file = Path("./log/antiban") / f"{safe_name}.json"
        else:
            self._state_file = None
        self.reset(clear_persisted=False)
        self._load()

    def reset(self, clear_persisted: bool = True) -> None:
        self._active_date = None
        self._active_seconds_today = 0.0
        self._rest_until = None
        if clear_persisted:
            self._save()

    def _load(self) -> None:
        if self._state_file is None or not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            date_str = data.get("active_date")
            if date_str:
                self._active_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            self._active_seconds_today = max(0.0, float(data.get("active_seconds_today", 0.0)))
            rest_str = data.get("rest_until")
            self._rest_until = datetime.fromisoformat(rest_str) if rest_str else None
        except Exception:
            pass

    def _save(self) -> None:
        if self._state_file is None:
            return
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "active_date": self._active_date.strftime("%Y-%m-%d") if self._active_date else None,
                "active_seconds_today": float(self._active_seconds_today),
                "rest_until": self._rest_until.isoformat() if self._rest_until else None,
            }
            tmp_path = self._state_file.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp_path, self._state_file)
        except Exception:
            pass

    @staticmethod
    def _in_sleep_window(t, start, end) -> bool:
        if start == end:
            return False
        if start < end:
            return start <= t < end
        return t >= start or t < end

    @staticmethod
    def _next_time_point(now: datetime, end) -> datetime:
        candidate = now.replace(hour=end.hour, minute=end.minute, second=end.second, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _roll_day(self, today) -> bool:
        if self._active_date != today:
            self._active_date = today
            self._active_seconds_today = 0.0
            if self._rest_until is not None and self._rest_until.date() < today:
                self._rest_until = None
            return True
        return False

    def record_active(self, seconds: float, now: datetime | None = None) -> None:
        current = now or datetime.now()
        self._roll_day(current.date())
        self._active_seconds_today += max(0.0, float(seconds))
        self._save()

    def wake_time(self, now: datetime, config):
        if not config.enable:
            return None
        changed = False
        wake = None
        if self._in_sleep_window(now.time(), config.sleep_start, config.sleep_end):
            wake = self._next_time_point(now, config.sleep_end)
        limit = config.daily_active_limit.total_seconds()
        if limit > 0:
            if self._roll_day(now.date()):
                changed = True
            if self._rest_until and now < self._rest_until:
                wake = max(wake, self._rest_until) if wake else self._rest_until
            elif self._active_seconds_today >= limit:
                # 保留当日已累计活跃时长，避免长休息或重启后丧失每日总量上限约束
                next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                if self._rest_until is None or self._rest_until.date() < now.date():
                    rest_end = now + config.long_rest_duration
                    cap_until = max(rest_end, next_midnight)
                    self._rest_until = cap_until
                    changed = True
                elif now >= self._rest_until:
                    self._rest_until = max(self._rest_until, next_midnight)
                    changed = True
                wake = max(wake, self._rest_until) if wake else self._rest_until
        if changed:
            self._save()
        return wake
