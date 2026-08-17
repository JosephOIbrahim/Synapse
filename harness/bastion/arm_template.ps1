# arm_template.ps1 - BASTION harness v2 arm TEMPLATE. RUN ONLY ON JOE'S EXPLICIT
# ARM WORD. Parametrised skeleton for any BASTION exec wave (B1..B7). FORK of the
# arm/orchestrate pattern in harness/autorevise/arm_w8.ps1 + rearm_morning.ps1
# (traced 2026-08-17, W8-SMITH), carrying every runner survival rule to source:
#
#   SURVIVAL RULES CARRIED (each traced, none from memory):
#   1. hold-turn clause .............. in the leg brief (prompts/_template.md +
#      the "Hold the turn" section); source CARD_cache-advisor.md:66-67.
#   2. CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 (LANDMINE 2, 600s ceiling kills
#      teams) ......................... arm_w8.ps1:21, CARD_cache-advisor.md:65.
#   3. CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (AGENT_TEAMS env) ... arm_w8.ps1:20.
#   4. detached Start-Process + pid capture ...... arm_w8.ps1:25-26;
#      runner form orchestrate.ps1:493,504.
#   5. debom discipline ............... quote_safe.py / quote-safe.ps1
#      (Write-Utf8NoBom); pid files written -Encoding ascii as the originals do.
#
#   v2 DELTAS (W8-SMITH target 4):
#   * STEWARD ARM/REFRESH folded in: this template (re)launches the bastion
#     steward with a fresh deadline PAST THE WAVE HORIZON, so steward liveness is
#     a property of arming, not a separate manual act (PROGRAM.md /rc doctrine).
#   * /rc BAKE-IN SLOT: $RcBakeIn below. Headless (-p) legs have no window and are
#     unreachable by the steward's SendKeys, so /rc must be baked into their
#     prompt. Its content is the /rc EXPANSION, which is UNKNOWN (W8-SMITH task 1
#     verdict - never guessed). The slot ships as a NAMED UNKNOWN sentinel; while
#     it holds that sentinel the template WARNS that headless legs run without /rc
#     coverage (windowed-or-steward-covered only), exactly per PROGRAM.md.
param(
    [Parameter(Mandatory = $true)][string]$Wave,             # e.g. 'wave9'
    [Parameter(Mandatory = $true)][string]$ManifestPath,     # legs/v1 live manifest
    [string]$ManifestBuilder = '',                           # optional python builder to run first
    [double]$StewardDeadlineHours = 12,                      # past the wave horizon
    [string]$RepoRoot = 'C:\Users\User\SYNAPSE',
    # /rc BAKE-IN SLOT (fills from W8-SMITH task 1 resolution). UNKNOWN today.
    [string]$RcBakeIn = '<<UNKNOWN: /rc expansion unresolved - W8-SMITH task 1; see harness/bastion/HARNESS_V2.md>>'
)
$ErrorActionPreference = 'Stop'
$bastion = Join-Path $RepoRoot 'harness\bastion'
$notes   = Join-Path $RepoRoot 'harness\notes\h22'

# --- kill a previously-armed orchestrator for this wave if its pid file is live
$pidFile = Join-Path $notes ("orchestrator-" + $Wave + ".pid")
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$old" -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale orchestrator pid " + $old) }
}

# --- optional manifest build (a builder script writes $ManifestPath)
if ($ManifestBuilder) {
    python $ManifestBuilder
    if ($LASTEXITCODE -ne 0) { throw 'manifest build failed' }
}
if (-not (Test-Path $ManifestPath)) { throw "manifest not found: $ManifestPath" }

# --- survival rules 2+3: env set BEFORE launch, inherited by orchestrate + legs
$env:CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1'   # AGENT_TEAMS  (arm_w8.ps1:20)
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'   # LANDMINE 2   (arm_w8.ps1:21)

# --- survival rule 4: detached Start-Process + pid capture (arm_w8.ps1:25-26)
$outLog = Join-Path $notes ("orchestrator-" + $Wave + ".log")
$errLog = Join-Path $notes ("orchestrator-" + $Wave + ".err")
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $RepoRoot 'harness\orchestrate.ps1'),'-ManifestPath',$ManifestPath -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$p.Id | Out-File $pidFile -Encoding ascii
Write-Host ("$Wave orchestrator armed, pid " + $p.Id)

# --- v2: STEWARD ARM/REFRESH (deadline past the wave horizon). Kill stale, relaunch.
$stewardPid = Join-Path $notes ("steward-" + $Wave + ".pid")
if (Test-Path $stewardPid) {
    $olds = Get-Content $stewardPid
    $sp = Get-CimInstance Win32_Process -Filter "ProcessId=$olds" -ErrorAction SilentlyContinue
    if ($sp) { Stop-Process -Id $olds -Force -ErrorAction SilentlyContinue; Write-Host ("killed stale steward pid " + $olds) }
}
$s = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $bastion 'steward.ps1'),'-DeadlineHours',$StewardDeadlineHours,'-LegLog',$outLog -WindowStyle Hidden -PassThru
$s.Id | Out-File $stewardPid -Encoding ascii
Write-Host ("$Wave steward armed (deadline +" + $StewardDeadlineHours + "h), pid " + $s.Id)

# --- /rc BAKE-IN SLOT status (target 4). Named UNKNOWN until task 1 resolves.
if ($RcBakeIn -like '*UNKNOWN*') {
    Write-Host ("WARN: /rc bake-in UNRESOLVED (W8-SMITH task 1). Headless (-p) legs run WITHOUT /rc coverage; windowed legs are steward-covered. UNKNOWN stays named - not guessed.") -ForegroundColor Yellow
} else {
    Write-Host ("/rc bake-in present; headless legs will carry it.") -ForegroundColor DarkGray
}
