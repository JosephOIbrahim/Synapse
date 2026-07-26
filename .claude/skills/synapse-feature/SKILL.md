# Implement SYNAPSE Feature

Autonomous multi-file feature development with architectural validation.

## Critical Rules

1. **NEVER** edit files under `~/.synapse/houdini/` (deployed copies) — ALL edits must go to the repo source at `SYNAPSE/houdini/`.
2. After every file edit, verify: the edited file is in the correct repo directory, all imports resolve, and the change is consistent with He2025 conventions.
3. Before marking complete, run a final validation that greps for any accidental edits to deployed paths.

## Workflow

1. Read the existing architecture in the relevant source directories
2. Propose a file-by-file implementation plan — do NOT begin editing until the user approves the plan
3. Implement each file change, validating after each edit
4. Run tests: `python -m pytest tests/ -v`
5. Final validation: confirm no deployed-path edits, all imports resolve, He2025 compliance (sort_keys=True on all json.dumps)
6. Report what changed and remind user to redeploy if Houdini integration files were modified

## Arguments

The user should describe the feature after invoking this skill:
- `/synapse-feature Add a new button to the panel that does X`
