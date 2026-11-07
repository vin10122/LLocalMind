# Parse without executing the installer, then verify launcher argument splitting.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$files = @(Get-Item (Join-Path $root 'install.ps1')) + @(Get-ChildItem (Join-Path $root 'scripts') -Filter *.ps1)
foreach ($file in $files) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count) { throw ($errors | Out-String) }
}
function Invoke-FakePython {
    param([Parameter(ValueFromRemainingArguments=$true)] [string[]]$Arguments)
    return $Arguments
}
$executable = 'Invoke-FakePython'
$interpreterArguments = @('-3.14')
$captured = @(& $executable @interpreterArguments --version)
if ($captured.Count -ne 2 -or $captured[0] -ne '-3.14' -or $captured[1] -ne '--version') {
    throw 'Python launcher arguments were not passed separately'
}
Write-Host 'Installer syntax and launcher invocation checks passed.'
