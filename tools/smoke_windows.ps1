param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$Report,
    [Parameter(Mandatory=$true)][string]$Screenshot
)
$ErrorActionPreference = "Stop"
$Executable = (Resolve-Path $Executable).Path
$Report = [System.IO.Path]::GetFullPath($Report)
$Screenshot = [System.IO.Path]::GetFullPath($Screenshot)
$arguments = @("--smoke-test", "--smoke-report", "`"$Report`"", "--smoke-screenshot", "`"$Screenshot`"")
$process = Start-Process -FilePath $Executable -ArgumentList $arguments -PassThru
$null = $process.Handle
if (-not $process.WaitForExit(180000)) {
    Stop-Process -Id $process.Id -Force
    throw "LLocalMind smoke test timed out."
}
$process.WaitForExit()
if ($process.ExitCode -ne 0 -or -not (Test-Path $Report)) {
    $log = Join-Path $env:LOCALAPPDATA "LLocalMind\logs\application.log"
    if (Test-Path $log) { Get-Content $log -Tail 100 }
    throw "LLocalMind smoke test failed (exit $($process.ExitCode))."
}
$result = Get-Content $Report -Raw | ConvertFrom-Json
if (-not $result.ok) { throw "LLocalMind smoke test failed: $($result.error)" }
Get-Content $Report
