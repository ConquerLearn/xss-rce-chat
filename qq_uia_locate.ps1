# qq_uia_locate.ps1  (READ-ONLY diagnostic)
# Uses UI Automation to look INSIDE the QQ Chromium window for the chat input
# control (the DOM textarea/contenteditable has no Win32 HWND, but UIA can
# usually reach it once accessibility is enabled by the AT connection).
# Does NOT focus, click, or send anything. Pure discovery + print.

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$ae      = [System.Windows.Automation.AutomationElement]
$cond    = [System.Windows.Automation.PropertyCondition]
$ctrl    = [System.Windows.Automation.ControlType]

# 1) locate the QQ main window - try class-only first (Chromium Name may be empty in UIA view)
$clsCond = New-Object $cond($ae::ClassNameProperty, 'Chrome_WidgetWin_1')
$qqWin = $ae::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children, $clsCond)

# diagnostic: show what UIA sees at top level
Write-Host "--- UIA top-level diagnostic (class + name) ---"
try {
    $tops = $ae::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::True)
    $n = 0
    foreach ($t in $tops) {
        $n++
        if ($n -gt 25) { Write-Host "...(truncated)"; break }
        $c = $t.Current.ClassName; $nm = $t.Current.Name
        if ($c -match 'Chrome|QQ|Widget') {
            Write-Host ("  hwnd=0x{0:X} cls='{1}' name='{2}'" -f $t.Current.NativeWindowHandle, $c, $nm)
        }
    }
} catch { Write-Host ("  diag err: " + $_.Exception.Message) }

if ($null -eq $qqWin) {
    Write-Host "QQ main window (Chrome_WidgetWin_1) not found via UIA -> accessibility likely dormant."
    exit 0
}
Write-Host ("Found QQ main window: hwnd=0x{0:X}" -f $qqWin.Current.NativeWindowHandle)

# 2) walk all descendants, collect keyboard-focusable edit-like controls
$editCond = New-Object $cond($ae::ControlTypeProperty, $ctrl::Edit)
$docCond  = New-Object $cond($ae::ControlTypeProperty, $ctrl::Document)
$orCond   = New-Object System.Windows.Automation.OrCondition($editCond, $docCond)

$found = @()
try {
    $elems = $qqWin.FindAll([System.Windows.Automation.TreeScope]::Descendants, $orCond)
    Write-Host ("UIA exposed {0} Edit/Document elements under QQ." -f $elems.Count)
    $i = 0
    foreach ($e in $elems) {
        $i++
        if ($i -gt 40) { Write-Host "...(truncated at 40)"; break }
        $rect = $e.Current.BoundingRectangle
        $patterns = ''
        try { if ($e.GetSupportedPatterns().Length -gt 0) { $patterns = ($e.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName }) -join ',' } } catch {}
        $line = ("[{0}] type={1} name='{2}' autoId='{3}' focusable={4} kbFocus={5} rect=({6},{7} {8}x{9})" `
                 -f $i, $e.Current.ControlType.ProgrammaticName, $e.Current.Name, $e.Current.AutomationId,
                    $e.Current.IsEnabled, $e.Current.IsKeyboardFocusable,
                    [int]$rect.X, [int]$rect.Y, [int]$rect.Width, [int]$rect.Height)
        Write-Host $line
        if ($patterns) { Write-Host ("      patterns: " + $patterns) }
    }
} catch {
    Write-Host ("UIA walk failed: " + $_.Exception.Message)
}

Write-Host ""
Write-Host "Done (read-only)."
