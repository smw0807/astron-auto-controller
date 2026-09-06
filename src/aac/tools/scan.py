"""CLI: 실행 중인 BlueStacks 인스턴스 조회.

    python -m aac.tools.scan
"""
from __future__ import annotations

from aac.bluestacks import scan_instances
from aac.config import SETTINGS


def main() -> int:
    print(f"adb      : {SETTINGS.resolve_adb()}")
    print(f"conf     : {SETTINGS.bluestacks_conf}")
    print("-" * 72)
    instances = scan_instances()
    if not instances:
        print("인스턴스를 찾지 못했습니다. BlueStacks 가 실행 중인지 확인하세요.")
        return 1
    hdr = f"{'별명':<12} {'key':<14} {'실행':<5} {'연결':<5} {'시리얼':<22} {'PID'}"
    print(hdr)
    print("-" * 72)
    for i in instances:
        print(
            f"{i.display_name:<12} {i.key:<14} "
            f"{'O' if i.running else '-':<5} {'O' if i.online else '-':<5} "
            f"{(i.serial or ''):<22} {i.pid or ''}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
