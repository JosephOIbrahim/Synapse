# ping_watch.ps1 - Windows toast when FID + PRST receipts land, then exit.
# Detached process; survives Claude Desktop closing. 8h patience, 30s polls.
$fid  = 'C:\Users\User\Synapse\.claude\worktrees\fidelity-unknown\harness\notes\receipts\FID.json'
$prst = 'C:\Users\User\Synapse\.claude\worktrees\network-persistence\harness\notes\receipts\PRST.json'
$mark = 'C:\Users\User\Synapse\harness\notes\PING_FIRED.txt'
$deadline = (Get-Date).AddHours(8)

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
  if ((Test-Path $fid) -and (Test-Path $prst)) {
    Toast 'SYNAPSE - wave 1 complete' 'FID + PRST landed. Paste harness/notes/CLOSE_2026-08-08.ps1 to merge and push.'
    Set-Content $mark ("fired " + (Get-Date))
    break
  }
  Start-Sleep -Seconds 30
}
