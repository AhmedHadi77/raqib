@echo off
cd /d "%~dp0"
echo ===== Edge tests (simulation) =====
pushd edge & ..\.venv\Scripts\python.exe -m pytest -q & popd
echo ===== End-to-end system test (T-01 ... T-10) =====
.venv\Scripts\python.exe tools\e2e_test.py
pause
