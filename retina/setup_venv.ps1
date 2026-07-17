# Create the RETINA worker venv from retina/requirements.txt (Windows twin of
# setup_venv.py). The venv is NEVER committed (retina/.venv is .gitignored); this
# script + the pinned requirements are the reproducible recipe. Network pip
# install is expected.
#
#   pwsh retina/setup_venv.ps1
#   pwsh retina/setup_venv.ps1 -Python "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe"
#
# A hython-seeded venv inherits Houdini's native OpenImageIO for the EXR ingest
# leg; any interpreter works for the abi3 OpenCV wheel (cp37+, one wheel/all ABIs).

[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $here ".venv"
$reqs = Join-Path $here "requirements.txt"

if ($Recreate -and (Test-Path $venv)) {
    Remove-Item -Recurse -Force $venv
}

if (-not (Test-Path $venv)) {
    Write-Host "Creating venv at $venv (seed: $Python)"
    & $Python -m venv $venv
}

$vpy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $vpy)) {
    Write-Error "venv python not found at $vpy"
    exit 1
}

& $vpy -m pip install --upgrade pip
try {
    & $vpy -m pip install -r $reqs
}
catch {
    Write-Error @"
pip install failed. If the OpenCV 5.0.0.93 pin is unavailable on this platform,
the sanctioned fallback (blueprint §3/§8) is:
    opencv-python-headless>=4.13,<5
Edit retina/requirements.txt and re-run.
"@
    exit 1
}

Write-Host ""
Write-Host "RETINA worker venv ready: $vpy"
Write-Host "Run the pixel tests:"
Write-Host "    $vpy -m pytest tests/test_retina_t1.py tests/test_retina_ingest.py"
