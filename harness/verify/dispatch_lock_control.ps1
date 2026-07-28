# Control for the dispatch lock (R134).
#
# A lock that has never been SEEN refusing is R127's defect wearing a new hat.
# This exercises all four paths against the real functions, dot-sourced from
# the orchestrator so there is no second copy to drift.

$ErrorActionPreference = 'Stop'
$orch = Join-Path $PSScriptRoot '..\orchestrate.ps1'

# Pull in just the lock functions. The orchestrator guards its main loop behind
# a param block, so dot-sourcing with -WhatIf-ish args would still run it - we
# extract the three functions instead.
$src = Get-Content $orch -Raw
$m = [regex]::Match($src, '(?s)function Get-LockDir.*?\nfunction Release-LegLock[^\}]*\}\s*\n')
if (-not $m.Success) { Write-Host "could not extract lock functions" -ForegroundColor Red; exit 1 }
$PSScriptRootShim = Split-Path $orch -Parent
Invoke-Expression ($m.Value -replace '\$PSScriptRoot', "'$PSScriptRootShim'")
function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }

$leg = "LOCKTEST_$PID"
$lockFile = Join-Path (Get-LockDir) "$leg.lock"
Remove-Item $lockFile -Force -EA SilentlyContinue

$pass = $true
function Check($label, $cond) {
    Write-Host ("  {0,-42} {1}" -f $label, $(if ($cond) { 'PASS' } else { 'FAIL' })) `
        -ForegroundColor $(if ($cond) { 'Green' } else { 'Red' })
    if (-not $cond) { $script:pass = $false }
}

Write-Host ''
Write-Host 'DISPATCH LOCK CONTROL' -ForegroundColor Cyan
Write-Host ('=' * 56)

# 1. a free leg is takeable
Check 'takes a free lock' (Take-LegLock $leg)

# 2. it recorded who holds it
$body = Get-Content $lockFile -Raw | ConvertFrom-Json
Check 'records the holding pid' ($body.pid -eq $PID)
Check 'records a start time' ([bool]$body.started)

# 3. THE POINT: a live lock is REFUSED
Check 'REFUSES while the holder is alive' (-not (Take-LegLock $leg))

# 4. a stale lock (dead pid) is taken over, not honoured forever
$dead = @{ leg = $leg; pid = 999999; started = (Get-Date -Format o) } | ConvertTo-Json -Compress
Set-Content $lockFile $dead -Encoding utf8
Check 'takes over a lock held by a dead pid' (Take-LegLock $leg)

# 5. release frees it
Release-LegLock $leg
Check 'release removes the lock' (-not (Test-Path $lockFile))
Check 'a released leg is takeable again' (Take-LegLock $leg)

Release-LegLock $leg
Write-Host ''
Write-Host ("RESULT: " + $(if ($pass) { 'PASS' } else { 'FAIL' })) `
    -ForegroundColor $(if ($pass) { 'Green' } else { 'Red' })
exit $(if ($pass) { 0 } else { 1 })
