# SYNAPSE ORCHESTRATOR - one window owns the whole board.
#
# Replaces run_relay.ps1, run_solaris_repair.ps1, run_repair_heats.ps1,
# run_followon.ps1, heartbeat.ps1 and watch_relay.ps1. Each of those was a
# bespoke dispatcher; adding a leg meant writing another one. Here a leg is a
# row in harness/legs.json.
#
# Owns: dependency gating - worktree creation - TRUST - launch - receipt
# monitoring - branch backup - notification. Nothing else spawns windows.
#
# NEVER: push to master, merge, tag. Gate C is human. A leg in state 'held' is
# held by RULING and is never auto-dispatched.
param([int]$PollSeconds = 45, [int]$StaleMinutes = 40, [int]$MaxHours = 12,
      [int]$DigestMinutes = 20, [int]$IdlePollSeconds = 120,
      [string]$Repo = 'C:\Users\User\SYNAPSE',
      [string]$ManifestPath = '',
      [string]$Budget = '',
      [switch]$Quiet, [switch]$DryRun)

$ErrorActionPreference = 'SilentlyContinue'
$repo = $Repo
Set-Location $repo

# S1/S8 quoting + encoding helpers (Sanitize-SQ, Write-Utf8NoBom). Dot-sourced so
# the launch runner and the lock write below cannot re-introduce the
# unquoted-interpolation (S1) or UTF-8-BOM (S8) failure classes. See
# harness/lib/quote-safe.ps1 (python twin: harness/autorevise/quote_safe.py).
# $ErrorActionPreference is SilentlyContinue here, so guard the load explicitly:
# a missing helper must fail loud, never silently leave $safeName empty (M5).
. (Join-Path $PSScriptRoot 'lib\quote-safe.ps1')
if (-not (Get-Command Sanitize-SQ -ErrorAction SilentlyContinue)) {
    throw 'FATAL: harness/lib/quote-safe.ps1 did not load - Sanitize-SQ/Write-Utf8NoBom missing.'
}
# Overridable so the orchestrator can be exercised against a throwaway manifest.
# It was hardcoded, which made the dispatcher itself untestable - a control could
# only be run against the live board, which is not a control.
$manifestPath = if ($ManifestPath) { $ManifestPath } else { Join-Path $repo 'harness\legs.json' }
$rdir         = Join-Path $repo 'harness\notes\receipts'
$log          = Join-Path $repo ("harness\notes\orchestrator_{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Say([string]$m, [string]$c = 'Gray') {
    $line = "{0}  {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Write-Host $line -ForegroundColor $c
    Add-Content -Path $log -Value $line
}

function Notify([string]$title, [string]$body) {
    if ($Quiet) { return }   # -Quiet for control runs: no toasts, no beeps
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
        $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
                [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $n = $t.GetElementsByTagName('text')
        $n.Item(0).AppendChild($t.CreateTextNode($title)) | Out-Null
        $n.Item(1).AppendChild($t.CreateTextNode($body))  | Out-Null
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SYNAPSE').Show(
            [Windows.UI.Notifications.ToastNotification]::new($t))
    } catch {
        Add-Type -AssemblyName System.Windows.Forms
        $ni = New-Object System.Windows.Forms.NotifyIcon
        $ni.Icon = [System.Drawing.SystemIcons]::Information; $ni.Visible = $true
        $ni.ShowBalloonTip(9000, $title, $body, [System.Windows.Forms.ToolTipIcon]::Info)
        Start-Sleep -Seconds 10; $ni.Dispose()
    }
    1..2 | ForEach-Object { [console]::beep(880, 150); Start-Sleep -Milliseconds 80 }
}

# --- leg lifecycle -----------------------------------------------------------

# Dry-run bookkeeping so a dry run exercises the same state machine as a real one.
$script:DryDispatched = @{}

# W6-GATE close-gate bookkeeping. CloseGateReason holds the exact missing
# condition for a leg currently held at 'closing'; CloseGateNotified remembers
# the reason already surfaced so an unchanged reason is not re-notified every
# poll (it is cleared when the leg leaves 'closing').
$script:CloseGateReason   = @{}
$script:CloseGateNotified = @{}

# --- BP1-RAILS budget rails (additive; inert unless -Budget is set) ----------
# When -Budget is passed (e.g. -Budget 8turns or -Budget "8turns,50000tokens")
# each dispatch is charged through harness/rails.py BEFORE Start-Leg. rails.py
# owns the cap arithmetic, the spend ledger (harness/battleplan/runs/<date>/) and
# the HARD STOP: a charge that would exceed the cap writes a blocked:budget
# receipt and returns non-zero, and this loop then halts dispatch - never a
# silent continue. Absent -Budget, Rails-Charge returns $true unconditionally and
# Rails-Open no-ops, so every default-path line stays byte-for-byte identical.
$script:BudgetHalted = $false
$script:RailsRun = if ($Budget) { "orch_{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss') } else { '' }

function Rails-Open {
    if (-not $Budget) { return }
    $rails = Join-Path $repo 'harness\rails.py'
    if (-not (Test-Path $rails)) {
        Say "  BUDGET: harness/rails.py not found - refusing to run capped (fail closed)" 'Red'
        throw "rails.py missing; -Budget cannot be honored"
    }
    & python $rails open --run $script:RailsRun --cap $Budget 2>&1 |
        ForEach-Object { Say "  rails: $_" 'DarkGray' }
}

function Rails-Charge([object]$leg) {
    # $true  = dispatch admitted (or -Budget absent, the inert default)
    # $false = cap hit or rails error; rails.py wrote the receipt. Fail closed.
    if (-not $Budget) { return $true }
    if ($script:BudgetHalted) { return $false }
    $rails = Join-Path $repo 'harness\rails.py'
    if ($leg.tier) {
        & python $rails charge --run $script:RailsRun --leg $leg.id --tier $leg.tier 2>&1 | Out-Null
    } else {
        $model = if ($manifest.model) { $manifest.model } else { '' }
        & python $rails charge --run $script:RailsRun --leg $leg.id --model $model 2>&1 | Out-Null
    }
    if ($LASTEXITCODE -eq 0) { return $true }
    $script:BudgetHalted = $true   # exit 7 (blocked:budget) or any error -> halt
    return $false
}

function Get-ReceiptPath([object]$leg) {
    # A leg writes its receipt into ITS OWN worktree, not the main tree.
    # 2026-07-26: the orchestrator watched only $repo\harness\notes\receipts and
    # reported three completed legs as 'running' for two hours. It was watching a
    # directory that could never fill. Check the worktree first, then the main
    # tree (for legs that ran in-place, like Q1/Q2).
    if ($leg.worktree) {
        $wtr = Join-Path (Join-Path $repo $leg.worktree) "harness\notes\receipts\$($leg.receipt)"
        if (Test-Path $wtr) { return $wtr }
    }
    $main = Join-Path $rdir $leg.receipt
    if (Test-Path $main) { return $main }
    return $null
}

# ---------------------------------------------------------------------------
# DISPATCH LOCK  (R134)
#
# Three times in two days, two agents have run against one leg or one worktree:
# two H6 agents 70 minutes past their receipt (R78); LEDGER and H6 editing one
# function from separate worktrees (R91); and a second I1 overwriting the first
# one's calibration file mid-run.
#
# `.orch_launched` was the previous mitigation and it is a MARKER, not a lock.
# It carries no pid, so a crashed leg either blocks forever or is ignored, and
# two dispatchers can both pass the check before either writes.
#
# The primitive is FileMode::CreateNew - it THROWS if the file exists, and the
# throw is the mutex. Not Test-Path then write, which has a window between them.
#
# Liveness is Get-Process. Deliberately NOT os.kill(pid, 0): on Windows that
# routes through TerminateProcess and KILLS the process it means to probe. This
# codebase shipped exactly that bug once in bridge_endpoint._pid_alive and had
# to fix it with OpenProcess + GetExitCodeProcess.
# ---------------------------------------------------------------------------
function Get-LockDir {
    $d = Join-Path $PSScriptRoot 'state\locks'
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    return $d
}

function Take-LegLock([string]$legId) {
    $lock = Join-Path (Get-LockDir) "$legId.lock"

    if (Test-Path $lock) {
        $prev = $null
        try { $prev = Get-Content $lock -Raw -EA Stop | ConvertFrom-Json } catch { }
        if ($prev -and $prev.pid) {
            if (Get-Process -Id $prev.pid -EA SilentlyContinue) {
                Say "  REFUSED: $legId held by pid $($prev.pid) since $($prev.started)" 'Red'
                return $false
            }
            Say "  lock: pid $($prev.pid) is gone - taking over its stale lock" 'Yellow'
        }
        Remove-Item $lock -Force -EA SilentlyContinue
    }

    try {
        $fs = [System.IO.File]::Open($lock, [System.IO.FileMode]::CreateNew,
                                     [System.IO.FileAccess]::Write)
        $body = (@{ leg = $legId; pid = $PID; started = (Get-Date -Format o)
                    machine = $env:COMPUTERNAME } | ConvertTo-Json -Compress)
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $fs.Write($bytes, 0, $bytes.Length)
        $fs.Close()
        return $true
    } catch {
        Say "  REFUSED: $legId lock was taken concurrently" 'Red'
        return $false
    }
}

function Release-LegLock([string]$legId) {
    Remove-Item (Join-Path (Get-LockDir) "$legId.lock") -Force -EA SilentlyContinue
}

function Short8([string]$s) { if ($s -and $s.Length -ge 8) { $s.Substring(0, 8) } else { $s } }

# W6-GATE CLOSE GATE (HARDENING-SPEC Part A, S4 + S5).
#
# A receipt FILE existing is not completion. Four waves of receipts asserted
# 'done' while their commit-state did not exist (S4/CRX0), and legs posted a
# `claim` on the bus but never the matching `status {release}` (S5). This gate
# makes the state machine refuse both: a leg self-closes only when its receipt
# is committed as the branch's LAST commit (receipt==HEAD - the W5H rule) AND an
# explicit RELEASE line for its claim is on the bus. Otherwise it returns
# done=$false with the exact missing condition named, and Get-LegState holds the
# leg at 'closing'.
#
# SCOPE / R135 (CTO_RULINGS_01.md:3895-3907). The gate binds ONLY a receipt that
# lives in the leg's OWN worktree. R135's standing answer - when a leg cannot
# safely preserve its own work, the operator harvests the receipt from OUTSIDE
# the contended tree, committing it from the MAIN tree - resolves via
# Get-ReceiptPath's main-tree fallback, for which this returns done=$true and
# never refuses. Manifest-pinned state:done (Get-LegState, next function) is the
# other escape valve. So this closes M11's worktree-draft half and defuses M20
# WITHOUT contradicting R135.
function Test-CloseGate([object]$leg) {
    # No worktree, or no receipt IN the worktree => legacy / in-place / operator-
    # harvested. Presence is 'done', exactly as before the gate (R135, M20).
    if (-not $leg.worktree) { return @{ done = $true; reason = '' } }
    $wt        = Join-Path $repo $leg.worktree
    $wtReceipt = Join-Path $wt "harness\notes\receipts\$($leg.receipt)"
    if (-not (Test-Path $wtReceipt)) { return @{ done = $true; reason = '' } }

    $branch     = if ($leg.branch) { $leg.branch } else { 'its branch' }
    $receiptRel = "harness/notes/receipts/$($leg.receipt)"

    # Conditions 1 + 2: the receipt is committed on the branch AND is the branch
    # HEAD. `git log -1` of the receipt path is the last commit that touched it:
    # empty => never committed; an ancestor => a later commit followed it; HEAD
    # => it IS the closing commit.
    $head          = (& git -C $wt rev-parse HEAD 2>$null)
    $receiptCommit = (& git -C $wt log -1 --format=%H -- $receiptRel 2>$null)
    if (-not $receiptCommit) {
        return @{ done = $false; reason =
            "receipt $($leg.receipt) exists in the worktree but is not committed on $branch - writing the receipt is not finishing, committing it is (W5H)" }
    }
    if ($receiptCommit -ne $head) {
        return @{ done = $false; reason =
            "receipt $($leg.receipt) is committed ($(Short8 $receiptCommit)) but is not the branch HEAD ($(Short8 $head)) - the receipt must land as the branch's closing commit (W5H)" }
    }

    # Condition 3: an explicit RELEASE line for this leg's claim on the bus. The
    # wave is derived from the leg id exactly as compile_wave.py does
    # (W6-GATE -> wave6); the bus `frm` is the leg id. bus.py exit 0 == released.
    $wave  = ($leg.id -split '-', 2)[0].ToLower() -replace '^w', 'wave'
    $busPy = Join-Path $repo 'harness\autorevise\bus.py'
    if (-not (Test-Path $busPy)) {
        return @{ done = $false; reason =
            "cannot verify RELEASE - bus.py not found at $busPy" }
    }
    & python $busPy released $wave $leg.id 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        return @{ done = $false; reason =
            "receipt is the closing commit but no RELEASE line for $($leg.id) is on the bus ($wave) - post an explicit release at close (S5)" }
    }
    return @{ done = $true; reason = '' }
}

function Get-LegState([object]$leg) {
    if ($leg.state -eq 'held') { return 'held' }

    # A leg pinned done in the manifest STAYS done, receipt or not.
    #
    # 2026-07-27: a housekeeping pass pruned the worktrees of H9, C0 and S1 -
    # all three finished and RULED ON. Their receipts had never been committed,
    # so they existed only in those worktrees. With the worktree gone,
    # Get-ReceiptPath found nothing, the legs read as 'ready', and the
    # orchestrator re-dispatched finished work.
    #
    # The receipts are lost. The findings survive as rulings with anchors. This
    # flag stops the harness spending tokens re-deriving them.
    if ($leg.state -eq 'done') { return 'done' }

    # W6-GATE (S4 + S5): a receipt file existing is NO LONGER 'done' on its own.
    # A worktree receipt must clear the close gate - committed as the branch HEAD
    # AND released on the bus - or the leg holds at 'closing' with the exact
    # missing condition recorded for the main loop to surface. The main-tree
    # fallback (in-place / operator-harvested per R135) still greens: Test-CloseGate
    # returns done there. This runs BEFORE the DryRun short-circuit below, so a
    # dry run exercises the identical checks a real run does.
    if ($leg.receipt -and (Get-ReceiptPath $leg)) {
        $gate = Test-CloseGate $leg
        if ($gate.done) { return 'done' }
        $script:CloseGateReason[$leg.id] = $gate.reason
        return 'closing'
    }
    if ($DryRun -and $script:DryDispatched[$leg.id]) { return 'running' }

    # R156: A LIVE LOCK MEANS RUNNING. Ask the lock before the filesystem.
    #
    # R146 ruled that the lock is the completion signal - "a receipt in a
    # worktree with a live lock is a draft" - and then nothing wired this
    # function to read it. The detector below infers 'running' from
    # .claude/settings.local.json, which Claude Code writes on the agent's first
    # real interaction. H3b ran for 18 minutes writing four probe files and a
    # 0.7 MB transcript WITHOUT that file ever appearing, so the board read
    # 'ready' the whole time and the leg was one poll from a second dispatch -
    # the exact concurrency failure the lock exists to prevent.
    #
    # Inferring liveness from a file the agent happens to write is a proxy.
    # The lock is the fact.
    $lockFile = Join-Path (Get-LockDir) "$($leg.id).lock"
    if (Test-Path $lockFile) {
        try {
            $lk = Get-Content $lockFile -Raw -EA Stop | ConvertFrom-Json
            if ($lk.pid -and (Get-Process -Id $lk.pid -EA SilentlyContinue)) { return 'running' }
        } catch { }
    }

    if ($leg.worktree) {
        $wt = Join-Path $repo $leg.worktree
        if (Test-Path (Join-Path $wt '.claude\settings.local.json')) {
            # settings.local.json is written on the agent's first real
            # interaction, so its presence means the leg genuinely started.
            return 'running'
        }
        # Worktree exists but the agent never really started - died at the trust
        # dialog, was killed, or the machine went down. This is READY, not
        # 'launched': treating it as launched strands the leg forever, because
        # dispatch only fires on 'ready'. The worktree is reused, not recreated.
        #
        # BUT: settings.local.json is not written the instant claude starts. On
        # 2026-07-26 H6 dispatched at 16:05:01 and AGAIN at 16:05:56, because in
        # the gap the leg read 'ready' a second time. Two agents, one worktree.
        # A launch marker closes the window: it is written by US at dispatch, so
        # it exists before the agent has done anything at all.
        $marker = Join-Path $wt '.claude\.orch_launched'
        if (Test-Path $marker) {
            $age = ((Get-Date) - (Get-Item $marker).LastWriteTime).TotalMinutes
            # Stale marker with no settings.local.json after 10 min = the launch
            # genuinely failed. Re-dispatch rather than stranding it.
            if ($age -lt 10) { return 'launched' }
            Say "  $($leg.id): launch marker is $([int]$age)m old with no session - re-dispatching" 'Yellow'
        }
        if (Test-Path $wt) { return 'ready' }
    }
    foreach ($d in @($leg.deps)) {
        $dep = $manifest.legs | Where-Object { $_.id -eq $d }
        if ($dep -and -not (Get-ReceiptPath $dep)) { return 'blocked' }
    }
    return 'ready'
}

function Start-Leg([object]$leg) {
    $wt = Join-Path $repo $leg.worktree
    Say "DISPATCH $($leg.id) $($leg.name)  ->  $($leg.branch)" 'Cyan'

    # WRONG-BASE DISPATCH. A leg may declare the ref its worktree is cut from.
    # The field already existed in the data - M5b carries
    # "base": "blocks/m5-reconciler", nine legs carry "base": "master" - and
    # NOTHING READ IT. The add below hardcoded HEAD, so every leg was cut from
    # the orchestrator's own HEAD and a leg told to build ON another leg's
    # branch silently started somewhere else. Two legs hit it this month
    # (M5b, CI0). No "base" -> 'HEAD', which is exactly the previous behaviour.
    $base = if ($leg.base) { $leg.base } else { 'HEAD' }

    # Model is a MANIFEST-level passthrough, the same shape as effort. legs.json
    # carried "model": "claude-opus-4-8" and a note conceding it was decorative
    # until this line existed; without it a leg inherited whatever model the
    # spawning terminal happened to default to, which is not a dispatch
    # decision. Absent -> the flag is not emitted at all, i.e. today's
    # behaviour, not --model with an empty value.
    $modelArg = if ($manifest.model) { " --model $($manifest.model)" } else { '' }

    # R61: a read-only leg is FENCED, not asked. Read-only was an instruction in
    # the brief and nothing enforced it - a read-only fleet edited five schema
    # files and kept writing four minutes past TaskStop. The profile is a
    # property of the leg, not a promise in prose.
    # Resolved HERE, above the dry-run return, so a control run prints the same
    # launch line the live path builds instead of a hand-assembled lookalike.
    $profile = if ($leg.readonly) {
        (Join-Path $repo 'harness\readonly-settings.json') -replace '\\','/'
    } else { $manifest.settings }

    # 2026-08-16 (S1, generalized by W6-QUOTE): every UNCONTROLLED string that
    # lands in the temp runner is interpolated into a single-quoted emitted line
    # (or an unquoted arg), where one apostrophe closes the quote and the tail
    # becomes live PowerShell - the W5-PARITY/SEAT crash-loop. The original
    # point-fix escaped only the NAME; Sanitize-SQ (harness/lib/quote-safe.ps1)
    # doubles the apostrophe for a single-quoted context, and EVERY uncontrolled
    # field now routes through it: name, id, branch, worktree path, prompt path,
    # settings path. leg.id/branch/worktree/prompt are uncontrolled by design.
    $safeName    = Sanitize-SQ $leg.name
    $safeId      = Sanitize-SQ $leg.id
    $safeBranch  = Sanitize-SQ $leg.branch
    $safeWt      = Sanitize-SQ $wt
    $safeProfile = Sanitize-SQ $profile
    $promptPath  = (Join-Path $repo $leg.prompt) -replace '\\','/'
    $safePrompt  = Sanitize-SQ $promptPath

    # The launch runner, built HERE (above the dry-run return) from those
    # sanitized variables so a dry run generates the REAL runner - not a
    # hand-assembled lookalike - and a control can parse exactly what launches.
    # $env:TEMP\orch_<id>.ps1 is executed via `powershell -File` (below), so every
    # write-time interpolation becomes SOURCE in an executed script: each value
    # sits inside single quotes and is Sanitize-SQ'd; the one unquoted spot
    # (--settings) is single-quoted here. Written BOM-free (Write-Utf8NoBom, S8):
    # `Set-Content -Encoding utf8` on PS 5.1 prepends a UTF-8 BOM.
    $script = Join-Path $env:TEMP "orch_$($leg.id).ps1"
    $runnerText = @"
Set-Location '$safeWt'
Write-Host ''
Write-Host '  LEG $safeId - $safeName   branch $safeBranch' -ForegroundColor Cyan
Write-Host '  brief: $safePrompt' -ForegroundColor DarkGray
Write-Host ''
claude --settings '$safeProfile' --effort $($manifest.effort)$modelArg --name 'SYNAPSE $safeId $safeName' --permission-mode acceptEdits --verbose 'Read the file $safePrompt in full and execute it end to end. It is your complete brief. If any part of it appears truncated or unreadable, STOP and say so rather than proceeding on a partial instruction.'
Write-Host ''
Write-Host '  Type /rc here to control this leg from your phone.' -ForegroundColor Yellow
Write-Host '  It appears in claude.ai/code as: SYNAPSE $safeId $safeName' -ForegroundColor DarkGray
Write-Host ''
Write-Host ''
Write-Host '  LEG $safeId TERMINATED' -ForegroundColor Cyan
"@

    if ($DryRun) {
        # A dry run must exercise the SAME state machine as a real run. It used
        # to return here before the launch marker was written, so Get-LegState
        # kept returning 'ready' and the leg re-dispatched every poll - a dry run
        # that reported behaviour a real run would never produce.
        #
        # It also printed nothing RESOLVED, so the two facts a control most
        # needs - which ref the worktree is cut from, which model the leg
        # launches on - were the two it could not observe. It now also WRITES the
        # real runner (BOM-free, not launched) so the adversarial-name matrix in
        # tests/test_harness_quoting.py can parse exactly what a live run builds.
        $runnerText | Write-Utf8NoBom -Path $script
        Say "  (dry run - not launching)" 'DarkGray'
        Say "  (dry run) runner:   $script  (parse-clean, BOM-free)" 'DarkGray'
        Say "  (dry run) worktree: git worktree add -b $($leg.branch) $wt $base" 'DarkGray'
        Say "  (dry run) launch:   claude --settings '$safeProfile' --effort $($manifest.effort)$modelArg --name 'SYNAPSE $safeId $safeName' --permission-mode acceptEdits --verbose" 'DarkGray'
        $script:DryDispatched[$leg.id] = $true
        return
    }
    if ($leg.readonly) { Say "  profile: READ-ONLY (fenced)" 'DarkGray' }

    # Refuse to dispatch into a missing brief. Found 2026-07-26 minutes before an
    # unattended afternoon: legs.json referenced h1.md and h2.md, neither of which
    # existed. Both would have launched into nothing the moment RES landed, and
    # reported no error. A leg that cannot read its brief must not start.
    $briefPath = Join-Path $repo $leg.prompt
    if (-not (Test-Path $briefPath)) {
        Say "  REFUSED - brief missing: $($leg.prompt)" 'Red'
        Notify "$($leg.id) NOT dispatched" "Brief missing: $($leg.prompt). Leg is stalled until it exists."
        return
    }
    if ((Get-Item $briefPath).Length -lt 200) {
        Say "  REFUSED - brief suspiciously short ($((Get-Item $briefPath).Length) bytes)" 'Red'
        Notify "$($leg.id) NOT dispatched" "Brief is only $((Get-Item $briefPath).Length) bytes - likely truncated."
        return
    }

    if (-not (Test-Path $wt)) {
        # THE ADD'S FAILURE USED TO BE INVISIBLE, AND THAT MANUFACTURED ORPHANS.
        #
        # This line piped straight into Say and never looked at the exit code.
        # Worse, $ErrorActionPreference = 'SilentlyContinue' (:19) drops the
        # stderr ErrorRecords on the way through the pipe, so a failed add
        # printed NOTHING - no error, no log line, nothing to notice. Dispatch
        # then carried on, and the unconditional New-Item further down created
        # $wt/.claude, leaving an unregistered directory at exactly the path the
        # NEXT dispatch would Test-Path as "exists" and skip creating.
        #
        # Reproduced: `git worktree add -b <existing-branch> ...` exits 255,
        # creates no directory, and prints nothing through this pipe. Observed
        # live on 2026-07-27 14:41:25-30 manufacturing six orphans - H9 V1 C0
        # RSI0 S0 S1 - each with directory CreationTime equal to the dispatch
        # second and only .claude/ inside. (The other 8 orphans came from a
        # different, still-unidentified process; see spec-CLOSER.md 3.4.)
        #
        # Capture to a variable so the ErrorRecords survive, and branch on the
        # exit code before anything downstream can run.
        if ($base -ne 'HEAD') { Say "  base: cutting $($leg.branch) from leg-declared $base" 'DarkGray' }
        $addOut = & git worktree add -b $leg.branch $wt $base 2>&1
        $addCode = $LASTEXITCODE
        foreach ($l in $addOut) { Say "  $l" 'DarkGray' }
        if ($addCode -ne 0 -or -not (Test-Path $wt)) {
            Say "  REFUSED - git worktree add failed (exit $addCode)" 'Red'
            Notify "$($leg.id) NOT dispatched" "git worktree add failed with exit $addCode. Nothing was launched and no directory was left behind. Check whether branch $($leg.branch) already exists."
            return
        }
    }
    else {
        # A DIRECTORY IS NOT A WORKTREE. Test-Path only asks whether something is
        # there, so an orphaned directory skips the creation above and dispatch
        # proceeds into it. Because these live INSIDE the repo, git run from one
        # walks up and resolves to the main tree:
        #
        #   git -C .claude/worktrees/h2-requalify rev-parse --show-toplevel
        #       -> C:/Users/User/SYNAPSE
        #   git -C .claude/worktrees/h2-requalify rev-parse --abbrev-ref HEAD
        #       -> feat/repair-heats-01
        #
        # So the agent launches with acceptEdits and commits to the LIVE branch
        # of the MAIN tree - Article V inverted, because the isolation mechanism
        # routes back into the thing it isolates from while the board still
        # reports the leg as isolated.
        #
        # Found 2026-07-29: 26 directories under .claude/worktrees, 12 registered,
        # 14 orphans, 14 legs pointing at them, 9 of those state=ready.
        #
        # The guard REPORTS and never reclaims. Law 4 - the 2026-07-27 pass
        # recorded at line 142 destroyed the only copies of three receipts, and
        # an orphan may be the last copy of something.
        $isoOut = & python (Join-Path $repo 'harness\worktree_guard.py') check $leg.id 2>&1
        if ($LASTEXITCODE -eq 5) {
            Say "  REFUSED - worktree is not a worktree" 'Red'
            Say "  $isoOut" 'DarkGray'
            Notify "$($leg.id) NOT dispatched" "Its worktree directory exists but is not a git worktree. An agent there would write to the main tree on the live branch. Nothing was deleted - run: python harness/worktree_guard.py audit"
            return
        }
    }

    # A fresh worktree is UNTRUSTED - Claude Code blocks on the trust dialog
    # before its first token. Silent, indefinite, indistinguishable from slow
    # work. Cost 13 minutes on 2026-07-26. Always trust before launch.
    python (Join-Path $repo 'harness\trust_worktrees.py') 2>&1 |
        Select-Object -Last 1 | ForEach-Object { Say "  trust: $_" 'DarkGray' }

    # Prompt delivery is BY FILE REFERENCE, never by argument.
    # 2026-07-26: a ~2000-char prompt passed as a positional arg was silently
    # truncated at the first embedded double quote - the agent received the
    # brief up to `hython3.13 -c "import` and nothing after, so it never got its
    # WORK steps, its oracle, or the instruction to write a receipt. It thought
    # for 2.5 hours and produced nothing. A one-line pointer has no quoting
    # surface and no length limit. $runnerText, $safePrompt and $script were all
    # resolved above (from sanitized variables), so the dry-run control builds
    # the identical runner; here we only commit it to disk, BOM-free.
    $runnerText | Write-Utf8NoBom -Path $script

    # R134: refuse to launch a leg another dispatcher already holds.
    if (-not (Take-LegLock $leg.id)) { return }

    $proc = Start-Process powershell -PassThru -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$script -WindowStyle Normal

    # R147: rewrite the lock with the LEG's pid, not the dispatcher's.
    #
    # Take-LegLock has to run BEFORE the launch to close the race, so it can
    # only record $PID - the orchestrator's. That makes the liveness probe ask
    # "is the orchestrator alive", which is always yes, so a crashed leg's lock
    # would never be seen as stale. Recording the window's pid here makes the
    # probe ask the question that matters: is THIS LEG still running.
    try {
        $lock = Join-Path (Get-LockDir) "$($leg.id).lock"
        (@{ leg = $leg.id; pid = $proc.Id; dispatcher = $PID
            started = (Get-Date -Format o); machine = $env:COMPUTERNAME } |
            ConvertTo-Json -Compress) | Write-Utf8NoBom -Path $lock
    } catch { }

    # Written by US, now, before the agent has done anything. Closes the window
    # between launch and the agent's first write in which the leg would
    # otherwise read 'ready' again and be dispatched twice.
    # -Force creates MISSING PARENTS, so this line creates $wt itself when the
    # worktree is not there - which is the second half of the orphan
    # manufacture. It runs after Start-Process and nothing between can abort,
    # so on a failed add it reliably produced an unregistered directory ~67ms
    # after launch. Guard it: write the marker into a worktree that exists,
    # never conjure one to write into.
    if (-not (Test-Path $wt)) {
        Say "  WARNING - worktree vanished before the launch marker; not creating it" 'Red'
        Notify "$($leg.id) worktree missing at marker time" "Refused to create $wt as a side effect of writing .orch_launched. An unregistered directory there is how orphans are manufactured."
    }
    else {
        New-Item -ItemType Directory -Force -Path (Join-Path $wt '.claude') | Out-Null
        Set-Content -Path (Join-Path $wt '.claude\.orch_launched') -Value (Get-Date -Format o)
    }

    Say "  launched" 'Green'
}

# Backup is structural, never remembered. Feature branches only, never master,
# never --force. Gate C stays human; this is backup, not integration.
function Backup-Branches {
    $pushed = @()
    foreach ($line in (git -C $repo worktree list)) {
        $p = ($line -split '\s+')[0]
        if (-not (Test-Path $p)) { continue }
        $br = (git -C $p rev-parse --abbrev-ref HEAD 2>$null)
        if (-not $br -or $br -eq 'HEAD' -or $br -in @('master','main')) { continue }

        # Claude Code's --effort ultracode spawns DYNAMIC WORKFLOW worktrees named
        # worktree-wf_<hash>-<n>. They are agent-internal scratch, not work to
        # preserve. On 2026-07-26 eleven of them appeared at once and this
        # function pushed every one to origin - the backup rule was written as
        # "any branch that is not master", which was too permissive the moment
        # something other than me started creating branches.
        # Backup preserves WORK. Ephemeral scratch is not work.
        if ($br -match '^worktree-wf_') { continue }
        $up = (git -C $p rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null)
        if (-not $up) {
            # no upstream yet - push once WITH tracking so subsequent polls can
            # tell ahead from up-to-date. Without -u, @{u} keeps failing and the
            # branch is re-pushed every single poll, reported as "(new)" forever.
            git -C $p push -u origin $br 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $pushed += "$br(tracked)" }
            continue
        }
        $ahead = (git -C $p rev-list --count '@{u}..HEAD' 2>$null)
        if (-not $ahead -or $ahead -eq '0') { continue }
        git -C $p push origin "${br}:${br}" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $pushed += "$br(+$ahead)" }
    }
    return $pushed
}

function Get-LastProgress {
    # Measure the AGENTS' work, never our own. The orchestrator writes its log
    # into harness/notes/ every poll, so scanning the repo made the staleness
    # detector detect itself - "last write 0m ago" forever, a check that cannot
    # fail, inside the thing built to detect stalls. Agent transcripts are the
    # honest signal: they are written by the agent and by nothing else.
    $newest = $null
    $proj = Join-Path $env:USERPROFILE '.claude\projects'
    # Match the FULL PATH, not the file's immediate parent name. A leg's own
    # session transcript sits at ...\<SYNAPSE-slug>\<session>.jsonl - parent
    # name carries 'SYNAPSE' - but a crucible deep in subagent probes, or any
    # ultracode workflow, writes ONLY to the subagent/workflow transcripts one
    # or more levels down:
    #   ...\<SYNAPSE-slug>\<session>\subagents\*.jsonl
    #   ...\<SYNAPSE-slug>\<session>\subagents\workflows\wf_*\agent-*.jsonl
    # whose parent names are 'subagents' / 'wf_*'. The old $_.Directory.Name
    # filter never matched those, so a busy subagent fan-out read as dead after
    # StaleMinutes - the exact false-STALE this detector exists to avoid.
    # FullName still carries 'SYNAPSE' at every depth (and still excludes other
    # projects), so subagent + workflow activity now counts as the liveness it
    # is. harness\progress.py and harness\statusline.py already read this path
    # shape; this brings the ps1 tracker in line with them.
    $f = Get-ChildItem $proj -Recurse -Filter *.jsonl -EA SilentlyContinue |
         Where-Object { $_.FullName -match 'SYNAPSE' } |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f) { $newest = $f.LastWriteTime }

    # plus real file writes in the worktrees, excluding our own notes dir
    $f2 = Get-ChildItem (Join-Path $repo '.claude\worktrees') -Recurse -File -EA SilentlyContinue |
          Where-Object { $_.FullName -notmatch '\\\.git\\|__pycache__|pytest_cache|harness\\notes' } |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f2 -and (-not $newest -or $f2.LastWriteTime -gt $newest)) { $newest = $f2.LastWriteTime }
    return $newest
}

# --- main loop ---------------------------------------------------------------

# Library mode. Tests dot-source this file to reach ONE function - e.g.
# Get-LastProgress - without launching the board. A real dispatch never sets
# this env var, so the running orchestrator is untouched; `return` from a
# dot-sourced script stops here yet keeps every function defined above in the
# caller's scope. Get-LastProgress has no Python twin (unlike lock.py /
# status.py), so dot-sourcing the real ps1 function is the only honest test.
if ($env:SYNAPSE_ORCH_LIB) { return }

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
Say "SYNAPSE ORCHESTRATOR" 'Cyan'
Say "manifest $($manifest.legs.Count) legs   base $($manifest.base)   log $log" 'DarkGray'
Say "one window owns the board. close it to stop everything." 'DarkGray'
Write-Host ""

$known = @{}
foreach ($leg in $manifest.legs) { $known[$leg.id] = Get-LegState $leg }
Say ("baseline: " + (($known.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join '  ')) 'DarkGray'
Write-Host ""

$staleAnnounced = $false
$idle = $false
$deadline = (Get-Date).AddHours($MaxHours)
$nextDigest = (Get-Date).AddMinutes($DigestMinutes)
Say "digest every $DigestMinutes min - first at $($nextDigest.ToString('HH:mm'))" 'DarkGray'
Say "board-complete enters IDLE WATCH, not exit - add a leg to legs.json any time" 'DarkGray'
Rails-Open   # BP1-RAILS: opens the run ledger when -Budget is set; no-op otherwise

while ((Get-Date) -lt $deadline) {

    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json   # re-read: edits take effect live
    $summary = @()

    foreach ($leg in $manifest.legs) {
        $now = Get-LegState $leg
        $was = $known[$leg.id]

        if ($now -ne $was) {
            $known[$leg.id] = $now
            Say "STATE  $($leg.id) $($leg.name)  $was -> $now" 'Yellow'

            if ($now -eq 'done') {
                # R168: KILL THE WINDOW, not just the lock.
                #
                # R147 wired Release-LegLock here and nothing closed the session.
                # On 2026-07-28 three finished legs were still alive when Joe
                # returned - V2 idle 85 minutes with its receipt already written,
                # H3b and V3 done and merged. A session that has finished still
                # holds a context, and the weekly limit is spent on session
                # length, not on prompt size.
                #
                # Zombie sessions are the single most wasteful thing here, and
                # nothing was watching for them.
                Release-LegLock $leg.id
                try {
                    $pat = "*-File*orch_$($leg.id).ps1*"
                    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
                        Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like $pat } |
                        ForEach-Object {
                            Get-CimInstance Win32_Process -Filter "ParentProcessId=$($_.ProcessId)" -EA SilentlyContinue |
                                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
                            Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue
                            Say "  reaped $($leg.id) window pid $($_.ProcessId)" 'DarkGray'
                        }
                } catch { }

                $r = Get-Content (Get-ReceiptPath $leg) -Raw | ConvertFrom-Json
                $status = $r.status; $ruling = @($r.for_ruling).Count
                $plain = switch -Wildcard ($status) {
                    'green*' { 'clean' } 'amber*' { 'passed, debt logged' }
                    'red*'   { 'ORACLE FAILED - needs you' } 'held*' { 'held' }
                    default  { $status }
                }
                Notify "$($leg.id) $($leg.name) - $plain" "$ruling items for your ruling. Nothing pushed."
                Say "  receipt: $status   $ruling ruling items" 'Green'
            }
        }

        # W6-GATE: a leg that produced a receipt but has not cleared the close
        # gate holds at 'closing'. Surface the exact missing condition the first
        # time it appears and again each time it ADVANCES (receipt not committed
        # -> not HEAD -> no RELEASE), but never re-notify an unchanged reason.
        # Self-clears when the leg leaves 'closing' (to 'done' on a clean close).
        if ($now -eq 'closing') {
            $why = $script:CloseGateReason[$leg.id]
            if ($script:CloseGateNotified[$leg.id] -ne $why) {
                $script:CloseGateNotified[$leg.id] = $why
                Say "  $($leg.id) held at closing: $why" 'Yellow'
                Notify "$($leg.id) held at closing" $why
            }
        } elseif ($script:CloseGateNotified.ContainsKey($leg.id)) {
            $script:CloseGateNotified.Remove($leg.id) | Out-Null
        }

        # dispatch anything whose deps are now met. 'held' is held by RULING.
        # BP1-RAILS: charge the dispatch through rails.py first when -Budget is
        # set. Rails-Charge returns $true unconditionally when -Budget is absent,
        # so this branch is byte-identical on the default path; a cap hit returns
        # $false (rails.py already wrote the blocked:budget receipt) and we stop
        # dispatching this poll - the halt is finalized after the loop.
        if ($now -eq 'ready' -and $leg.prompt) {
            if (Rails-Charge $leg) { Start-Leg $leg; $known[$leg.id] = 'launched' }
            else { break }
        }

        $summary += "$($leg.id):$($known[$leg.id])"
    }

    # BP1-RAILS: a budget halt ends the run - never a silent continue. Guarded so
    # it can only fire when -Budget is set and rails.py refused a dispatch.
    if ($script:BudgetHalted) {
        Say "BUDGET HALT: dispatch stopped by -Budget '$Budget'. rails.py wrote a blocked:budget receipt under harness/battleplan/runs/. Nothing pushed to master." 'Red'
        Notify "SYNAPSE - budget halt" "-Budget '$Budget' reached. Dispatch stopped; receipt written."
        break
    }

    $backed = Backup-Branches
    if ($backed.Count) { Say "backed up  $($backed -join ' ')" 'DarkGray' }

    $last = Get-LastProgress
    $mins = if ($last) { [int]((Get-Date) - $last).TotalMinutes } else { 999 }
    if ($mins -ge $StaleMinutes -and -not $staleAnnounced) {
        $staleAnnounced = $true
        Notify "SYNAPSE - no progress in ${mins}m" "Nothing written across any tree. Worth a look."
        Say "STALE - ${mins}m since last write anywhere" 'Red'
    } elseif ($mins -lt $StaleMinutes -and $staleAnnounced) {
        $staleAnnounced = $false; Say "progress resumed" 'Green'
    }

    Say ("board  " + ($summary -join '  ') + "   | last write ${mins}m ago")

    # Periodic digest. The per-poll board line is for the window; this is for the
    # phone. Counts only - a digest that needs reading is not a digest.
    if ((Get-Date) -ge $nextDigest) {
        $nextDigest = (Get-Date).AddMinutes($DigestMinutes)
        $done    = @($known.Values | Where-Object { $_ -eq 'done' }).Count
        $running = @($manifest.legs | Where-Object { $known[$_.id] -eq 'running' })
        $held    = @($known.Values | Where-Object { $_ -eq 'held' }).Count
        $ruling  = 0
        foreach ($leg in $manifest.legs) {
            $rp = Get-ReceiptPath $leg
            if ($rp) {
                try { $ruling += @((Get-Content $rp -Raw | ConvertFrom-Json).for_ruling).Count } catch { }
            }
        }
        $runNames = if ($running.Count) { ($running | ForEach-Object { $_.id }) -join ' ' } else { 'none' }
        Notify "SYNAPSE $done/$($manifest.legs.Count) - running: $runNames" `
               "$ruling items banked for your ruling. $held held for you. Last write ${mins}m ago. Nothing pushed to master."
        Say "DIGEST sent  $done done, running $runNames, $ruling ruling, $held held" 'Cyan'
    }

    # Board complete does NOT end the run. It enters IDLE WATCH.
    #
    # 2026-07-26: the loop used to `break` here. H9 was added to the manifest at
    # 20:00 and sat undispatched until 22:51 - nearly three hours - because the
    # orchestrator had exited at 19:58 on board-complete and was sitting at a
    # prompt, alive but not polling. A leg added after completion did nothing,
    # silently, which is precisely the failure this harness exists to remove.
    #
    # The manifest is re-read every poll, so a new leg is dispatchable the moment
    # it lands. Idling instead of exiting costs one file read per interval and
    # buys the property that adding a row to legs.json is always sufficient.
    # W6-GATE: 'closing' counts as live. A leg whose close gate is unmet needs a
    # human/agent to commit its receipt as HEAD or post its RELEASE - the board
    # is NOT complete, so it must not enter idle watch and report otherwise.
    $live = @($manifest.legs | Where-Object { $known[$_.id] -in @('running','launched','ready','blocked','closing') })

    if ($live.Count -eq 0) {
        if (-not $idle) {
            $idle = $true
            Notify "SYNAPSE - board complete" `
                   "Every dispatchable leg has a receipt. Held legs need a human. Still watching - add a leg to legs.json and it dispatches."
            Say "BOARD COMPLETE - idle watch, still reading legs.json every ${IdlePollSeconds}s" 'Cyan'
            Say "  add a row to the manifest and it dispatches. close this window to stop." 'DarkGray'
        }
        Backup-Branches | Out-Null      # keep preserving work even while idle
        Start-Sleep -Seconds $IdlePollSeconds
        continue
    }

    if ($idle) {
        $idle = $false
        $newly = ($live | ForEach-Object { $_.id }) -join ' '
        Notify "SYNAPSE - resumed" "New work on the board: $newly"
        Say "RESUMED from idle - $newly" 'Green'
    }

    Start-Sleep -Seconds $PollSeconds
}
