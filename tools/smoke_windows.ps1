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
$stdout = $Report + '.stdout.log'
$stderr = $Report + '.stderr.log'
New-Item -ItemType Directory -Path (Split-Path -Parent $Report) -Force | Out-Null
$process = Start-Process -FilePath $Executable -ArgumentList $arguments -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$null = $process.Handle
if (-not $process.WaitForExit(180000)) {
    Stop-Process -Id $process.Id -Force
    if (Test-Path $stderr) { Get-Content $stderr -Tail 60 }
    if (Test-Path $Report) { Get-Content $Report }
    throw "LLocalMind smoke test timed out."
}
$process.WaitForExit()
if ($process.ExitCode -ne 0 -or -not (Test-Path $Report)) {
    $log = Join-Path $env:LOCALAPPDATA "LLocalMind\logs\application.log"
    if (Test-Path $log) { Get-Content $log -Tail 100 }
    $details = ''
    if (Test-Path $stderr) { $details += (Get-Content $stderr -Raw) }
    if (Test-Path $Report) { $details += (Get-Content $Report -Raw) }
    Write-Output $details
    if ($env:GITHUB_ACTIONS -eq 'true') {
        $message = $details.Replace('%','%25').Replace("`r",'%0D').Replace("`n",'%0A')
        Write-Output "::error title=LLocalMind runtime::$message"
    }
    throw "LLocalMind smoke test failed (exit $($process.ExitCode))."
}
$result = Get-Content $Report -Raw | ConvertFrom-Json
if (-not $result.ok) { throw "LLocalMind smoke test failed: $($result.error)" }
Get-Content $Report
