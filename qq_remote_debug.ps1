# qq_remote_debug.ps1
# Attempts to launch QQ with Chrome DevTools Protocol enabled (--remote-debugging-port=9222)
# so you can inspect the chat renderer DOM (textContent vs innerHTML) via a browser at
# http://127.0.0.1:9222
#
# IMPORTANT:
# - Close QQ completely first (single-instance lock will otherwise block / ignore the flag).
# - Release builds may strip this flag or anti-debug may alter behavior. Best-effort only.
# - This only exposes YOUR local renderer to localhost. For your own testing.
#
# ============================ CONFIRMED NOT VIABLE ============================
# (2026-09-14) On this QQ build (9.9.35-52892, signed/hardened) passing
# --remote-debugging-port=9222 makes QQ EXIT WITHIN ~12s (procs 3 -> 1 -> 0) and
# port 9222 NEVER listens. Without the flag QQ runs fine. So CDP is NOT usable
# on this install. DO NOT rely on this script; it will only break the running QQ.
# To restore QQ afterwards use: .\restore_qq.ps1 -Wait
# =============================================================================

param([switch]$Launch, [switch]$Force)

$qq = $null
$qp = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'QQ\.exe$' } | Select-Object -First 1
if ($qp) { $qq = $qp.ExecutablePath }
if (-not $qq) {
    $cands = @('D:\qq\QQ.exe','C:\Program Files\Tencent\QQ\QQ.exe','D:\Program Files\Tencent\QQ\QQ.exe')
    foreach ($c in $cands) { if (Test-Path $c) { $qq = $c; break } }
}
if (-not $qq) { Write-Host "QQ.exe not found. Set path manually."; exit 1 }
Write-Host ("QQ.exe: " + $qq)

if (Get-Process -Name 'QQ' -ErrorAction SilentlyContinue) {
    if (-not $Force) {
        Write-Host "QQ is already running. Close it fully first (right-click tray -> exit), then re-run."
        Write-Host "Or re-run with -Force to stop existing QQ and relaunch with the debug port."
        exit 1
    }
    Write-Host "[-Force] Stopping existing QQ processes ..."
    Stop-Process -Name 'QQ' -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

$cmd = '"{0}" --remote-debugging-port=9222' -f $qq
Write-Host ("Command: " + $cmd)
if ($Launch) {
    Write-Host "Launching with remote debugging on port 9222 ..."
    Start-Process -FilePath $qq -ArgumentList '--remote-debugging-port=9222'
    Write-Host "Open http://127.0.0.1:9222 in Chrome/Edge to inspect the renderer."
} else {
    Write-Host "Re-run with -Launch to actually start it (after closing QQ)."
}
