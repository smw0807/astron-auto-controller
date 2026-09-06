"""CLI: 플로우를 인스턴스에 대해 1회 실행.

    python -m aac.tools.flow <플로우이름> <인스턴스별명>
    python -m aac.tools.flow 자동사냥루프 물돌 --repeat 5 --interval 20
"""
from __future__ import annotations

import argparse

from aac.adb import AdbClient, Device
from aac.bluestacks import scan_instances
from aac.config import SETTINGS
from aac.flow import Flow, FlowEngine, StopToken
from aac.tools._console import setup as _console_setup

_SCAN_CACHE: list = []


def _scan() -> list:
    if not _SCAN_CACHE:
        _SCAN_CACHE.extend(scan_instances())
    return _SCAN_CACHE


def _resolve_serial(name: str) -> str | None:
    for i in _scan():
        if name in (i.key, i.display_name) and i.online and i.serial:
            return i.serial
    return None


def _key_of(name: str) -> str:
    for i in _scan():
        if name in (i.key, i.display_name):
            return i.key
    return name


def main() -> int:
    _console_setup()
    ap = argparse.ArgumentParser()
    ap.add_argument("flow")
    ap.add_argument("instance")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--interval", type=float, default=15.0, help="반복 간 대기(초)")
    ap.add_argument("--var", action="append", default=[], metavar="NAME=VALUE",
                    help="플로우 변수 주입 (여러 번 가능). settings.json 의 instance_vars 보다 우선")
    args = ap.parse_args()

    init_vars = dict(SETTINGS.instance_vars.get(_key_of(args.instance), {}))
    for pair in args.var:
        if "=" in pair:
            k, v = pair.split("=", 1)
            init_vars[k.strip()] = v.strip()

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
        n = 0
        while args.repeat < 0 or n < args.repeat:
            n += 1
            if args.repeat != 1:
                tag = "무한" if args.repeat < 0 else f"{n}/{args.repeat}"
                print(f"--- 반복 {tag} ---")
            FlowEngine(dev, print, stop, init_vars=init_vars).run(flow)
            if args.repeat < 0 or n < args.repeat:
                stop.sleep(args.interval)
    except KeyboardInterrupt:
        stop.stop()
        print("중단")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
