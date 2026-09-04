@echo off
cd /d "%~dp0"
set NO_BROWSER=
set PORT=5055
python run.py
pause
