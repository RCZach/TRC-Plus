@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
python -m trc_plus.app %*
if errorlevel 1 pause
