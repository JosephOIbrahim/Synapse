# =============================================================================
# AUTORESEARCH driver v1.1 - Desktop Commander entry points.
#
#   . .\harness\autoresearch\drive_autoresearch.ps1
#   Start-AutoResearch -Mission solaris_basic
#   Get-AutoResearchState          # poll - single-shot by design, never blocks
#   Complete-AutoResearch          # gate: verify DONE + evidence, release lock
#   Start-AutoResearchScout        # DeepSeek triage + next-mission author (v1.1)
#   Stop-AutoResearch              # abandon: kill pid, release lock
#
# Design scars honored:
#   - DC drops its connection on long calls  -> launch is DETACHED
#     (Start-Process -PassThru returns in ms; the runner heartbeats state.json)
#   - PS pipe chains with 2>&1 truncate      -> Start-Process file-handle
#     redirects to run.out.log / run.err.log instead
#   - polling loops inside a DC call hold the session -> no Watch- function
#     exists on purpose. Poll with repeated Get-AutoResearchState calls.
#   - R147/R168: lock release happens on the -> done transition (Complete-)
#
# Scout layer (v1.1): model names live in tiers.json ONLY - never in code.
# The scout has no lock: it is read-only over evidence and writes only to
# missions\proposed\. Probe runs keep the one-leg-at-a-time lock.
#
# PowerShell 5.1 compatible. No ternaries, no null-coalescing.
# =============================================================================

Set-StrictMode -Version Latest

$script:AR_Root      = Split-Path -Parent $PSCommandPath          # harness\autoresearch
$script:HarnessRoot  = Split-Path -Parent $script:AR_Root         # harness
$script:RepoRoot     = Split-Path -Parent $script:HarnessRoot     # repo
$script:LockDir      = Join-Path $script:HarnessRoot 'state\locks'
$script:LockPath     = Join-Path $script:LockDir 'autoresearch.lock'
$script:RunsDir      = Join-Path $script:AR_Root 'runs'
$script:LatestPtr    = Join-Path $script:RunsDir 'LATEST.txt'
$script:DefaultHython = 'C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe'

function _q([string]$s) {
    if ($s -match '\s') { return '"' + $s + '"' } else { return $s }
}

function Find-Hython {
    param([string]$Override)
    $candidates = @()
    if ($Override) { $candidates += $Override }
    if ($env:AR_HYTHON) { $candidates += $env:AR_HYTHON }
    if ($env:HFS) { $candidates += (Join-Path $env:HFS 'bin\hython.exe') }
    $candidates += $script:DefaultHython
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    throw ("hython not found. Tried: " + ($candidates -join '; ') +
           ". Pass -Hython <path> or set AR_HYTHON / HFS.")
}

function _ReadLock {
    if (-not (Test-Path $script:LockPath)) { return $null }
    try { return (Get-Content -Raw $script:LockPath | ConvertFrom-Json) }
    catch { return $null }
}

function _PidAlive([int]$ProcId) {
    if ($ProcId -le 0) { return $false }
    $p = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
    return ($null -ne $p)
}

function Release-AutoResearchLock {
    if (Test-Path $script:LockPath) {
        Remove-Item $script:LockPath -Force
        Write-Host "lock released: $script:LockPath"
    } else {
        Write-Host "no lock present"
    }
}

function _ResolveRunDir([string]$RunDir) {
    if ($RunDir) { return $RunDir }
    if (Test-Path $script:LatestPtr) {
        $p = (Get-Content -Raw $script:LatestPtr).Trim()
        if ($p) { return $p }
    }
    throw "no run dir given and no LATEST pointer - has a run been started?"
}

# -----------------------------------------------------------------------------
function Start-AutoResearch {
    param(
        [Parameter(Mandatory = $true)][string]$Mission,
        [string]$Hython
    )

    # --- lock discipline: one probe leg at a time ----------------------------
    $lock = _ReadLock
    if ($lock) {
        if (_PidAlive $lock.pid) {
            throw ("autoresearch lock held by pid $($lock.pid) since $($lock.started) " +
                   "on $($lock.machine). Complete-AutoResearch or Stop-AutoResearch first.")
        }
        Write-Warning "stale lock (pid $($lock.pid) not alive) - removing."
        Remove-Item $script:LockPath -Force
    }

    $missionPath = Join-Path $script:AR_Root ("missions\" + $Mission + ".json")
    if (-not (Test-Path $missionPath)) { throw "mission file not found: $missionPath" }

    $hy = Find-Hython -Override $Hython
    $runnerPath = Join-Path $script:AR_Root 'runner.py'

    $stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
    $safeName = ($Mission -replace '[\\/]', '_')
    $runDir = Join-Path $script:RunsDir ($safeName + '_' + $stamp)
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    if (-not (Test-Path $script:LockDir)) {
        New-Item -ItemType Directory -Path $script:LockDir -Force | Out-Null
    }

    $outLog = Join-Path $runDir 'run.out.log'
    $errLog = Join-Path $runDir 'run.err.log'
    $argList = @((_q $runnerPath), '--mission', (_q $missionPath), '--out', (_q $runDir))

    # --- DETACHED launch: this call returns in milliseconds ------------------
    $proc = Start-Process -FilePath $hy `
        -ArgumentList $argList `
        -WorkingDirectory $script:RepoRoot `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError  $errLog `
        -WindowStyle Hidden -PassThru

    @{
        pid     = $proc.Id
        started = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        machine = $env:COMPUTERNAME
        leg     = 'autoresearch'
        run_dir = $runDir
    } | ConvertTo-Json | Set-Content -Path $script:LockPath -Encoding UTF8

    Set-Content -Path $script:LatestPtr -Value $runDir -Encoding UTF8

    Write-Host "started  mission=$Mission pid=$($proc.Id)"
    Write-Host "run dir  $runDir"
    Write-Host "poll     Get-AutoResearchState"
}

# -----------------------------------------------------------------------------
function Get-AutoResearchState {
    param([string]$RunDir)

    $rd = _ResolveRunDir $RunDir
    Write-Host "run dir  $rd"

    $doneP   = Join-Path $rd 'DONE'
    $failP   = Join-Path $rd 'FAILED'
    $stateP  = Join-Path $rd 'state.json'

    if (Test-Path $failP) {
        Write-Host "status   FAILED" -ForegroundColor Red
        Write-Host "--- FAILED (tail) ---"
        Get-Content $failP -Tail 15
        return
    }

    if (Test-Path $doneP) {
        $d = Get-Content -Raw $doneP | ConvertFrom-Json
        Write-Host ("status   DONE - entries=$($d.entries) failures=$($d.failures) " +
                    "evidence=$($d.evidence)") -ForegroundColor Green
        if ($d.PSObject.Properties.Name -contains 'kind') {
            Write-Host "next     review triage + proposed mission in the run dir"
        } else {
            Write-Host "next     Complete-AutoResearch"
        }
        return
    }

    if (-not (Test-Path $stateP)) {
        Write-Host "status   LAUNCHING (no heartbeat yet - hython boot takes up to ~60s)"
        $errLog = Join-Path $rd 'run.err.log'
        if ((Test-Path $errLog) -and ((Get-Item $errLog).Length -gt 0)) {
            Write-Host "--- run.err.log (tail) ---"
            Get-Content $errLog -Tail 10
        }
        return
    }

    $s = Get-Content -Raw $stateP | ConvertFrom-Json
    $age = [int]((Get-Date).ToUniversalTime() - ([datetime]::Parse($s.ts).ToUniversalTime())).TotalSeconds
    Write-Host "status   RUNNING  $($s.pct)%  [$($s.done)/$($s.total)]"
    Write-Host "phase    $($s.phase)  q=$($s.question)"
    Write-Host "beat     ${age}s ago  pid=$($s.pid)"
    if ($age -gt 120) {
        Write-Warning "heartbeat older than 120s with no sentinel - possibly hung. Check run.err.log; Stop-AutoResearch to abandon."
    }
}

# -----------------------------------------------------------------------------
function Complete-AutoResearch {
    param([string]$RunDir)

    $rd = _ResolveRunDir $RunDir
    $doneP = Join-Path $rd 'DONE'
    if (-not (Test-Path $doneP)) {
        throw "no DONE sentinel in $rd - run not finished. Get-AutoResearchState to check."
    }

    $d = Get-Content -Raw $doneP | ConvertFrom-Json
    $evP = Join-Path $rd $d.evidence
    if (-not (Test-Path $evP)) { throw "DONE names evidence '$($d.evidence)' but file is missing" }

    $ev = Get-Content -Raw $evP | ConvertFrom-Json   # throws on malformed JSON
    $n = @($ev.entries).Count
    if ($n -lt 1) { throw "evidence file parsed but contains zero entries" }

    $fails = @($ev.entries | Where-Object {
        $_.value -and ($_.value.PSObject.Properties.Name -contains 'error')
    })

    Write-Host "gate     PASS" -ForegroundColor Green
    Write-Host "build    $($ev.meta.build)  (target match: $($ev.meta.target_build_match))"
    Write-Host "entries  $n   probe failures: $(@($fails).Count)"
    foreach ($f in $fails) { Write-Host "  FAIL   $($f.claim)" -ForegroundColor Yellow }
    Write-Host "evidence $evP"

    # R147 / R168 - release on the -> done transition.
    Release-AutoResearchLock
    Write-Host "next     Start-AutoResearchScout for triage, or author fixtures from this evidence (BLOCKS Mile 4)."
}

# -----------------------------------------------------------------------------
function Stop-AutoResearch {
    $lock = _ReadLock
    if ($lock -and (_PidAlive $lock.pid)) {
        Stop-Process -Id $lock.pid -Force
        Write-Host "killed pid $($lock.pid)"
    } else {
        Write-Host "no live autoresearch process found"
    }
    if ($lock -and $lock.run_dir) {
        $sentinelDone = Join-Path $lock.run_dir 'DONE'
        $sentinelFail = Join-Path $lock.run_dir 'FAILED'
        if (-not (Test-Path $sentinelDone) -and -not (Test-Path $sentinelFail)) {
            Set-Content -Path (Join-Path $lock.run_dir 'ABANDONED') `
                -Value ((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')) -Encoding UTF8
            Write-Host "run marked ABANDONED: $($lock.run_dir)"
        }
    }
    Release-AutoResearchLock
}

# =============================================================================
# v1.1 - SCOUT layer. DeepSeek (via ollama, tiers.json) triages evidence and
# authors the next mission. No lock: read-only over evidence; writes only to
# missions\proposed\. Same sentinel shape - Get-AutoResearchState polls it.
# =============================================================================
function Start-AutoResearchScout {
    param(
        [string]$Evidence,
        [string]$Objective = ''
    )

    if (-not $Evidence) {
        $rd = _ResolveRunDir $null
        $doneP = Join-Path $rd 'DONE'
        if (-not (Test-Path $doneP)) {
            throw "no -Evidence given and latest run has no DONE - point me at a lop_truth_*.json"
        }
        $d = Get-Content -Raw $doneP | ConvertFrom-Json
        $Evidence = Join-Path $rd $d.evidence
    }
    if (-not (Test-Path $Evidence)) { throw "evidence not found: $Evidence" }

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $scoutDir = Join-Path $script:RunsDir ('scout_' + $stamp)
    New-Item -ItemType Directory -Path $scoutDir -Force | Out-Null

    $scoutPy = Join-Path $script:AR_Root 'scout.py'
    $argList = @((_q $scoutPy), '--evidence', (_q $Evidence), '--out', (_q $scoutDir))
    if ($Objective) { $argList += @('--objective', (_q $Objective)) }

    $proc = Start-Process -FilePath 'python' `
        -ArgumentList $argList `
        -WorkingDirectory $script:RepoRoot `
        -RedirectStandardOutput (Join-Path $scoutDir 'run.out.log') `
        -RedirectStandardError  (Join-Path $scoutDir 'run.err.log') `
        -WindowStyle Hidden -PassThru

    Set-Content -Path $script:LatestPtr -Value $scoutDir -Encoding UTF8

    Write-Host "scout    started pid=$($proc.Id)"
    Write-Host "run dir  $scoutDir"
    Write-Host "poll     Get-AutoResearchState   (same sentinel shape)"
}

Write-Host "AUTORESEARCH driver v1.1 loaded - Start-AutoResearch -Mission solaris_basic"

# =============================================================================
# v1.2 - live terminal. Opens ONE visible window that follows LATEST across
# runs: status header + log tails, 2s refresh. This is NOT a blocking watcher
# inside a DC call - it lives in its own console. Close it anytime.
# =============================================================================
function Show-AutoResearchTerminal {
    $watch = Join-Path $script:AR_Root 'watch_terminal.ps1'
    if (-not (Test-Path $watch)) { throw "watch_terminal.ps1 missing at $watch" }
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-File', $watch
    Write-Host "live terminal opened - safe to close anytime; workers are unaffected"
}
