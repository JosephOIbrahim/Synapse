# REPAIR-HEATS-01 follow-on dispatch. Two legs, disjoint, parallel worktrees.
#   A - H3a  cancel-path probe        (R44: probe runs now, implementation held)
#   B - RES  fake-hou residency       (R42/R43: unblocks H2, heads its scope)
$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\User\SYNAPSE'

$base = git rev-parse HEAD
Write-Host ""
Write-Host "  REPAIR follow-on  base $base" -ForegroundColor Cyan
Write-Host ""

$legs = @(
  @{ id='h3a'; branch='repair/h3a-cancel-probe'; wt='.claude/worktrees/h3a-cancel-probe'
     prompt=@'
Read harness/AGENT_CONSTITUTION.md first - it binds you. Then read harness/SYNAPSE_REPAIR_HEATS.md and harness/notes/CTO_RULINGS_01.md rulings R44 and R46. You are ORCHESTRATOR for H3a.

H3 was SPLIT by ruling R44. You are the PROBE half only. H3b (implementation) remains HELD and you must not begin it.

SCOPE - read-only live confirmation, nothing else:
Confirm by live dir()/hasattr against Houdini 22.0.368 every symbol a cook-cancel path would need. At minimum: tops_cancel_cook or its real equivalent, the PDG graph cancelCook(), render-ROP interrupt/abort, and whatever hdefereval marshal the UI thread would use. Dispatch assayer for every symbol - assayer answers only "does this exist", never "should we use it".

R46 is binding: prior-session evidence about the render chokepoint and the hdefereval marshal is UNVERIFIED in this run. Re-probe or do not use. No design work proceeds on recall.

IF SYMBOLS ARE ABSENT on 22.0.368, that absence IS the deliverable. Write it up as a SideFX ask. Do NOT invent a workaround, do not substitute an assumed API for a refuted one - that is how a decay clock becomes a phantom.

Write harness/notes/receipts/H3a.json (receipt/v1, include model and settings_profile per R25). Every symbol gets CONFIRMED / ABSENT / UNVERIFIABLE with a file:line or dir() anchor. No implementation, no source edits outside harness/notes/. Never push, never merge, never tag.
'@ },
  @{ id='res'; branch='repair/fake-hou-residency'; wt='.claude/worktrees/fake-hou-residency'
     prompt=@'
Read harness/AGENT_CONSTITUTION.md first - it binds you. Then read harness/notes/CTO_RULINGS_01.md rulings R41, R42 and R43. You are ORCHESTRATOR for the fake-hou residency leg. This leg is the release condition for H2 - H2 cannot start until it lands.

THE DEFECT, verified 2026-07-26 (R41):
python/synapse/mcp/tool_impls/solaris/component_builder.py:315 raises
  AttributeError: 'Parm' object has no attribute 'set'
under hython3.13 against REAL Houdini. Same at scene_template.py:218.

POSITIVE CONTROL, already established - do not re-derive:
  hython3.13 -c "import hou; print(hou.Parm.set)"  ->  exists, 22.0.368,
  module .../houdini/python3.13libs/hou.py
hou.Parm.set EXISTS. Therefore a STUB Parm is shadowing the real class. This is Q1's defect class - fake-hou residency - surviving in a different module. tests/solaris/test_live_wiring.py believes it drives live Houdini and does not.

WORK:
1. Find what installs the stub hou/Parm and when. Import-time sys.modules planting is the prime suspect (Q1's mechanism), but PROVE it rather than assuming - Q1's real diagnosis was restore-by-object vs restore-by-reimport, which looks identical and is not.
2. Eliminate the residency on the Solaris test path. Q1's pattern in tests/test_hda_panel.py:160-204 is the reference: capture the ORIGINAL module OBJECTS, restore those exact objects. Restore-by-reimport is NOT equivalent.
3. Then the ~17 tests in Q2 bucket 2 (R43) - same mechanism, same fix.
4. Every regression pin must FAIL against a deliberately broken implementation (R34 mutation standard). A pin that survives its own mutation is a decoration - report it, do not quietly fix it.

ORACLE: the AttributeError disappears under hython3.13; tests/solaris/test_live_wiring.py drives real hou; gate suite holds at 4881+ with 0 failed; Commandment 7 - count strictly increases or holds.

Write harness/notes/receipts/RES.json (receipt/v1, model + settings_profile per R25). Never push, never merge, never tag.
'@ }
)

foreach ($leg in $legs) {
  Write-Host "  --- $($leg.id) ---" -ForegroundColor DarkGray
  git worktree add -b $leg.branch $leg.wt $base 2>&1 | Select-Object -Last 1 | Write-Host

  # A fresh worktree is UNTRUSTED. Claude Code blocks on the trust dialog before
  # its first token - silent, indefinite, and indistinguishable from slow work
  # unless you check CPU. Cost us 13 minutes on 2026-07-26. Trust before launch.
  python C:\Users\User\SYNAPSE\harness\trust_worktrees.py 2>&1 | Select-Object -Last 1 | Write-Host

  $script = Join-Path $env:TEMP "run_$($leg.id).ps1"
  @"
Set-Location '$((Resolve-Path $leg.wt).Path)'
Write-Host ''
Write-Host '  LEG $($leg.id.ToUpper())  branch $($leg.branch)' -ForegroundColor Cyan
Write-Host ''
`$p = @'
$($leg.prompt)
'@
claude --settings C:\Users\User\SYNAPSE\harness\relay-settings.json --permission-mode acceptEdits --verbose `$p
Write-Host ''
Write-Host '  LEG $($leg.id.ToUpper()) TERMINATED' -ForegroundColor Cyan
"@ | Set-Content $script -Encoding utf8
  Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File',$script -WindowStyle Normal
  Start-Sleep -Seconds 4
}

Write-Host ""
Write-Host "  both legs dispatched" -ForegroundColor Cyan
