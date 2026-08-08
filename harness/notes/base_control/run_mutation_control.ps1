# BASE mutation control - Law 1: every check must be able to fail, prove it can.
#
# run_control.ps1 returning 0 means nothing on its own. A check that passes
# against BOTH the fixed dispatcher and the broken one is a decoration, and this
# repo has shipped four of those in a single day.
#
# So: take the CURRENT orchestrate.ps1, knock out one passthrough at a time in a
# COPY under TEMP, and re-run the identical control against the copy. The
# knocked-out cells must go red. If they stay green, the control is not measuring
# the passthrough and its green verdict is worthless.
#
# The real orchestrate.ps1 is never written to - only read.
#
# Exit code = number of mutants the control failed to catch. 0 = control is live.

param(
    [string]$Orch    = (Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSCommandPath))) 'orchestrate.ps1'),
    [string]$Control = (Join-Path (Split-Path -Parent $PSCommandPath) 'run_control.ps1'),
    [int]$RunSeconds = 15
)

$ErrorActionPreference = 'Continue'
$survivors = 0

# name, the line prefix to knock out, the pre-fix line to put back
$mutants = @(
    @{ name = 'base-passthrough-removed'
       match = '^\s*\$base = '
       with  = "    `$base = 'HEAD'"
       note  = 'reverts to the hardcoded HEAD every leg was cut from' },
    @{ name = 'model-passthrough-removed'
       match = '^\s*\$modelArg = '
       with  = "    `$modelArg = ''"
       note  = 'reverts to no --model flag, leg inherits the terminal default' }
)

Write-Host ""
Write-Host "BASE MUTATION CONTROL"
Write-Host "  subject : $Orch"
Write-Host "  control : $Control"

foreach ($m in $mutants) {
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host "MUTANT  $($m.name)  -  $($m.note)"
    Write-Host ("=" * 78)

    $lines = Get-Content $Orch
    $hits = 0
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $m.match) { $lines[$i] = $m.with; $hits++ }
    }
    if ($hits -ne 1) {
        Write-Host "  ABORT - expected exactly 1 line matching $($m.match), found $hits"
        Write-Host "          the mutation control cannot vouch for a control it did not apply."
        $survivors++
        continue
    }

    $mut = Join-Path $env:TEMP "orchestrate_mutant_$($m.name).ps1"
    Set-Content -Path $mut -Value $lines -Encoding utf8

    $t = $null; $e = $null
    [System.Management.Automation.Language.Parser]::ParseFile($mut, [ref]$t, [ref]$e) | Out-Null
    if ($e -and $e.Count) {
        Write-Host "  ABORT - mutant does not parse ($($e.Count) errors); a syntax break is not a control"
        $survivors++
        continue
    }

    & $Control -Orch $mut -RunSeconds $RunSeconds | ForEach-Object { Write-Host "    $_" }
    $code = $LASTEXITCODE

    if ($code -gt 0) {
        Write-Host "  CAUGHT  control returned $code failed cell(s) against this mutant"
    } else {
        Write-Host "  SURVIVED  control returned 0 against a knocked-out passthrough - THE CONTROL IS BLIND"
        $survivors++
    }
    Remove-Item $mut -Force -EA SilentlyContinue
}

Write-Host ""
Write-Host ("MUTATION RESULT  {0} surviving mutant(s)" -f $survivors)
exit $survivors
