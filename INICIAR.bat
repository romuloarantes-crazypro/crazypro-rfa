@echo off
title CrazyPro RFA
color 0B
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  CrazyPro RFA — iniciando em http://localhost:8080
echo  Para encerrar: feche esta janela.
echo.
start "" cmd /c "timeout /t 2 >nul && start http://localhost:8080"
set PORT=8080
python app.py
pause
