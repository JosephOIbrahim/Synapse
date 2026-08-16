# w6gate_close_gate_probe.ps1 - FIRST-HAND proof of the W6-GATE close gate.
#
# Acceptance (probe): "done requires receipt==HEAD + RELEASE; three violation
# refusals with exact messages". This walks ONE scratch leg through each
# condition in turn against the REAL orchestrate.ps1 state machine and prints
# the state + exact message it produced first-hand.
#
# Method: build an isolated scratch world (a throwaway git repo as the leg's
# worktree + a scratch bus), dot-source orchestrate.ps1 in LIBRARY MODE
# (SYNAPSE_ORCH_LIB=1 -> functions defined, board loop skipped) with -Repo
# pointed at the scratch root and -DryRun set, then call the real Get-LegState.
# The gate runs identically under -DryRun (it precedes the DryRun short-circuit)
# - "dry-run must exercise the same checks".
#
# Scenarios (monotonic - one leg fixing its own close, in order):
#   V1  receipt written to the worktree, NOT committed        -> closing
#   V2  receipt committed, then a LATER commit follows it     -> closing
#   V3  receipt IS the branch HEAD but no bus RELEASE         -> closing
#   OK  receipt is HEAD AND an explicit RELEASE is posted     -> done
#
# Isolated, self-asserting, self-cleaning. Exit 0 = all four as expected.

$ErrorActionPreference = 'Stop'
$ORCH = Join-Path $PSScriptRoot '..\..\orchestrate.ps1' | Resolve-Path | Select-Object -ExpandProperty Path
$srcBus = Join-Path $PSScriptRoot '..\..\autorevise\bus.py' | Resolve-Path | Select-Object -ExpandProperty Path

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("w6gate_probe_" + [guid]::NewGuid().ToString('N').Substring(0,10))
$fail = 0
$results = @()

function RunGit($wt, [string[]]$a) {
    # git.exe explicitly - a bare `git` would resolve to THIS function first
    # (PowerShell prefers functions over external commands) and recurse forever.
    $out = & git.exe -C $wt @a 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git $($a -join ' ') failed: $out" }
    return $out
}

try {
    # --- scratch world -------------------------------------------------------
    $wt = Join-Path $root 'wt'
    New-Item -ItemType Directory -Force -Path $wt | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $root 'harness\autorevise') | Out-Null
    Copy-Item $srcBus (Join-Path $root 'harness\autorevise\bus.py') -Force

    RunGit $wt @('init', '-q')
    RunGit $wt @('config', 'user.email', 'probe@synapse.local')
    RunGit $wt @('config', 'user.name', 'gate probe')
    RunGit $wt @('checkout', '-q', '-b', 'wave99/probe')
    Set-Content -Path (Join-Path $wt 'product.txt') -Value 'product work' -Encoding utf8
    RunGit $wt @('add', 'product.txt')
    RunGit $wt @('commit', '-q', '-m', 'product work')

    $rcptDir = Join-Path $wt 'harness\notes\receipts'
    New-Item -ItemType Directory -Force -Path $rcptDir | Out-Null
    $rcpt = Join-Path $rcptDir 'W99-GATEPROB.json'
    $rcptRel = 'harness/notes/receipts/W99-GATEPROB.json'

    # --- dot-source the REAL state machine in library mode -------------------
    $env:SYNAPSE_ORCH_LIB = '1'
    . $ORCH -Repo $root -DryRun -Quiet *> $null
    $ErrorActionPreference = 'Stop'   # orchestrate.ps1 sets SilentlyContinue; restore

    $leg = [pscustomobject]@{
        id = 'W99-GATEPROB'; name = 'scratch close-gate probe'
        receipt = 'W99-GATEPROB.json'; branch = 'wave99/probe'
        worktree = 'wt'; deps = @()
    }

    function Scenario([string]$tag, [string]$expectState, [string]$expectPhrase) {
        $script:CloseGateReason['W99-GATEPROB'] = $null
        $state  = Get-LegState $leg
        $reason = $script:CloseGateReason['W99-GATEPROB']
        $okState  = ($state -eq $expectState)
        $okReason = ([string]::IsNullOrEmpty($expectPhrase)) -or ($reason -and $reason.Contains($expectPhrase))
        if ($okState -and $okReason) { $verdict = 'PASS' } else { $verdict = 'FAIL'; $script:fail++ }
        $color = if ($verdict -eq 'PASS') { 'Green' } else { 'Red' }
        Write-Host ""
        Write-Host ("  [{0}] {1}" -f $tag, $verdict) -ForegroundColor $color
        Write-Host ("       state  : {0}   (expected {1})" -f $state, $expectState)
        if ($reason) { Write-Host ("       message: {0}" -f $reason) }
        $script:results += [pscustomobject]@{ tag = $tag; state = $state; expected = $expectState; message = $reason; verdict = $verdict }
    }

    Write-Host "=== W6-GATE close-gate probe (first-hand, real Get-LegState, -DryRun) ===" -ForegroundColor Cyan
    Write-Host "    leg W99-GATEPROB  branch wave99/probe  wave99 bus  scratch $root" -ForegroundColor DarkGray

    # V1: receipt in the worktree, NOT committed
    Set-Content -Path $rcpt -Value '{"leg":"W99-GATEPROB","status":"green","note":"draft, uncommitted"}' -Encoding utf8
    Scenario 'V1 receipt-not-committed' 'closing' 'is not committed on'

    # V2: commit the receipt, then a LATER non-receipt commit so receipt != HEAD
    RunGit $wt @('add', $rcptRel)
    RunGit $wt @('commit', '-q', '-m', 'receipt (not yet the closing commit)')
    Set-Content -Path (Join-Path $wt 'product2.txt') -Value 'follow-on work after the receipt' -Encoding utf8
    RunGit $wt @('add', 'product2.txt')
    RunGit $wt @('commit', '-q', '-m', 'later work - receipt is now an ancestor, not HEAD')
    Scenario 'V2 receipt-not-HEAD' 'closing' 'is not the branch HEAD'

    # V3: make the receipt the HEAD commit, but post NO bus release
    Set-Content -Path $rcpt -Value '{"leg":"W99-GATEPROB","status":"green","note":"now the closing commit"}' -Encoding utf8
    RunGit $wt @('add', $rcptRel)
    RunGit $wt @('commit', '-q', '-m', 'receipt is the closing commit')
    Scenario 'V3 no-bus-RELEASE' 'closing' 'no RELEASE line for W99-GATEPROB'

    # OK: post an explicit RELEASE -> clean pass to done. The body uses the
    # \"-escaped form (the sanctioned PowerShell bus idiom) - a plain
    # single-quoted '{"k":..}' loses its inner quotes crossing into the native
    # python process on PS 5.1, which is the whole reason W6-QUOTE exists.
    & python (Join-Path $root 'harness\autorevise\bus.py') post wave99 W99-GATEPROB status '{\"release\":[\"harness/orchestrate.ps1\",\"harness/autorevise/bus.py\"]}' *> $null
    Scenario 'OK clean-close' 'done' ''

    Write-Host ""
    if ($fail -eq 0) {
        Write-Host "=== PROBE PASS: 3 refusals with exact messages, then a clean pass to done ===" -ForegroundColor Green
    } else {
        Write-Host "=== PROBE FAIL: $fail scenario(s) did not match expectation ===" -ForegroundColor Red
    }
}
finally {
    Remove-Item Env:\SYNAPSE_ORCH_LIB -ErrorAction SilentlyContinue
    if (Test-Path $root) { Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue }
}

exit $fail
