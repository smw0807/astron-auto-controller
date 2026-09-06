"""엔트리 포인트: `python -m aac` 또는 `aac`."""
from __future__ import annotations


def main() -> int:
    from aac.gui.app import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
