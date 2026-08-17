# W5-WXC — crucible shard C audit: divergence history, mandates, version reconcile

**Leg:** W5-WXC (band TRUTH, read-only probe). **Branch:** `wave5/wxc`.
**Method:** first-hand side-tree git/tool runs from this worktree; nothing inherited.
**Under audit:** `wave5/measures` @ tip `520a10d4`; CTO ruling
`harness/notes/h22/CTO-RULING-measures-divergence-2026-08-16.md`.

All commit shas, file:line anchors, and tool verdicts below were produced by my own
runs. Where a figure could only come from the leg's own claim (e.g. the full 6479-test
suite), it is labelled **leg-claim** and held UNKNOWN-to-me, never restated as measured.

---

## Target 1 — Divergence arc verdict

**Verdict: ruling points 1–2 STAND; points 3–4 DISCHARGED by `520a10d4` (and *not* laundered).**

### Point 1 — "The audit work is KEEP" → STANDS
The six audit/metrics-honesty commits are all present on `wave5/measures`
(`git merge-base --is-ancestor <c> wave5/measures`):

| commit | subject |
|---|---|
| `5320da97` | notes(measures): unmeasured-as-measured audit — 5 confirmed in 2 seams, 0 critical |
| `9bd298c4` | fix(panel): unmeasured Bug B (consumer) — hero gauge UNKNOWN, not red 0% |
| `e544534b` | notes(measures): Bug B producer ticket — consumer shipped, producer ready-to-apply |
| `eeebca16` | fix(measures): Bug A — shed metrics cycle marks UNKNOWN, not fabricated fps=24/0 |
| `a1e3fa03` | fix(measures): Bug A siblings — Routing/Resilience mark UNKNOWN |
| `d44b750f` | notes(measures): audit R2 — Bug A + siblings shipped, verify pass tally 7 confirmed |

The audit body is real and banked. (Full-suite green = **leg-claim** `6479p/1f`; I did not
re-run the whole suite. The one failure the leg names is F-VER, not the audit — see Target 3.)

### Point 2 — "Layer-6 / metrics-honesty attribution, not the cook-verify charter" → STANDS
`wave5/measures:harness/notes/h22/AUDIT-2026-08-16-unmeasured.md:23-28`:
*"Every confirmed finding is the same shape as the Layer-6 `synapse_doctor` `fidelity=0.0`
bug … Layer 6's fix note ended with an un-run to-do — audit every other probe …"*.
The branch's **own** framing attributes the work to Layer-6 lineage. Correct attribution,
not goalpost-moving.

### Points 3–4 — "UNMET → stays OPEN / no receipt-merge-flip by orchestrator" → DISCHARGED by `520a10d4`
The ruling described the state at the **first** agent's death (audit delivered, charter
unbuilt, DIVERGED-OPEN). It was superseded by events: the leg was re-dispatched (20:32) and
the **second** agent built the charter. Verified first-hand:

- Charter contracts commit `31de38b8` ("5 output kinds + explosion detector + goldens"),
  hardened by `6f8a158a` (+6 FP2 holes) and `a6db2286` (OC2 ordering).
- Charter **acceptance artifacts exist** on the branch (`git cat-file -e/-s wave5/measures:<f>`):
  `python/synapse/validation/measures.py` (12294 b), `python/synapse/validation/explosion.py`
  (7930 b), `rulebook/goldens/sim/healthy_sim.json` (843 b), `.../exploding_sim.json` (959 b),
  `rulebook/goldens/README.md` (2007 b), `tests/test_measures_contracts.py` (11073 b).
- Receipt `harness/notes/receipts/W5-MEASURES.json` self-reports **A1 PASS, A2 PASS,
  A3 PARTIAL-EXTENDS** (MCP registry disclosure deferred, S1) — the honest PARTIAL is why
  this is **not** a laundered green: the receipt names its own gap rather than fabricating a PASS.

**Not-laundered basis:** my verdict rests on artifact existence I checked myself, not on the
receipt's self-claims. The supersession note (ruling L67-77) is an ACCURATE record of the
divergence-then-recovery arc.

---

## Target 2 — MEASURES mandate table inputs (binary)

| Input | Answer | Anchor |
|---|---|---|
| receipt-is-closing-commit (receipt == tip?) | **YES** | tip `520a10d4` touches **only** `harness/notes/receipts/W5-MEASURES.json` (96 insertions); `git rev-parse wave5/measures` == `520a10d4` |
| bus RELEASE present? | **YES** | `harness/autorevise/bus/wave5/bus.jsonl` — `frm W5-MEASURES` `status@2026-08-16T23:36:34` with `body.release`=[7 files], `RELEASE:true`, `receipt_head:520a10d4`, `product_head:a6db2286`; `has_release(wave5,W5-MEASURES)`=True |
| one-writer on `panel/health_infographic.py` (commit `9bd298c4`) | **NOT a two-writer collision** — see below | git log/diff anchors below |

### one-writer attribution of `9bd298c4`
- File **introduced** by `a8a2627b` ("close RSI Line O") and **hardened** by `fb1a30b9`
  (PySide6 enum scoping) — both **ON master** (`git merge-base --is-ancestor … master` → true).
  = shared ancestry, not divergent work.
- `wave5/panel` (the W5-PANEL owner) has **zero** divergent edits to it:
  `git diff --stat master...wave5/panel -- python/synapse/panel/health_infographic.py` = empty.
- `9bd298c4` is the **sole** commit making the branch copy differ from master
  (`git log master..wave5/measures -- …` → one line; `18 +/3 −`), contained **only** on
  `wave5/measures` (`git branch --contains` → wave5/measures + origin).

**Attribution:** `9bd298c4` = the **MEASURES leg / Layer-6 audit lineage** (subject: "unmeasured
Bug B (consumer) — hero gauge UNKNOWN, not red 0%"). It **is** a crossing of MEASURES
crucible-criterion 3 ("no overlap with W5-PANEL's `python/synapse/panel/`"), and it **is**
prior-audit (Layer-6 Bug-B-consumer) work — both true. It is **not** a merge collision, because
no competing divergent writer of that file exists. Disposition is CTO's (tracked by the leg as
**F-PANEL** in its own RELEASE); flagged honestly, not hidden.

---

## Target 3 — F-VER reconcile plan (concrete, one merge-train step)

**State (first-hand):** `master:VERSION`=`5.51.0`, `wave5/measures:VERSION`=`5.50.0`, tag
`v5.51.0` exists (`0545881b`). On the branch **all six** version surfaces read 5.50.0 and are
mutually consistent (`git show wave5/measures:<surface>`): VERSION, pyproject `version="5.50.0"`,
`__version__="5.50.0"`, docstring `Version: 5.50.0`, CLAUDE.md `SYNAPSE v5.50.0`, README
`v5.50.0 · Houdini`. The branch is **stale-but-internally-consistent**; the *only* drift is
tree-vs-published-tag.

**The failing test** (the leg's "1f"): `tests/test_phase0c_doc1_version_conformance.py:184`
`test_no_published_tag_outruns_the_canonical_version` asserts `not (newest_tag > canonical)`.
On the branch: `(5,51,0) > (5,50,0)` → assertion False → **FAIL**. This is a repo-global tag
comparison, so it fires on the branch tree but passes on master.

**The six surfaces (5 files)** — canonical map `scripts/sync_version.py:41-53`:
`VERSION` · `pyproject.toml` · `python/synapse/__init__.py` (**×2**: `__version__` + docstring
`Version:`) · `CLAUDE.md` (`SYNAPSE vX.Y.Z`) · `README.md` (`<sub>vX.Y.Z · Houdini`).

**Which files a merge must reconcile: NONE require manual reconciliation.**
- merge-base(master, wave5/measures) = `df8c9ef3`.
- master bumped **all five** version files (`03ced883`, master-only since base):
  `git diff --stat df8c9ef3..master -- <5 files>` = 5 files changed.
- wave5/measures touched **zero** of them: `git diff --stat df8c9ef3..wave5/measures -- <5 files>`
  = empty.
- => a standard 3-way merge (either direction) auto-resolves every version surface to master's
  **5.51.0**, no conflict markers, because only one side changed those lines.

**Does `sync_version.py --write` post-merge suffice? YES, but it is REDUNDANT (a no-op here).**
`sync_version.py` treats root VERSION as **canonical and propagates outward**; it never reads
git tags (`:41-53`, `:100-120`). Post-merge the tree is already fully at 5.51.0 (master's side
won), so `--check` passes with zero writes and the failing test self-heals
(canonical 5.51.0 == tag v5.51.0). `--write` would find nothing to propagate.

**One merge-train step:**
1. Merge `wave5/measures` → master (clean on all version files).
2. `python scripts/sync_version.py --check` → expect `verdict=PASS` (no-op).
3. `pytest tests/test_phase0c_doc1_version_conformance.py -q` → expect 11 passed.

**First-hand tool proof (on master tree, this session):** `sync_version.py --check` → all six
CONFORM, `verdict=PASS`, exit 0; conformance test → **11 passed**.

---

## What I did NOT measure (honesty ledger)
- Full 6479-test suite on the branch tree — **not re-run** (disproportionate, out of charter);
  the branch's suite-green is **leg-claim**, held UNKNOWN-to-me. What I *did* run: the version
  conformance slice (11 green on master) + `sync_version --check` (PASS on master).
- Live hython golden cook of the MEASURES charter — `gui_required`, **UNKNOWN headless**
  (matches MEASURES crucible-criterion 2). Not obtainable from this side-tree; recorded UNKNOWN.
