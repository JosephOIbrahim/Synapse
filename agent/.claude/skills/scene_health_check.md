# Skill: Scene Health Check

## When to Use
When the artist asks for a diagnostic, or when starting work on an unfamiliar scene.

## Steps
1. Inspect full scene graph at max_depth=3
2. Check for: nodes with errors, nodes with warnings, unconnected inputs,
   deprecated node types, bypass flags that might be accidental
3. Report findings in priority order:
   - Errors (blocking)
   - Warnings (may affect output)
   - Suggestions (optimization)
4. Offer to fix issues that have clear solutions

## Report Format
Keep it scannable:
- Lead with the headline: "Scene looks healthy" or "Found 3 issues to look at"
- Group by severity
- Each issue: what, where, suggested fix
