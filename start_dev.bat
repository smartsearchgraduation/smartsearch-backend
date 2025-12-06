@echo off
cd /d "%~dp0"
echo Activating virtual environment...
call venv\Scripts\activate
echo Starting Flask development server...
python app.py
pause
