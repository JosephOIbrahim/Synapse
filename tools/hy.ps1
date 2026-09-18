<#
  hy.ps1 - pinned hython launcher for headless SYNAPSE development.

  Usage:
      powershell.exe -File tools\hy.ps1 <script.py> [args...]
      $env:HY_TIMEOUT=600; powershell.exe -File tools\hy.ps1 <script.py>

  Why -File and not -Command: -Command mode strips $-variables, which breaks
  every $env: assignment below. This script must always be invoked with -File.

  Pins that matter on this machine:
    * Build 22.0.417 explicitly. Six Houdini builds are installed and bare
      `hython` on PATH resolves to whichever installed last. A build mismatch
      is the apex_probes.py H21-stamp failure class; the stamp is printed on
      every run so a mismatch is visible at the top, not three artifacts later.
    * HOUDINI_USER_PREF_DIR is set explicitly because the OneDrive known-folder
      redirect means the default lookup misses the package dir.
    * Watchdog. run_on_main fast path 2 applies NO timeout by design ("any
      timeout on this path would be a lie"), so a runaway handler under hython
      hangs forever. The only real interrupt is process-level, and this is it.
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$HyArgs
)

$ErrorActionPreference = 'Stop'

$Build    = '22.0.417'
# Cross-build override. The line above stays the DECLARED pin -- the contract's
# freshness check parses it -- so a run under any other build produces an
# artifact whose stamp no longer matches the pin, and freshness fails loudly
# instead of silently overwriting the frozen baseline's evidence.
if ($env:HY_BUILD) { $Build = $env:HY_BUILD }
$Hfs      = "C:\Program Files\Side Effects Software\Houdini $Build"
$Hython   = Join-Path $Hfs 'bin\hython.exe'
$RepoRoot = Split-Path -Parent $PSScriptRoot

$TimeoutSec = 180
if ($env:HY_TIMEOUT) { $TimeoutSec = [int]$env:HY_TIMEOUT }

if (-not (Test-Path $Hython)) {
    Write-Host "[hy] FATAL: hython not found at $Hython"
    exit 2
}
if (-not $HyArgs -or $HyArgs.Count -eq 0) {
    Write-Host "[hy] FATAL: no script supplied."
    exit 2
}

$env:HFS                   = $Hfs
$env:HOUDINI_USER_PREF_DIR = 'C:\Users\User\OneDrive\Documents\houdini22.0'
$env:PYTHONPATH            = "$RepoRoot\python;$RepoRoot\.hython_deps"
$env:SYNAPSE_HEADLESS      = '1'

Write-Host "[hy] build=$Build timeout=${TimeoutSec}s repo=$RepoRoot"
Write-Host "[hy] exec: $($HyArgs -join ' ')"

$proc = Start-Process -FilePath $Hython -ArgumentList $HyArgs -NoNewWindow -PassThru
# Touch .Handle before waiting: without the cached handle the Process object
# returned by Start-Process -PassThru reports an EMPTY ExitCode, which a
# contract would read as success. Do not remove.
$null = $proc.Handle
if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
    Write-Host "[hy] WATCHDOG FIRED: no exit in ${TimeoutSec}s. Killing PID $($proc.Id)."
    try { $proc.Kill() } catch { }
    $null = $proc.WaitForExit(5000)
    exit 124
}
$proc.Refresh()
Write-Host "[hy] exit=$($proc.ExitCode)"
exit $proc.ExitCode
