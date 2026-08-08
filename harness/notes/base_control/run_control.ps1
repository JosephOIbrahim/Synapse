# BASE control - producer for harness/notes/base_control/EVIDENCE.md
#
# Exercises the two dispatch passthroughs added to harness/orchestrate.ps1:
#   per-leg  "base"  -> the ref the worktree is cut from
#   manifest "model" -> the --model flag on the claude launch
#
# TWO INDEPENDENT CONTROLS, because a dry run alone proves only that a string
# was PRINTED:
#
#   PART 1  git semantics.  Runs the changed call shape for real against a
#           throwaway repo and reads the resulting HEADs. Proves the argument
#           actually moves the cut, that the absent-base default is unchanged,
#           and that refuse-if-branch-exists still refuses WITH a base present.
#   PART 2  orchestrator dry run.  -DryRun -ManifestPath over two throwaway
#           manifests x two legs = the four cells the brief names.
#
# ISOLATION IS NOT OPTIONAL.  Backup-Branches runs on every poll of the main
# loop and is NOT guarded by -DryRun: it pushes every non-master worktree branch
# it can find. Pointed at the real repo, a "dry" run would push to origin. So
# the control passes -Repo <scratch>, a one-branch repo named master OUTSIDE the
# SYNAPSE tree, where that function has nothing to push and nothing to find.
#
# Exit code = number of failed cells. 0 = all cells passed.

param(
    [string]$Orch = (Join-Path (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSCommandPath))) 'orchestrate.ps1'),
    [int]$RunSeconds = 15
)

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $PSCommandPath
$root = Join-Path $env:TEMP 'base_control'
$repo = Join-Path $root 'repo'

$script:fails = 0
function Check([string]$name, [bool]$ok, [string]$detail) {
    if ($ok) { Write-Host ("  PASS  {0,-34} {1}" -f $name, $detail) }
    else     { $script:fails++; Write-Host ("  FAIL  {0,-34} {1}" -f $name, $detail) }
}

Write-Host ""
Write-Host "BASE CONTROL"
Write-Host "  orchestrator : $Orch"
Write-Host "  scratch repo : $repo"
Write-Host ""

# --- scratch repo ------------------------------------------------------------
if (Test-Path $root) {
    Get-ChildItem $root -Recurse -Force -EA SilentlyContinue |
        ForEach-Object { $_.Attributes = 'Normal' }
    Remove-Item $root -Recurse -Force -EA SilentlyContinue
}
New-Item -ItemType Directory -Force -Path (Join-Path $repo 'harness\notes') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root 'wt') | Out-Null

git -C $repo init -q                                  2>&1 | Out-Null
git -C $repo symbolic-ref HEAD refs/heads/master      2>&1 | Out-Null
Set-Content (Join-Path $repo 'seed.txt') 'A'
git -C $repo add -A                                   2>&1 | Out-Null
git -C $repo -c user.email=c@c -c user.name=control commit -q -m 'A' 2>&1 | Out-Null
$shaA = (git -C $repo rev-parse HEAD).Trim()

# a second ref, distinct from master, standing in for "another leg's branch"
git -C $repo checkout -q -b blocks/m5-reconciler      2>&1 | Out-Null
Set-Content (Join-Path $repo 'seed.txt') 'B'
git -C $repo add -A                                   2>&1 | Out-Null
git -C $repo -c user.email=c@c -c user.name=control commit -q -m 'B' 2>&1 | Out-Null
$shaB = (git -C $repo rev-parse HEAD).Trim()
git -C $repo checkout -q master                       2>&1 | Out-Null

Write-Host "PART 1  git semantics of the changed call"
Write-Host "  master               = $shaA"
Write-Host "  blocks/m5-reconciler = $shaB"
Check 'refs are distinct' ($shaA -ne $shaB) "$($shaA.Substring(0,8)) vs $($shaB.Substring(0,8))"

# cell 1 - base honoured
$wt1 = Join-Path $root 'wt\from-base'
git -C $repo worktree add -b control/from-base $wt1 blocks/m5-reconciler 2>&1 | Out-Null
$got1 = (git -C $wt1 rev-parse HEAD 2>$null)
if ($got1) { $got1 = $got1.Trim() }
Check 'base honoured' ($got1 -eq $shaB) "worktree HEAD $got1 (want $shaB)"

# cell 2 - no base -> HEAD, the previous behaviour, unchanged
$wt2 = Join-Path $root 'wt\from-head'
git -C $repo worktree add -b control/from-head $wt2 HEAD 2>&1 | Out-Null
$got2 = (git -C $wt2 rev-parse HEAD 2>$null)
if ($got2) { $got2 = $got2.Trim() }
Check 'absent base -> HEAD unchanged' ($got2 -eq $shaA) "worktree HEAD $got2 (want $shaA)"

# cell 3 - refuse-if-branch-exists still refuses, WITH a base argument present.
# This is the guard the orchestrator relies on at :296 and the brief requires it
# to stay exactly. It fails if the add succeeds or leaves a directory behind.
$wt3 = Join-Path $root 'wt\dup-branch'
$dupOut = & git -C $repo worktree add -b control/from-base $wt3 blocks/m5-reconciler 2>&1
$dupCode = $LASTEXITCODE
Check 'existing branch still refused' (($dupCode -ne 0) -and (-not (Test-Path $wt3))) "exit $dupCode, directory left behind: $(Test-Path $wt3)"
Write-Host "        git said: $($dupOut -join ' / ')"

# cells 4/5 - the production EXPRESSION, verbatim, not a literal-argument
# lookalike. Cells 1-3 proved git's CLI semantics; these prove PowerShell splices
# a leg object's fields into that call the way orchestrate.ps1:295 writes it.
# The real path has no -C: it relies on the Set-Location at :21, so this mirrors
# that with Push-Location rather than quietly using a different call shape.
foreach ($case in @(
        @{ label = 'spliced, base declared'; leg = [pscustomobject]@{ branch = 'control/spliced-base'; base = 'blocks/m5-reconciler' }; want = $shaB },
        @{ label = 'spliced, no base field'; leg = [pscustomobject]@{ branch = 'control/spliced-head' };                              want = $shaA })) {
    $leg  = $case.leg
    $wt   = Join-Path $root ("wt\" + ($leg.branch -replace '.*/', ''))
    $base = if ($leg.base) { $leg.base } else { 'HEAD' }      # orchestrate.ps1:220
    Push-Location $repo
    $addOut  = & git worktree add -b $leg.branch $wt $base 2>&1   # orchestrate.ps1:295
    $addCode = $LASTEXITCODE
    Pop-Location
    $got = (git -C $wt rev-parse HEAD 2>$null)
    if ($got) { $got = $got.Trim() }
    Check $case.label (($addCode -eq 0) -and ($got -eq $case.want)) "exit $addCode, HEAD $got (want $($case.want))"
}
Write-Host ""

# --- PART 2  orchestrator dry run -------------------------------------------
function Invoke-DryRun([string]$label, [string]$manifest) {
    $notes = Join-Path $repo 'harness\notes'
    Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
    $p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Orch,
        '-DryRun', '-Quiet',
        '-Repo', $repo,
        '-ManifestPath', $manifest,
        '-PollSeconds', '300', '-IdlePollSeconds', '300',
        '-DigestMinutes', '999', '-MaxHours', '1')
    Start-Sleep -Seconds $RunSeconds
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 1
    $lg = Get-ChildItem $notes -Filter 'orchestrator_*.log' -EA SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $lg) { return @() }
    Copy-Item $lg.FullName (Join-Path $here "raw_$label.log") -Force
    return (Get-Content $lg.FullName)
}

function Resolved([string[]]$lines, [string]$legId, [string]$kind) {
    # the DISPATCH line names the leg; the two resolved lines follow it
    $out = ''
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "DISPATCH $legId ") {
            for ($j = $i + 1; $j -lt [Math]::Min($i + 5, $lines.Count); $j++) {
                if ($lines[$j] -match "\(dry run\) $kind") { $out = $lines[$j]; break }
            }
            break
        }
    }
    return $out
}

Write-Host "PART 2  orchestrator -DryRun -ManifestPath, four cells"
$cells = @()
foreach ($m in @(
        @{ label = 'model';   file = (Join-Path $here 'manifest_model.json');   hasModel = $true },
        @{ label = 'nomodel'; file = (Join-Path $here 'manifest_nomodel.json'); hasModel = $false })) {

    $lines = Invoke-DryRun $m.label $m.file
    Check "log produced ($($m.label))" ($lines.Count -gt 0) "$($lines.Count) lines"

    foreach ($leg in @(
            @{ id = 'CTRLA'; wantBase = 'blocks/m5-reconciler' },
            @{ id = 'CTRLB'; wantBase = 'HEAD' })) {

        $w = Resolved $lines $leg.id 'worktree'
        $l = Resolved $lines $leg.id 'launch'
        $cells += [pscustomobject]@{ manifest = $m.label; leg = $leg.id; worktree = $w; launch = $l }

        Check "$($m.label)/$($leg.id) base = $($leg.wantBase)" ($w -match ([regex]::Escape($leg.wantBase)) + '\s*$') $w
        if ($m.hasModel) {
            Check "$($m.label)/$($leg.id) --model emitted" ($l -match '--model claude-opus-4-8') $l
        } else {
            Check "$($m.label)/$($leg.id) --model absent"  ($l -notmatch '--model') $l
        }
    }

    # the trap: top-level "base" is display-only. If per-leg resolution ever
    # fell through to it, this nonsense string would surface in a resolved line.
    $leak = @($lines | Where-Object { $_ -match 'dry run' -and $_ -match 'control/never-read' })
    Check "$($m.label) no manifest-base leak" ($leak.Count -eq 0) "$($leak.Count) leaked lines"
}

Write-Host ""
Write-Host "THE FOUR RESOLVED LINES"
foreach ($c in $cells) {
    Write-Host ("  [{0}/{1}]" -f $c.manifest, $c.leg)
    Write-Host ("     {0}" -f $c.worktree.Trim())
    Write-Host ("     {0}" -f $c.launch.Trim())
}

$cells | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $here 'resolved_lines.json') -Encoding utf8

Write-Host ""
Write-Host ("RESULT  {0} failed cell(s)" -f $script:fails)
exit $script:fails
