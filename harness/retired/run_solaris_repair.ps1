$ErrorActionPreference = 'Continue'
$wt = 'C:\Users\User\SYNAPSE\.claude\worktrees\solaris-repair'
Set-Location $wt

Write-Host ''
Write-Host '  SOLARIS REPAIR 01  (parallel team)' -ForegroundColor Cyan
Write-Host '  worktree: .claude/worktrees/solaris-repair   branch: feat/solaris-repair-01' -ForegroundColor DarkGray
Write-Host ''

git add harness/BATON_SOLARIS_REPAIR.md 2>&1 | Out-Null
git commit -q -m "docs(baton): SOLARIS REPAIR 01 - rulings 12-16, roots before symptoms" 2>&1 | Out-Null

$prompt = @'
Read harness/AGENT_CONSTITUTION.md first - it binds you. Then read harness/BATON_SOLARIS_REPAIR.md and execute it end to end. You are ORCHESTRATOR for the Solaris repair team.

Dispatch the existing specialists in .claude/agents/ - do not invent roles. Suggested: assayer for every live hou.* confirmation, h22-forge for implementation, seam-hunter to certify composition, crucible for the final adversarial pass. One agent per Task subagent, never nested. Load skills per Article V of the constitution.

Supporting evidence, all anchored: harness/notes/l2_wiring_findings.md (F1-F11) and harness/notes/CTO_RULINGS_01.md (Rulings 12-16, decided - execute, do not re-open).

Non-negotiable:
- Constitution Law 1: every check must be able to fail. Mock-hou tests are banned for host-behaviour assertions. A skip is honest, a pass is a lie.
- Constitution Law 3: status describes what happened, never what was attempted.
- Commandment 7: test count strictly increases or holds. Fix forward.
- Probes beat memory: confirm every hou.* symbol by live dir() on 22.0.368 before writing against it.
- Never push, never merge, never open a PR. Gate C belongs to Joe.
- Roots before symptoms: M1, M2, M3 land before any defect repair in M4.

You are running in parallel with CTO-RELAY-01 on another branch. Stay in this worktree.

Write harness/notes/receipts/SR1.json when done. Do not ask Joe anything until then. Begin at M1.
'@

claude --settings C:\Users\User\SYNAPSE\harness\relay-settings.json --permission-mode acceptEdits --verbose $prompt

Write-Host ''
Write-Host '  SOLARIS REPAIR TERMINATED' -ForegroundColor Cyan
