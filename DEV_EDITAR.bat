@echo off
title CrazyPro RFA — MODO EDICAO
color 0E
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   MODO EDICAO — Auto-reload ativado         ║
echo  ║   Salve qualquer arquivo e o servidor        ║
echo  ║   reinicia automaticamente.                  ║
echo  ║                                              ║
echo  ║   Arquivos para editar:                      ║
echo  ║   • app.py         (logica do servidor)      ║
echo  ║   • templates\index.html  (tela do app)      ║
echo  ║                                              ║
echo  ║   Acesse: http://localhost:8080              ║
echo  ╚══════════════════════════════════════════════╝
echo.
start "" cmd /c "timeout /t 2 >nul && start http://localhost:8080"
set PORT=8080
set FLASK_ENV=development
set FLASK_DEBUG=1
python -c "
import os
os.environ['PORT']='8080'
from app import app
app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=True)
"
pause
