$repo = 'C:\Users\User\SYNAPSE'
$log  = Join-Path $repo 'harness\notes\h22\orchestrator-w5l.log'
$b = Select-String -Path $log -Pattern 'board ' | Select-Object -Last 1
if ($b) { Write-Host ('BOARD=' + $b.Line) } else { Write-Host 'BOARD=none' }
$names = @('life','panel','shelf','rope','lcrux')
foreach ($t in $names) {
    $n = git -C $repo rev-list --count ("master..wave5/" + $t) 2>$null
    if ($LASTEXITCODE -ne 0) { $n = '-' }
    Write-Host ('AHEAD_' + $t + '=' + $n)
}
$pairs = @('w5-life|W5-LIFE','w5-panel|W5-PANEL','w5-shelf|W5-SHELF','w5-rope|W5-ROPE','w5-lcrux|W5-LCRUX')
foreach ($pair in $pairs) {
    $parts = $pair.Split('|'); $wt = $parts[0]; $id = $parts[1]
    $r = (Test-Path (Join-Path $repo (".claude\worktrees\" + $wt + "\harness\notes\receipts\" + $id + ".json"))) -or (Test-Path (Join-Path $repo ("harness\notes\receipts\" + $id + ".json")))
    Write-Host ('RECEIPT_' + $id + '=' + $r)
}
Write-Host ('FLAG=' + (Test-Path (Join-Path $repo 'harness\notes\h22\w5l-landed.flag')))
$opid = Get-Content (Join-Path $repo 'harness\notes\h22\orchestrator-w5l.pid') -ErrorAction SilentlyContinue
$alive = $false
if ($opid) { $alive = [bool](Get-CimInstance Win32_Process -Filter ("ProcessId=" + $opid) -ErrorAction SilentlyContinue) }
Write-Host ('ORCH=' + $opid + ':' + $alive)
Write-Host 'TAIL:'
Get-Content $log -Tail 4
