"""HD-Adb.exe 래퍼. 자체 adb 서버를 사용해 시스템 adb 와 충돌을 피한다."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from aac.config import SETTINGS

_CREATE_NO_WINDOW = 0x08000000  # Windows: 콘솔창 안 뜨게


@dataclass
class AdbResult:
    ok: bool
    stdout: str
    stderr: str
    code: int


class AdbClient:
    """지정된 adb 실행파일 + 서버 포트로 명령을 실행한다."""

    def __init__(self, adb_path: str | None = None, server_port: int | None = None):
        self.adb_path = adb_path or SETTINGS.resolve_adb()
        self.server_port = server_port or SETTINGS.adb_server_port

    # --- 저수준 실행 ------------------------------------------------------
    def _base(self) -> list[str]:
        return [self.adb_path, "-P", str(self.server_port)]

    def run(
        self,
        args: list[str],
        *,
        serial: str | None = None,
        timeout: float = 15.0,
        binary: bool = False,
    ) -> AdbResult | bytes:
        cmd = self._base()
        if serial:
            cmd += ["-s", serial]
        cmd += args
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                creationflags=_CREATE_NO_WINDOW,
                check=False,
            )
        except subprocess.TimeoutExpired:
            if binary:
                return b""
            return AdbResult(False, "", f"timeout after {timeout}s", -1)
        if binary:
            return proc.stdout
        return AdbResult(
            proc.returncode == 0,
            proc.stdout.decode("utf-8", "replace").strip(),
            proc.stderr.decode("utf-8", "replace").strip(),
            proc.returncode,
        )

    # --- 서버/연결 -------------------------------------------------------
    def start_server(self) -> AdbResult:
        return self.run(["start-server"], timeout=20)

    def connect(self, host_port: str) -> AdbResult:
        return self.run(["connect", host_port], timeout=10)

    def disconnect(self, host_port: str) -> AdbResult:
        return self.run(["disconnect", host_port], timeout=10)

    def devices(self) -> list[str]:
        res = self.run(["devices"])
        if not isinstance(res, AdbResult) or not res.ok:
            return []
        serials: list[str] = []
        for line in res.stdout.splitlines()[1:]:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            serial, state = line.split("\t", 1)
            if state.strip() == "device":
                serials.append(serial.strip())
        return serials
