$log='C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w4.log'
(Select-String -Path $log -Pattern 'board ' | Select-Object -Last 1).Line
Select-String -Path $log -Pattern 'STATE|DIGEST|receipt|BLOCK|FAIL' | Select-Object -Last 3 | ForEach-Object { $_.Line }
foreach ($l in 'help','know','guard','crux') { $c = git -C C:\Users\User\SYNAPSE rev-list --count ("master..wave4/" + $l) 2>$null; Write-Output ("wave4/" + $l + " ahead:" + $c) }
foreach ($l in 'w4-help','w4-know','w4-guard','w4-crux') { $p = 'C:\Users\User\SYNAPSE\.claude\worktrees\' + $l + '\harness\notes\receipts\' + $l.ToUpper() + '.json'; if (Test-Path $p) { Write-Output ($l + ' RECEIPT') } }
$n = (Get-Content C:\Users\User\SYNAPSE\harness\autorevise\bus\wave4\bus.jsonl | Measure-Object -Line).Lines; Write-Output ("bus:" + $n)
