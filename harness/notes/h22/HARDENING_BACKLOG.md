# HARDENING BACKLOG — deferred items, not-this-week

Opened 2026-08-31 EOD. Items that are real but off the demo path. One card;
append here, do not multiply. Each line: what · why it matters · candidate fix.

## From BP1 wave (2026-08-31)
- **Six BP1 nits** (R-N1/H-N1/T-N2/T-N3/W-N1/W-N2) · noted at merge, none
  blocking · address when touching each leg's surface.
- **Unguarded Backup-Branches push in orchestrate.ps1** · a wave-teardown side
  effect pushes without a gate · fold into the teardown verb below.
- **Scripted wave-teardown verb** · twice on 2026-08-31 "clean" was declared
  before verified at operator scale (shell echo; terminal sweep) — same
  green-light family at session-driver scale · candidate:
  harness/battleplan/teardown_wave.ps1 doing shells + agent PIDs + terminal
  windows as one act. harness/notes/h22/_proc_sweep.ps1 is a starting organ.

## From tonight's CI + release check (2026-08-31 EOD-2)
- **Stale RELEASE-DRAFT-vNEXT.md** · still carries v5.51.0-era text while the
  live gh draft is v5.57.0 "the store stops having two owners" · rewrite to
  current scope when v5.57.0 is walked, or delete if the gh draft is the single
  source. Not a blocker (gh draft carries its own notes).
- **CRLF→LF on every commit** · every JSON/text commit tonight warned
  "CRLF will be replaced by LF" · add a `.gitattributes` with `* text=auto` (and
  explicit `*.json text eol=lf`) to normalize line endings repo-wide and silence
  the churn · one small commit, this week.

## Standing (pre-tonight, carried)
- **JSONL probe receipts vs .json extension** · RESOLVED tonight for the four
  BP1 receipts (wrapped as single-object JSON). FUTURE probe runs still emit
  JSONL — if a new receipt lands committed as .json it will trip the S8 gate
  again. Durable fix: either the probe writer wraps-on-final-write, or committed
  receipts standardize on a records[] envelope. Watch for recurrence.
