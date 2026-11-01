# Start the LiveWell lab Mosquitto broker (run after setup_lab.py).
$ErrorActionPreference = "Stop"
$conf = Join-Path $env:LOCALAPPDATA "LiveWellMqtt\mosquitto.conf"
$exe = "C:\Program Files\mosquitto\mosquitto.exe"
if (-not (Test-Path $conf)) { throw "Run python deploy/mqtt/setup_lab.py first ($conf missing)" }
if (-not (Test-Path $exe)) { throw "Mosquitto not found at $exe" }
& $exe -c $conf
