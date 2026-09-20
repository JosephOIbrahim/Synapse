# dryrun_bp8.ps1 - clone of dryrun_bp4.ps1 (wave id swap). Proves the BP8 rows parse as legs/v1,
# dependency gating holds and the merged orchestrate.ps1 (JEV-EDGE / JEV-DRIFT hooks) does not crash,
# with both hooks in shadow exactly as the live arm will run them. Dispatches nothing.
$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'
$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$env:SYNAPSE_JEV_EDGE  = 'shadow'
$env:SYNAPSE_JEV_DRIFT = 'shadow'
$man = Join-Path $af 'waves\bp8.control.json'
$log = Join-Path $af 'waves\bp8.dryrun.log'
$err = Join-Path $af 'waves\bp8.dryrun.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$man,'-DryRun','-Budget','6turns,70000000tokens' -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
$p.Id | Out-File (Join-Path $af 'waves\bp8.dryrun.pid') -Encoding ascii
Write-Host ("bp8 dry run started pid " + $p.Id + " -> " + $log)
