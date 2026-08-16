Write-Host ("now " + (Get-Date -Format 'HH:mm:ss'))
Get-Content C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.log -Tail 3
Get-ChildItem C:\Users\User\SYNAPSE\harness\notes\h22\*-landed.flag -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name
Write-Host 'rc handled by steward (dedup ledger in steward.log)'
