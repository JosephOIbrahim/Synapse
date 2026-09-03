# dryrun_bp4.ps1 - BP4 preflight: orchestrate.ps1 -DryRun over waves\bp4.control.json. NEVER dispatches.
# Proves: rows parse as legs/v1, dependency gating holds (CRUX/TIDY read blocked), the -Budget cap string
# parses (turns floor + token ceiling), the dry-run launch lines carry --effort max and the tier models.
# Detached; DC polls waves\bp4.dryrun.log. Stop the pid when the pass is read.
$ErrorActionPreference = 'Continue'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'
$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$man = Join-Path $af 'waves\bp4.control.json'
$log = Join-Path $af 'waves\bp4.dryrun.log'
$err = Join-Path $af 'waves\bp4.dryrun.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$man,'-DryRun','-Budget','12turns,105000000tokens' -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
$p.Id | Out-File (Join-Path $af 'waves\bp4.dryrun.pid') -Encoding ascii
Write-Host ("bp4 dry run started pid " + $p.Id + " -> " + $log)
