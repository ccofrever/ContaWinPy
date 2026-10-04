@echo off
REM Instala las librerias necesarias (solo la primera vez)
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo No se encontro Python. Descarguelo de https://www.python.org/downloads/ ^(marque "Add Python to PATH"^)
  pause
  exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Listo. Ejecute ContaWin.bat para iniciar el sistema.
pause
