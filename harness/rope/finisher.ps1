# rope finisher -- unattended afternoon chain.
# 1) waits out the current pass  2) fires the revival run (picks up L1-3)
# 3) loops until nothing is eligible  4) writes AFTERNOON_REPORT.md + toasts.
# Safe to close this window: it only orchestrates; each pass is its own process.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$log = "harness\rope\finisher.log"
function Say($m) {
  $line = "$(Get-Date -Format 'HH:mm:ss')  $m"
  Write-Host $line; Add-Content -Path $log -Value $line
}
function RunnerPid {
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'runner\.py run' } |
    Select-Object -First 1 -ExpandProperty ProcessId
}
function Toast($title, $msg) {
  try {
    $appid = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $t = $xml.GetElementsByTagName('text')
    $t.Item(0).AppendChild($xml.CreateTextNode($title)) | Out-Null
    $t.Item(1).AppendChild($xml.CreateTextNode($msg)) | Out-Null
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appid).Show(
      [Windows.UI.Notifications.ToastNotification]::new($xml))
  } catch { }
}

Say "finisher armed -- waiting for the current pass to end"
$waited = 0
while ((RunnerPid) -and $waited -lt 5400) { Start-Sleep 20; $waited += 20 }
if (RunnerPid) { Say "current pass still alive after 90min -- standing down, not killing it"; exit }
Say "pass complete. starting revival passes."

# Up to 3 chained passes. Each start revives orphaned in_progress tasks, so
# L1-3 (zombie from the early kill) gets picked up automatically.
for ($i = 1; $i -le 3; $i++) {
  $before = (Get-Content harness\rope\results.tsv -ErrorAction SilentlyContinue).Count
  Say "pass $i starting"
  $p = Start-Process python -ArgumentList "harness\rope\runner.py","run","--model","claude-fable-5","--confirm-model","--live-seat-ok" `
       -WorkingDirectory $root -WindowStyle Minimized -PassThru `
       -RedirectStandardOutput "harness\rope\pass$i.log" -RedirectStandardError "harness\rope\pass$i.err.log"
  $p.WaitForExit()
  $after = (Get-Content harness\rope\results.tsv -ErrorAction SilentlyContinue).Count
  $delta = $after - $before
  Say "pass $i finished -- $delta ledger rows added"
  if ($delta -le 0) { Say "no progress; chain complete"; break }
}

# ---- final report -------------------------------------------------------
$gate    = (python harness\rope\runner.py gate 2>$null) -join "`n"
$status  = (python harness\rope\runner.py status 2>$null) -join "`n"
$ledger  = (Get-Content harness\rope\results.tsv -ErrorAction SilentlyContinue) -join "`n"
$commits = (git log --oneline rope/gate-a --not master) -join "`n"
$review  = @(python harness\rope\runner.py status 2>$null | Select-String " needs_review ")
$dirty   = (git status --porcelain) -join "`n"

$rep = @"
# ROPE -- afternoon report ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))

## Gate
$gate

## What needs YOU (nothing else is blocking)
1. L3-2  record the first-prompt video, embed in README
     python harness\rope\runner.py human L3-2 --done "video embedded"
2. L3-5  one Apprentice session, fill the support matrix
     python harness\rope\runner.py human L3-5 --done "Apprentice row filled"
3. Sign off anything at needs_review below:
     python harness\rope\runner.py verify <ID> --passed
4. Optional: L2-4 PDG kwarg (seat-verified rename)

## needs_review (agent work done; your eyes required)
$($review -join "`n")

## Task board
$status

## Ledger
$ledger

## Commits on rope/gate-a
$commits

## Working tree
$dirty
"@
Set-Content -Path "harness\rope\AFTERNOON_REPORT.md" -Value $rep -Encoding UTF8
Say "report written -> harness\rope\AFTERNOON_REPORT.md"
Toast "ROPE chain complete" ($gate -split "`n")[0]
Say "finisher done. this window can be closed."
