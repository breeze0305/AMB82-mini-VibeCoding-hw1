param([string]$Port = 'COM3', [int]$Seconds = 40)
$ErrorActionPreference = 'Stop'
if ($Seconds -lt 1 -or $Seconds -gt 300) { throw 'Seconds must be between 1 and 300.' }
$taskSerial = [System.IO.Ports.SerialPort]::new($Port, 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$taskSerial.ReadTimeout = 1000
$taskSerial.DtrEnable = $false
$taskSerial.RtsEnable = $false
$taskFound = $false
try {
    $taskSerial.Open()
    Write-Host "Listening on $Port at 115200 baud. Press RESET on the board if it is still in download mode."
    $taskDeadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $taskDeadline) {
        try {
            $taskLine = $taskSerial.ReadLine().Trim()
            if ($taskLine -match 'AMB_IP=([0-9.]+)') {
                Write-Host ('AMB IP: ' + $Matches[1] + '   TCP port: 8266')
                $taskFound = $true
                break
            }
            if ($taskLine -match 'Wi-Fi|Connecting to configured|endpoint starting|server ready') { Write-Host $taskLine }
        } catch [System.TimeoutException] { }
    }
    if (-not $taskFound) { Write-Host 'No IP received yet. Check RESET, Wi-Fi credentials and signal, then try again.' }
} finally {
    if ($taskSerial.IsOpen) { $taskSerial.Close() }
    $taskSerial.Dispose()
}
