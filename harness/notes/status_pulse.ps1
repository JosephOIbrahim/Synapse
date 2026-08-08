# status_pulse.ps1 - loop-closure status toast every 5 minutes.
# Stops itself when the completion ping fires (PING_FIRED.txt) or after 4h.
# Kill early: delete harness\notes\PULSE_STOP marker check below, or
#             Stop-Process on the pid reported at launch.
$fid  = 'C:\Users\User\Synapse\.claude\worktrees\fidelity-unknown\harness\notes\receipts\FID.json'
$mark = 'C:\Users\User\Synapse\harness\notes\PING_FIRED.txt'
$stop = 'C:\Users\User\Synapse\harness\notes\PULSE_STOP'
$t0   = Get-Date '2026-08-08 12:50'
$deadline = (Get-Date).AddHours(4)

function Toast($title, $body) {
  try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
    $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
           [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $n = $t.GetElementsByTagName('text')
    $n.Item(0).AppendChild($t.CreateTextNode($title)) | Out-Null
    $n.Item(1).AppendChild($t.CreateTextNode($body)) | Out-Null
    $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show(
      [Windows.UI.Notifications.ToastNotification]::new($t))
  } catch { }
}

while ((Get-Date) -lt $deadline) {
  if ((Test-Path $mark) -or (Test-Path $stop)) { break }
  $el = (Get-Date) - $t0
  $msg = if (Test-Path $fid) { 'FID receipt landed - completion toast imminent.' }
         else { 'Waiting on FID ({0}h {1:d2}m elapsed). 1 receipt from close.' -f [int]$el.TotalHours, $el.Minutes }
  Toast 'SYNAPSE loop closure' $msg
  Start-Sleep -Seconds 300
}
