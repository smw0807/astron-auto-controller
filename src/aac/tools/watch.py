"""CLI: 배정된 모든 인스턴스에 대해 감시 루프 실행 (GUI 없이).

settings.json 의 instance_flows 배정을 읽어 온라인 인스턴스에서 무한 실행한다.
Ctrl+C 로 종료.

    python -m aac.tools.watch
    python -m aac.tools.watch --only 물돌 에분기1
"""
from __future__ import annotations

import argparse
import signal

from PySide6.QtCore import QCoreApplication

from aac.bluestacks import scan_instances
from aac.runner import RunnerManager
from aac.tools._console import setup as _console_setup


def main() -> int:
    _console_setup()
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="특정 인스턴스(별명/key)만")
    ap.add_argument("--interval", type=float, default=None)
    args = ap.parse_args()

    app = QCoreApplication([])
    mgr = RunnerManager()
    mgr.log.connect(lambda k, m: print(f"[{k}] {m}", flush=True))

    instances = scan_instances()
    mgr.update_instances(instances)

    def wanted(st) -> bool:
        if not (st.flow_name and st.online):
            return False
        if args.only is None:
            return True
        return any(
            o == st.key or o == st.display_name or o.lower() in st.display_name.lower()
            for o in args.only
        )

    started = [st.key for st in mgr.all_states() if wanted(st) and mgr.start(st.key, args.interval)]
    if not started:
        print("실행할 인스턴스가 없습니다. GUI 대시보드에서 플로우를 배정하세요.")
        return 1
    print(f"감시 시작: {', '.join(started)}  (Ctrl+C 종료)")

    signal.signal(signal.SIGINT, lambda *_: (mgr.shutdown(), app.quit()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
