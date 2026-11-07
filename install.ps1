<#PSScriptInfo
.VERSION 0.1.0
.GUID 12345678-1234-1234-1234-123456789abc
.AUTHOR Intel-Optimized-MoE Project
.DESCRIPTION Experimental installer for Intel-Optimized-MoE. THIS IS WORK IN PROGRESS - NOT PRODUCTION READY.
#>

<#
INTEL-OPTIMIZED-MOE - INSTALLER SPERIMENTALE
==============================================

AVVERTENZE IMPORTANTI:
- Questo progetto e' in fase sperimentale (work in progress)
- Non e' adatto per uso in produzione
- Le performance possono variare notevolmente tra sistemi
- E' necessario un modello GGUF esterno (non incluso)
- Richiede hardware Intel compatibile con OpenVINO

Per dettagli, leggi README.md
#>

param(
    [switch]$SkipChecks = $false,
    [switch]$NoCompile = $false,
    [string]$PythonPath = "py",
    [string[]]$PythonArguments = @("-3.14")
)

# Configurazione
$ProjectDir = $PSScriptRoot
$RequirementsFile = Join-Path $ProjectDir "requirements.txt"
$ScriptsDir = Join-Path $ProjectDir "scripts"

# Colori per output
$Red = "\e[91m"
$Yellow = "\e[93m"
$Green = "\e[92m"
$Cyan = "\e[96m"
$Bold = "\e[1m"
$Reset = "\e[0m"

function Write-Warning {
    param([string]$Message)
    Write-Host "$Yellow$Bold[AVVERTENZA]$Reset $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "$Red$Bold[ERRORE]$Reset $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "$Cyan$Bold[INFO]$Reset $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "$Green$Bold[OK]$Reset $Message" -ForegroundColor Green
}

# Banner iniziale
Clear-Host
Write-Host ""
Write-Host "  $Bold$Cyan============================================================$Reset"
Write-Host "  $Bold$Cyan   INTEL-OPTIMIZED-MOE - INSTALLER SPERIMENTALE$Reset"
Write-Host "  $Bold$Cyan============================================================$Reset"
Write-Host ""
Write-Warning "Questo e' un progetto SPERIMENTALE (work in progress)"
Write-Warning "Non e' adatto per uso in produzione"
Write-Warning "Le performance possono variare tra sistemi"
Write-Warning "Leggi README.md per dettagli e limitazioni"
Write-Host ""

# Verifica se l'utente ha letto le avvertenze
if (-not $SkipChecks) {
    $confirmation = Read-Host "Vuoi continuare con l'installazione? (s/n)"
    if ($confirmation -notmatch '^[sS]') {
        Write-Info "Installazione annullata."
        exit 0
    }
}

# Verifica sistema
Write-Host ""
Write-Info "Verifica requisiti di sistema..."

# Verifica Windows 64-bit
if ([Environment]::Is64BitOperatingSystem -eq $false) {
    Write-ErrorMsg "Sistema a 32-bit non supportato. Richiesto Windows 64-bit."
    exit 1
}
Write-Success "Sistema: Windows 64-bit"

# Verifica Python
Write-Info "Verifica Python 3.14+..."
try {
    $pythonOutput = & $PythonPath @PythonArguments --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Python non trovato"
    }
    if ($pythonOutput -match 'Python (\d+\.\d+)') {
        $version = $matches[1]
        $major = [version]$version
        if ($major -ge [version]"3.14") {
            Write-Success "Python $version trovato"
        } else {
            Write-ErrorMsg "Python $version trovato. Richiesto Python 3.14 o superiore."
            exit 1
        }
    }
} catch {
    Write-ErrorMsg "Python 3.14+ non trovato. Installa Python 3.14 da https://www.python.org/downloads/"
    Write-Info "Assicurati che 'py -3.14' punti alla versione corretta."
    exit 1
}

# Verifica pip
Write-Info "Verifica pip..."
try {
    & $PythonPath @PythonArguments -m pip --version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pip non disponibile" }
    Write-Success "pip disponibile"
} catch {
    Write-ErrorMsg "pip non disponibile. Reinstalla Python."
    exit 1
}

# Verifica Visual Studio Build Tools (solo se non SkipChecks)
if (-not $NoCompile -and -not $SkipChecks) {
    Write-Info "Verifica Visual Studio C++ x64 Build Tools..."
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $vcvars = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find VC\Auxiliary\Build\vcvars64.bat 2>$null
        if ($vcvars) {
            Write-Success "Visual Studio C++ Build Tools trovato"
        } else {
            Write-Warning "Visual Studio C++ Build Tools non trovato"
            Write-Info "Per compilare i kernel nativi, installa 'C++ Build Tools' da:"
            Write-Info "https://visualstudio.microsoft.com/visual-cpp-build-tools/"
            Write-Info "Seleziona 'C++ build tools' -> 'MSVC v143 - VS 2022 C++ x64/x86 build tools'"
        }
    } else {
        Write-Warning "vswhere.exe non trovato"
    }
}

# Creazione ambiente virtuale
Write-Host ""
$venvName = ".venv"
$venvPath = Join-Path $ProjectDir $venvName

if (Test-Path $venvPath) {
    Write-Info "Ambiente virtuale esistente trovato in $venvName"
    $useVenv = Read-Host "Vuoi usare quello esistente? (s/n)"
    if ($useVenv -notmatch '^[sS]') {
        Write-Info "Rimuovi $venvName e riavvia l'installazione"
        exit 0
    }
} else {
    Write-Info "Creazione ambiente virtuale Python..."
    try {
        & $PythonPath @PythonArguments -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw "Creazione venv fallita"
        }
        Write-Success "Ambiente virtuale creato"
    } catch {
        Write-ErrorMsg "Impossibile creare ambiente virtuale"
        exit 1
    }
}

# Attivazione ambiente virtuale
$ActivateScript = Join-Path $venvPath "Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    # Esegui lo script di attivazione nel contesto corrente
    . $ActivateScript
    Write-Success "Ambiente virtuale attivato"
} else {
    Write-ErrorMsg "Impossibile attivare ambiente virtuale"
    exit 1
}

# Installazione dipendenze
Write-Host ""
Write-Info "Installazione dipendenze Python..."
try {
    & python -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Upgrade pip fallito"
    }
    
    & python -m pip install -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "Installazione requisiti fallita"
    }
    Write-Success "Dipendenze installate"
} catch {
    Write-ErrorMsg "Errore durante installazione dipendenze: $_"
    exit 1
}

# Verifica OpenVINO
Write-Host ""
Write-Info "Verifica installazione OpenVINO..."
try {
    $ovVersion = & python -c "import openvino as ov; print(ov.__version__)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "OpenVINO versione $ovVersion installato"
    } else {
        throw "OpenVINO non trovato"
    }
} catch {
    Write-ErrorMsg "OpenVINO non installato correttamente. Reinstalla le dipendenze."
    exit 1
}

# Compilazione kernel nativi
if (-not $NoCompile) {
    Write-Host ""
    Write-Info "Compilazione kernel nativi..."
    
    $compileScripts = @(
        "compile_dequant_k.bat",
        "compile_native_expert.bat"
    )
    
    foreach ($script in $compileScripts) {
        $compilePath = Join-Path $ScriptsDir $script
        if (Test-Path $compilePath) {
            Write-Info "Esecuzione $script..."
            $process = Start-Process -FilePath $compilePath -WorkingDirectory $ScriptsDir -NoNewWindow -Wait -PassThru
            if ($process.ExitCode -eq 0) {
                Write-Success "$script completato"
            } else {
                Write-Warning "$script fallito con codice $($process.ExitCode)"
                Write-Info "Puoi compilare manualmente in seguito con: .\scripts\$script"
            }
        } else {
            Write-Warning "Script $script non trovato"
        }
    }
}

# Creazione file batch per esecuzione
Write-Host ""
Write-Info "Creazione file batch per esecuzione..."

$runChatBat = @"
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
    set "PYTHON=.venv\Scripts\python.exe"
    set "PYTHON_ARGS="
) else (
    set "PYTHON=py"
    set "PYTHON_ARGS=-3.14"
)

REM Imposta variabili ambiente per BLAS
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set BLIS_NUM_THREADS=1

REM Avvia chat
"%PYTHON%" %PYTHON_ARGS% chat.py default %*

pause
"@

$runChatPath = Join-Path $ProjectDir "run_chat.bat"
$runChatBat | Out-File -FilePath $runChatPath -Encoding ASCII
Write-Success "Creato run_chat.bat"

# Creazione file batch per benchmark
$runBenchBat = @"
@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    set "PYTHON_ARGS="
) else (
    set "PYTHON=py"
    set "PYTHON_ARGS=-3.14"
)

set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set BLIS_NUM_THREADS=1

"%PYTHON%" %PYTHON_ARGS% tools\bench_stability.py default --native-decode native --max-tokens 512 --max-seq 2048

pause
"@

$runBenchPath = Join-Path $ProjectDir "run_benchmark.bat"
$runBenchBat | Out-File -FilePath $runBenchPath -Encoding ASCII
Write-Success "Creato run_benchmark.bat"

# Summary
Write-Host ""
Write-Host "$Bold$Green============================================================$Reset"
Write-Host "$Bold$Green                    INSTALLAZIONE COMPLETATA$Reset"
Write-Host "$Bold$Green============================================================$Reset"
Write-Host ""

Write-Info "PER INIZIARE:"
Write-Host ""
Write-Host "  1. Posiziona il file modello GGUF nella directory del progetto"
Write-Host "     OR impostare il percorso con:"
Write-Host '     $env:FLASH_MOE_GGUF = "D:\percorso\al\modello.gguf"'
Write-Host ""
Write-Host "  2. Esegui il chat client:"
Write-Host "     .\run_chat.bat"
Write-Host ""
Write-Host "  3. Per eseguire benchmark:"
Write-Host "     .\run_benchmark.bat"
Write-Host ""

Write-Info "OPZIONI COMUNI:"
Write-Host ""
Write-Host "  --max-tokens 512        : Limite massimo token generati"
Write-Host "  --max-seq 2048          : Dimensione massima contesto"
Write-Host "  --temp 0.7              : Temperatura per sampling"
Write-Host "  --cache 320             : Cache esperti quantizzati"
Write-Host "  --weight-cache 1        : Cache pesi convertiti"
Write-Host ""

Write-Info "COMANDI CHAT:"
Write-Host ""
Write-Host "  /exit        : Esci dal chat"
Write-Host "  /help        : Mostra aiuto"
Write-Host ""

Write-Warning "Questo e' software sperimentale. Problemi e instabilita' sono attesi."
Write-Warning "Leggi README.md per informazioni dettagliate e limitazioni."
Write-Host ""

# Chiedi se creare collegamento sul desktop
$createShortcut = Read-Host "Vuoi creare un collegamento sul desktop? (s/n)"
if ($createShortcut -match '^[sS]') {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Intel-Optimized-MoE.lnk"
    
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = $runChatPath
    $Shortcut.WorkingDirectory = $ProjectDir
    $Shortcut.Description = "Intel-Optimized-MoE Chat Client (Sperimentale)"
    $Shortcut.IconLocation = "powershell.exe,0"
    $Shortcut.Save()
    
    Write-Success "Collegamento creato sul desktop: Intel-Optimized-MoE.lnk"
}

Write-Host ""
Write-Success "Installazione completata!"
Write-Host ""
