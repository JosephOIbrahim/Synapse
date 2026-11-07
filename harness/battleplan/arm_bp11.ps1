# arm_bp11.ps1 - arm wave BP11 (clone of arm_bp10.ps1, wave id swap) WITH budget rails.
# IDENTIFY + HARDENING: FIXFWD(mech) || IDCORE(auto) -> IDSURF(auto) -> SALIENCE(auto) -> HARDEN(auto)
# -> CRUX(referee) -> TIDY(mech). The Identify chain is serial by base, so at most one Opus leg is live.
# Joe's words 2026-09-28: arm at the 60M cap (CTO option), HARDEN pinned mechanical, effort xhigh (R-7 trial).
# 9turns = 7 dispatches + 2 slack for re-dispatch. 60M cost-weighted cap on a MEASURED basis: BP10's analog legs
# cost 7.0-9.9M per Opus builder, 5.5M CRUX, 1.6-2.5M per Haiku leg (runs/2026-09-21/ledger_orch_20260921-121433.json),
# which projects BP11 to ~45M (4 Opus builders, notes/BP11_CTO_PLAN.md sec. 5). 45/60 = 75%: the budget advisor's
# caution band, so the HALT is a real guard. Joe's ceiling stays 100M; raising this cap is his word. JEV-EDGE and
# JEV-DRIFT run in SHADOW. ARMED ONLY ON JOE'S WORD. Never headless through DC; DC polls the log.
param([string]$Budget = '9turns,60000000tokens')
$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\User\SYNAPSE'
$af   = Join-Path $repo 'harness\battleplan'

foreach ($doc in 'IDENTIFY_BLUEPRINT.md','BP11_CTO_PLAN.md') {
    if (-not (Test-Path (Join-Path $af "notes\$doc"))) { throw "missing source doc notes\$doc - refusing to arm" }
}
if (-not (Test-Path (Join-Path $af 'waves\bp11.rows.json'))) { throw 'waves\bp11.rows.json missing - run compile_wave.py bp11 first' }

$pidFile = Join-Path $repo 'harness\notes\h22\orchestrator-bp11.pid'
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale bp11 orchestrator pid " + $old) }
}

python (Join-Path $af 'build_manifest_bp11.py')
if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }

$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'
$env:SYNAPSE_JEV_EDGE  = 'shadow'
$env:SYNAPSE_JEV_DRIFT = 'shadow'
$manPath = Join-Path $af 'waves\bp11.live.json'
$outLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp11.log'
$errLog  = Join-Path $repo 'harness\notes\h22\orchestrator-bp11.err'
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $repo 'harness\orchestrate.ps1'),'-ManifestPath',$manPath,'-Budget',$Budget -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("bp11 orchestrator armed, pid " + $p.Id + ", budget " + $Budget + " (rails turn = leg dispatch); JEV-EDGE + JEV-DRIFT in shadow")
