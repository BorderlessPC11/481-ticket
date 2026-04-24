@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto :run

echo.
echo [ERRO] Nao encontrei .venv\Scripts\python.exe
echo Crie o ambiente (uma vez) na pasta pos_system:
echo   "%LocalAppData%\Programs\Python\Python312\python.exe" -m venv .venv
echo   .venv\Scripts\pip install -r requirements.txt
echo Copie .env de .env.example se ainda nao tiver: copy .env.example .env
echo.
exit /b 1

:run
".venv\Scripts\python.exe" run.py %*
