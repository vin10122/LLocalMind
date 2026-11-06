param([switch]$Installer)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    & py -3.14 -m PyInstaller --noconfirm --clean .\packaging\windows\LLocalMind.spec
    if ($LASTEXITCODE -ne 0) { throw "Compilazione EXE non riuscita." }
    Write-Host "App pronta: $ProjectRoot\dist\LLocalMind\LLocalMind.exe"
    if ($Installer) {
        & py -3.14 .\tools\build_windows_installer.py --app-dir .\dist\LLocalMind
        if ($LASTEXITCODE -ne 0) { throw "Creazione installer non riuscita." }
    }
} finally {
    Pop-Location
}
