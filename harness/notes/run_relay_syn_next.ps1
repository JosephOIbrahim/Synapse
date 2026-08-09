# Relay launcher — SYN-NEXT-001 intake drive on Opus 4.8 (dispatched 2026-08-08, Joe-authorized)
Set-Location 'C:\Users\User\SYNAPSE'
$prompt = 'Workflow({ name: "h22-relay", args: { intakeArtifact: "docs/SYNAPSE_NEXT_SYSTEM_BLUEPRINT.md", intakeSlug: "syn-next-001" } })'
claude -p $prompt --model claude-opus-4-8 --verbose 2>&1 |
  Tee-Object -FilePath 'C:\Users\User\SYNAPSE\harness\notes\relay_syn-next-001.log'
