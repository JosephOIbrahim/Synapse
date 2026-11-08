# Create the RETINA worker venv, CPU profile, from retina/requirements.txt
# (Windows twin of setup_venv.py). The venv is NEVER committed (retina/.venv is
# .gitignored); this script + the pinned requirements are the reproducible
# recipe. Network pip install is expected.
#
# Worker runtime (owner ruling R4, 2026-11-07; ADR-0002): CPython 3.12.10 with
# the isolated cp312 win_amd64 OpenImageIO wheel. The seed must be CPython 3.12.
# The script refuses a hython seed (by file name, before anything runs it) and
# any interpreter that is not CPython 3.12, exits 2 and creates nothing. R4
# names 3.12.10; another 3.12 micro version seeds with a warning. An existing
# retina/.venv that is not a 3.12 venv is refused too: re-run with -Recreate.
#
#   pwsh retina/setup_venv.ps1 -Python <CPython 3.12 python.exe>
#   pwsh retina/setup_venv.ps1        # seeds from "python" on PATH if it is 3.12
#
# CPU profile only: it installs the stock opencv-python-headless wheel and only
# ever writes retina/.venv. The GPU worker profile is separate
# (harness/vision/gpu_worker_env/): its cv2 is the custom OpenCV 5.1 CUDA build,
# so it never installs any opencv-python* package.

[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $here ".venv"
$reqs = Join-Path $here "requirements.txt"

# A native command does not throw on a non-zero exit, so every step below checks
# $LASTEXITCODE, and every stop writes to stderr and exits with its own code
# (2 = refused under R4, 1 = a step failed).
function Stop-Setup([string]$Message, [int]$Code = 2) {
    [Console]::Error.WriteLine("ERROR: $Message")
    exit $Code
}

# R4: never run hython, not even to probe it.
if ((Split-Path -Leaf $Python) -like "hython*") {
    Stop-Setup "refusing seed ${Python}: R4 rules out a hython-seeded worker venv; seed from a CPython 3.12 interpreter"
}

try {
    $probe = & $Python -I -c "import sys; print(sys.implementation.name, *sys.version_info[:3])"
}
catch {
    Stop-Setup "could not run seed ${Python}: $($_.Exception.Message)"
}
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "could not probe seed ${Python} (exit $LASTEXITCODE)"
}
$parts = "$probe".Trim() -split "\s+"
if ($parts.Count -lt 4) {
    Stop-Setup "unexpected probe output from ${Python}: $probe"
}
$impl = $parts[0]
$ver = "$($parts[1]).$($parts[2]).$($parts[3])"
if ($impl -ne "cpython" -or $parts[1] -ne "3" -or $parts[2] -ne "12") {
    Stop-Setup "refusing seed $Python ($impl $ver): R4 rules the worker runtime to CPython 3.12.10; seed from a CPython 3.12 interpreter"
}
if ($ver -ne "3.12.10") {
    Write-Warning "R4 names CPython 3.12.10; seeding from $ver."
}

if ($Recreate -and (Test-Path $venv)) {
    Remove-Item -Recurse -Force $venv
}

if (Test-Path $venv) {
    $have = $null
    $cfg = Join-Path $venv "pyvenv.cfg"
    if (Test-Path $cfg) {
        $line = Get-Content $cfg | Where-Object { $_ -match '^\s*version(_info)?\s*=' } | Select-Object -First 1
        if ($line) { $have = ($line -split "=", 2)[1].Trim() }
    }
    if (-not $have -or -not $have.StartsWith("3.12.")) {
        Stop-Setup "existing $venv is not a CPython 3.12 venv (pyvenv.cfg version: $have); re-run with -Recreate"
    }
}
else {
    Write-Host "Creating venv at $venv (seed: $Python, CPython $ver)"
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup "venv creation failed (exit $LASTEXITCODE)" 1
    }
}

$vpy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $vpy)) {
    Stop-Setup "venv python not found at $vpy" 1
}

& $vpy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Stop-Setup "pip self-upgrade failed (exit $LASTEXITCODE)" 1
}
& $vpy -m pip install -r $reqs
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine(@"
pip install failed (exit $LASTEXITCODE; see pip's output above). If the failing
requirement is the OpenCV 5.0.0.93 pin, the sanctioned fallback (blueprint
sections 3 and 8) is:
    opencv-python-headless>=4.13,<5
Edit retina/requirements.txt and re-run.
"@)
    exit 1
}

Write-Host ""
Write-Host "RETINA worker venv ready: $vpy"
Write-Host "Run the pixel tests:"
Write-Host "    $vpy -m pytest tests/test_retina_t1.py tests/test_retina_ingest.py"
