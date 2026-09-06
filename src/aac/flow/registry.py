"""스텝 타입 메타데이터 레지스트리.

각 스텝 타입에 대해:
  - label      : GUI 표시 이름
  - category   : 팔레트 분류
  - has_children / has_else : 블록 스텝 여부
  - params     : ParamSpec 리스트 (GUI 폼 자동 생성 + 기본값)
실제 실행 로직은 engine.py 의 _EXECUTORS 에 있다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ParamType = Literal["float", "int", "str", "bool", "template", "region", "keycode", "flow", "seconds"]


@dataclass
class ParamSpec:
    name: str
    type: ParamType
    default: Any = None
    label: str = ""
    help: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = self.name


@dataclass
class StepSpec:
    type: str
    label: str
    category: str
    params: list[ParamSpec] = field(default_factory=list)
    has_children: bool = False
    has_else: bool = False
    summary_fmt: str = ""  # 트리에 보여줄 한 줄 요약 템플릿, {param} 치환

    def default_params(self) -> dict[str, Any]:
        return {p.name: p.default for p in self.params}

    def summary(self, params: dict[str, Any]) -> str:
        if not self.summary_fmt:
            return self.label
        try:
            return self.summary_fmt.format(**{**self.default_params(), **params})
        except (KeyError, IndexError, ValueError):
            return self.label


_XY = [
    ParamSpec("x", "float", 0.5, "x(0~1)"),
    ParamSpec("y", "float", 0.5, "y(0~1)"),
]

STEP_TYPES: dict[str, StepSpec] = {}


def _reg(spec: StepSpec) -> None:
    STEP_TYPES[spec.type] = spec


_reg(StepSpec(
    "tap", "탭", "입력",
    params=[
        *_XY,
        ParamSpec("template", "template", "", "템플릿(선택)",
                  "지정 시 좌표 대신 이 이미지를 찾아 중심을 탭"),
        ParamSpec("region", "region", "", "검색영역 x,y,w,h", "비우면 전체 화면"),
        ParamSpec("taps", "int", 1, "탭 횟수", "2 = 더블탭"),
        ParamSpec("tap_gap_ms", "int", 120, "탭 간격(ms)", "더블탭 간격"),
        ParamSpec("jitter", "float", 0.0, "흔들기(0~1)", "탭 좌표 랜덤 오프셋"),
        ParamSpec("after_ms", "int", 400, "후 대기(ms)"),
    ],
    summary_fmt="탭 ({x:.3f}, {y:.3f}) {template} x{taps}",
))
_reg(StepSpec(
    "tap_template", "템플릿 탭", "입력",
    params=[
        ParamSpec("template", "template", "", "템플릿"),
        ParamSpec("region", "region", "", "검색영역 x,y,w,h", "비우면 전체 화면"),
        ParamSpec("threshold", "float", 0.85, "임계값"),
        ParamSpec("timeout", "seconds", 5.0, "탐색 제한(초)"),
        ParamSpec("poll_ms", "int", 700, "폴링(ms)"),
        ParamSpec("taps", "int", 1, "탭 횟수", "2 = 더블탭"),
        ParamSpec("tap_gap_ms", "int", 120, "탭 간격(ms)"),
        ParamSpec("offset_x", "float", 0.0, "x 오프셋", "매칭 중심에서 이동(정규화)"),
        ParamSpec("offset_y", "float", 0.0, "y 오프셋"),
        ParamSpec("required", "bool", True, "실패 시 중단"),
        ParamSpec("after_ms", "int", 500, "후 대기(ms)"),
    ],
    summary_fmt="템플릿 탭 [{template}] thr={threshold} x{taps}",
))
_reg(StepSpec(
    "swipe", "스와이프", "입력",
    params=[
        ParamSpec("x1", "float", 0.5, "시작 x"),
        ParamSpec("y1", "float", 0.7, "시작 y"),
        ParamSpec("x2", "float", 0.5, "끝 x"),
        ParamSpec("y2", "float", 0.3, "끝 y"),
        ParamSpec("duration_ms", "int", 400, "시간(ms)"),
    ],
    summary_fmt="스와이프 ({x1:.2f},{y1:.2f})→({x2:.2f},{y2:.2f})",
))
_reg(StepSpec(
    "key", "키 입력", "입력",
    params=[ParamSpec("keycode", "keycode", "BACK", "키")],
    summary_fmt="키 {keycode}",
))
_reg(StepSpec(
    "text", "텍스트 입력", "입력",
    params=[ParamSpec("value", "str", "", "문자열")],
    summary_fmt="텍스트 '{value}'",
))

_reg(StepSpec(
    "wait", "대기", "흐름",
    params=[ParamSpec("seconds", "seconds", 1.0, "초")],
    summary_fmt="대기 {seconds}s",
))
_reg(StepSpec(
    "wait_template", "템플릿 대기", "흐름",
    params=[
        ParamSpec("template", "template", "", "템플릿"),
        ParamSpec("region", "region", "", "검색영역 x,y,w,h"),
        ParamSpec("threshold", "float", 0.85, "임계값"),
        ParamSpec("timeout", "seconds", 15.0, "제한(초)"),
        ParamSpec("poll_ms", "int", 800, "폴링(ms)"),
        ParamSpec("required", "bool", True, "실패 시 중단"),
    ],
    summary_fmt="템플릿 대기 [{template}] ~{timeout}s",
))
_reg(StepSpec(
    "if_template", "만약 템플릿이 보이면", "흐름",
    params=[
        ParamSpec("template", "template", "", "템플릿"),
        ParamSpec("region", "region", "", "검색영역 x,y,w,h"),
        ParamSpec("threshold", "float", 0.85, "임계값"),
        ParamSpec("negate", "bool", False, "반대로(안 보이면)"),
    ],
    has_children=True, has_else=True,
    summary_fmt="IF [{template}] 보이면",
))
_reg(StepSpec(
    "loop", "반복(횟수)", "흐름",
    params=[ParamSpec("count", "int", 3, "횟수")],
    has_children=True,
    summary_fmt="반복 x{count}",
))
_reg(StepSpec(
    "if_frozen", "만약 화면이 멈췄으면", "흐름",
    params=[
        ParamSpec("gap_s", "seconds", 12.0, "비교 간격(초)"),
        ParamSpec("threshold", "float", 2.0, "차이 임계값",
                  "두 스크린샷 평균 픽셀차. 이하면 멈춤으로 판정"),
        ParamSpec("region", "region", "", "비교 영역 x,y,w,h", "비우면 전체 화면"),
        ParamSpec("samples", "int", 2, "샘플 수", "3 이상이면 연속 프레임 모두 동일해야 멈춤"),
    ],
    has_children=True, has_else=True,
    summary_fmt="IF 화면 멈춤 (간격 {gap_s}s)",
))
_reg(StepSpec(
    "repeat_until_template", "템플릿 나올 때까지 반복", "흐름",
    params=[
        ParamSpec("template", "template", "", "종료 템플릿"),
        ParamSpec("region", "region", "", "검색영역 x,y,w,h"),
        ParamSpec("threshold", "float", 0.85, "임계값"),
        ParamSpec("max_iterations", "int", 20, "최대 반복"),
        ParamSpec("iter_wait_ms", "int", 1000, "반복 간 대기(ms)"),
    ],
    has_children=True,
    summary_fmt="~ [{template}] 나올 때까지 (최대 {max_iterations})",
))
_reg(StepSpec(
    "call_flow", "다른 플로우 실행", "흐름",
    params=[ParamSpec("flow", "flow", "", "플로우 이름")],
    summary_fmt="▶ 플로우 '{flow}'",
))

_reg(StepSpec(
    "launch_app", "앱 실행", "앱",
    params=[
        ParamSpec("package", "str", "", "패키지"),
        ParamSpec("activity", "str", "", "액티비티(선택)"),
        ParamSpec("wait_s", "seconds", 8.0, "실행 후 대기"),
    ],
    summary_fmt="앱 실행 {package}",
))
_reg(StepSpec(
    "stop_app", "앱 강제종료", "앱",
    params=[ParamSpec("package", "str", "", "패키지")],
    summary_fmt="앱 종료 {package}",
))

_reg(StepSpec(
    "ocr_region", "OCR 숫자 읽기", "인식",
    params=[
        ParamSpec("region", "region", "0,0,0.2,0.1", "영역 x,y,w,h"),
        ParamSpec("var", "str", "kills", "저장 변수"),
        ParamSpec("digits_only", "bool", True, "숫자만"),
    ],
    summary_fmt="OCR {region} → ${var}",
))
_reg(StepSpec(
    "screenshot", "스크린샷 저장", "인식",
    params=[ParamSpec("label", "str", "", "파일 라벨")],
    summary_fmt="스크린샷 {label}",
))

_reg(StepSpec(
    "set_var", "변수 설정", "변수",
    params=[
        ParamSpec("var", "str", "x", "변수명"),
        ParamSpec("value", "str", "", "값", "${다른변수} 치환 가능"),
    ],
    summary_fmt="${var} = {value}",
))
_reg(StepSpec(
    "if_var", "만약 변수가 (조건)", "변수",
    params=[
        ParamSpec("var", "str", "kills", "변수명"),
        ParamSpec("op", "str", ">=", "연산자",
                  "== != >= <= > <  contains  empty  not_empty  changed"),
        ParamSpec("value", "str", "490", "비교값"),
    ],
    has_children=True, has_else=True,
    summary_fmt="IF ${var} {op} {value}",
))
_reg(StepSpec(
    "repeat_until_var", "변수 조건까지 반복", "변수",
    params=[
        ParamSpec("var", "str", "kills", "변수명"),
        ParamSpec("op", "str", ">=", "연산자"),
        ParamSpec("value", "str", "490", "비교값"),
        ParamSpec("max_iterations", "int", 60, "최대 반복"),
        ParamSpec("iter_wait_ms", "int", 1000, "반복 간 대기(ms)"),
    ],
    has_children=True,
    summary_fmt="~ ${var} {op} {value} 까지 (최대 {max_iterations})",
))

_reg(StepSpec(
    "notify", "알림", "기타",
    params=[
        ParamSpec("title", "str", "", "제목"),
        ParamSpec("message", "str", "", "내용"),
        ParamSpec("level", "str", "info", "수준", "info / warn / error"),
    ],
    summary_fmt="🔔 {title}: {message}",
))
_reg(StepSpec(
    "log", "로그", "기타",
    params=[ParamSpec("message", "str", "", "메시지")],
    summary_fmt="로그: {message}",
))


def get_step_spec(step_type: str) -> StepSpec | None:
    return STEP_TYPES.get(step_type)


def step_spec_list() -> list[StepSpec]:
    return list(STEP_TYPES.values())
