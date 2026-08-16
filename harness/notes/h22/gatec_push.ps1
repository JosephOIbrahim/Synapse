Set-Location C:\Users\User\SYNAPSE
$env:SYNAPSE_GATE_C = 1
git push origin master
Remove-Item Env:SYNAPSE_GATE_C
git status -sb | Select-Object -First 1
git log --oneline -1
