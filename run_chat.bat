@echo off
chcp 65001 >nul
echo ============================================================
echo   INTEL-OPTIMIZED-MOE - Chat Client
echo ============================================================
echo.
echo AVVERTENZA: Progetto sperimentale - work in progress
echo.

cd /d "%~dp0"

REM Attiva ambiente virtuale
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=".venv\Scripts\python.exe"
) else (
    set "PYTHON=py -3.14"
)

REM Imposta variabili ambiente per BLAS (1 thread per prestazioni ottimali)
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set BLIS_NUM_THREADS=1

REM Avvia chat con preset default
%PYTHON% chat.py default

pause
