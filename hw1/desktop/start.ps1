param([string]$IP = "", [int]$Device = -1, [string]$Model = "")
$ErrorActionPreference = "Stop"
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Run setup.ps1 first to install the desktop application dependencies."
}
$appArgs = @((Join-Path $PSScriptRoot "app.py"))
if ($IP) { $appArgs += @("--ip", $IP) }
if ($Device -ge 0) { $appArgs += @("--device", "$Device") }
if ($Model) { $appArgs += @("--model", $Model) }
& $venvPython @appArgs
exit $LASTEXITCODE
