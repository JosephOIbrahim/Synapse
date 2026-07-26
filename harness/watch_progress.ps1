# Receipt-staleness watcher. Q0 item 4.
#
# Every watcher on 2026-07-25 died because it tracked a PID that vanished in a crash.
# A PID is a handle to something that can disappear; a file appearing is durable evidence.
# This reports facts about the WORK, never about the bridge - the bridge is the unreliable part.
param([int]$StaleMinutes = 40, [int]$PollSeconds = 60, [int]$MaxHours = 12)

$ErrorActionPreference = 'SilentlyContinue'
$repo   = 'C:\Users\User\SYNAPSE'
$rdir   = Join-Path $repo 'harness\notes\receipts'
$stages = [ordered]@{ Q0='bridge'; Q1='unpoison'; Q2='baseline'; H1='schemas'
                      H2='requalify'; H3='cook-cancel'; H4='panel-finish'
                      F1='integrate'; F2='tag call' }

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
        $ni.Icon = [System.Drawing.SystemIcons]::Information
        $ni.Visible = $true
        $ni.ShowBalloonTip(9000, $title, $body, [System.Windows.Forms.ToolTipIcon]::Info)
        Start-Sleep -Seconds 10; $ni.Dispose()
    }
    1..2 | ForEach-Object { [console]::beep(880, 150); Start-Sleep -Milliseconds 80 }
}

# Progress = anything the agents write, not just receipts. A long stage is not a dead one.
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

$seen = @{}
foreach ($k in $stages.Keys) { if (Test-Path (Join-Path $rdir "$k.json")) { $seen[$k] = $true } }
Write-Host "baseline (not re-announced): $($seen.Keys -join ' ')"
Write-Host "watching receipts + progress. stale threshold ${StaleMinutes}m. close window to stop."

$staleAnnounced = $false
$deadline = (Get-Date).AddHours($MaxHours)

while ((Get-Date) -lt $deadline) {

    foreach ($k in $stages.Keys) {
        $fp = Join-Path $rdir "$k.json"
        if ((Test-Path $fp) -and -not $seen[$k]) {
            $seen[$k] = $true; $staleAnnounced = $false
            $status = '?'; $ruling = 0; $failed = '?'
            try {
                $j = Get-Content $fp -Raw | ConvertFrom-Json
                $status = $j.status; $ruling = @($j.for_ruling).Count; $failed = $j.suite.failed
            } catch { }
            $plain = switch ($status) {
                'green' { 'clean' } 'amber' { 'passed, debt logged' }
                'red'   { 'ORACLE FAILED - needs you' } default { $status }
            }
            Notify "$k $($stages[$k]) - $plain  ($($seen.Count)/9)" `
                   "$ruling items for your ruling. Suite failures: $failed. Nothing pushed."
            Write-Host ("{0}  {1} landed [{2}]" -f (Get-Date -Format 'HH:mm:ss'), $k, $status)
        }
    }

    $last = Get-LastProgress
    $mins = if ($last) { [int]((Get-Date) - $last).TotalMinutes } else { 999 }

    if ($mins -ge $StaleMinutes -and -not $staleAnnounced) {
        $staleAnnounced = $true
        Notify "SYNAPSE - no progress in ${mins}m" `
               "$($seen.Count)/9 receipts. Nothing written across either tree. Worth a look."
        Write-Host ("{0}  STALE - {1}m since last write" -f (Get-Date -Format 'HH:mm:ss'), $mins)
    } elseif ($mins -lt $StaleMinutes -and $staleAnnounced) {
        $staleAnnounced = $false
        Write-Host ("{0}  progress resumed" -f (Get-Date -Format 'HH:mm:ss'))
    }

    Write-Host ("{0}  {1}/9 receipts | last write {2}m ago" -f `
        (Get-Date -Format 'HH:mm:ss'), $seen.Count, $mins)

    Start-Sleep -Seconds $PollSeconds
}
