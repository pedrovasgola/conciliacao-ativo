@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
cd /d "%~dp0"
set "CONCILIACAO_RAIZ=%CD%"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente ainda nao criado. Na pasta do projeto, rode: python -m venv .venv ^& .venv\Scripts\python.exe -m pip install -e .
  pause
  exit /b 1
)
if "%~1"=="" (
  echo Consignado a Receber - informe o periodo.
  echo Pasta: %CD%
  echo Excel em: %CD%\saida
  echo.
  ".venv\Scripts\python.exe" -m conciliacao rodar consignado_a_receber
  echo.
  pause
) else (
  ".venv\Scripts\python.exe" -m conciliacao %*
)
