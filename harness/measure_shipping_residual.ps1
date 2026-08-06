# GATE B measurement instrument -- the shipping residual.
#
# suite_baseline.json records shipping_with_deps as 57 failed / 12 errors / 2
# collection errors and explicitly marks it NOT a ratchet floor: it is a first
# measurement, not a green line. You cannot write task cards against failures
# you have not read, so this run captures IDENTITIES, not just counts (-rfE).
#
# Not a fix. Supplying deps to a side directory does nothing for an artist
# installing fresh. Any claim citing this number must say the deps were supplied.
param([string]$HoudiniRoot = "C:\Program Files\Side Effects Software\Houdini 22.0.368")

$ErrorActionPreference = 'Continue'
$py   = Join-Path $HoudiniRoot "bin\hython3.13.exe"
$root = "C:\Users\User\SYNAPSE"
$deps = Join-Path $root ".hython_deps"
$ts   = Get-Date -Format 'yyyyMMdd-HHmmss'
$log  = Join-Path $root "harness\notes\shipping_residual_$ts.log"
$tmp  = Join-Path $env:TEMP "pytest_shipping_$ts"

if (-not (Test-Path $py))   { "NOT FOUND: $py" | Out-File $log; exit 2 }
if (-not (Test-Path $deps)) { "NO DEPS: run harness\supply_shipping_deps.ps1 first" | Out-File $log; exit 2 }

Set-Location $root
# pywin32 does not lay out flat under `pip install --target`: pywintypes.py
# lands in win32\lib\. VERIFIED 2026-08-05 -- supply_shipping_deps.ps1 -Verify
# prints OK for pywintypes with exactly these three entries present. Keep this
# list identical to the one in supply_shipping_deps.ps1 or the instrument
# measures a different environment than the one the supplier built.
$env:PYTHONPATH = "$deps;$deps\win32;$deps\win32\lib;$root\python;$root"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# -rfE is the whole point: f = failed identities, E = errored identities.
# --basetemp is REQUIRED -- without it pytest temp cleanup raises PermissionError
# on pytest-current and EATS THE SUMMARY LINE (harness\supply_shipping_deps.ps1).
#
# Encoding: Tee-Object on PS 5.1 has NO -Encoding parameter and writes UTF-16LE.
# Any downstream Python reader opening this as UTF-8 gets mojibake and silently
# matches nothing -- a log that exists, is the right size, and says nothing. Out-File
# -Encoding utf8 is the fix; the log must be readable by the tools that consume it.
& $py -m pytest -q --continue-on-collection-errors -p no:cacheprovider -rfE --basetemp=$tmp *>&1 |
    Out-File -Encoding utf8 -FilePath $log

"MEASUREMENT COMPLETE: $log" | Out-File -Append $log
Write-Host $log
