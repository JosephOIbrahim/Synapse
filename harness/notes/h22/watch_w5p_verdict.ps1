# watch_w5p_verdict.ps1 - detached sentinel for the PARITY crucible.
# On W5-PCRUX landing: flag file + desktop alert. Ephemeral debris, untracked.
$deadline = (Get-Date).AddHours(10)
$flag = 'C:\Users\User\SYNAPSE\harness\notes\h22\w5p-landed.flag'
Add-Type -AssemblyName System.Windows.Forms
while ((Get-Date) -lt $deadline) {
    $c = @(Get-ChildItem 'C:\Users\User\SYNAPSE\.claude\worktrees\w5-*\harness\notes\receipts\W5-PCRUX.json','C:\Users\User\SYNAPSE\harness\notes\receipts\W5-PCRUX.json' -ErrorAction SilentlyContinue)
    if ($c.Count -gt 0) {
        $t = Get-Date -Format 'HH:mm:ss'
        "LANDED $t  $($c[0].FullName)" | Out-File $flag -Encoding ascii
        [System.Windows.Forms.MessageBox]::Show(
            "W5-PCRUX parity verdict landed at $t.`n`n$($c[0].FullName)`n`nRead it: is the panel 1:1 with the repo, and what stays UNKNOWN for your seat.",
            "SYNAPSE - panel parity wave",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information,
            [System.Windows.Forms.MessageBoxDefaultButton]::Button1,
            [System.Windows.Forms.MessageBoxOptions]::DefaultDesktopOnly) | Out-Null
        exit 0
    }
    Start-Sleep -Seconds 30
}
"TIMEOUT $(Get-Date -Format 'HH:mm:ss') - no parity verdict within 10h" | Out-File $flag -Encoding ascii
