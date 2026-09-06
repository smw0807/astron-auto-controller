"""플로우 / 스텝 데이터 모델 및 JSON 직렬화.

플로우 = 스텝의 트리.
  - 대부분의 스텝은 리프.
  - if_template / loop / repeat_until_template 는 자식 블록을 가진다.
  - if_template 은 else 블록(else_children)도 가질 수 있다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aac.config import FLOWS_DIR

SCHEMA_VERSION = 1


@dataclass
class Step:
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    note: str = ""
    children: list[Step] = field(default_factory=list)
    else_children: list[Step] = field(default_factory=list)

    # --- 직렬화 ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "params": self.params}
        if not self.enabled:
            d["enabled"] = False
        if self.note:
            d["note"] = self.note
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        if self.else_children:
            d["else_children"] = [c.to_dict() for c in self.else_children]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Step:
        return cls(
            type=d["type"],
            params=dict(d.get("params", {})),
            enabled=d.get("enabled", True),
            note=d.get("note", ""),
            children=[cls.from_dict(c) for c in d.get("children", [])],
            else_children=[cls.from_dict(c) for c in d.get("else_children", [])],
        )

    # --- 편의 ---------------------------------------------------
    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()
        for c in self.else_children:
            yield from c.walk()


@dataclass
class Flow:
    name: str
    steps: list[Step] = field(default_factory=list)
    description: str = ""
    # 이 플로우가 사용하는 게임 패키지(선택)
    package: str = ""
    schema_version: int = SCHEMA_VERSION

    # --- 직렬화 ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "description": self.description,
            "package": self.package,
            "steps": [s.to_dict() for s in self.steps],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Flow:
        return cls(
            name=d.get("name", "untitled"),
            description=d.get("description", ""),
            package=d.get("package", ""),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            steps=[Step.from_dict(s) for s in d.get("steps", [])],
        )

    @classmethod
    def from_json(cls, text: str) -> Flow:
        return cls.from_dict(json.loads(text))

    # --- 파일 I/O ----------------------------------------------
    @staticmethod
    def path_for(name: str) -> Path:
        safe = "".join(c for c in name if c.isalnum() or c in " _-()가-힣").strip()
        return FLOWS_DIR / f"{safe or 'untitled'}.json"

    def save(self, path: str | Path | None = None) -> Path:
        p = Path(path) if path else self.path_for(self.name)
        p.write_text(self.to_json(), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> Flow:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def load_by_name(cls, name: str) -> Flow:
        return cls.load(cls.path_for(name))

    @staticmethod
    def list_saved() -> list[str]:
        return sorted(p.stem for p in FLOWS_DIR.glob("*.json"))
