@echo off
chcp 65001 >nul
title Servidor FullGas League
echo =======================================================
echo   Iniciando o servidor FullGas League...
echo =======================================================

cd /d "%~dp0"

set PYTHONUNBUFFERED=1

if exist "venv\Scripts\python.exe" (
    echo Usando o Python do ambiente virtual 'venv'...
    "venv\Scripts\python.exe" -u run.py
    goto end
)

if exist ".venv\Scripts\python.exe" (
    echo Usando o Python do ambiente virtual '.venv'...
    ".venv\Scripts\python.exe" -u run.py
    goto end
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    echo Ambiente virtual nao detectado. Usando Python do sistema...
    python -u run.py
    goto end
)

echo [ERRO] Nao foi possivel localizar o interpretador Python ou ambiente virtual!
echo Certifique-se de que o Python esta instalado e adicione-o ao PATH do sistema.

:end
if %errorlevel% neq 0 (
    echo.
    echo O servidor foi finalizado ou ocorreu um erro (Codigo: %errorlevel%).
)
pause

