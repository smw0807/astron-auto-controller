"""CLI: 특정 인스턴스 스크린샷 저장 / 좌표 탭 테스트.

    python -m aac.tools.shoot <별명 또는 key>            # 스크린샷 저장
    python -m aac.tools.shoot <별명 또는 key> --tap 0.5 0.9
"""
from __future__ import annotations

import argparse
import time

from aac.adb import AdbClient, Device
from aac.bluestacks import scan_instances
from aac.config import CAPTURES_DIR
from aac.tools._console import setup as _console_setup


def _resolve(name: str):
    for i in scan_instances():
        if name in (i.key, i.display_name) and i.online and i.serial:
            return i
    return None


def main() -> int:
    _console_setup()
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--tap", nargs=2, type=float, metavar=("NX", "NY"))
    args = ap.parse_args()

    inst = _resolve(args.name)
    if not inst:
        print(f"'{args.name}' 온라인 인스턴스를 찾지 못함")
        return 1

    dev = Device(serial=inst.serial, client=AdbClient())
    dev.connect()
    print(f"{inst.label}  serial={inst.serial}  size={dev.size}")

    if args.tap:
        dev.tap(args.tap[0], args.tap[1])
        print(f"tap {args.tap} -> px {dev.to_px(*args.tap)}")
        return 0

    img = dev.screenshot()
    if img is None:
        print("스크린샷 실패")
        return 1
    import cv2

    out = CAPTURES_DIR / f"{inst.key}_{int(time.time())}.png"
    cv2.imwrite(str(out), img)
    print(f"저장: {out}  ({img.shape[1]}x{img.shape[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
