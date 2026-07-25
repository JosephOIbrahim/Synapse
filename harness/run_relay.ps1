$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\User\SYNAPSE'

$ts  = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = "C:\Users\User\SYNAPSE\harness\notes\relay_run_$ts.log"

Write-Host ''
Write-Host '  SYNAPSE - CTO RELAY 01' -ForegroundColor Cyan
Write-Host '  six legs / receipt-driven / one ruling block' -ForegroundColor DarkGray
Write-Host "  log: $log" -ForegroundColor DarkGray
Write-Host ''

git checkout -B feat/cto-relay-01 2>&1 | Write-Host

$prompt = @'
Read harness/SYNAPSE_CTO_RELAY.md and execute it end to end. You are ORCHESTRATOR.

Dispatch the EXISTING specialists in .claude/agents/ per the leg-to-agent binding in section 2 - do not invent new agent roles. Spawn one agent per Task subagent, never nested. You hold receipts only; you do not read source yourself.

Write every leg receipt to harness/notes/receipts/L*.json per the receipt/v1 schema in section 3.

Standing orders, non-negotiable:
- Commandment 7: test count strictly increases or holds. Fix forward. Never weaken, skip, xfail or delete a test to make a leg green.
- Probes beat memory: confirm every hou.* symbol by live dir() against 22.0.368 before writing code against it.
- Never push, never merge, never open a PR. That is GATE C and it belongs to Joe.
- Do not decide T.4. It is frozen.
- Do not ask Joe anything until section 5. Batch every decision into the single ruling block.

Work on branch feat/cto-relay-01. Begin at Leg 0.
'@

claude --settings harness/relay-settings.json --permission-mode acceptEdits --verbose $prompt 2>&1 | Tee-Object -FilePath $log

Write-Host ''
Write-Host '  RELAY TERMINATED - receipts in harness/notes/receipts/' -ForegroundColor Cyan
Write-Host ''
