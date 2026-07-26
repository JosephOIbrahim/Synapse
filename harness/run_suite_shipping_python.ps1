# RULING 1a - run the suite on the interpreter that SHIPS.
# The default `python` on this box is 3.14.x, where the cp311/cp313 vendored wheels
# do not match and synapse._VENDOR_ABI_RISK is True - the vendor tree is INACTIVE.
# Every green run on 3.14 therefore tested pip-installed pydantic/anthropic, not the
# artifact artists receive. This runs against Houdini's own python313.
param([string]$HoudiniRoot = "C:\Program Files\Side Effects Software\Houdini 22.0.368")

$py = Join-Path $HoudiniRoot "bin\hython3.13.exe"
if (-not (Test-Path $py)) { Write-Host "NOT FOUND: $py" -ForegroundColor Red; exit 2 }

Set-Location 'C:\Users\User\SYNAPSE'
$ts  = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = "harness\notes\suite_hou313_$ts.log"

Write-Host ""
Write-Host "  SUITE ON THE SHIPPING INTERPRETER" -ForegroundColor Cyan
& $py --version
& $py -c "import sys; sys.path.insert(0,'python'); import synapse; print('  VENDOR_ABI_RISK:', synapse._VENDOR_ABI_RISK)"
Write-Host "  log: $log" -ForegroundColor DarkGray
Write-Host ""

$env:PYTHONPATH = "C:\Users\User\SYNAPSE\python;C:\Users\User\SYNAPSE"

# Q2-F2: this line previously carried
#   --ignore=tests/test_load.py --ignore=tests/test_passthrough_hygiene.py
#   --ignore=tests/test_port_wave_scene1.py
# which are exactly the three files that fail to COLLECT on the shipping interpreter.
# The runner was authored around the breakage rather than recording it - Law 3 at the
# harness level, an instrument reporting what it attempted rather than what happened.
# It is why a shipping number never surfaced: the instrument was built not to see the
# fault. The ignores are removed. Collection errors are the measurement, not noise.
& $py -m pytest -q --continue-on-collection-errors 2>&1 | Tee-Object -FilePath $log | Select-Object -Last 30

Write-Host ""
Write-Host "  full log: $log" -ForegroundColor DarkGray
