# Debug Windows Environment Issue

Parallel diagnostic workflow for permanent environment fixes on Windows 11.

## Context

- OS: Windows 11 Pro for Workstations
- Primary terminal: Git Bash
- Elevated commands: PowerShell
- Prefer PowerShell for environment variables (setx), registry, and admin privileges
- Git Bash has escaping issues with setx and UAC interactions

## Workflow

Execute these phases — do NOT skip ahead:

### Phase 1: Diagnose
- Run `where <tool>` and `Get-Command <tool>` (PowerShell) to find all instances of the target binary
- Check for Windows App Execution Aliases (zero-byte stubs in WindowsApps/)
- Inspect PATH ordering
- Identify the exact root cause
- Report findings before proceeding

### Phase 2: Fix
- Write a PowerShell script (.ps1) that:
  - Fixes the root cause
  - Includes error handling for UAC/elevation failures with automatic retry
  - Handles Git Bash vs PowerShell escaping differences explicitly
- Save the script to disk for repeatability
- Execute with appropriate elevation

### Phase 3: Verify
- Open a NEW shell subprocess and verify the issue is resolved
- Check BOTH PowerShell and Git Bash contexts
- If verification fails, loop back to Phase 2 with the new error
- Do NOT consider resolved until Phase 3 passes in both shells

## Arguments

The user should describe the issue after invoking this skill:
- `/debug-env The claude CLI shows "not recognized" even though it's installed`
