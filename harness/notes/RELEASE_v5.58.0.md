# v5.58.0 — the night the loops closed honest

Draft release notes. **Draft only — not published, no tag cut.** Publish is
gated on the operator seat (g1/g5/g6/g9 · Ctrl+Z · drop.json · verify), per the
release ritual. Every claim below is receipt-backed on master (HEAD at draft
time; CI green).

Scope: this release is the BP1-wave + hardening span of 2026-08-31, distinct
from v5.57.0 ("the store stops having two owners"), which tags the store-owner
work on its own.

## For artists

**Recall tells the truth or says why.** Memory recall can no longer return a
green, empty result that reads like "nothing to remember." When it can't reach
its substrate it says so and names the gate that failed; when it looked and
matched nothing it says that explicitly; a hit returns the hit. An empty list
wearing a success badge is now impossible.

**The panel is provably the code in the repo, and closing the tab keeps your
session** — both carried forward, both pinned by tests that go red if anyone
regresses them.

## Under the hood

**BP1 wave merged and closed.** Three fix legs (triage, rails, honesty) plus an
adversarial crucible, all SOUND-WITH-NITS, merged zero-conflict, 84/84
post-merge sweep, torn down clean.

**Budget rails are law, not aspiration** (contract ratified). Every harness run
carries a cap in the unit the runtime actually reports, halts hard on breach
with reason=budget (never a silent continue), and prints a spend ledger. Model
choice is a swappable lookup table so a local engine slots in later without a
code change. Proven by a hard-stop halt artifact.

**Recall-honesty is law** (contract ratified). The envelope above, bound to the
loop-orchestrator, same failure class as BASTION B1 killed inside the port.

**The build is pinned to 22.0.400 for the demo span.** A build-ownership probe
reads the running version across three surfaces and fails loud on drift — five
builds share one prefs dir and nothing pinned the default; now something does.

**The launch-path env split is closed.** The package now resolves from the repo
as the single source of truth, so the GUI and headless lanes no longer diverge;
a fresh headless run passes env, plugin, layer, and recall end to end.

**A probe false-negative and a CI gate both corrected honestly.** The Gate-0
G4 predicate now reads the claim id where it actually lives (inside the payload
content), and four JSONL probe receipts were wrapped as valid single-object
JSON to satisfy the S8 parse gate — without weakening the gate, which keeps its
negative-control proof.

## Honest state — ritual walked 2026-08-31 evening

Operator seat gates, all PASS by Joe's hands at the 22.0.400 rig: g1 clean
install · g5 lifecycle (build receipt 22.0.400 on three surfaces) · g6 core smoke
· Ctrl+Z reversibility (one undo reversed a multi-part build; the standing
W5-UNDO-GUI receipt is discharged) · g9 rollback (no segfault this walk).
drop.json written from live .400 values. Version surfaces CONFORM at 5.58.0.
CI green on the tagged head. R.R verify, Mode B: suite 6,833 passed / 0 failed,
ratchet holds, guardrail violations empty, and G3 host truth reads green for the
first time — a field-name mismatch between the drop schema and the checker had
kept it red through every prior release; corrected in this span.

**Still RED, carried unchanged from v5.56.0:** the release-readiness review's
four standing blockers — `mutation_fail_closed`, `hot_reload_gated`,
`installer_host_targeted`, `ci_covers_shipping_surface`. Named debt, not hidden
debt: v5.56.0 published over the same four. Publishing this release over them is
a per-act decision of Joe's, recorded here if taken; either way they head the
hardening backlog.

The one demo-critical thing still UNMEASURED is cross-session recall (close →
reopen → remember) — the red-tier demo-round-trip contract, GUI, on camera. That
is the Tuesday branch predicate, not part of this tag.

The tag is cut at publish, by Joe's word.
