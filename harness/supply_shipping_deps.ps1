# Supply the shipping interpreter's missing dependencies into a SIDE directory.
#
# R47: six packages account for 88% of the shipping suite's failures and 98% of
# its errors. websockets, mcp, pytest-asyncio, orjson, xxhash and filelock are
# shipping dependencies that are NOT shipped - demonstrated, not argued.
#
# THIS IS A MEASUREMENT INSTRUMENT, NOT A FIX. It makes the shipping suite
# measurable on this machine. It does nothing for an artist installing fresh.
# No release claim may cite a number produced with it unless the number says so.
#
# Houdini's own site-packages is never touched. Reverted by deleting .hython_deps.
param([switch]$Verify)

$hy   = "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython3.13.exe"
$deps = "C:\Users\User\SYNAPSE\.hython_deps"
$pkgs = @('websockets','mcp','pytest-asyncio','orjson','xxhash','filelock')

if (-not (Test-Path $hy)) { Write-Host "hython3.13 not found: $hy" -ForegroundColor Red; exit 2 }

if (-not $Verify) {
    New-Item -ItemType Directory -Force -Path $deps | Out-Null
    Write-Host "installing $($pkgs.Count) packages to $deps" -ForegroundColor Cyan
    & $hy -m pip install --target $deps --quiet --disable-pip-version-check @pkgs 2>&1 |
        Select-String -Pattern 'Successfully|ERROR' | Select-Object -Last 3
}

$env:PYTHONPATH = "$deps;" + $env:PYTHONPATH
Write-Host ""
Write-Host "resolution under hython3.13:" -ForegroundColor Cyan
& $hy -c @"
import importlib
for m in ['websockets','mcp','pytest_asyncio','orjson','xxhash','filelock']:
    try:
        importlib.import_module(m); print('  OK   ' + m)
    except Exception as e:
        print('  FAIL ' + m + '  ' + type(e).__name__)
"@ 2>&1 | Select-String 'OK|FAIL'

Write-Host ""
Write-Host "to measure with these present:" -ForegroundColor DarkGray
Write-Host '  $env:PYTHONPATH = "C:\Users\User\SYNAPSE\.hython_deps;" + $env:PYTHONPATH' -ForegroundColor DarkGray
Write-Host '  hython3.13 -m pytest -q --continue-on-collection-errors --basetemp=<fresh-dir>' -ForegroundColor DarkGray
Write-Host ""
Write-Host "  --basetemp is REQUIRED: without it pytest's temp cleanup raises" -ForegroundColor DarkGray
Write-Host "  PermissionError on pytest-current and EATS THE SUMMARY LINE." -ForegroundColor DarkGray
