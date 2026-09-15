$repo = 'C:\Users\User\SYNAPSE'
$legs = @('bp1/triage','bp1/rails','bp1/honesty','bp1/crux')
foreach ($b in $legs) {
    git -C $repo merge --no-ff $b -m "merge(bp1): $b - SOUND-WITH-NITS, rides (verdicts: harness/battleplan/notes/BP1-CRUX_verdicts.md)"
    if ($LASTEXITCODE -ne 0) {
        git -C $repo merge --abort 2>$null
        Write-Output "CONFLICT-STOP at $b - this merge aborted; earlier merges in the train stand; awaiting instruction"
        exit 1
    }
    Write-Output "MERGED $b"
}
Write-Output '--LOG--'
git -C $repo log --oneline -12
Write-Output '--FLAG-ON-MASTER--'
Test-Path (Join-Path $repo 'harness\notes\h22\BP1_CRUX_LANDED.flag')
Write-Output '--TESTS--'
Set-Location $repo
python -m pytest tests/test_rails.py tests/test_memory_recall_honesty.py tests/test_loop_contracts.py tests/test_memory_port_v51.py -q
Write-Output "PYTEST-EXIT=$LASTEXITCODE"
exit 0
