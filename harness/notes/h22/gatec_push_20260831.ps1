$env:SYNAPSE_GATE_C = '1'
git -C C:\Users\User\SYNAPSE push origin master
$pushExit = $LASTEXITCODE
Remove-Item Env:SYNAPSE_GATE_C -ErrorAction SilentlyContinue
Write-Output '--POST-PUSH-STATE--'
git -C C:\Users\User\SYNAPSE status -sb | Select-Object -First 2
Write-Output '--REMOTE-HEAD--'
git -C C:\Users\User\SYNAPSE ls-remote origin refs/heads/master
Write-Output "--PUSH-EXIT=$pushExit--"
exit $pushExit
