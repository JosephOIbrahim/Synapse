# SYNAPSE harness — Windows runner (PowerShell control plane)
#
# The harness is a plain Python CLI, not a Claude Code session. It SPAWNS headless
# `claude -p` as its one sequential worker. This wrapper just guards the billing footgun
# and passes your args through.
#
#   .\synapse.ps1 init quarantine-dead-tree
#   .\synapse.ps1 queue add quarantine-dead-tree failure-trail theme-seed-tokens docking-minimums
#   .\synapse.ps1 run --autonomy amber --budget 12
#   .\synapse.ps1 run --autonomy green --dry-run
#   .\synapse.ps1 status

$ErrorActionPreference = "Stop"

# Billing footgun: a stray ANTHROPIC_API_KEY overrides your Max plan and bills API from
# token 1. SYNAPSE keeps its key under SYNAPSE_ANTHROPIC_KEY; ANTHROPIC_API_KEY must be
# UNSET for the worker so it draws the subscription / Agent SDK credit.
if ($env:ANTHROPIC_API_KEY) {
    Write-Host "WARNING: ANTHROPIC_API_KEY is set — this would bill pay-as-you-go API." -ForegroundColor Yellow
    Write-Host "Clearing it for THIS process only (your shell env is untouched)." -ForegroundColor Yellow
    $env:ANTHROPIC_API_KEY = $null
}
if (-not $env:SYNAPSE_ANTHROPIC_KEY) {
    Write-Host "Note: SYNAPSE_ANTHROPIC_KEY not set. Interactive `claude` uses your login;" -ForegroundColor DarkGray
    Write-Host "headless `claude -p` needs auth available to the CLI." -ForegroundColor DarkGray
}

# Prefer the Windows launcher, fall back to python on PATH.
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }

& $py ".synapse/harness.py" @args
exit $LASTEXITCODE
