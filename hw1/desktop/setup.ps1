param([string]$Python = "")
$ErrorActionPreference = "Stop"
$venvDir = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonArgs = @()
    if ($Python) {
        $bootstrap = (Get-Command -Name $Python -ErrorAction Stop).Source
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $bootstrap = (Get-Command py).Source
        $pythonArgs = @("-3")
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $bootstrap = (Get-Command python).Source
    } else {
        throw "Python was not found. Install 64-bit Python with tkinter, or pass -Python C:\path\python.exe."
    }
    & $bootstrap @pythonArgs -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
}
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Python package installation failed." }
& $venvPython (Join-Path $PSScriptRoot "download_model.py")
if ($LASTEXITCODE -ne 0) { throw "Speech model installation failed." }
& $venvPython -c "import tkinter, faster_whisper, sounddevice, pypinyin; print('Desktop dependencies are ready.')"
if ($LASTEXITCODE -ne 0) { throw "Dependency check failed." }
Write-Host "Setup complete. Run start.ps1 (or double-click start.cmd)."
