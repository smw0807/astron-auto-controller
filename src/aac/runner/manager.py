"""인스턴스별 플로우 실행 관리.

각 BlueStacks 인스턴스(key)에 플로우를 배정하고, 무한 반복(감시 루프)으로 실행한다.
배정은 settings.json(instance_flows)에 저장된다.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from aac.bluestacks import BlueStacksInstance
from aac.config import SETTINGS
from aac.flow import Flow
from aac.runner.thread import RunnerThread


@dataclass
class RunnerState:
    key: str
    display_name: str = ""
    flow_name: str = ""
    status: str = "정지"  # 정지 / 실행중 / 정지중 / 오류
    iterations: int = 0
    serial: str | None = None
    online: bool = False


class RunnerManager(QObject):
    status_changed = Signal(str)          # key
    log = Signal(str, str)                # key, message
    notify = Signal(str, str, str, str)   # key, title, message, level

    def __init__(self, parent=None):
        super().__init__(parent)
        self._threads: dict[str, RunnerThread] = {}
        self._states: dict[str, RunnerState] = {}
        # 저장된 배정 복원
        for key, flow_name in SETTINGS.instance_flows.items():
            self._states[key] = RunnerState(key=key, flow_name=flow_name)

    # --- 상태 조회 --------------------------------------------
    def state(self, key: str) -> RunnerState:
        return self._states.setdefault(key, RunnerState(key=key))

    def all_states(self) -> list[RunnerState]:
        return list(self._states.values())

    def is_running(self, key: str) -> bool:
        t = self._threads.get(key)
        return bool(t and t.isRunning())

    # --- 인스턴스 목록 갱신 ----------------------------------
    def update_instances(self, instances: list[BlueStacksInstance]) -> None:
        by_key = {i.key: i for i in instances}
        # 새로 발견된 인스턴스 상태 등록
        for i in instances:
            st = self._states.setdefault(i.key, RunnerState(key=i.key))
            st.display_name = i.display_name
            st.serial = i.serial
            st.online = i.online
        # 사라진/오프라인 인스턴스 처리
        for key, st in self._states.items():
            if key not in by_key:
                st.serial = None
                st.online = False
            if not st.online and self.is_running(key):
                self.log.emit(key, "[경고] 인스턴스 오프라인 — 중지")
                self.stop(key)

    # --- 배정 -----------------------------------------------
    def assign(self, key: str, flow_name: str) -> None:
        self.state(key).flow_name = flow_name
        if flow_name:
            SETTINGS.instance_flows[key] = flow_name
        else:
            SETTINGS.instance_flows.pop(key, None)
        SETTINGS.save()
        self.status_changed.emit(key)

    # --- 실행 / 정지 ---------------------------------------
    def start(self, key: str, interval_s: float | None = None) -> bool:
        if self.is_running(key):
            return True
        st = self.state(key)
        if not st.online or not st.serial:
            self.log.emit(key, "[오류] 온라인 인스턴스가 아님")
            return False
        if not st.flow_name:
            self.log.emit(key, "[오류] 배정된 플로우 없음")
            return False
        try:
            flow = Flow.load_by_name(st.flow_name)
        except (FileNotFoundError, ValueError) as exc:
            self.log.emit(key, f"[오류] 플로우 로드 실패: {exc}")
            return False

        interval = SETTINGS.watch_interval_sec if interval_s is None else interval_s
        t = RunnerThread(st.serial, flow, repeat=-1, interval_s=interval,
                         init_vars=SETTINGS.instance_vars.get(key, {}))
        t.log.connect(lambda m, k=key: self.log.emit(k, m))
        t.iteration.connect(lambda n, k=key: self._on_iteration(k, n))
        t.notify.connect(
            lambda title, msg, lv, k=key: self.notify.emit(k, title, msg, lv)
        )
        t.finished_ok.connect(lambda ok, k=key: self._on_finished(k, ok))
        self._threads[key] = t
        st.status = "실행중"
        st.iterations = 0
        t.start()
        self.log.emit(key, f"▶ 시작: {st.flow_name} (간격 {interval:.0f}s)")
        self.status_changed.emit(key)
        return True

    def stop(self, key: str) -> None:
        t = self._threads.get(key)
        if not t:
            return
        t.stop()
        self.state(key).status = "정지중"
        self.status_changed.emit(key)

    def start_all(self, interval_s: float | None = None) -> None:
        for st in self._states.values():
            if st.flow_name and st.online:
                self.start(st.key, interval_s)

    def stop_all(self) -> None:
        for key in list(self._threads):
            self.stop(key)

    def shutdown(self) -> None:
        for t in self._threads.values():
            t.stop()
        for t in self._threads.values():
            t.wait(4000)

    # --- 콜백 ---------------------------------------------
    def _on_iteration(self, key: str, n: int) -> None:
        self.state(key).iterations = n
        self.status_changed.emit(key)

    def _on_finished(self, key: str, ok: bool) -> None:
        st = self.state(key)
        was_running = st.status == "실행중"
        st.status = "정지"
        self._threads.pop(key, None)
        self.log.emit(key, f"■ 종료 ({'정상' if ok else '중단/오류'})")
        # 사용자가 정지를 누르지 않았는데 멈췄으면(=플로우가 STOP 반환) 알림
        if was_running and not ok:
            name = st.display_name or key
            self.notify.emit(key, "감시 중단됨", f"{name}: 플로우가 예기치 않게 종료", "error")
        self.status_changed.emit(key)
