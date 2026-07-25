# CTO-RELAY-01 completion watcher. Polls receipts; notifies on 6/6 or on relay death.
param([int]$RelayPid = 62808, [int]$PollSeconds = 30, [int]$MaxHours = 6)

$ErrorActionPreference = 'SilentlyContinue'
$repo   = 'C:\Users\User\SYNAPSE'
$rdir   = Join-Path $repo 'harness\notes\receipts'
$marker = Join-Path $repo 'harness\notes\RELAY_COMPLETE.txt'
$legs   = @('L0','L1','L2','L3','L4','L5')

function Notify([string]$title, [string]$body) {
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
        $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
                [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $n = $t.GetElementsByTagName('text')
        $n.Item(0).AppendChild($t.CreateTextNode($title)) | Out-Null
        $n.Item(1).AppendChild($t.CreateTextNode($body))  | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($t)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SYNAPSE').Show($toast)
    } catch {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($body, $title) | Out-Null
    }
    1..3 | ForEach-Object { [console]::beep(880, 180); Start-Sleep -Milliseconds 90 }
}

$deadline = (Get-Date).AddHours($MaxHours)
Write-Host "watching CTO-RELAY-01 (pid $RelayPid) — poll ${PollSeconds}s, deadline $deadline"

while ((Get-Date) -lt $deadline) {
    $have = @($legs | Where-Object { Test-Path (Join-Path $rdir "$_.json") })
    $n = $have.Count
    Write-Host ("{0}  receipts {1}/6  [{2}]" -f (Get-Date -Format 'HH:mm:ss'), $n, ($have -join ' '))

    if ($n -ge 6) {
        $body = "All six legs landed. Ruling block ready. 0 pushed - Gate C is yours."
        "COMPLETE $(Get-Date -Format o)`nreceipts: $($have -join ' ')" | Set-Content $marker
        Notify "SYNAPSE relay complete - 6/6" $body
        Write-Host "COMPLETE"
        break
    }

    $alive = Get-Process -Id $RelayPid -ErrorAction SilentlyContinue
    if (-not $alive) {
        $body = "Relay process exited at $n/6 receipts. Resume line is in harness/SYNAPSE_CTO_RELAY.md section 6."
        "STOPPED $(Get-Date -Format o)`nreceipts: $n/6" | Set-Content $marker
        Notify "SYNAPSE relay stopped - $n/6" $body
        Write-Host "RELAY GONE at $n/6"
        break
    }
    Start-Sleep -Seconds $PollSeconds
}

if (-not (Test-Path $marker)) {
    Notify "SYNAPSE relay - watcher timed out" "Hit the $MaxHours-hour limit. Check: python harness\relay_status.py"
}
