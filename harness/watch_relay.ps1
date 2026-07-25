# CTO-RELAY-01 watcher. Toast on EACH leg landing, and on completion or death.
param([int]$RelayPid = 62808, [int]$PollSeconds = 20, [int]$MaxHours = 6)

$ErrorActionPreference = 'SilentlyContinue'
$repo   = 'C:\Users\User\SYNAPSE'
$rdir   = Join-Path $repo 'harness\notes\receipts'
$marker = Join-Path $repo 'harness\notes\RELAY_COMPLETE.txt'
$legs   = [ordered]@{ L0='ground'; L1='context'; L2='solaris'; L3='panel truth'; L4='panel skin'; L5='ruling' }

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
        $ni.ShowBalloonTip(8000, $title, $body, [System.Windows.Forms.ToolTipIcon]::Info)
        Start-Sleep -Seconds 9; $ni.Dispose()
    }
    1..2 | ForEach-Object { [console]::beep(880, 160); Start-Sleep -Milliseconds 80 }
}

$seen = @{}
foreach ($k in $legs.Keys) { if (Test-Path (Join-Path $rdir "$k.json")) { $seen[$k] = $true } }
Write-Host "baseline (not re-announced): $($seen.Keys -join ' ')"
Write-Host "watching for new landings, poll ${PollSeconds}s"

$deadline = (Get-Date).AddHours($MaxHours)
while ((Get-Date) -lt $deadline) {

    foreach ($k in $legs.Keys) {
        $fp = Join-Path $rdir "$k.json"
        if ((Test-Path $fp) -and -not $seen[$k]) {
            $seen[$k] = $true
            $status = '?'; $ruling = 0; $failed = '?'
            try {
                $j = Get-Content $fp -Raw | ConvertFrom-Json
                $status = $j.status
                $ruling = @($j.for_ruling).Count
                $failed = $j.suite.failed
            } catch { }
            $done = @($seen.Keys).Count
$plain = switch ($status) {
    'green' { 'clean' }
    'amber' { 'passed, debt logged' }
    'red'   { 'ORACLE FAILED - needs you' }
    default { $status }
}
Notify "$k $($legs[$k]) - $plain  ($done/6)" "$ruling items for your ruling. Suite failures: $failed. Nothing pushed - Gate C is yours."
            Write-Host ("{0}  {1} landed [{2}]  {3}/6" -f (Get-Date -Format 'HH:mm:ss'), $k, $status, $done)
        }
    }

    if (@($seen.Keys).Count -ge 6) {
        "COMPLETE $(Get-Date -Format o)" | Set-Content $marker
        Notify "SYNAPSE relay complete - 6/6" "Ruling block ready. Gate C is yours - nothing pushed."
        Write-Host "COMPLETE"; break
    }

    if (-not (Get-Process -Id $RelayPid -ErrorAction SilentlyContinue)) {
        $n = @($seen.Keys).Count
        "STOPPED $(Get-Date -Format o) at $n/6" | Set-Content $marker
        Notify "SYNAPSE relay stopped - $n/6" "Resume line is in harness/SYNAPSE_CTO_RELAY.md section 6."
        Write-Host "RELAY GONE at $n/6"; break
    }
    Start-Sleep -Seconds $PollSeconds
}
