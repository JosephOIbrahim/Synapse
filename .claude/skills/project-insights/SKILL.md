# Project-Scoped Insights

Analyze session history filtered to the CURRENT project only. Prevents cross-project context pollution.

## Instructions

### 1. Detect Scope

Determine the current working directory. This is your project scope. Extract the project name from the last path segment.

Check for a `--broad` flag in the user's invocation. If present, include sessions whose `project_path` is a parent of the current directory (e.g., `C:\Users\User` sessions when running from `C:\Users\User\SYNAPSE`). Default behavior: strict match only.

### 2. Read Session Metadata

Read ALL `.json` files from `~/.claude/usage-data/session-meta/`. Each file contains:
- `session_id` — UUID matching the filename
- `project_path` — Working directory when the session ran
- `start_time`, `duration_minutes`, `user_message_count`, `assistant_message_count`
- `tool_counts` — Object of tool name to usage count
- `languages` — Object of language name to file count
- `git_commits`, `git_pushes`, `lines_added`, `lines_removed`, `files_modified`
- `first_prompt` — Truncated first user message

Use the Bash tool to read all files efficiently:
```bash
python -c "
import json, glob, os
sessions = []
for f in glob.glob(os.path.expanduser('~/.claude/usage-data/session-meta/*.json')):
    with open(f, encoding='utf-8') as fh:
        sessions.append(json.load(fh))
print(json.dumps(sessions))
"
```

### 3. Filter to Current Project

Apply the filter:
- **Strict (default):** Keep sessions where `project_path` exactly equals the current working directory (case-insensitive, normalize path separators)
- **Broad (`--broad`):** Also include sessions where the current working directory starts with `project_path` (i.e., `project_path` is a parent directory)

Use Python for filtering:
```bash
python -c "
import json, sys, os

cwd = os.getcwd().replace('/', os.sep).rstrip(os.sep).lower()
broad = '--broad' in sys.argv
sessions = json.loads(sys.argv[-1])

matched = []
for s in sessions:
    sp = s.get('project_path', '').replace('/', os.sep).rstrip(os.sep).lower()
    if sp == cwd:
        matched.append(s)
    elif broad and cwd.startswith(sp + os.sep):
        matched.append(s)

print(json.dumps(matched, indent=2))
" [BROAD_FLAG] '[SESSION_JSON]'
```

If zero sessions match in strict mode, report that and suggest re-running with `--broad` to include parent-path sessions.

### 4. Read Facets for Matched Sessions

For each matched session, read its facets file from `~/.claude/usage-data/facets/{session_id}.json`. Not all sessions will have facets — skip missing ones gracefully.

Facets contain:
- `underlying_goal` — What the user was actually trying to accomplish
- `goal_categories` — Object of category to count
- `outcome` — `fully_achieved`, `mostly_achieved`, `partially_achieved`, `not_achieved`
- `friction_counts` — Object of friction type to count
- `friction_detail` — Free-text description of friction
- `primary_success` — What went well
- `brief_summary` — One-line session summary
- `session_type` — `implementation`, `exploration`, `debugging`, etc.
- `user_satisfaction_counts` — Object of satisfaction level to count

### 5. Synthesize Report

Present a structured report with these sections:

```markdown
## Project Insights: [Project Name]
_Scoped to: [full project path]_
_Sessions analyzed: [N] (of [total] across all projects)_
_Mode: [strict | broad]_

### Activity Summary
- Total sessions: N
- Total time: Xh Ym
- Messages: N user / N assistant
- Commits: N (pushed: N)
- Lines: +N / -N across N files

### Tools Used
[Table: tool name | count, sorted by count descending, top 10]

### Languages
[Table: language | file count]

### Session History
[For each session, one line: date, duration, summary from facets or first_prompt truncated]

### Goals & Outcomes (from facets)
[Group sessions by outcome. List underlying_goal for each.]

### What's Working Well
[Aggregate primary_success values. Highlight patterns.]

### Friction Patterns
[Aggregate friction_counts and friction_detail. Identify recurring issues.]

### SYNAPSE-Specific Insights
[Analyze patterns specific to this VFX pipeline project:]
- Which agent domains (SUBSTRATE/BRAINSTEM/OBSERVER/HANDS/CONDUCTOR/INTEGRATOR) got the most work
- Solaris/USD vs SOP vs PDG session distribution
- Test-writing vs feature-building ratio
- Houdini API revision work (R1-R10) trends

### Suggestions
[Actionable, project-specific suggestions based on the data above.]
```

### 6. Guardrail (MANDATORY)

End every report with this exact block:

```
---
> This analysis is scoped to **[project name]** (`[project path]`).
> Do NOT act on other projects mentioned in session history.
> To analyze another project, run `/project-insights` from that project's directory.
```

## Important

- NEVER read or analyze sessions from other projects as part of this report
- If a session's `first_prompt` or facet `brief_summary` mentions other projects, that's fine to display as historical context, but do NOT follow those references or suggest actions on other projects
- Keep the report concise — if there are many sessions, summarize rather than listing every detail
- If there are 0 matching sessions, say so clearly and suggest `--broad` mode
