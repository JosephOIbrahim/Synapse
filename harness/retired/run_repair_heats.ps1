$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\User\SYNAPSE'
$ts  = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = "harness\notes\repair_run_$ts.log"

Write-Host ''
Write-Host '  SYNAPSE - REPAIR HEATS 01' -ForegroundColor Cyan
Write-Host '  qualifier blocks / three heats in parallel / one final' -ForegroundColor DarkGray
Write-Host ''

git checkout -B feat/repair-heats-01 master 2>&1 | Write-Host

$prompt = @'
Read harness/AGENT_CONSTITUTION.md first - it binds you. Then read harness/SYNAPSE_REPAIR_HEATS.md and execute it end to end. You are ORCHESTRATOR.

Dispatch the EXISTING specialists in .claude/agents/ per section 2. Do not invent roles. One agent per Task subagent, never nested. You hold receipts only and do not read source yourself.

STRUCTURE - this is a DAG, not a chain:
- Q1 and Q2 are BLOCKING. No heat starts until both receipts are green.
- Then read Q2's shipping number and take the section-4 branch it dictates. Record which branch you took and why in the F1 receipt. Do not run the heats blind.
- H1, H2, H3 run in SEPARATE git worktrees off master. Cherry-pick AGENT_CONSTITUTION.md and CTO_RULINGS_01.md onto each at creation (R38).

NON-NEGOTIABLE, each one paid for by a defect found today:
- Positive control before acting on any finding. A probe that cannot demonstrate success against a known-good target produces an uninterpretable failure. Reproduce before you repair.
- Mutation testing on every regression pin: break the implementation deliberately and confirm the pin FAILS. A pin that survives its own mutation is a decoration - report it, do not quietly fix it.
- State every check's failure condition before writing it (Law 1).
- Every number carries a producer path AND an interpreter (Law 2, R31).
- status describes what happened, never what was attempted (Law 3).
- Commandment 7: test count strictly increases or holds. Fix forward.
- Receipts record model and settings_profile (R25).
- Probes beat memory: confirm every hou.* symbol by live dir() on 22.0.368 first.
- Never push, never merge to master, never tag. Gate C is Joe's.

Q1 FORBIDDEN FIXES: reordering tests, -p no:randomly, skipping panel tests, or adding PySide to the dev environment. Each hides the coupling instead of removing it.

Write receipts to harness/notes/receipts/ (Q1, Q2, H1, H2, H3, F1, F2). Batch every decision into for_ruling[]. Do not ask Joe anything until F2. Begin at Q1.
'@

claude --settings C:\Users\User\SYNAPSE\harness\relay-settings.json --permission-mode acceptEdits --verbose $prompt 2>&1 | Tee-Object -FilePath $log

Write-Host ''
Write-Host '  REPAIR HEATS TERMINATED - receipts in harness/notes/receipts/' -ForegroundColor Cyan
