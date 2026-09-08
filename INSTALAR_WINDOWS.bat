@echo off
title CrazyPro RFA — Instalacao Windows
color 0A
chcp 65001 >nul

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   CRAZYPRO RFA — Instalacao Windows         ║
echo  ║   RFA Marketing Digital                     ║
echo  ╚══════════════════════════════════════════════╝
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado!
    echo.
    echo  1. Acesse: https://www.python.org/downloads/
    echo  2. Baixe a versao mais recente
    echo  3. Na instalacao, marque: "Add Python to PATH"
    echo  4. Depois execute este arquivo novamente.
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  OK: %PYVER%

set DESTINO=D:\CrazyPro-RFA
echo.
echo  Pasta de instalacao: %DESTINO%

if not exist "D:\" (
    echo  [AVISO] Unidade D: nao encontrada. Instalando em C:\CrazyPro-RFA
    set DESTINO=C:\CrazyPro-RFA
)

if not exist "%DESTINO%" (
    mkdir "%DESTINO%"
    echo  Pasta criada: %DESTINO%
) else (
    echo  Pasta ja existe, atualizando arquivos...
)

echo.
echo  Copiando arquivos do app...
xcopy /E /I /Y /Q "%~dp0app.py"           "%DESTINO%\" >nul
xcopy /E /I /Y /Q "%~dp0icon_data.py"     "%DESTINO%\" >nul
xcopy /E /I /Y /Q "%~dp0requirements.txt" "%DESTINO%\" >nul
xcopy /E /I /Y /Q "%~dp0INICIAR.bat"      "%DESTINO%\" >nul
xcopy /E /I /Y /Q "%~dp0DEV_EDITAR.bat"   "%DESTINO%\" >nul
xcopy /E /I /Y /Q "%~dp0templates"        "%DESTINO%\templates\" >nul
xcopy /E /I /Y /Q "%~dp0static"           "%DESTINO%\static\" >nul
xcopy /E /I /Y /Q "%~dp0COMO_EDITAR.txt"  "%DESTINO%\" >nul 2>&1
echo  OK: todos os arquivos copiados

echo.
echo  Instalando dependencias Python (aguarde ~1 min)...
python -m pip install --upgrade pip --quiet --disable-pip-version-check
python -m pip install flask pillow piexif requests openpyxl werkzeug --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  [AVISO] Erro ao instalar dependencias.
    echo  Execute manualmente: pip install flask pillow piexif requests openpyxl werkzeug
) else (
    echo  OK: dependencias instaladas
)

echo.
echo  Criando atalho na Area de Trabalho...
powershell -NoProfile -Command ^
  "$ws=New-Object -ComObject WScript.Shell; ^
   $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\CrazyPro RFA.lnk'); ^
   $s.TargetPath='%DESTINO%\INICIAR.bat'; ^
   $s.WorkingDirectory='%DESTINO%'; ^
   $s.Description='CrazyPro RFA Marketing Digital'; ^
   $s.Save()" >nul 2>&1
echo  OK: atalho criado na Area de Trabalho

echo.
echo  Abrindo pasta de instalacao...
explorer "%DESTINO%"

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   INSTALACAO CONCLUIDA!                     ║
echo  ║                                              ║
echo  ║   Para USAR o app: clique em INICIAR.bat    ║
echo  ║   Para EDITAR:     clique em DEV_EDITAR.bat ║
echo  ╚══════════════════════════════════════════════╝
echo.
set /p INICIAR="Iniciar o app agora? (S/N): "
if /i "%INICIAR%"=="S" (
    cd /d "%DESTINO%"
    call INICIAR.bat
)
