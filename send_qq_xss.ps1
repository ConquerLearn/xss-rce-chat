# send_qq_xss.ps1
# Sends XSS test payloads into the CURRENTLY FOCUSED QQ chat window, one by one.
# YOU must: (1) open the "xiao hou / alt" chat, (2) click into its text input, (3) keep it focused.
# The script only sends to whatever window is in the foreground. Mis-focus = mis-send.
#
# This is for testing YOUR OWN two accounts. Risk: Tencent anti-spam may restrict the account.
# Sends with a delay (default 5s). Abort anytime with Ctrl+C.
#
# Usage:
#   .\send_qq_xss.ps1              # 30-line faithful sample (derived from easyXssPayload.txt), 5s gap
#   .\send_qq_xss.ps1 -Delay 8     # 8s gap
#   .\send_qq_xss.ps1 -All         # full payload file (NOT recommended: high ban risk)
#   .\send_qq_xss.ps1 -ListFile payload_expanded.txt   # custom wordlist
#   .\send_qq_xss.ps1 -DryRun      # list what would be sent, do nothing

param(
    [int]$Delay = 5,
    [switch]$All,
    [string]$ListFile = '',
    [switch]$DryRun
)

$short = Join-Path $PSScriptRoot 'payload_sample_30.txt'
$full  = 'C:\Users\Administrator\Downloads\easyXssPayload-master\easyXssPayload.txt'
if ($ListFile) { $file = $ListFile } elseif ($All) { $file = $full } else { $file = $short }
$items = @(Get-Content -LiteralPath $file -Encoding UTF8 | Where-Object { $_.Trim().Length -gt 0 })

Write-Host ("Loaded {0} payloads from {1}" -f $items.Count, $file)
if ($All) { Write-Host "WARNING: full 1850 blast. High ban risk. Ctrl+C to abort." }

if ($DryRun) {
    for ($i = 0; $i -lt $items.Count; $i++) { Write-Host ("  [{0}] {1}" -f $i, $items[$i]) }
    exit 0
}

Write-Host ""
Write-Host "STEP 1: Open the QQ 'xiao hao' (alt) chat and click into its message input box."
Write-Host "STEP 2: Keep that window focused. The script sends to the FOREGROUND window only."
$ans = Read-Host "Type 'yes' once the alt chat input is focused and ready"
if ($ans -ne 'yes') { Write-Host "Aborted."; exit 1 }

Add-Type -AssemblyName System.Windows.Forms

Write-Host ""
Write-Host ("Sending {0} payloads with {1}s gap." -f $items.Count, $Delay)
Write-Host ">>> Switch to the 小号->主号 chat input NOW. Sending starts in 6 seconds. Ctrl+C to abort."
Start-Sleep -Seconds 6

for ($i = 0; $i -lt $items.Count; $i++) {
    $p = $items[$i]
    [System.Windows.Forms.Clipboard]::SetText($p)
    Start-Sleep -Milliseconds 400
    [System.Windows.Forms.SendKeys]::SendWait("^v")
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    Write-Host ("[{0}/{1}] sent: {2}" -f ($i+1), $items.Count, $p)
    if ($i + 1 -lt $items.Count) { Start-Sleep -Seconds $Delay }
}
Write-Host "Done."
