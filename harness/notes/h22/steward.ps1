# steward.ps1 - detached ops steward. READS harness state; NEVER touches gates.
# Automates: /rc delivery to new leg windows, crash-loop detection, FAILED/stale toasts.
# The P4 seam (merge/push-word/drop/ratified) stays human. Ephemeral ops, ~10h life.
$deadline = (Get-Date).AddHours(10)
$log = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.log'
$out = 'C:\Users\User\SYNAPSE\harness\notes\h22\steward.log'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic
$wsh = New-Object -ComObject WScript.Shell
$rcDone = @{ 'W5-PARITY' = $true }
$toasted = @{}
$lastLine = 0
function Toast($title, $msg) {
    [System.Windows.Forms.MessageBox]::Show($msg, $title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning,
        [System.Windows.Forms.MessageBoxDefaultButton]::Button1,
        [System.Windows.Forms.MessageBoxOptions]::DefaultDesktopOnly) | Out-Null
}
while ((Get-Date) -lt $deadline) {
    # 1) /rc to any new leg window, once each
    $wins = Get-Process | Where-Object { $_.MainWindowTitle -match 'SYNAPSE (W[56]-[A-Z]+)' }
    foreach ($p in $wins) {
        if ($p.MainWindowTitle -match 'SYNAPSE (W[56]-[A-Z]+)') {
            $leg = $Matches[1]
            if (-not $rcDone[$leg]) {
                [Microsoft.VisualBasic.Interaction]::AppActivate($p.Id); Start-Sleep -Milliseconds 700
                $wsh.SendKeys('/rc'); Start-Sleep -Milliseconds 300; $wsh.SendKeys('~')
                $rcDone[$leg] = $true
                Add-Content $out ((Get-Date -Format 'HH:mm:ss') + "  /rc -> " + $leg)
            }
        }
    }
    # 2+3) scan new orchestrator lines for FAILED / stale / crash signals
    $lines = @(Get-Content $log -ErrorAction SilentlyContinue)
    if ($lines.Count -gt $lastLine) {
        foreach ($l in $lines[$lastLine..($lines.Count - 1)]) {
            if ($l -match 'FAILED|STALE|NOT dispatched|crash') {
                $key = ($l -replace '\d', '').Substring(0, [Math]::Min(60, $l.Length))
                if (-not $toasted[$key]) {
                    $toasted[$key] = $true
                    Add-Content $out ((Get-Date -Format 'HH:mm:ss') + "  ALERT " + $l)
                    Toast 'SYNAPSE steward' ("Attention: " + $l + "`n`nSteward detected this; gates untouched.")
                }
            }
        }
        $lastLine = $lines.Count
    }
    Start-Sleep -Seconds 60
}
Add-Content $out ((Get-Date -Format 'HH:mm:ss') + '  steward deadline reached, exiting')
