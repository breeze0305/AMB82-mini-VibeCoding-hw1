param(
    [string]$Port = 'COM3',
    [string]$CliPath = ''
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskSketch = Join-Path $taskRoot 'firmware\amb82_voice_led'
if (-not (Test-Path -LiteralPath (Join-Path $taskSketch 'wifi_config.h'))) {
    throw 'Create firmware/amb82_voice_led/wifi_config.h from wifi_config.example.h and set Wi-Fi credentials first.'
}
if (-not $CliPath) {
    $taskCommand = Get-Command arduino-cli -ErrorAction SilentlyContinue
    if ($taskCommand) {
        $CliPath = $taskCommand.Source
    } else {
        $taskCandidates = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'),
            (Join-Path $env:ProgramFiles 'Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe')
        )
        $CliPath = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
}
if (-not $CliPath -or -not (Test-Path -LiteralPath $CliPath)) {
    throw 'arduino-cli was not found. Supply -CliPath with the executable path.'
}
$taskBoard = 'realtek:AmebaPro2:Ameba_AMB82-MINI:01_AutoUploadMode=Disable,02_UploadBaudrate=2M,03_EraseFlash=Disable'
$taskBuild = Join-Path $taskRoot '.build\amb82'
$taskOutput = Join-Path $taskRoot 'build'
$taskLogs = Join-Path $taskRoot 'logs'
New-Item -ItemType Directory -Force -Path $taskBuild, $taskOutput, $taskLogs | Out-Null
# The vendor's Windows executables reject the C.UTF-8 locale inherited from
# some terminals. Change it for this invocation only, then restore it.
$taskOldLang = $env:LANG
$taskOldLocale = $env:LC_ALL
$taskOldCtype = $env:LC_CTYPE
try {
    $env:LANG = 'C'
    $env:LC_ALL = 'C'
    $env:LC_CTYPE = 'C'
    Write-Host 'Compiling AMB82-MINI firmware...'
    & $CliPath compile --fqbn $taskBoard --build-path $taskBuild --output-dir $taskOutput $taskSketch 2>&1 | Tee-Object -FilePath (Join-Path $taskLogs 'compile.log')
    if ($LASTEXITCODE -ne 0) { throw "Compilation failed ($LASTEXITCODE). See hw1/logs/compile.log." }
    # Ameba emits flash_ntz.bin instead of the sketch-name artifact expected by
    # newer CLI releases. Pass the exact binary rather than asking CLI to find it.
    $taskBinary = Join-Path $taskOutput 'flash_ntz.bin'
    Copy-Item -LiteralPath (Join-Path $taskBuild 'flash_ntz.bin') -Destination $taskBinary -Force
    Write-Host "Uploading to $Port. The board must be in download mode."
    & $CliPath upload --fqbn $taskBoard --port $Port --input-file $taskBinary $taskSketch 2>&1 | Tee-Object -FilePath (Join-Path $taskLogs 'upload.log')
    if ($LASTEXITCODE -ne 0) { throw "Upload failed ($LASTEXITCODE). See hw1/logs/upload.log." }
    Write-Host 'Upload completed. Press RESET if necessary; the IP is printed on Serial at 115200 baud.'
} finally {
    $env:LANG = $taskOldLang
    $env:LC_ALL = $taskOldLocale
    $env:LC_CTYPE = $taskOldCtype
}
