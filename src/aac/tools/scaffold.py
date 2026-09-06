"""CLI: 복합 이벤트 스켈레톤 플로우를 flows/ 에 생성.

    python -m aac.tools.scaffold          # 없는 것만 생성
    python -m aac.tools.scaffold --force  # 덮어쓰기
"""
from __future__ import annotations

import argparse

from aac.flow.events import scaffold_all
from aac.tools._console import setup as _console_setup


def main() -> int:
    _console_setup()
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    created = scaffold_all(overwrite=args.force)
    if created:
        print("생성됨:", ", ".join(created))
    else:
        print("생성할 항목 없음 (이미 존재). --force 로 덮어쓰기")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
