# Freeze-relief live verification — the F1 + F5a probe gates in one entry point.
#
# Usage (PowerShell, from anywhere):
#   & C:\Users\User\SYNAPSE\scripts\live_verify_freeze.ps1
#
# What it does:
#   1. F5a render-offload probe — runs headless under hython Houdini 22.0.400.
#      Settles the contested husk/Indie evidence via the --indie matrix.
#   2. F1 update-mode sandwich probe — GUI-only by design, so this script
#      prints the exact exec() line to paste into the Houdini 22.0.400
#      Python shell with a scene open.
#   3. Captures all output to harness\notes\preflight_logs\freeze_verify_<date>.log
#
# Exit code: 0 if the F5a probe completed (its own PASS/FAIL/UNKNOWN lines
# are the verdicts to read). F1 verdicts appear in the GUI shell output.

$ErrorActionPreference = 'Stop'

$repo   = 'C:\Users\User\SYNAPSE'
$hy22   = 'C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe'
$logDir = Join-Path $repo 'harness\notes\preflight_logs'
$stamp  = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$log    = Join-Path $logDir "freeze_verify_$stamp.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

"freeze-relief live verification  $stamp" | Tee-Object -FilePath $log

if (-not (Test-Path $hy22)) {
    "FATAL: hython not found at $hy22" | Tee-Object -FilePath $log -Append
    exit 1
}

"`n==[ F5a — render offload probe (hython 22.0.400) ]==" |
    Tee-Object -FilePath $log -Append
& $hy22 (Join-Path $repo 'harness\notes\probe_render_offload.py') 2>&1 |
    Tee-Object -FilePath $log -Append

"`n==[ F1 — update-mode sandwich probe (GUI-only) ]==" |
    Tee-Object -FilePath $log -Append
@"
F1 needs a Houdini 22.0.400 GUI session. In its Python shell (Windows >
Python Shell), with any scene open, run ONE line:

    exec(open(r"$repo\harness\notes\probe_update_mode_sandwich.py", encoding="utf-8").read())

Read the PASS/FAIL/SKIP lines it prints. PASS on all four = the sandwich is
cleared to lose its dev-flag. FAIL on (b), (c) or (d) = F1 descopes per spec.
"@ | Tee-Object -FilePath $log -Append

"`nLog: $log" | Tee-Object -FilePath $log -Append
exit 0
