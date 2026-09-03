# watch_bp4.ps1 - detached verdict watcher (clone of watch_bp1.ps1, wave id swap):
# fires a desktop alert + drops a flag file the moment the BP4-CRUX receipt lands
# in the bp4-crux worktree or in-tree. Verdicts are READ before merge words fire.
$ErrorActionPreference = 'SilentlyContinue'
$repo = 'C:\Users\User\SYNAPSE'
$flag = Join-Path $repo 'harness\notes\h22\BP4_CRUX_LANDED.flag'
$paths = @(
    (Join-Path $repo 'harness\notes\receipts\BP4-CRUX.json'),
    (Join-Path $repo '.claude\worktrees\bp4-crux\harness\notes\receipts\BP4-CRUX.json')
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
            $n.ShowBalloonTip(10000, 'SYNAPSE BATTLEPLAN', 'BP4-CRUX verdict landed. Read it before any merge word.', [System.Windows.Forms.ToolTipIcon]::Info)
            Start-Sleep -Seconds 12
            $n.Dispose()
            exit 0
        }
    }
    Start-Sleep -Seconds 30
}
