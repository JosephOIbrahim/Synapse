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
      [int]$DigestMinutes = 20, [switch]$DryRun)

$ErrorActionPreference = 'SilentlyContinue'
$repo = 'C:\Users\User\SYNAPSE'
Set-Location $repo
$manifestPath = Join-Path $repo 'harness\legs.json'
$rdir         = Join-Path $repo 'harness\notes\receipts'
$log          = Join-Path $repo ("harness\notes\orchestrator_{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Say([string]$m, [string]$c = 'Gray') {
    $line = "{0}  {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Write-Host $line -ForegroundColor $c
    Add-Content -Path $log -Value $line
}

function Notify([string]$title, [string]$body) {
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

function Get-LegState([object]$leg) {
    if ($leg.state -eq 'held') { return 'held' }
    if ($leg.receipt -and (Get-ReceiptPath $leg)) { return 'done' }
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
    if ($DryRun) { Say "  (dry run - not launching)" 'DarkGray'; return }

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
        git worktree add -b $leg.branch $wt HEAD 2>&1 | Select-Object -Last 1 | ForEach-Object { Say "  $_" 'DarkGray' }
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
    # surface and no length limit.
    $promptPath = (Join-Path $repo $leg.prompt) -replace '\\','/'

    # R61: a read-only leg is FENCED, not asked. Read-only was an instruction in
    # the brief and nothing enforced it - a read-only fleet edited five schema
    # files and kept writing four minutes past TaskStop. The profile is a
    # property of the leg, not a promise in prose.
    $profile = if ($leg.readonly) {
        (Join-Path $repo 'harness\readonly-settings.json') -replace '\\','/'
    } else { $manifest.settings }
    if ($leg.readonly) { Say "  profile: READ-ONLY (fenced)" 'DarkGray' }

    $script = Join-Path $env:TEMP "orch_$($leg.id).ps1"
    @"
Set-Location '$wt'
Write-Host ''
Write-Host '  LEG $($leg.id) - $($leg.name)   branch $($leg.branch)' -ForegroundColor Cyan
Write-Host '  brief: $promptPath' -ForegroundColor DarkGray
Write-Host ''
claude --settings $profile --effort $($manifest.effort) --name 'SYNAPSE $($leg.id) $($leg.name)' --permission-mode acceptEdits --verbose 'Read the file $promptPath in full and execute it end to end. It is your complete brief. If any part of it appears truncated or unreadable, STOP and say so rather than proceeding on a partial instruction.'
Write-Host ''
Write-Host '  Type /rc here to control this leg from your phone.' -ForegroundColor Yellow
Write-Host '  It appears in claude.ai/code as: SYNAPSE $($leg.id) $($leg.name)' -ForegroundColor DarkGray
Write-Host ''
Write-Host ''
Write-Host '  LEG $($leg.id) TERMINATED' -ForegroundColor Cyan
"@ | Set-Content $script -Encoding utf8

    Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$script -WindowStyle Normal
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
    $f = Get-ChildItem $proj -Recurse -Filter *.jsonl -EA SilentlyContinue |
         Where-Object { $_.Directory.Name -match 'SYNAPSE' } |
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
$deadline = (Get-Date).AddHours($MaxHours)
$nextDigest = (Get-Date).AddMinutes($DigestMinutes)
Say "digest every $DigestMinutes min - first at $($nextDigest.ToString('HH:mm'))" 'DarkGray'

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

        # dispatch anything whose deps are now met. 'held' is held by RULING.
        if ($now -eq 'ready' -and $leg.prompt) { Start-Leg $leg; $known[$leg.id] = 'launched' }

        $summary += "$($leg.id):$($known[$leg.id])"
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

    $live = @($manifest.legs | Where-Object { $known[$_.id] -in @('running','launched','ready','blocked') })
    if ($live.Count -eq 0) {
        Notify "SYNAPSE - board complete" "Every dispatchable leg has a receipt. Held legs need a human."
        Say "BOARD COMPLETE - nothing left to dispatch" 'Cyan'
        break
    }

    Start-Sleep -Seconds $PollSeconds
}
