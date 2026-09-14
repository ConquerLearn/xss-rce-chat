# restore_qq.ps1
# Reliably (re)start QQ in a CLEAN environment.
#
# WHY THIS EXISTS
# ---------------
# The agent shell exports ELECTRON_RUN_AS_NODE=1 (and possibly other Node/Electron
# vars). QQ is an Electron/CEF app, so when it is started from that shell it runs
# in plain Node mode and crashes immediately in QQNT.dll ("QQ遇到错误").
#
# Launching through explorer.exe makes QQ inherit the logged-on user's normal
# environment (same as a desktop double-click), so it starts healthy.
#
# Verified: QQ comes up with ~9 processes, its local auth service on port 9210
# starts listening, and the main window (class Chrome_WidgetWin_1, title 'QQ')
# appears.
#
# NOTE: Do NOT pass --remote-debugging-port to QQ. This signed/hardened release
# build rejects/strips it: the browser process fails to initialise and QQ exits
# within ~12s. Chrome DevTools Protocol is therefore NOT usable on this install.

param([switch]$Wait)

$qqPath = "D:\qq\QQ.exe"
if (-not (Test-Path $qqPath)) {
    $cands = @('D:\qq\QQ.exe','C:\Program Files\Tencent\QQ\QQ.exe','D:\Program Files\Tencent\QQ\QQ.exe')
    foreach ($c in $cands) { if (Test-Path $c) { $qqPath = $c; break } }
}
if (-not (Test-Path $qqPath)) { Write-Host "QQ.exe not found."; exit 1 }

# stop a broken/half-dead instance if present
if (Get-Process -Name 'QQ' -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing QQ processes ..."
    Stop-Process -Name 'QQ' -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

Write-Host ("Launching via explorer (clean user environment): " + $qqPath)
Start-Process -FilePath "explorer.exe" -ArgumentList ('"' + $qqPath + '"')

if ($Wait) {
    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Seconds 2
        $procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -like 'D:\qq*' }
        Write-Host ("  t+{0}s procs={1}" -f ($i*2), $procs.Count)
        if ($procs.Count -ge 5) { break }
    }
    $win = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -like 'D:\qq*' -and $_.MainWindowHandle -ne 0 }
    if ($win) { Write-Host ("QQ window OK: hwnd={0} title='{1}'" -f $win[0].MainWindowHandle, $win[0].MainWindowTitle) }
    else { Write-Host "QQ window not detected yet (may still be initialising)." }
}
