"""실행 중인 BlueStacks 인스턴스를 조회한다.

전략:
  1) bluestacks.conf 를 파싱해 인스턴스 목록 + 별명 + adb 포트를 얻는다.
  2) psutil 로 HD-Player.exe 프로세스를 찾아 --instance 인자로 '실행 중' 여부를 판단한다.
  3) adb devices 로 실제 연결 가능한 시리얼을 확인한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from aac.adb.client import AdbClient
from aac.config import SETTINGS

_CONF_LINE_RE = re.compile(r'^bst\.instance\.([^.]+)\.([^=]+)="?([^"]*)"?\s*$')


@dataclass
class BlueStacksInstance:
    key: str  # 예: "Nougat64_1"
    display_name: str  # 한글 별명 예: "에분기1"
    adb_port: int | None = None  # 고정 포트 (bst.instance.<k>.adb_port)
    status_adb_port: int | None = None  # 동적 포트 (bst.instance.<k>.status.adb_port)
    running: bool = False
    pid: int | None = None
    serial: str | None = None  # adb 로 연결된 시리얼
    online: bool = False
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.display_name} ({self.key})" if self.display_name else self.key

    def candidate_serials(self) -> list[str]:
        ports: list[int] = []
        for p in (self.status_adb_port, self.adb_port):
            if p and p not in ports:
                ports.append(p)
        return [f"127.0.0.1:{p}" for p in ports]


# --- conf 파싱 -----------------------------------------------------------
def parse_conf(conf_path: str | Path) -> dict[str, BlueStacksInstance]:
    path = Path(conf_path)
    instances: dict[str, BlueStacksInstance] = {}
    if not path.exists():
        return instances
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _CONF_LINE_RE.match(line.strip())
        if not m:
            continue
        key, prop, value = m.group(1), m.group(2), m.group(3)
        inst = instances.setdefault(key, BlueStacksInstance(key=key, display_name=""))
        if prop == "display_name":
            inst.display_name = value
        elif prop == "adb_port":
            inst.adb_port = _to_int(value)
        elif prop == "status.adb_port":
            inst.status_adb_port = _to_int(value)
        else:
            inst.extra[prop] = value
    return instances


def _to_int(v: str) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# --- 프로세스 조회 -----------------------------------------------------
def _running_instances() -> dict[str, int]:
    """{instance_key: pid} — 실행 중인 HD-Player 프로세스."""
    result: dict[str, int] = {}
    try:
        import psutil
    except ImportError:
        return result
    for proc in psutil.process_iter(["name", "pid", "cmdline"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name not in ("hd-player.exe", "bluestacks.exe"):
                continue
            cmdline = proc.info["cmdline"] or []
            key = None
            for i, tok in enumerate(cmdline):
                if tok == "--instance" and i + 1 < len(cmdline):
                    key = cmdline[i + 1]
                    break
                if tok.startswith("--instance="):
                    key = tok.split("=", 1)[1]
                    break
            if key:
                result[key] = proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


# --- 메인 스캔 --------------------------------------------------------
def scan_instances(client: AdbClient | None = None) -> list[BlueStacksInstance]:
    client = client or AdbClient()
    client.start_server()

    conf_path = SETTINGS.bluestacks_conf
    instances = parse_conf(conf_path) if conf_path else {}

    running = _running_instances()
    for key, pid in running.items():
        inst = instances.setdefault(key, BlueStacksInstance(key=key, display_name=""))
        inst.running = True
        inst.pid = pid

    online_serials = set(client.devices())

    for inst in instances.values():
        # 후보 시리얼 중 온라인인 것을 우선 채택
        for serial in inst.candidate_serials():
            if serial in online_serials:
                inst.serial = serial
                inst.online = True
                break
        # 실행 중인데 아직 연결 안 됐으면 connect 시도
        if inst.running and not inst.online:
            for serial in inst.candidate_serials():
                res = client.connect(serial)
                if hasattr(res, "stdout") and (
                    "connected" in res.stdout or "already" in res.stdout
                ):
                    inst.serial = serial
                    inst.online = True
                    break

    # 실행 중인 것 먼저, 그다음 이름순
    return sorted(instances.values(), key=lambda i: (not i.running, i.display_name, i.key))
