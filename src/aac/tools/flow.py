"""CLI: 플로우를 인스턴스에 대해 1회 실행.

    python -m aac.tools.flow <플로우이름> <인스턴스별명>
    python -m aac.tools.flow 자동사냥루프 물돌 --repeat 5 --interval 20
"""
from __future__ import annotations

import argparse
import time

from aac.adb import AdbClient, Device
from aac.bluestacks import scan_instances
from aac.flow import Flow, FlowEngine, StopToken
from aac.tools._console import setup as _console_setup


def _resolve_serial(name: str) -> str | None:
    for i in scan_instances():
        if name in (i.key, i.display_name) and i.online and i.serial:
            return i.serial
    return None


def main() -> int:
    _console_setup()
    ap = argparse.ArgumentParser()
    ap.add_argument("flow")
    ap.add_argument("instance")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--interval", type=float, default=15.0, help="반복 간 대기(초)")
    args = ap.parse_args()

    serial = _resolve_serial(args.instance)
    if not serial:
        print(f"온라인 인스턴스 '{args.instance}' 없음")
        return 1
    try:
        flow = Flow.load_by_name(args.flow)
    except FileNotFoundError:
        print(f"플로우 '{args.flow}' 없음. python -m aac.tools.scaffold 로 생성 가능")
        return 1

    dev = Device(serial=serial, client=AdbClient())
    dev.connect()
    stop = StopToken()

    try:
        for n in range(args.repeat):
            if args.repeat > 1:
                print(f"--- 반복 {n + 1}/{args.repeat} ---")
            FlowEngine(dev, print, stop).run(flow)
            if n + 1 < args.repeat:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        stop.stop()
        print("중단")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
