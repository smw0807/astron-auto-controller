@echo off
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run run.bat once first to finish setup.
  pause
  popd
  exit /b 1
)

rem Run assigned flows on all online instances (Ctrl+C to stop)
".venv\Scripts\python.exe" -m aac.tools.watch %*
popd
