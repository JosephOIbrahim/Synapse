# ROPE /remote-control beacon
**2026-08-03 14:24:17** | runner: ALIVE | sentinel relaunches used: 0/6

## Gate
```
GATE A: HOLDING -- open: L2-4, L3-2, L3-5, L5-4, L5-10, L5-11
tally: {"verified": 18, "blocked_seat": 1, "blocked_human": 2, "needs_review": 2, "in_progress": 1}
```

## Ledger (last 10)
```
2026-08-03 13:13	L5-5	claude-fable-5	keep	1	128	unavailable	clean
2026-08-03 13:18	L5-6	claude-fable-5	keep	1	287	unavailable	clean
2026-08-03 13:22	L5-4	claude-fable-5	discard	1	274	unavailable	fails: pytest:tests/test_rope_switcher_state.py -q | You've hit your session limit Â· resets 1:40pm (America/New_York)
2026-08-03 13:23	L5-4	claude-fable-5	discard	2	4	unavailable	fails: pytest:tests/test_rope_switcher_state.py -q | You've hit your session limit Â· resets 1:40pm (America/New_York)
2026-08-03 13:23	L1-3	-	revive	0	0	unavailable	orphaned in_progress reset to pending at startup
2026-08-03 13:23	L1-3	claude-fable-5	discard	1	4	unavailable	fails: grep_min:README.md, grep_min:pyproject.toml, grep_min:python/synapse/server/handlers.py | You've hit your session limit Â· resets 1:40pm (America/New_York)
2026-08-03 13:23	L1-3	claude-fable-5	discard	2	4	unavailable	fails: grep_min:README.md, grep_min:pyproject.toml, grep_min:python/synapse/server/handlers.py | You've hit your session limit Â· resets 1:40pm (America/New_York)
2026-08-03 14:08	L1-3	claude-fable-5	keep	1	45	unavailable	clean
2026-08-03 14:17	L5-4	claude-fable-5	keep	1	519	unavailable	manual pending: seat: switch tabs, close panel, reopen -> same tab, history intact
2026-08-03 14:21	L5-10	claude-fable-5	keep	1	282	unavailable	manual pending: copy reviewed against the axiom and L6
```

Refresh this page for updates (~5 min cycle). Read-only: this beacon carries
status OUT; it executes nothing FROM the repo, by design.
