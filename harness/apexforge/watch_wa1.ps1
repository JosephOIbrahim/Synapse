# watch_wa1.ps1 - detached verdict watcher: fires a desktop alert + drops a
# flag file the moment the WA1-ACRUX receipt lands in any wa1 worktree or in-tree.
$ErrorActionPreference = 'SilentlyContinue'
$repo = 'C:\Users\User\SYNAPSE'
$flag = Join-Path $repo 'harness\notes\h22\WA1_ACRUX_LANDED.flag'
$paths = @(
    (Join-Path $repo 'harness\notes\receipts\WA1-ACRUX.json'),
    (Join-Path $repo '.claude\worktrees\wa1-acrux\harness\notes\receipts\WA1-ACRUX.json')
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
            $n.ShowBalloonTip(10000, 'SYNAPSE APEXFORGE', 'WA1-ACRUX verdict landed. Wave WA1 awaits your ruling.', [System.Windows.Forms.ToolTipIcon]::Info)
            Start-Sleep -Seconds 12
            $n.Dispose()
            exit 0
        }
    }
    Start-Sleep -Seconds 30
}
