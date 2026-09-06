"""플로우 편집 + 실행 위젯 (트리 기반)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aac.flow import Flow, Step
from aac.flow.events import scaffold_all
from aac.flow.registry import get_step_spec, step_spec_list
from aac.gui.param_form import ParamForm
from aac.runner import RunnerThread

ROLE_STEP = Qt.UserRole
ROLE_ELSE = Qt.UserRole + 1


class FlowEditor(QWidget):
    request_instances = Signal()  # 메인창에 인스턴스 목록 갱신 요청

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flow: Flow | None = None
        self._run: RunnerThread | None = None
        self._instances: list = []  # BlueStacksInstance

        # --- 상단: 플로우 선택 ---
        self.flow_combo = QComboBox()
        self.flow_combo.currentTextChanged.connect(self._load_selected)
        self.new_btn = QPushButton("새로")
        self.new_btn.clicked.connect(self._new_flow)
        self.save_btn = QPushButton("저장")
        self.save_btn.clicked.connect(self._save)
        self.scaffold_btn = QPushButton("이벤트 스켈레톤 생성")
        self.scaffold_btn.clicked.connect(self._scaffold)
        self.json_btn = QPushButton("JSON")
        self.json_btn.clicked.connect(self._edit_json)
        self.reload_btn = QPushButton("↻")
        self.reload_btn.setFixedWidth(28)
        self.reload_btn.clicked.connect(self.refresh_flow_list)

        top = QHBoxLayout()
        top.addWidget(QLabel("플로우"))
        top.addWidget(self.flow_combo, 1)
        top.addWidget(self.reload_btn)
        top.addWidget(self.new_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.json_btn)
        top.addWidget(self.scaffold_btn)

        # --- 좌: 트리 + 툴바 ---
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["스텝"])
        self.tree.setColumnCount(1)
        self.tree.currentItemChanged.connect(self._on_tree_select)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)

        self.add_btn = QPushButton("＋ 스텝")
        self.add_btn.clicked.connect(self._show_add_menu)
        self.del_btn = QPushButton("삭제")
        self.del_btn.clicked.connect(self._delete_current)
        self.up_btn = QPushButton("▲")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = QPushButton("▼")
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.indent_btn = QPushButton("→ 들여쓰기")
        self.indent_btn.clicked.connect(self._indent)
        self.outdent_btn = QPushButton("← 내어쓰기")
        self.outdent_btn.clicked.connect(self._outdent)
        self.dup_btn = QPushButton("복제")
        self.dup_btn.clicked.connect(self._duplicate)

        tb = QHBoxLayout()
        for b in (self.add_btn, self.del_btn, self.dup_btn, self.up_btn, self.down_btn,
                  self.indent_btn, self.outdent_btn):
            tb.addWidget(b)
        tb.addStretch(1)

        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(2, 2, 2, 2)
        llay.addLayout(tb)
        llay.addWidget(self.tree)

        # --- 우: 속성 폼 ---
        self.form = ParamForm()
        self.form.changed.connect(self._on_param_changed)
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(2, 2, 2, 2)
        rlay.addWidget(QLabel("스텝 속성"))
        rlay.addWidget(self.form)
        rlay.addStretch(1)

        mid_split = QSplitter(Qt.Horizontal)
        mid_split.addWidget(left)
        mid_split.addWidget(right)
        mid_split.setSizes([560, 380])

        # --- 하단: 실행 컨트롤 + 로그 ---
        self.instance_combo = QComboBox()
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(-1, 9999)
        self.repeat_spin.setValue(1)
        self.repeat_spin.setToolTip("-1 = 무한 반복")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 3600)
        self.interval_spin.setValue(15)
        self.interval_spin.setSuffix(" s")
        self.run_btn = QPushButton("▶ 실행")
        self.run_btn.clicked.connect(self._toggle_run)

        run_bar = QHBoxLayout()
        run_bar.addWidget(QLabel("대상"))
        run_bar.addWidget(self.instance_combo, 1)
        run_bar.addWidget(QLabel("반복"))
        run_bar.addWidget(self.repeat_spin)
        run_bar.addWidget(QLabel("간격"))
        run_bar.addWidget(self.interval_spin)
        run_bar.addWidget(self.run_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setFixedHeight(160)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addLayout(top)
        outer.addWidget(mid_split, 1)
        outer.addLayout(run_bar)
        outer.addWidget(QLabel("실행 로그"))
        outer.addWidget(self.log)

        self.refresh_flow_list()

    # ============ 인스턴스 목록 (메인창이 주입) ============
    def set_instances(self, instances: list) -> None:
        self._instances = instances
        cur = self.instance_combo.currentText()
        self.instance_combo.clear()
        for i in instances:
            if i.online and i.serial:
                self.instance_combo.addItem(f"{i.display_name} ({i.key})", i.serial)
        idx = self.instance_combo.findText(cur)
        if idx >= 0:
            self.instance_combo.setCurrentIndex(idx)

    # ============ 플로우 목록/로드/저장 ============
    def refresh_flow_list(self) -> None:
        cur = self.flow_combo.currentText()
        self.flow_combo.blockSignals(True)
        self.flow_combo.clear()
        self.flow_combo.addItems(Flow.list_saved())
        if cur:
            i = self.flow_combo.findText(cur)
            if i >= 0:
                self.flow_combo.setCurrentIndex(i)
        self.flow_combo.blockSignals(False)
        self._load_selected(self.flow_combo.currentText())

    def _load_selected(self, name: str) -> None:
        if not name:
            self._flow = None
            self.tree.clear()
            return
        try:
            self._flow = Flow.load_by_name(name)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.warning(self, "로드 실패", str(exc))
            return
        self._rebuild_tree()

    def _new_flow(self) -> None:
        name, ok = QInputDialog.getText(self, "새 플로우", "이름:")
        if not ok or not name.strip():
            return
        self._flow = Flow(name=name.strip(), steps=[Step("log", {"message": "시작"})])
        self._flow.save()
        self.refresh_flow_list()
        self.flow_combo.setCurrentText(name.strip())

    def _save(self) -> None:
        if self._flow is None:
            return
        self._commit_tree_to_model()
        path = self._flow.save()
        self._log(f"저장: {path}")

    def _scaffold(self) -> None:
        created = scaffold_all(overwrite=False)
        self.refresh_flow_list()
        msg = "생성: " + ", ".join(created) if created else "이미 모두 존재"
        QMessageBox.information(self, "이벤트 스켈레톤", msg)

    # ============ 트리 <-> 모델 ============
    def _rebuild_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        if self._flow:
            for s in self._flow.steps:
                self._add_item(self.tree.invisibleRootItem(), s)
        self.tree.expandAll()
        self.tree.blockSignals(False)

    def _add_item(self, parent: QTreeWidgetItem, step: Step) -> QTreeWidgetItem:
        it = QTreeWidgetItem([self._summary(step)])
        it.setData(0, ROLE_STEP, step)
        if not step.enabled:
            it.setForeground(0, Qt.gray)
        parent.addChild(it)
        spec = get_step_spec(step.type)
        if spec and spec.has_children:
            for c in step.children:
                self._add_item(it, c)
        if spec and spec.has_else:
            else_it = QTreeWidgetItem(["── 아니면(ELSE) ──"])
            else_it.setData(0, ROLE_ELSE, True)
            else_it.setForeground(0, Qt.darkCyan)
            it.addChild(else_it)
            for c in step.else_children:
                self._add_item(else_it, c)
        return it

    def _summary(self, step: Step) -> str:
        spec = get_step_spec(step.type)
        base = spec.summary(step.params) if spec else step.type
        if step.note:
            base += f"   — {step.note.splitlines()[0]}"
        if not step.enabled:
            base = f"(꺼짐) {base}"
        return base

    def _commit_tree_to_model(self) -> None:
        if self._flow is None:
            return
        children, _ = self._collect(self.tree.invisibleRootItem())
        self._flow.steps = children

    def _collect(self, parent_item: QTreeWidgetItem) -> tuple[list[Step], list[Step]]:
        children: list[Step] = []
        else_list: list[Step] = []
        for i in range(parent_item.childCount()):
            it = parent_item.child(i)
            if it.data(0, ROLE_ELSE):
                sub, _ = self._collect(it)
                else_list = sub
                continue
            step: Step = it.data(0, ROLE_STEP)
            sub_children, sub_else = self._collect(it)
            step.children = sub_children
            step.else_children = sub_else
            children.append(step)
        return children, else_list

    # ============ 선택/편집 ============
    def _on_tree_select(self, cur: QTreeWidgetItem | None, _prev) -> None:
        step = cur.data(0, ROLE_STEP) if cur else None
        self.form.set_step(step, Flow.list_saved())

    def _on_param_changed(self) -> None:
        it = self.tree.currentItem()
        if it and it.data(0, ROLE_STEP):
            it.setText(0, self._summary(it.data(0, ROLE_STEP)))

    def _current_real_item(self) -> QTreeWidgetItem | None:
        it = self.tree.currentItem()
        if it and it.data(0, ROLE_STEP):
            return it
        return None

    # ============ 스텝 추가 ============
    def _show_add_menu(self) -> None:
        if self._flow is None:
            QMessageBox.information(self, "안내", "먼저 플로우를 선택/생성하세요")
            return
        menu = QMenu(self)
        by_cat: dict[str, list] = {}
        for spec in step_spec_list():
            by_cat.setdefault(spec.category, []).append(spec)
        for cat, specs in by_cat.items():
            sub = menu.addMenu(cat)
            for spec in specs:
                act = sub.addAction(spec.label)
                act.triggered.connect(lambda _=False, s=spec.type: self._add_step(s))
        menu.exec(self.add_btn.mapToGlobal(self.add_btn.rect().bottomLeft()))

    def _add_step(self, step_type: str) -> None:
        spec = get_step_spec(step_type)
        step = Step(step_type, dict(spec.default_params()) if spec else {})
        cur = self.tree.currentItem()
        if cur is None:
            parent = self.tree.invisibleRootItem()
            idx = parent.childCount()
        elif cur.data(0, ROLE_ELSE):
            parent = cur
            idx = cur.childCount()
        elif cur.data(0, ROLE_STEP):
            parent = cur.parent() or self.tree.invisibleRootItem()
            idx = parent.indexOfChild(cur) + 1
        else:
            parent = self.tree.invisibleRootItem()
            idx = parent.childCount()
        new_it = self._add_item(parent, step)
        parent.removeChild(new_it)
        parent.insertChild(idx, new_it)
        self.tree.expandAll()
        self.tree.setCurrentItem(new_it)
        self._commit_tree_to_model()

    def _duplicate(self) -> None:
        it = self._current_real_item()
        if not it:
            return

        step: Step = it.data(0, ROLE_STEP)
        clone = Step.from_dict(step.to_dict())
        parent = it.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(it) + 1
        new_it = self._add_item(parent, clone)
        parent.removeChild(new_it)
        parent.insertChild(idx, new_it)
        self.tree.setCurrentItem(new_it)
        self._commit_tree_to_model()

    def _delete_current(self) -> None:
        it = self._current_real_item()
        if not it:
            return
        (it.parent() or self.tree.invisibleRootItem()).removeChild(it)
        self._commit_tree_to_model()

    def _toggle_enabled(self) -> None:
        it = self._current_real_item()
        if not it:
            return
        step: Step = it.data(0, ROLE_STEP)
        step.enabled = not step.enabled
        it.setForeground(0, Qt.gray if not step.enabled else self.tree.palette().text().color())
        it.setText(0, self._summary(step))
        self._commit_tree_to_model()

    def _tree_context_menu(self, pos) -> None:
        it = self._current_real_item()
        if not it:
            return
        step: Step = it.data(0, ROLE_STEP)
        menu = QMenu(self)
        menu.addAction("끄기" if step.enabled else "켜기", self._toggle_enabled)
        menu.addAction("복제", self._duplicate)
        menu.addAction("삭제", self._delete_current)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _edit_json(self) -> None:
        if self._flow is None:
            return
        self._commit_tree_to_model()
        dlg = QDialog(self)
        dlg.setWindowTitle(f"JSON — {self._flow.name}")
        dlg.resize(640, 560)
        editor = QPlainTextEdit(self._flow.to_json())
        editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay = QVBoxLayout(dlg)
        lay.addWidget(editor)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            new_flow = Flow.from_json(editor.toPlainText())
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "JSON 오류", str(exc))
            return
        new_flow.name = self._flow.name
        self._flow = new_flow
        self._flow.save()
        self._rebuild_tree()
        self._log("JSON 편집 반영됨")

    def _move(self, delta: int) -> None:
        it = self._current_real_item()
        if not it:
            return
        parent = it.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(it)
        new_idx = idx + delta
        # ELSE 마커는 건너뛸 수 없게 범위 제한
        real_count = sum(
            1 for i in range(parent.childCount()) if not parent.child(i).data(0, ROLE_ELSE)
        )
        if not (0 <= new_idx < parent.childCount()) or new_idx >= real_count and parent.child(
            min(new_idx, parent.childCount() - 1)
        ).data(0, ROLE_ELSE):
            return
        parent.removeChild(it)
        parent.insertChild(new_idx, it)
        self.tree.setCurrentItem(it)
        self._commit_tree_to_model()

    def _indent(self) -> None:
        """앞 형제(블록 스텝)의 자식으로 이동."""
        it = self._current_real_item()
        if not it:
            return
        parent = it.parent() or self.tree.invisibleRootItem()
        idx = parent.indexOfChild(it)
        if idx == 0:
            return
        prev = parent.child(idx - 1)
        prev_step = prev.data(0, ROLE_STEP)
        spec = get_step_spec(prev_step.type) if prev_step else None
        if not (spec and spec.has_children):
            QMessageBox.information(self, "안내", "앞 스텝이 블록(반복/조건)이어야 합니다")
            return
        parent.removeChild(it)
        # 블록의 children 영역 = ELSE 마커 앞
        insert_at = sum(
            1 for i in range(prev.childCount()) if not prev.child(i).data(0, ROLE_ELSE)
        )
        prev.insertChild(insert_at, it)
        prev.setExpanded(True)
        self.tree.setCurrentItem(it)
        self._commit_tree_to_model()

    def _outdent(self) -> None:
        it = self._current_real_item()
        if not it:
            return
        parent = it.parent()
        if parent is None:
            return
        grand = parent.parent() or self.tree.invisibleRootItem()
        # ELSE 컨테이너 안이면 그 부모(if)의 뒤로
        anchor = parent
        if parent.data(0, ROLE_ELSE):
            anchor = parent.parent()
            grand = anchor.parent() or self.tree.invisibleRootItem()
        idx = grand.indexOfChild(anchor)
        parent.removeChild(it)
        grand.insertChild(idx + 1, it)
        self.tree.setCurrentItem(it)
        self._commit_tree_to_model()

    # ============ 실행 ============
    def _toggle_run(self) -> None:
        if self._run and self._run.isRunning():
            self._run.stop()
            self.run_btn.setText("정지 중…")
            return
        if self._flow is None:
            return
        serial = self.instance_combo.currentData()
        if not serial:
            QMessageBox.information(self, "안내", "대상 인스턴스를 선택하세요 (인스턴스 탭에서 스캔)")
            return
        self._save()
        self.log.clear()
        self._run = RunnerThread(
            serial, self._flow, self.repeat_spin.value(), float(self.interval_spin.value())
        )
        self._run.log.connect(self._log)
        self._run.finished_ok.connect(self._on_run_done)
        self._run.start()
        self.run_btn.setText("■ 정지")

    def _on_run_done(self, ok: bool) -> None:
        self.run_btn.setText("▶ 실행")
        self._log(f"[완료] {'성공' if ok else '실패/중단'}")

    def _log(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    # ============ 정리 ============
    def shutdown(self) -> None:
        if self._run and self._run.isRunning():
            self._run.stop()
            self._run.wait(3000)
