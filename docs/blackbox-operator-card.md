# BLACKBOX — Operator's Card

**Crash recovery for Claude Code sessions.** When a chat dies, nothing in flight is lost — the transcript on disk is the flight recorder; these tools read it.

---

## After a crash

New sessions check automatically (SessionStart hook) and print one line if a recent session *appears* to have died mid-work (a tool call orphaned at the very tail of its transcript — deliberate mid-call exits can look the same, so treat it as a prompt to check, not proof). To recover by hand:

```
python scripts/blackbox_recover.py
```

Auto-picks the most recent dead session and writes the full recovery capsule to
`harness/state/recovery/<session>-capsule.md` — orphaned tool calls (your resume
points), killed subagents and their last commands, repo state, Windows forensics.

```
python scripts/blackbox_recover.py --list            # show candidate sessions
python scripts/blackbox_recover.py --session <id>    # pick one explicitly
python scripts/blackbox_mine.py <transcript.jsonl>   # deep-mine any transcript
```

---

## Launching Claude (crash-evidence mode)

```
claude-logged
```

Same as `claude`, but the next silent abort leaves its message in
`%USERPROFILE%\.claude\stderr-crash.log`. Lives at `C:\Users\User\claude-logged.cmd`.
Escalation for a suspicious session: `claude --debug --debug-file C:\Users\User\claude-debug.log`

---

## The three rules that prevent the crash

1. **Long-running work goes detached** — `Start-Process` writing to a file in `.synapse/`, never inline, never in a background agent (agents die with the CLI; detached processes survive and finish).
2. **Retire heavy sessions** — crash pressure grows with session mass and resets to zero in a fresh chat. State lives in memory files + capsules, not the conversation.
3. **Persist memory before long operations** — the crash always lands at the worst moment.

claude.ai connectors are disabled for this project (`.claude/settings.local.json`,
`disableClaudeAiConnectors`) — delete that key if you ever need Gmail/Drive/etc. in a SYNAPSE chat.

---

## When it breaks

- **Hook line never appears after a real crash** → run `python scripts/blackbox_recover.py --detect` by hand; if silent, the dead transcript is >6h old — use `--list` + `--session`.
- **"no transcript older than --grace"** → everything looks live; wait 2 min or pass `--grace 0` from a terminal (not from inside a running session).
- **Capsule missing forensics** → PowerShell queries are best-effort; the in-flight sections are still authoritative.

Tests: `python -m pytest tests/test_blackbox_recover.py -q`
