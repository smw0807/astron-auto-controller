@echo off
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run run.bat once first to finish setup.
  pause
  popd
  exit /b 1
)

".venv\Scripts\python.exe" -m aac.tools.scan
echo.
pause
popd
