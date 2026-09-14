# qq_xss_clip.ps1
# Purpose: copy the Nth XSS payload from the shortlist to the clipboard,
#          so YOU can paste (Ctrl+V) + Enter it into QQ manually.
# Design : one payload at a time, user-controlled. No auto bulk sending
#          (avoids anti-spam bans / platform ToS violation).
#
# Usage:
#   .\qq_xss_clip.ps1            # payload #1
#   .\qq_xss_clip.ps1 -Index 3   # payload #4
#   .\qq_xss_clip.ps1 -List      # show the list only, do not copy
#   .\qq_xss_clip.ps1 -Dump      # write all payloads to payloads_all.txt
param(
    [int]$Index = 0,
    [string]$ListFile = (Join-Path $PSScriptRoot 'payload_shortlist.txt'),
    [switch]$List,
    [switch]$Dump
)

$items = @(Get-Content -LiteralPath $ListFile -Encoding UTF8 | Where-Object { $_.Trim().Length -gt 0 })

if ($Dump) {
    $out = Join-Path $PSScriptRoot 'payloads_all.txt'
    $items | Set-Content -LiteralPath $out -Encoding UTF8
    Write-Host ("Wrote {0} payloads to {1}" -f $items.Count, $out)
    exit 0
}

if ($List) {
    for ($i = 0; $i -lt $items.Count; $i++) {
        Write-Host ("  [{0,2}] {1}" -f $i, $items[$i])
    }
    Write-Host ("Total: {0}" -f $items.Count)
    exit 0
}

if ($Index -lt 0 -or $Index -ge $items.Count) {
    Write-Host ("Index out of range. Valid: 0..{0}" -f ($items.Count - 1))
    exit 1
}

$p = $items[$Index]
Set-Clipboard -Value $p

Write-Host ("[{0}/{1}] copied to clipboard:" -f ($Index + 1), $items.Count)
Write-Host ("  " + $p)
Write-Host ""
Write-Host "Next: switch to the QQ window -> Ctrl+V -> Enter"
if ($Index + 1 -lt $items.Count) {
    Write-Host ("Next payload: .\qq_xss_clip.ps1 -Index {0}" -f ($Index + 1))
} else {
    Write-Host "This is the last one."
}
