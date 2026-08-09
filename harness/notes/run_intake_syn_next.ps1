# Direct intake — SYN-NEXT-001 adjudication on Opus 4.8 (Option 1 per orient session, Joe-authorized dispatch)
Set-Location 'C:\Users\User\SYNAPSE'
$prompt = 'Workflow({ name: "h22-intake", args: { artifact: "docs/SYNAPSE_NEXT_SYSTEM_BLUEPRINT.md", slug: "syn-next-001" } })'
claude -p $prompt --model claude-opus-4-8 --verbose 2>&1 |
  Tee-Object -FilePath 'C:\Users\User\SYNAPSE\harness\notes\intake_syn-next-001.log'
