@echo off
REM Importa los datos del ContaWin antiguo (carpeta padre) a datos\contawin.db
cd /d "%~dp0"
python -m contawin.importer ".." "datos\contawin.db" %*
pause
