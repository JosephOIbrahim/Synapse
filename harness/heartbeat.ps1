# CTO-RELAY-01 heartbeat. Periodic status digest by toast. Independent of watch_relay.ps1.
param([int]$EveryMinutes = 30, [int]$RelayPid = 62808, [int]$SolarisPid = 57872, [int]$MaxHours = 8)

$ErrorActionPreference = 'SilentlyContinue'
$repo = 'C:\Users\User\SYNAPSE'
$rdir = Join-Path $repo 'harness\notes\receipts'
$legs = [ordered]@{ L0='ground'; L1='context'; L2='solaris'; L3='panel truth'; L4='panel skin'; L5='ruling' }

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
    [console]::beep(660, 140)
}

$deadline = (Get-Date).AddHours($MaxHours)
Write-Host "heartbeat every $EveryMinutes min until $deadline  (close this window to stop)"

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds ($EveryMinutes * 60)

    $have = @($legs.Keys | Where-Object { Test-Path (Join-Path $rdir "$_.json") })
    $current = ($legs.Keys | Where-Object { $_ -notin $have } | Select-Object -First 1)
    $where = if ($current) { "$current $($legs[$current]) running" } else { "all six landed" }

    $ruling = 0; $blockers = 0
    foreach ($k in $have) {
        try {
            $j = Get-Content (Join-Path $rdir "$k.json") -Raw | ConvertFrom-Json
            $ruling += @($j.for_ruling).Count
            $blockers += @($j.findings | Where-Object { $_.severity -eq 'blocker' }).Count
        } catch { }
    }

    Push-Location $repo
    $commits = (git rev-list --count master..HEAD 2>$null)
    Pop-Location

    $relay = if (Get-Process -Id $RelayPid -EA SilentlyContinue) { 'relay up' } else { 'relay STOPPED' }
    $sol   = if (Get-Process -Id $SolarisPid -EA SilentlyContinue) { 'solaris up' } else { 'solaris done' }
    $sr1   = if (Test-Path (Join-Path $repo '.claude\worktrees\solaris-repair\harness\notes\receipts\SR1.json')) { ' SR1 landed.' } else { '' }

    $title = "SYNAPSE - $($have.Count)/6 - $where"
    $body  = "$ruling for your ruling, $blockers blockers. $commits commits unpushed. $relay, $sol.$sr1"
    Notify $title $body
    Write-Host ("{0}  {1} | {2}" -f (Get-Date -Format 'HH:mm:ss'), $title, $body)

    if ($have.Count -ge 6 -and -not (Get-Process -Id $SolarisPid -EA SilentlyContinue)) {
        Notify "SYNAPSE - everything landed" "Both tracks done. Ruling block ready. Gate C is yours."
        break
    }
}
