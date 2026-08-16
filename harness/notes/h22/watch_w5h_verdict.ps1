# watch_w5h_verdict.ps1 - detached sentinel. Polls for the W5-HCRUX verdict;
# on landing: writes the flag file (poll-to-flag pattern) and pops a desktop alert.
# Exits silently at the deadline if nothing lands. Ephemeral debris, untracked.
$deadline = (Get-Date).AddHours(8)
$flag = 'C:\Users\User\SYNAPSE\harness\notes\h22\w5h-landed.flag'
Add-Type -AssemblyName System.Windows.Forms
while ((Get-Date) -lt $deadline) {
    $c = @(Get-ChildItem 'C:\Users\User\SYNAPSE\.claude\worktrees\w5-*\harness\notes\receipts\W5-HCRUX.json','C:\Users\User\SYNAPSE\harness\notes\receipts\W5-HCRUX.json' -ErrorAction SilentlyContinue)
    if ($c.Count -gt 0) {
        $t = Get-Date -Format 'HH:mm:ss'
        "LANDED $t  $($c[0].FullName)" | Out-File $flag -Encoding ascii
        [System.Windows.Forms.MessageBox]::Show(
            "W5-HCRUX verdict landed at $t.`n`n$($c[0].FullName)`n`nRead it, then give the merge word.",
            "SYNAPSE - house-cleaning wave",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information,
            [System.Windows.Forms.MessageBoxDefaultButton]::Button1,
            [System.Windows.Forms.MessageBoxOptions]::DefaultDesktopOnly) | Out-Null
        exit 0
    }
    Start-Sleep -Seconds 30
}
"TIMEOUT $(Get-Date -Format 'HH:mm:ss') - no verdict within 8h" | Out-File $flag -Encoding ascii
