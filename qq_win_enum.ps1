# qq_win_enum.ps1  (READ-ONLY diagnostic)
# Enumerates QQ's window tree to discover the chat input control's HWND + class.
# Does NOT send, focus, or modify anything. Pure enumeration + print.

Add-Type @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public class WinApi {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc lp, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hParent, EnumProc lp, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);

    public static string Title(IntPtr h) {
        var sb = new StringBuilder(256); GetWindowText(h, sb, sb.Capacity); return sb.ToString();
    }
    public static string Class(IntPtr h) {
        var sb = new StringBuilder(256); GetClassName(h, sb, sb.Capacity); return sb.ToString();
    }
}
'@

# --- find QQ PIDs ---
$qqProcs = @(Get-Process | Where-Object { $_.Name -match 'QQ' })
if ($qqProcs.Count -eq 0) { Write-Host "No QQ process found."; exit 0 }
$qqPids = @($qqProcs | ForEach-Object { $_.Id })
Write-Host ("QQ PIDs: " + ($qqPids -join ', '))
Write-Host ""

$results = [System.Collections.Generic.List[string]]::new()

# callback state
$script:topPid = 0

$childProc = {
    param([IntPtr]$h, [IntPtr]$l)
    $procId = 0
    [WinApi]::GetWindowThreadProcessId($h, [ref]$procId) | Out-Null
    if ($procId -ne $script:topPid) { return $true }
    $cls = [WinApi]::Class($h)
    $ttl = [WinApi]::Title($h)
    $vis = [WinApi]::IsWindowVisible($h)
    $script:childCount++
    # only keep input-like windows to avoid dumping the whole CEF tree
    if ($cls -match 'edit|input|rich|text|imm|atlas|chrome|cef|webview') {
        $results.Add(("    [child] hwnd=0x{0:X} cls='{1}' vis={2} title='{3}'  <== INPUT-LIKE" -f [int]$h, $cls, $vis, $ttl))
    }
    if ($script:childCount -gt 4000) { return $false }  # safety stop
    return $true
}

$topProc = {
    param([IntPtr]$h, [IntPtr]$l)
    $procId = 0
    [WinApi]::GetWindowThreadProcessId($h, [ref]$procId) | Out-Null
    if ($qqPids -notcontains $procId) { return $true }
    $script:topPid = $procId
    $script:childCount = 0
    $cls = [WinApi]::Class($h)
    $ttl = [WinApi]::Title($h)
    $vis = [WinApi]::IsWindowVisible($h)
    $results.Add(("=== TOP hwnd=0x{0:X} pid={1} cls='{2}' vis={3} title='{4}'" -f [int]$h, $procId, $cls, $vis, $ttl))
    [WinApi]::EnumChildWindows($h, $childProc, [IntPtr]::Zero) | Out-Null
    $results.Add(("    (enumerated {0} child windows under this top window)" -f $script:childCount))
    $results.Add("")
    return $true
}

[WinApi]::EnumWindows($topProc, [IntPtr]::Zero) | Out-Null

foreach ($line in $results) { Write-Host $line }
Write-Host ""
Write-Host "Done (read-only)."
