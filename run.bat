@echo off
chcp 65001 >NUL 2>&1
taskkill /F /IM python.exe >NUL 2>&1
timeout /t 1 /nobreak >NUL
cd /d "%~dp0"
start "" /B .venv\Scripts\python app.py
echo SprintLens started (http://localhost:5000)
