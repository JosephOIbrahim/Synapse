# rope closer -- CTO pre-approved tail. Waits out the finisher chain, merges
# the staged design task, runs it, rewrites the report. Fully unattended.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$log = "harness\rope\closer.log"
function Say($m) {
  $line = "$(Get-Date -Format 'HH:mm:ss')  $m"
  Write-Host $line; Add-Content -Path $log -Value $line
}
function Busy {
  $r = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match 'runner\.py run' }
  $f = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match 'finisher\.ps1' }
  return [bool]($r -or $f)
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

Say "closer armed (CTO pre-approved) -- waiting out runner + finisher"
$w = 0
while ((Busy) -and $w -lt 10800) { Start-Sleep 30; $w += 30 }   # 3h ceiling
if (Busy) { Say "still busy after 3h -- standing down, changing nothing"; exit }
Start-Sleep 10
if (Test-Path "harness\rope\.runner.lock") {
  Say "stale lock present, no runner alive -- clearing"
  Remove-Item "harness\rope\.runner.lock" -Force -ErrorAction SilentlyContinue
}

Say "merging staged tasks"
$m = & python harness\rope\merge_pending.py 2>&1
Say "merge: $m"

Say "running L5-11 design conformance pass"
$p = Start-Process python -ArgumentList "harness\rope\runner.py","run","--model","claude-fable-5",`
     "--confirm-model","--live-seat-ok","--task","L5-11" -WorkingDirectory $root `
     -WindowStyle Minimized -PassThru -RedirectStandardOutput "harness\rope\l511.log" `
     -RedirectStandardError "harness\rope\l511.err.log"
$p.WaitForExit()
Say "L5-11 pass finished"

# ---- final report (supersedes the finisher's) ---------------------------
$gate    = (python harness\rope\runner.py gate 2>$null) -join "`n"
$status  = (python harness\rope\runner.py status 2>$null) -join "`n"
$ledger  = (Get-Content harness\rope\results.tsv -ErrorAction SilentlyContinue) -join "`n"
$commits = (git log --oneline rope/gate-a --not master) -join "`n"
$review  = @(python harness\rope\runner.py status 2>$null | Select-String " needs_review ") -join "`n"
$gaps    = ""
if (Test-Path docs\PROFILES.md) {
  $gaps = (Select-String -Path docs\PROFILES.md -Pattern "Design gap" -Context 0,12 | Out-String)
}
$rep = @"
# ROPE -- afternoon report ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))

## Gate
$gate

## YOUR MOVES (nothing else blocks the gate)
1. L3-2  record first-prompt video, embed in README
     python harness\rope\runner.py human L3-2 --done "video embedded"
2. L3-5  Apprentice session, fill support matrix
     python harness\rope\runner.py human L3-5 --done "Apprentice row filled"
3. Sign off each needs_review item after eyeballing it:
     python harness\rope\runner.py verify <ID> --passed
4. Optional: L2-4 PDG kwarg (seat-verified rename)

## needs_review -- agent work done, your judgement required
$review

## DESIGN GAPS logged by L5-11 (decisions the agent refused to make for you)
$gaps

## Task board
$status

## Ledger
$ledger

## Commits on rope/gate-a
$commits
"@
Set-Content -Path "harness\rope\AFTERNOON_REPORT.md" -Value $rep -Encoding UTF8
Say "report rewritten -> harness\rope\AFTERNOON_REPORT.md"
Toast "ROPE afternoon complete" ($gate -split "`n")[0]
Say "closer done."
