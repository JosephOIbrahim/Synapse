# watch_bp1.ps1 - detached verdict watcher: fires a desktop alert + drops a
# flag file the moment the BP1-CRUX receipt lands in any bp1 worktree or in-tree.
$ErrorActionPreference = 'SilentlyContinue'
$repo = 'C:\Users\User\SYNAPSE'
$flag = Join-Path $repo 'harness\notes\h22\BP1_CRUX_LANDED.flag'
$paths = @(
    (Join-Path $repo 'harness\notes\receipts\BP1-CRUX.json'),
    (Join-Path $repo '.claude\worktrees\bp1-crux\harness\notes\receipts\BP1-CRUX.json')
)
while ($true) {
    foreach ($p in $paths) {
        if (Test-Path $p) {
            $stamp = (Get-Date).ToString('s')
            ("landed " + $stamp + " at " + $p) | Out-File $flag -Encoding ascii
            Add-Type -AssemblyName System.Windows.Forms
            $n = New-Object System.Windows.Forms.NotifyIcon
            $n.Icon = [System.Drawing.SystemIcons]::Information
            $n.Visible = $true
            $n.ShowBalloonTip(10000, 'SYNAPSE BATTLEPLAN', 'BP1-CRUX verdict landed. Wave BP1 awaits your ruling.', [System.Windows.Forms.ToolTipIcon]::Info)
            Start-Sleep -Seconds 12
            $n.Dispose()
            exit 0
        }
    }
    Start-Sleep -Seconds 30
}
