# Astron Auto Controller

블루스택(BlueStacks 5 / nxt)에서 실행 중인 **아스트로엔** 인스턴스를 스캔하고,
인스턴스별로 자동화 **플로우**를 만들어 실행하는 데스크톱 컨트롤러.

목적: 500킬 후 자동사냥이 종료되고 마을로 이동되면 → 자동으로 사냥터 복귀 & 사냥 재개.

## 상태

**섬능1/섬능2 자동사냥 실동작 확인** (2026-09-06): 마을 감지 → 사냥터 복귀 → 편대 가입
(편대장 자동 승인) → 편대원 텔레포트 → 블루스택 매크로 사냥. 전체 무인 루프 완성.

## 기능 (Phase 1~4)

- [x] BlueStacks 인스턴스 스캐너 (`bluestacks.conf` 파싱 + `HD-Player.exe` 프로세스 매칭 + adb 연결)
- [x] ADB 제어 계층 (`HD-Adb.exe` 래퍼, 인스턴스별 tap / swipe / keyevent / screencap / wm size)
- [x] 좌표 정규화(0~1) — 인스턴스 해상도가 달라도 동일 플로우 동작
- [x] 템플릿 매칭 유틸 (멀티스케일 `cv2.matchTemplate`) + OCR(RapidOCR, 선택)
- [x] PySide6 GUI: 인스턴스 목록 + 라이브 스크린샷 + 클릭→좌표 + 영역 선택 + 탭 테스트
- [x] **플로우 모델 + JSON 직렬화** (스텝 트리, if/loop/else 블록)
- [x] **실행 엔진** (백그라운드 스레드, 협조적 취소, 스크린샷 캐시)
- [x] **코어 스텝 21종**: tap / tap_template / swipe / key / text / wait / wait_template /
      if_template / loop / repeat_until_template / call_flow / launch_app / stop_app /
      ocr_region / set_var / if_var / repeat_until_var / notify / screenshot / log
- [x] **복합 이벤트 스켈레톤**: 재접속 / 사냥터이동 / 텔레포트 / 사냥시작 / 무기상점이동 /
      아이템수리 / 자동사냥루프 (서브플로우, `call_flow` 로 조합)
- [x] **플로우 편집기 탭** (트리 편집 + 속성 폼 자동생성 + 대상 인스턴스에서 실행/반복)
- [x] **템플릿 매니저**: 캡처 화면에서 드래그 → `templates/*.png` 크롭 저장, 썸네일 목록,
      현재 화면에서 매칭 테스트(점수 + 위치 마커)
- [x] **인스턴스별 감시 루프** (`RunnerManager`): 인스턴스 ↔ 플로우 배정(settings 저장),
      무한 반복 실행, 오프라인 자동 중지
- [x] **대시보드 탭**: 인스턴스 × 배정 플로우 × 상태 × 반복수, 개별/전체 시작·정지, 통합 로그
- [x] **헤드리스 감시** (`aac.tools.watch` / `watch.bat`): GUI 없이 배정된 플로우 실행
- [x] **변수/OCR 트리거**: `ocr_region` 로 킬수 읽어 `${kills}` 변수 저장,
      `if_var ${kills} >= 490`, `repeat_until_var` 로 조건 분기 (500킬 감지)
- [x] **데스크톱 알림**: `notify` 스텝 + 트레이 알림, 감시가 예기치 않게 멈추면 자동 경고
- [x] **스케줄러**: 활성 시간대(예 `09:00-23:30`) / 일일 재시작 / N분마다 재시작 (대시보드에서 설정)
- [x] **편집기 개선**: 우클릭 메뉴(켜기·끄기/복제/삭제), JSON 직접 보기·편집
- [ ] Phase 5: 블록 캔버스(드래그) 에디터 / 인스턴스 그룹 프로필 / 원격 모니터링

## 실행 (가장 간단)

- **`run.bat`** 더블클릭 → 최초 1회는 자동으로 가상환경 생성 + 의존성 설치, 이후엔 바로 GUI 실행
- **`scan.bat`** 더블클릭 → 콘솔에 인스턴스 목록 출력
- **`watch.bat`** 더블클릭 → GUI 없이 대시보드에서 배정한 플로우로 감시 루프 실행 (Ctrl+C 종료)

> 사전 조건: Python 3.11 이상 설치 (`py -3.13` 권장). `run.bat` 이 알아서 찾음.

## 실행 (수동)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e .
# OCR(킬수 인식)까지: .venv\Scripts\python -m pip install -e ".[ocr]"

.venv\Scripts\python -m aac                       # GUI
.venv\Scripts\python -m aac.tools.scan            # 인스턴스 조회
.venv\Scripts\python -m aac.tools.shoot 물돌       # 스크린샷 저장
.venv\Scripts\python -m aac.tools.shoot 물돌 --tap 0.5 0.9
.venv\Scripts\python -m aac.tools.scaffold        # 이벤트 스켈레톤 flows/ 생성
.venv\Scripts\python -m aac.tools.flow 자동사냥루프 물돌 --repeat -1 --interval 20
.venv\Scripts\python -m aac.tools.watch           # 배정된 모든 인스턴스 감시 실행
```

## 아스트로엔 실전 설정 (섬능1/섬능2 예시)

`flows/` 에 커밋된 것: `자동사냥루프`(감시), `사냥시작`(마을→사냥 시퀀스), `승인`(편대장 전용).
`templates/` 에 실측 크롭 이미지들.

| 인스턴스 | 플로우 | 변수 | 간격 |
|---|---|---|---|
| 섬능1 | 자동사냥루프 | `tp_target=sq_member_toodan4.png` | 600s |
| 섬능2 | 자동사냥루프 | `tp_target=sq_member_toodans.png` | 600s |
| 에분기1 (편대장) | 승인 | — | 3s |

대시보드에서 각 행의 **⚙** 버튼으로 `tp_target` / 간격 override 편집 → settings.json 저장.
사냥터가 다르면 M6-1(1) 부분 템플릿(`hg_paren1.png`)을 각자 것으로 교체.

**동작**: `자동사냥루프` 가 10분마다 TAB 으로 지도를 열어 `map_village.png`(무기상점 텍스트)가
보이면 = 마을 = 500킬 종료 → `사냥시작` 호출. 편대 가입 요청은 편대장 인스턴스의 `승인`
플로우가 요청자 이름에 "TooDan" 이 있을 때만 승인.

## 플로우 만들기 (GUI "플로우" 탭)

1. "플로우" 탭 → **이벤트 스켈레톤 생성** → `flows/` 에 7개 서브플로우 뼈대 생성
2. "인스턴스 / 캡처" 탭에서 인스턴스 선택 → 화면을 보며:
   - 버튼 위치 **클릭** → 정규화 좌표 확인 (`tap` 스텝의 x, y 에 입력)
   - 버튼 영역 **드래그** → 이름 입력 후 **[드래그한 영역 → 템플릿 저장]** → `templates/*.png`
   - 오른쪽 템플릿 목록에서 더블클릭 → 현재 화면에서 매칭 테스트 (초록 마커 = 발견)
3. "플로우" 탭에서 각 스텝의 좌표/템플릿을 채움 (`＋ 스텝`, 들여쓰기로 블록 중첩)
4. 대상 인스턴스 선택 후 **▶ 실행** (반복 `-1` = 무한)
5. 완성되면 "대시보드" 탭 → 인스턴스별로 플로우 배정 → **전체 시작**

**동작 원리**: `자동사냥루프` 가 `hud_town.png`(마을 화면) 템플릿을 감지하면
→ (내구도 낮으면) `무기상점이동`+`아이템수리` → `사냥터이동` → `사냥시작` 을 차례로 호출.
대시보드/`watch.bat` 가 이 루프를 인스턴스별로 `watch_interval_sec` 간격으로 무한 반복.

**킬수 기반 감지(대안)**: `ocr_region` 으로 킬 카운터 영역을 읽어 `${kills}` 저장 →
`if_var ${kills} >= 490` 이면 `notify` 로 미리 알림 + 복귀 준비. 마을 이동은 템플릿으로,
"곧 끝남" 예고는 OCR 로 조합하는 것을 권장.

## 스텝 타입

| 분류 | 스텝 |
|---|---|
| 입력 | `tap`(좌표/템플릿, `taps`=더블탭), `tap_template`(`region` 검색영역, `offset_x/y`, `taps`), `swipe`, `key`, `text` |
| 흐름 | `wait`, `wait_template`, `if_template`(+else), `loop`, `repeat_until_template`, `call_flow` |
| 앱 | `launch_app`, `stop_app` |
| 인식 | `ocr_region`(숫자→`${var}` / `${var}_int` / `${var}_prev`), `screenshot` |
| 변수 | `set_var`(`${x}` 치환), `if_var`(`== != >= <= > < contains empty not_empty changed`), `repeat_until_var` |
| 기타 | `notify`(트레이 알림), `log` |

## 설정 (`settings.json`, 최초 실행 시 자동 생성 · git 무시)

| 키 | 설명 |
|---|---|
| `adb_path` | `HD-Adb.exe` 경로 (자동 탐지) |
| `bluestacks_conf` | `bluestacks.conf` 경로 (자동 탐지) |
| `adb_server_port` | HD-Adb 서버 포트 (기본 5037) |
| `instance_flows` | 인스턴스 key → 플로우 파일 매핑 |
| `instance_vars` | 인스턴스 key → {변수명: 값} (플로우 시작 시 주입, `${var}` 로 참조) |
| `instance_intervals` | 인스턴스 key → 감시 간격(초) override |
| `watch_interval_sec` | 기본 감시 루프 주기 |
| `template_match_threshold` | 템플릿 매칭 임계값 (기본 0.85) |
| `notifications_enabled` | 데스크톱(트레이) 알림 |
| `schedule_enabled` / `active_hours` / `daily_restart_time` / `periodic_restart_min` | 스케줄러 |

## 구조

```
src/aac/
  adb/         HD-Adb 래퍼 + 인스턴스 Device
  bluestacks/  인스턴스 스캐너
  vision/      capture / template(매칭·크롭) / ocr(RapidOCR)
  flow/        model(Flow/Step+JSON) / registry(스텝 스펙) / engine(실행) / events(스켈레톤)
  runner/      thread(RunnerThread) / manager(RunnerManager: 배정·감시) / scheduler
  gui/         app / capture_view / instances_panel / flow_editor / param_form /
               template_panel / dashboard / workers
  tools/       CLI (scan / shoot / scaffold / flow / watch)
flows/         사용자 플로우 (*.json) — 이벤트 스켈레톤 커밋됨
templates/     버튼/아이콘 크롭 이미지
captures/      스크린샷 저장
```
