@echo off
setlocal
pushd "%~dp0"

if exist ".venv\Scripts\python.exe" goto run

echo ============================================
echo   First run - creating venv and installing
echo ============================================

set "PYEXE="
py -3.13 --version >nul 2>nul && set "PYEXE=py -3.13"
if not defined PYEXE py -3 --version >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE python --version >nul 2>nul && set "PYEXE=python"
if not defined PYEXE (
  echo [ERROR] Python not found. Install Python 3.11 or newer.
  pause
  popd
  exit /b 1
)

echo [1/3] create venv with %PYEXE%
%PYEXE% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] failed to create venv
  pause
  popd
  exit /b 1
)

echo [2/3] upgrade pip
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo [3/3] install dependencies ^(may take a few minutes^)
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
  echo [ERROR] dependency install failed
  pause
  popd
  exit /b 1
)
echo Done.
echo.

:run
".venv\Scripts\python.exe" -m aac %*
if errorlevel 1 pause
popd
