"""경로 및 설정 관리."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- 프로젝트 경로 -----------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FLOWS_DIR = PROJECT_ROOT / "flows"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
CAPTURES_DIR = PROJECT_ROOT / "captures"
LOGS_DIR = PROJECT_ROOT / "logs"

for _d in (FLOWS_DIR, TEMPLATES_DIR, CAPTURES_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SETTINGS_PATH = PROJECT_ROOT / "settings.json"

# --- BlueStacks 기본 경로 --------------------------------------------------
_DEFAULT_ADB_CANDIDATES = [
    r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
    r"C:\Program Files\BlueStacks\HD-Adb.exe",
    r"C:\Program Files (x86)\BlueStacks_nxt\HD-Adb.exe",
]
_DEFAULT_CONF_CANDIDATES = [
    r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf",
    r"C:\ProgramData\BlueStacks\bluestacks.conf",
]


def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        if Path(p).exists():
            return p
    return None


@dataclass
class Settings:
    adb_path: str | None = field(default_factory=lambda: _first_existing(_DEFAULT_ADB_CANDIDATES))
    bluestacks_conf: str | None = field(
        default_factory=lambda: _first_existing(_DEFAULT_CONF_CANDIDATES)
    )
    adb_server_port: int = 5037
    # 인스턴스 key -> 플로우 파일명 매핑
    instance_flows: dict[str, str] = field(default_factory=dict)
    # 인스턴스 key -> {변수명: 값} — 플로우 시작 시 주입 (텔레포트 대상 등)
    instance_vars: dict[str, dict[str, str]] = field(default_factory=dict)
    # 인스턴스 key -> 감시 간격(초). 없으면 watch_interval_sec 사용 (승인 플로우는 짧게)
    instance_intervals: dict[str, float] = field(default_factory=dict)
    # 감시 루프 주기(초)
    watch_interval_sec: float = 20.0
    template_match_threshold: float = 0.85
    # 데스크톱 알림
    notifications_enabled: bool = True
    # 스케줄러
    schedule_enabled: bool = False
    active_hours: str = ""            # "09:00-23:30" 형식. 이 시간대에만 실행
    periodic_restart_min: int = 0     # N분마다 전체 재시작 (0=끔)
    daily_restart_time: str = ""      # "06:00" — 매일 이 시각에 전체 재시작

    @classmethod
    def load(cls) -> Settings:
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                known = {k: data[k] for k in cls().__dict__ if k in data}
                return cls(**known)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return cls()

    def save(self) -> None:
        SETTINGS_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def resolve_adb(self) -> str:
        if self.adb_path and Path(self.adb_path).exists():
            return self.adb_path
        env = os.environ.get("AAC_ADB_PATH")
        if env and Path(env).exists():
            return env
        found = _first_existing(_DEFAULT_ADB_CANDIDATES)
        if found:
            return found
        # PATH 의 adb 로 폴백
        return "adb"


SETTINGS = Settings.load()
