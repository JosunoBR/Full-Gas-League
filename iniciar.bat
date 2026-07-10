@echo off
title Servidor FullGas League
echo =======================================================
echo   Iniciando o servidor FullGas League...
echo =======================================================

cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    echo Usando o Python do ambiente virtual 'venv'...
    "%~dp0venv\Scripts\python.exe" "%~dp0run.py"
    goto end
)

if exist "%~dp0.venv\Scripts\python.exe" (
    echo Usando o Python do ambiente virtual '.venv'...
    "%~dp0.venv\Scripts\python.exe" "%~dp0run.py"
    goto end
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    echo Ambiente virtual nao detectado. Usando Python do sistema...
    python "%~dp0run.py"
    goto end
)

echo [ERRO] Nao foi possivel localizar o interpretador Python ou ambiente virtual!
echo Certifique-se de que o Python esta instalado e adicione-o ao PATH do sistema.

:end
pause
