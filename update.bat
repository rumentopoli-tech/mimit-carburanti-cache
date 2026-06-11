@echo off
setlocal
cd /d "%~dp0"

echo [%date% %time%] Aggiornamento carburanti MIMIT

python scripts\update_carburanti.py
if %errorlevel% neq 0 (
    echo ERROR: script failed
    exit /b 1
)

git add data\
git commit -m "Update %date%" 2>nul
git push origin main

echo Done
