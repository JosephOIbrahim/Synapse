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
      [switch]$DryRun)

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

function Get-LegState([object]$leg) {
    if ($leg.state -eq 'held') { return 'held' }
    if ($leg.receipt -and (Test-Path (Join-Path $rdir $leg.receipt))) { return 'done' }
    if ($leg.worktree) {
        $wt = Join-Path $repo $leg.worktree
        if (Test-Path (Join-Path $wt '.claude\settings.local.json')) {
            # launched and past the trust dialog; running until its receipt lands
            return 'running'
        }
        if (Test-Path $wt) { return 'launched' }
    }
    foreach ($d in @($leg.deps)) {
        $dep = $manifest.legs | Where-Object { $_.id -eq $d }
        if ($dep -and -not (Test-Path (Join-Path $rdir $dep.receipt))) { return 'blocked' }
    }
    return 'ready'
}

function Start-Leg([object]$leg) {
    $wt = Join-Path $repo $leg.worktree
    Say "DISPATCH $($leg.id) $($leg.name)  ->  $($leg.branch)" 'Cyan'
    if ($DryRun) { Say "  (dry run - not launching)" 'DarkGray'; return }

    if (-not (Test-Path $wt)) {
        git worktree add -b $leg.branch $wt HEAD 2>&1 | Select-Object -Last 1 | ForEach-Object { Say "  $_" 'DarkGray' }
    }

    # A fresh worktree is UNTRUSTED - Claude Code blocks on the trust dialog
    # before its first token. Silent, indefinite, indistinguishable from slow
    # work. Cost 13 minutes on 2026-07-26. Always trust before launch.
    python (Join-Path $repo 'harness\trust_worktrees.py') 2>&1 |
        Select-Object -Last 1 | ForEach-Object { Say "  trust: $_" 'DarkGray' }

    $prompt = Get-Content (Join-Path $repo $leg.prompt) -Raw
    $script = Join-Path $env:TEMP "orch_$($leg.id).ps1"
    @"
Set-Location '$wt'
Write-Host ''
Write-Host '  LEG $($leg.id) - $($leg.name)   branch $($leg.branch)' -ForegroundColor Cyan
Write-Host ''
`$p = @'
$prompt
'@
claude --settings $($manifest.settings) --permission-mode acceptEdits --verbose `$p
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
        $up = (git -C $p rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null)
        $ahead = if ($up) { (git -C $p rev-list --count '@{u}..HEAD' 2>$null) } else { 'new' }
        if ($ahead -eq '0') { continue }
        git -C $p push origin "${br}:${br}" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $pushed += "$br($ahead)" }
    }
    return $pushed
}

function Get-LastProgress {
    $newest = $null
    foreach ($root in @($repo, (Join-Path $repo '.claude\worktrees'))) {
        $f = Get-ChildItem $root -Recurse -File -EA SilentlyContinue |
             Where-Object { $_.FullName -notmatch '\\\.git\\|__pycache__|pytest_cache|mypy_cache' } |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($f -and (-not $newest -or $f.LastWriteTime -gt $newest)) { $newest = $f.LastWriteTime }
    }
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
                $r = Get-Content (Join-Path $rdir $leg.receipt) -Raw | ConvertFrom-Json
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

    $live = @($manifest.legs | Where-Object { $known[$_.id] -in @('running','launched','ready','blocked') })
    if ($live.Count -eq 0) {
        Notify "SYNAPSE - board complete" "Every dispatchable leg has a receipt. Held legs need a human."
        Say "BOARD COMPLETE - nothing left to dispatch" 'Cyan'
        break
    }

    Start-Sleep -Seconds $PollSeconds
}
