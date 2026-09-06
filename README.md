# Astron Auto Controller

블루스택(BlueStacks 5 / nxt)에서 실행 중인 **아스트로엔** 인스턴스를 스캔하고,
인스턴스별로 자동화 **플로우**를 만들어 실행하는 데스크톱 컨트롤러.

목적: 500킬 후 자동사냥이 종료되고 마을로 이동되면 → 자동으로 사냥터 복귀 & 사냥 재개.

## 상태 (Phase 2 완료)

- [x] BlueStacks 인스턴스 스캐너 (`bluestacks.conf` 파싱 + `HD-Player.exe` 프로세스 매칭 + adb 연결)
- [x] ADB 제어 계층 (`HD-Adb.exe` 래퍼, 인스턴스별 tap / swipe / keyevent / screencap / wm size)
- [x] 좌표 정규화(0~1) — 인스턴스 해상도가 달라도 동일 플로우 동작
- [x] 템플릿 매칭 유틸 (멀티스케일 `cv2.matchTemplate`) + OCR(RapidOCR, 선택)
- [x] PySide6 GUI: 인스턴스 목록 + 라이브 스크린샷 + 클릭→좌표 + 영역 선택 + 탭 테스트
- [x] **플로우 모델 + JSON 직렬화** (스텝 트리, if/loop/else 블록)
- [x] **실행 엔진** (백그라운드 스레드, 협조적 취소, 스크린샷 캐시)
- [x] **코어 스텝 16종**: tap / tap_template / swipe / key / text / wait / wait_template /
      if_template / loop / repeat_until_template / call_flow / launch_app / stop_app /
      ocr_region / screenshot / log
- [x] **복합 이벤트 스켈레톤**: 재접속 / 사냥터이동 / 텔레포트 / 사냥시작 / 무기상점이동 /
      아이템수리 / 자동사냥루프 (서브플로우, `call_flow` 로 조합)
- [x] **플로우 편집기 탭** (트리 편집 + 속성 폼 자동생성 + 대상 인스턴스에서 실행/반복)
- [ ] Phase 3: 블록 캔버스 에디터 / 템플릿 매니저(스샷에서 크롭) / 인스턴스별 상시 감시 루프
- [ ] Phase 4: 다중 인스턴스 대시보드 / 스케줄링 / 알림

## 실행 (가장 간단)

- **`run.bat`** 더블클릭 → 최초 1회는 자동으로 가상환경 생성 + 의존성 설치, 이후엔 바로 GUI 실행
- **`scan.bat`** 더블클릭 → 콘솔에 인스턴스 목록 출력

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
```

## 플로우 만들기 (GUI "플로우" 탭)

1. **이벤트 스켈레톤 생성** → `flows/` 에 7개 서브플로우 뼈대 생성
2. "인스턴스 / 캡처" 탭에서 스크린샷을 보며 버튼 위치를 클릭 → 좌표 확인,
   또는 드래그로 영역 선택 → `templates/` 에 크롭 이미지 저장(Phase 3 예정, 현재는 수동 저장)
3. "플로우" 탭에서 각 스텝의 좌표/템플릿을 채움 (`＋ 스텝`, 들여쓰기로 블록 중첩)
4. 대상 인스턴스 선택 후 **▶ 실행** (반복 `-1` = 무한)

**동작 원리**: `자동사냥루프` 가 `hud_town.png`(마을 화면) 템플릿을 감지하면
→ (내구도 낮으면) `무기상점이동`+`아이템수리` → `사냥터이동` → `사냥시작` 을 차례로 호출.
Phase 3에서 이 루프를 인스턴스별로 상시 백그라운드 실행.

## 스텝 타입

| 분류 | 스텝 |
|---|---|
| 입력 | `tap`(좌표/템플릿), `tap_template`, `swipe`, `key`, `text` |
| 흐름 | `wait`, `wait_template`, `if_template`(+else), `loop`, `repeat_until_template`, `call_flow` |
| 앱 | `launch_app`, `stop_app` |
| 인식 | `ocr_region`(숫자→변수), `screenshot` |
| 기타 | `log` |

## 설정 (`settings.json`, 최초 실행 시 자동 생성)

| 키 | 설명 |
|---|---|
| `adb_path` | `HD-Adb.exe` 경로 (자동 탐지) |
| `bluestacks_conf` | `bluestacks.conf` 경로 (자동 탐지) |
| `adb_server_port` | HD-Adb 서버 포트 (기본 5037) |
| `instance_flows` | 인스턴스 key → 플로우 파일 매핑 |
| `watch_interval_sec` | 감시 루프 주기 |
| `template_match_threshold` | 템플릿 매칭 임계값 (기본 0.85) |

## 구조

```
src/aac/
  adb/         HD-Adb 래퍼 + 인스턴스 Device
  bluestacks/  인스턴스 스캐너
  vision/      스크린샷 캡처 + 템플릿 매칭 (+ OCR 예정)
  flow/        model(Flow/Step+JSON) / registry(스텝 스펙) / engine(실행) / events(스켈레톤)
  runner/      인스턴스↔플로우 바인딩 + 감시 루프 (Phase 3)
  gui/         PySide6 UI (capture_page + flow_editor + param_form + *_runner)
  tools/       CLI 유틸 (scan / shoot / scaffold / flow)
flows/         사용자 플로우 (*.json)
templates/     버튼/아이콘 크롭 이미지
captures/      스크린샷 저장
```
