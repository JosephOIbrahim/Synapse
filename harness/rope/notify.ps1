# rope notify -- 20-minute digest: Windows toast + PROGRESS.md + ticker line.
# Close this window anytime; it only reads. First digest fires immediately.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$appid = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
$last = 0
while ($true) {
  $rows = @(Get-Content harness\rope\results.tsv -ErrorAction SilentlyContinue | Select-Object -Skip 1)
  $new = $rows.Count - $last; $last = $rows.Count
  $gate = (python harness\rope\runner.py gate 2>$null | Select-Object -First 1)
  $flight = ((python harness\rope\runner.py status 2>$null | Select-String " in_progress ") -join "; ").Trim()
  if (-not $flight) { $flight = "none" }
  $alive = "runner STOPPED"
  if (Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'runner\.py run' }) { $alive = "runner ALIVE" }
  $stamp = Get-Date -Format "HH:mm"
  $line = "ROPE $stamp | $alive | +$new done this interval | $gate | in flight: $flight"
  $line | Tee-Object -FilePath harness\rope\PROGRESS.md -Append
  try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $t = $xml.GetElementsByTagName('text')
    $t.Item(0).AppendChild($xml.CreateTextNode("ROPE $stamp")) | Out-Null
    $t.Item(1).AppendChild($xml.CreateTextNode("$alive | +$new done | $gate")) | Out-Null
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appid).Show(
      [Windows.UI.Notifications.ToastNotification]::new($xml))
  } catch { }
  Start-Sleep 1200
}
