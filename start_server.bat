@echo off
cd /d "%~dp0"
echo Activating virtual environment...
call venv\Scripts\activate
echo Starting Waitress server...
python run_waitress.py
pause
