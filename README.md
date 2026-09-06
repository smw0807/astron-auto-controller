# Astron Auto Controller

블루스택(BlueStacks 5 / nxt)에서 실행 중인 **아스트로엔** 인스턴스를 스캔하고,
인스턴스별로 자동화 **플로우**를 만들어 실행하는 데스크톱 컨트롤러.

목적: 500킬 후 자동사냥이 종료되고 마을로 이동되면 → 자동으로 사냥터 복귀 & 사냥 재개.

## 상태 (Phase 1 완료)

- [x] BlueStacks 인스턴스 스캐너 (`bluestacks.conf` 파싱 + `HD-Player.exe` 프로세스 매칭 + adb 연결)
- [x] ADB 제어 계층 (`HD-Adb.exe` 래퍼, 인스턴스별 tap / swipe / keyevent / screencap / wm size)
- [x] 좌표 정규화(0~1) — 인스턴스 해상도가 달라도 동일 플로우 동작
- [x] 템플릿 매칭 유틸 (멀티스케일 `cv2.matchTemplate`)
- [x] PySide6 GUI: 인스턴스 목록 + 라이브 스크린샷 + 클릭→좌표 + 영역 선택 + 탭 테스트
- [ ] Phase 2: 플로우 모델 / 비동기 엔진 / 코어 스텝 / 복합 이벤트
- [ ] Phase 3: 블록 캔버스 플로우 에디터 / 템플릿 매니저 / 인스턴스별 감시 루프(사냥종료 자동감지)
- [ ] Phase 4: 다중 인스턴스 대시보드 / 스케줄링 / 알림

## 설치

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e .
# OCR(킬수 인식)까지: .venv\Scripts\python -m pip install -e ".[ocr]"
```

## 실행

```powershell
# GUI
.venv\Scripts\python -m aac

# CLI: 인스턴스 조회
.venv\Scripts\python -m aac.tools.scan

# CLI: 스크린샷 저장 / 좌표 탭 테스트
.venv\Scripts\python -m aac.tools.shoot 물돌
.venv\Scripts\python -m aac.tools.shoot 물돌 --tap 0.5 0.9
```

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
  flow/        플로우 모델 / 스텝 / 엔진 (Phase 2)
  runner/      인스턴스↔플로우 바인딩 + 감시 루프 (Phase 3)
  gui/         PySide6 UI
  tools/       CLI 유틸
flows/         사용자 플로우 (*.json)
templates/     버튼/아이콘 크롭 이미지
captures/      스크린샷 저장
```
