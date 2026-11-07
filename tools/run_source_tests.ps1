# Keep a useful failure annotation even when anonymous Actions logs are unavailable.
$ErrorActionPreference = 'Stop'
$env:FLASH_MOE_TEST_NATIVE = "$env:GITHUB_WORKSPACE\src\flash_moe\moe_quant_dot.dll"
. "$PSScriptRoot\test_installer.ps1"
foreach ($test in @('test_updater.py','test_gui.py','test_multimodal.py','test_vision_runtime.py','test_optimized_inference.py','test_performance_policy.py')) {
    $output = & python (Join-Path $PSScriptRoot $test) 2>&1
    $code = $LASTEXITCODE
    $output | Write-Output
    if ($code -ne 0) {
        $details = "$test failed: " + ($output | Out-String)
        if ($details.Length -gt 10000) { $details = $details.Substring($details.Length - 10000) }
        $message = $details.Replace('%','%25').Replace("`r",'%0D').Replace("`n",'%0A')
        Write-Output "::error title=Source tests::$message"
        exit $code
    }
}
