"""복합 '이벤트' = 재사용 가능한 서브플로우 스켈레톤 생성기.

사용자가 GUI에서 [재접속] [사냥터이동] [텔레포트] [사냥시작] [무기상점이동] [아이템수리]
같은 블록을 바로 쓸 수 있도록, 각 이벤트의 뼈대 플로우를 flows/ 에 만들어 둔다.
좌표/템플릿은 TODO 로 비워두고 사용자가 채운다.
메인 루프(자동사냥루프)는 call_flow 로 이 서브플로우들을 조합한다.
"""
from __future__ import annotations

from aac.flow.model import Flow, Step

# 게임 패키지 — 실제 값으로 교체 필요 (adb shell pm list packages | findstr astro 등으로 확인)
GAME_PACKAGE = ""


def _tpl_wait(name: str, timeout: float = 15.0, required: bool = True, note: str = "") -> Step:
    return Step("wait_template", {"template": name, "timeout": timeout, "required": required},
               note=note)


def _tap_tpl(
    name: str, timeout: float = 8.0, required: bool = True, after_ms: int = 800, note: str = ""
) -> Step:
    return Step("tap_template", {"template": name, "timeout": timeout,
                                 "required": required, "after_ms": after_ms}, note=note)


def build_reconnect() -> Flow:
    return Flow(
        name="재접속",
        description="접속 끊김 감지 시 게임 재실행 후 캐릭터 선택까지",
        package=GAME_PACKAGE,
        steps=[
            Step("log", {"message": "재접속 시작"}),
            Step("stop_app", {"package": GAME_PACKAGE}, note="패키지명 입력 필요"),
            Step("wait", {"seconds": 2.0}),
            Step("launch_app", {"package": GAME_PACKAGE, "wait_s": 12.0}, note="패키지명 입력 필요"),
            _tap_tpl("btn_start_screen.png", timeout=40, after_ms=1500),
            _tap_tpl("btn_char_select.png", timeout=20, after_ms=1500),
            _tpl_wait("hud_ingame.png", timeout=30),
            Step("log", {"message": "재접속 완료"}),
        ],
    )


def build_goto_hunting_ground() -> Flow:
    return Flow(
        name="사냥터이동",
        description="마을에서 지정 사냥터로 이동 (NPC/이동목록/지도 등)",
        package=GAME_PACKAGE,
        steps=[
            Step("log", {"message": "사냥터 이동 시작"}),
            _tap_tpl("btn_menu.png", after_ms=600),
            _tap_tpl("btn_move_list.png", after_ms=800),
            _tap_tpl("dest_hunting_ground.png", after_ms=1000, note="목표 사냥터 항목"),
            _tap_tpl("btn_move_confirm.png", timeout=6, required=False, after_ms=500),
            _tpl_wait("hud_field.png", timeout=25),
            Step("log", {"message": "사냥터 도착"}),
        ],
    )


def build_teleport() -> Flow:
    return Flow(
        name="텔레포트",
        description="텔레포트 아이템/스킬 사용",
        package=GAME_PACKAGE,
        steps=[
            Step("log", {"message": "텔레포트"}),
            Step("key", {"keycode": "MENU"}, note="인벤토리 단축키가 있으면 교체"),
            _tap_tpl("item_teleport.png", after_ms=600),
            _tap_tpl("btn_use.png", timeout=5, required=False, after_ms=1500),
            _tap_tpl("teleport_dest.png", timeout=8, required=False, after_ms=1500),
            _tpl_wait("hud_ingame.png", timeout=20, required=False),
        ],
    )


def build_start_hunt() -> Flow:
    return Flow(
        name="사냥시작",
        description="블루스택 오토(자동사냥) 재개",
        package=GAME_PACKAGE,
        steps=[
            Step("log", {"message": "사냥 시작"}),
            Step("wait", {"seconds": 1.5}),
            _tap_tpl("btn_auto_hunt.png", timeout=10, after_ms=1000,
                     note="자동사냥 토글 버튼"),
            Step("if_template", {"template": "auto_hunt_active.png", "negate": True},
                 note="아직 활성화 안 됐으면 한 번 더",
                 children=[_tap_tpl("btn_auto_hunt.png", timeout=5, required=False)]),
            Step("log", {"message": "사냥 진행 중"}),
        ],
    )


def build_goto_weapon_shop() -> Flow:
    return Flow(
        name="무기상점이동",
        description="마을 무기상점 NPC 로 이동",
        package=GAME_PACKAGE,
        steps=[
            Step("log", {"message": "무기상점 이동"}),
            _tap_tpl("btn_menu.png", after_ms=600),
            _tap_tpl("btn_move_list.png", after_ms=800),
            _tap_tpl("dest_weapon_shop.png", after_ms=1000),
            _tpl_wait("npc_weapon_shop.png", timeout=20, required=False),
        ],
    )


def build_repair_items() -> Flow:
    return Flow(
        name="아이템수리",
        description="상점 NPC 대화 → 전체 수리",
        package=GAME_PACKAGE,
        steps=[
            Step("log", {"message": "아이템 수리"}),
            _tap_tpl("npc_weapon_shop.png", timeout=8, required=False, after_ms=800),
            _tap_tpl("btn_repair.png", after_ms=600),
            _tap_tpl("btn_repair_all.png", timeout=5, required=False, after_ms=500),
            _tap_tpl("btn_confirm.png", timeout=5, required=False, after_ms=800),
            Step("key", {"keycode": "BACK"}),
        ],
    )


def build_auto_hunt_loop() -> Flow:
    """메인 루프: 마을로 튕겨나오면 감지 → 수리 → 사냥터 복귀 → 사냥 재개, 무한 반복."""
    return Flow(
        name="자동사냥루프",
        description="500킬 종료 후 마을 감지 시 자동 복귀. 감시 루프에서 이 플로우를 반복 호출.",
        package=GAME_PACKAGE,
        steps=[
            Step("log", {"message": "자동사냥루프 tick"}),
            Step(
                "if_template",
                {"template": "hud_town.png"},
                note="마을 화면이면 복귀 시퀀스",
                children=[
                    Step("log", {"message": "마을 감지 → 복귀 시퀀스"}),
                    Step("if_template", {"template": "gear_low_durability.png"},
                         note="내구도 경고 있으면 수리",
                         children=[
                             Step("call_flow", {"flow": "무기상점이동"}),
                             Step("call_flow", {"flow": "아이템수리"}),
                         ]),
                    Step("call_flow", {"flow": "사냥터이동"}),
                    Step("call_flow", {"flow": "사냥시작"}),
                ],
                else_children=[
                    Step("if_template", {"template": "dialog_disconnected.png"},
                         children=[Step("call_flow", {"flow": "재접속"}),
                                   Step("call_flow", {"flow": "사냥터이동"}),
                                   Step("call_flow", {"flow": "사냥시작"})]),
                ],
            ),
        ],
    )


ALL_BUILDERS = {
    "재접속": build_reconnect,
    "사냥터이동": build_goto_hunting_ground,
    "텔레포트": build_teleport,
    "사냥시작": build_start_hunt,
    "무기상점이동": build_goto_weapon_shop,
    "아이템수리": build_repair_items,
    "자동사냥루프": build_auto_hunt_loop,
}


def scaffold_all(overwrite: bool = False) -> list[str]:
    """모든 이벤트 스켈레톤을 flows/ 에 생성. 이미 있으면 건너뜀(overwrite=False)."""
    created: list[str] = []
    for name, builder in ALL_BUILDERS.items():
        path = Flow.path_for(name)
        if path.exists() and not overwrite:
            continue
        builder().save(path)
        created.append(name)
    return created
