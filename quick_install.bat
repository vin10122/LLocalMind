@echo off
chcp 65001 >nul
echo ============================================================
echo   INTEL-OPTIMIZED-MOE - Installazione Rapida
echo ============================================================
echo.
echo AVVERTENZA: Progetto sperimentale - work in progress
echo.

cd /d "%~dp0"

echo Verifica se PowerShell e' disponibile...
powershell -Command "exit 0" >nul 2>&1
if errorlevel 1 (
    echo ERRORE: PowerShell non trovato
    pause
    exit /b 1
)

echo.
echo Avvio installazione automatica...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install.ps1" -NoCompile

if errorlevel 1 (
    echo.
    echo ============================================================
    echo Installazione fallita. Vedi messaggi sopra per dettagli.
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Installazione completata!
echo ============================================================
echo.
echo Per compilare i kernel nativi (opzionale ma consigliato):
echo   .\scripts\compile_native_expert.bat
    .\scripts\compile_dequant_k.bat
echo.
echo Per avviare il chat:
echo   .\run_chat.bat
echo.
pause
