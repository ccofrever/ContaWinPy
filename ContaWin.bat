@echo off
cd /d "%~dp0"
python -c "import PySide6" >nul 2>&1
if errorlevel 1 call instalar.bat
start "" pythonw main.py
