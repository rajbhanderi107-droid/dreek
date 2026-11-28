@echo off
cd /d "%~dp0"
if not exist venv (
  echo First run: setting up...
  python -m venv venv || (echo Install Python 3.10+ from python.org first & pause & exit /b)
  venv\Scripts\python -m pip install -r requirements.txt
)
venv\Scripts\python app.py
pause
