$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'QQ' -or ($_.CommandLine -and $_.CommandLine -match 'QQ') }
$hit = $false
foreach ($p in $procs) {
    if ($p.CommandLine -and $p.CommandLine -match 'remote-debugging|inspect|devtools|--debug|9222|9229') {
        $hit = $true
        Write-Host ("HIT: " + $p.Name + " PID=" + $p.ProcessId)
        Write-Host $p.CommandLine
        Write-Host "----"
    }
}
if (-not $hit) { Write-Host "No QQ process with debug flags detected in command line." }
Write-Host "=== listeners on 9222 / 9229 / 9210 ==="
$lines = netstat -ano 2>$null | Select-String -Pattern ':9222 |:9229 |:9210 '
if ($lines) { $lines | ForEach-Object { Write-Host $_.Line } } else { Write-Host "(none)" }
