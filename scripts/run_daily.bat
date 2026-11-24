@echo off
setlocal
cd /d "%~dp0\.."
python scripts\wardwatch.py --ward 05 --build
endlocal
