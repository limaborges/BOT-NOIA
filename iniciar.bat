@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python start_v2.py
pause
