# W6-HCRX — Hardening Crucible Verdict

**Leg:** W6-HCRX (band TRUTH) · **Branch:** `wave6/hcrx` · **Status:** `green_with_findings`
**Date:** 2026-08-16 · **Model:** Opus 4.8
**Mandate:** attack the four new W6 gates — metachar names, bypass attempts, behaviour regressions.
**Deps re-attacked (nothing inherited):** W6-QUOTE · W6-PROV · W6-BEAT · W6-GATE. Attack list: W6-FORGE `HARDENING-SPEC.md`.

> House rule (SPEC.md): CRUX before merge; the attack list is the FORGE ledger. **Merge remains Joe's word per leg.**

**One-line verdict:** every gate **fails closed on its target defect** and all 108 builder acceptances re-pass on a
cleanly-composed combined tree with the ratchet held (+67, 0 regressions) — but adversarial re-attack (this leg
plus an independent completeness pass, each finding **verified first-hand**) surfaced **one confirmed false-green
per gate** in the gates' *stated* scope, plus two sibling legs not yet closed per the mandate. Real, net-positive
defences with cheaply-closable coverage gaps. `green_with_findings`.

---

## 0 · Method — combined scratch-tree staging (target 6)

The four products live on separate unmerged branches. I reconstructed a **single combined scratch tree** from
their committed bytes and attacked *that* — "isolated-green hides composed regressions."

- Base = `git archive master` (`8e278b65`). Single-editor product files overlaid via `git show <branch>:<path>`.
- **Two shared files, two editors each,** 3-way merged with `git merge-file` (no refs, no merge commit):
  `harness/orchestrate.ps1` (QUOTE runner **+** GATE close-state) and `harness/verify/checks.py`
  (PROV `check_provenance_not_bypassed` **+** BEAT `check_runtime_owns_heartbeat`) — **both merge exit 0, zero
  conflict markers.**
- `checks.py` imports clean (DISPATCH = 85 checks, both new gates present); `bus.py` imports clean.

**Finding-0 (compose-clean):** the four products compose with **zero conflict** on the two shared files — the
builders' region-split coordination held. This is the substrate for every attack below. (A live M19 merge-time-
coupling case, resolved.) Product commits: QUOTE `b29ecb0a`, PROV `a342e2fc`, BEAT `3b26ab0a`, GATE `ee04ea33`,
FORGE ledger `57f23a5c`.

---

## 1 · Acceptance re-execution — nothing inherited (target 1)

Every builder acceptance re-run first-hand on the combined tree:

| Test file | leg | result |
|---|---|---|
| `tests/test_provenance_gate.py` | PROV | **11 passed** |
| `tests/test_r_track.py` (R-track + BEAT legs) | BEAT | **44 passed** |
| `tests/test_w6_beat_runtime_heartbeat.py` (behavioural, run for real) | BEAT | **6 passed** |
| `tests/test_orchestrate_close_gate.py` | GATE | **6 passed** |
| `tests/test_harness_quoting.py` (real PowerShell dry-run matrix) | QUOTE | **41 passed** |
| **TOTAL** | | **108 / 108 passed** |

Every acceptance was measurable headless → **no UNKNOWNs required, none laundered.**

---

## 2 · QUOTE attack (S1/S8) — my own adversarial name set (target 2)

**17 fresh inputs the builder's set did not pick** — here-string terminator (`\n"@`), `-ForegroundColor` breakout,
`$(...)` subexpr, 5- and 6-apostrophe runs, empty name, CRLF, 2000-char apostrophe-laden brief (the `943e5375`
truncation class), `@'evil'@`, metachar id and branch — driven through the **real `orchestrate.ps1 -DryRun`**.
Per runner I checked: PS Language Parser error count, BOM, and **AST `CommandAst` enumeration** (only
`Set-Location`/`Write-Host`/`claude` allowed; any extra command = a payload reached a code position).

**Content result: 17/17 parse-clean, BOM-free, ZERO injected commands.** Apostrophe-doubling is provably complete
for the single-quoted context (single-quoted PS literals absorb newlines and `"@`/`$`/backtick literally). The one
flag (`crlf-name`) was a `\r`-round-trip artifact in my own substring check (`b''c` present, 0 `Remove-Item`,
parse-clean) — not a defense hole.

**QUOTE verdict: PASS on content.** See **F-QUOTE** below — the gate's *stated* id coverage is broken on the
filesystem-path surface.

---

## 3 · PROV attack (S2) — fresh bypass, must fail closed (target 3)

Against the **real** product surface (`handlers.py` + `floor_gate.py` + whole `server/`):

| attack | expect | got |
|---|---|---|
| baseline (clean real surface) | GREEN | **GREEN** |
| **A** — FloorGate **constructed but `wrap()` bypassed** in `invoke()` (an M1 "built-connected-to-nothing" shape) | RED | **RED** ✓ |
| **A2** — real `floor_gate.py` `write_report` persist removed | RED | **RED** ✓ |
| **B1** — two-line get-and-call `h = self._registry.get(cmd)` / `return h(payload)` | RED | **GREEN — hollow spot** |
| **B2** — dict-dispatch `self._handlers[cmd].handle(payload)` in a non-`handle()` method | RED | **GREEN — hollow spot** |

Target 3 satisfied: my fresh bypass **A** (a shape the builder never fixtured) **fails closed**, as does A2.
B1/B2 are static-idiom evasions of leg-3 (honest-open). See **F-PROV** for a sharper, confirmed false-green.

**PROV verdict: PASS (fail-closed on fresh bypass)** + coverage gaps (F-PROV, B1/B2).

---

## 4 · BEAT attack (S3) — the behavioural pin must go RED (target 4)

Run first-hand with the **real** `_beat_behaviour_proof` (not stubbed):

| attack | expect | got |
|---|---|---|
| baseline (combined tree, real behavioural proof) | GREEN | **GREEN** |
| **Form 1** — simulate the ORIGINAL panel-parented wiring `self._freeze_timer = QTimer(self)` | RED | **structural RED** ✓ |
| **Form 2** — marker `# RUNTIME_BEAT_SOURCE` kept but the beat **hollowed** (`_emit_beat` no longer feeds the chain) | RED | **behavioural RED** ✓ ("MARKER PRESENT BUT THE BEAT IS HOLLOW") |

The gate reads **behaviour, not the grep marker** — the exact S3/F5 grep-only-gate kill. Target 4 satisfied.

**BEAT verdict: PASS.** See **F-BEAT** — the inconclusive fallback is code-triggerable.

---

## 5 · GATE attack (S4/S5) — forge non-HEAD receipt + close without RELEASE (target 5)

Fresh scenarios (distinct from the builder's V1/V2/V3 walk) driving the **real** `Get-LegState`/`Test-CloseGate`
in a scratch git world:

| scenario | expect | got + exact message |
|---|---|---|
| **G-B** receipt = HEAD, only a **decoy** release (wrong `frm`) + a `claim`-not-`status` from the right frm | closing | **closing** — "no RELEASE line for W99-HCRXGATE is on the bus (wave99)" ✓ |
| **G-A** receipt **buried 2 commits deep**, a **valid** RELEASE present (isolates the HEAD check from the RELEASE check) | closing | **closing** — "is committed (35bf298f) but is not the branch HEAD (a6de8af2)" ✓ |
| OK receipt = HEAD + valid RELEASE | done | **done** ✓ |

Target 5 satisfied: a forged non-HEAD receipt and a close without a valid RELEASE are both refused with the
**exact** messages; a decoy release (wrong frm / wrong type) does not fool the gate. See **F-GATE**.

**GATE verdict: PASS** (S4 receipt==HEAD spine + S5 presence check).

---

## 6 · Combined staging — ratchet, guardrails, mandate table (target 6)

### 6a · Ratchet vs base

Full `pytest tests/` on **identical stable-git contexts** (fresh `git init`, single commit, `.git` a directory =
CI context), differing only by the four products:

| tree | passed | failed | errors | skipped |
|---|---|---|---|---|
| base (master archive) | 6505 | **0** | **0** | 181 |
| combined (+QUOTE+PROV+BEAT+GATE) | **6572** | **0** | **0** | 181 |
| **delta** | **+67** | **0** | **0** | **0** |

**Ratchet holds:** failures stay at 0, passes go **up by 67** (exactly the W6 new tests), zero regressions from
composing all four products. (Committed floor `suite_baseline.json` = 6389/0/170 at `b2412b6b`; base 6505 > floor
because master grew since 2026-08-15 — passes only up.) An earlier no-stable-git run showed 13/18 *spurious*
failures in git-infra tests (`test_statusline`/`test_harness_lock`/`test_perf_ratchet`/`test_worktree_guard`) — a
live **M6 environment-dependent-verdict** instance, controlled for by putting both trees in the same git state.

### 6b · guardrail_violations

The 5 sprint guardrails on the combined tree: `scout_no_apex_corpus` **True**, `no_rigging_drift` **True**,
`provenance_not_bypassed` **True** (PROV's wired gate GREEN on the composed tree), `phantom_clean` **True**
(HEAD==master, no drift); `suite_baseline` = the ratchet above. **guardrail_violations (product-caused): NONE.**

### 6c · Mandate table — binary per leg, incl. RELEASE check (target 6, acceptance 3)

Dogfooding W6-GATE's own S4/S5 close gate on the four sibling legs (real `Test-CloseGate` conditions +
live-wave6 `has_release`):

| leg | receipt in worktree | committed | == branch HEAD | bus RELEASE (`has_release`) | close-gate verdict |
|---|:---:|:---:|:---:|:---:|---|
| **W6-QUOTE** | ✓ | ✓ `9bdd69b3` | ✓ | ✓ True | **done** |
| **W6-PROV** | ✓ | ✓ `21257a34` | ✓ | ✓ True | **done** |
| **W6-BEAT** | ✓ | ✓ `f3eaccf6` | ✓ | ✗ **False** | **CLOSING — S5: no bus RELEASE** |
| **W6-GATE** | ✓ (**untracked**) | ✗ **not committed** | — | ✗ False | **CLOSING — S4: receipt not committed** |

**F-MANDATE-1 (W6-BEAT):** receipt committed as HEAD, **no bus RELEASE** → held at `closing` by its sibling's S5 gate.
**F-MANDATE-2 (W6-GATE):** its own `W6-GATE.json` is **written to the worktree but untracked (never committed)** —
the leg that built *"receipt-is-closing-commit"* did not commit its own receipt → held at `closing` by its own S4
gate. A live recurrence of the exact CRX0/W5H class the wave targeted. (Merge is Joe's word; an operator close-pass
can still commit + release per R135 — but per the wave's own doctrine, "operator rescue is a failure mode, not the
plan.") Point-in-time observation of the live wave6 bus + worktrees at 2026-08-16.

### 6d · HARDENING-SPEC row → defense mapping (target 6, acceptance 2)

Every class row → a now-wired defense, a ruling, or an honest-open row (R80 vocab: WIRED = a machine gate that CAN
fail). Anchors spot-verified first-hand.

**Part A (seeded):** S1 → **WIRED** (QUOTE Sanitize-SQ; §2) · S2 → **WIRED** (PROV fail-closed; §3, + F-PROV/B1/B2
gaps) · S3 → **WIRED** (BEAT behavioural; §4, + F-BEAT gap) · S4 → **WIRED** (GATE commit==HEAD; §5) · S5 →
**WIRED, presence-only** (GATE RELEASE; §5, + F-GATE gap) · S6 face_token → unchanged (crucible + narrow WIRED
test) · S7 UNKNOWN-laundering → unchanged (schema + crucible; **W6-HCRX honors it — no UNKNOWN laundered**) · S8 →
**WIRED** (QUOTE Write-Utf8NoBom + JSON lint; §2).

**Part B (mined):** M1 → PROV catches the FloorGate M1 shape (§3-A); general class honest-open. **M2
a-check-that-cannot-fail → the quality bar; every new gate shown RED-able (§2–§5).** M3 → crucible discipline
(two-sided controls). M4 → PARTIAL (ratchet reads the summary line). M5 → honest-open. **M6 → live instance §6a,
controlled for.** M7 → WIRED (lock; GATE reads it). M8/M9/M10 → PROSE/NONE honest-open (security for-ruling).
**M11 → root of S4, worktree-draft half closed by GATE commit==HEAD.** M12/M13 → honest-open. M14 → WIRED
(statusline). M15/M16/M18 → honest-open (my brief cited HARDENING-SPEC, which **exists** on wave6/forge — no M16
here). **M17 → honored (I re-derived, never copied builder figures — the crucible re-derive predicate).** **M19 →
the two shared files are a live case; proved they 3-way merge clean (§0).** **M20 → defused by GATE self-commit;
R135 main-tree fallback preserved.** M21 capped-adversarial-pass → guarded (the independent verification workflow
ran to completion; 4/4 gate critics returned — recorded, not silently treated as complete). M22 → avoided (all
runs in scratch trees, never the production log). M23/M24/M25 → honest-open by design.

**Part C:** META ordered-check-never-built → the wave moved S1/S2/S3/S4/S5/S8 from PROSE/WARN/HOLLOW to **WIRED**,
each shown RED-able first-hand here; R80 vocab guards reopening. **No row laundered.** The ledger's forecast
honest-open set (M12/M13/M15/M16/M18/M20/M21–M25) is confirmed still-open — none a single builder wave closes.

---

## 7 · Independent adversarial completeness pass (verification workflow)

A separate workflow ran **four independent gate critics** (builders ≠ reviewers ≠ crucible) tasked to find a
bypass the builder AND this crucible both missed. **Every critic confirmed this crucible's own findings accurate
and fairly framed**, and each surfaced one additional gap — **each of which this leg then reproduced first-hand**
(never inherited). The critics rated three gates "defense-broken"; I temper that to "WIRED with a coverage gap +
over-claiming comment" (see each finding), because every gate still fails-closed on the shapes it fingerprints and
on the lived defect instances — the gaps are in never-lived adversarial variants and in comments that over-claim
scope. The four confirmed gaps are F-QUOTE / F-PROV / F-BEAT / F-GATE below.

---

## 8 · Findings

*None is verdict-blocking: every gate fails closed on its target defect and on every lived instance of its class.
The findings are coverage gaps against never-lived adversarial variants + gate comments that over-claim scope —
all cheaply closable.*

**F-QUOTE — id path-traversal (write + exec outside TEMP).** `orchestrate.ps1:359` builds the runner path from the
**raw** `$leg.id`, not `$safeId`: `$script = Join-Path $env:TEMP "orch_$($leg.id).ps1"`. Verified first-hand: an id
`..\..\..\TARGET_OUTSIDE\PWNED` writes the runner to `TARGET_OUTSIDE\PWNED.ps1` **outside `$env:TEMP`**; on the
live path that file is the `Start-Process powershell -File $script` exec target → arbitrary-location `.ps1`
write+exec from a per-leg field the gate's own comment (`:335-342`) enumerates as made-safe. Content sanitization
(Sanitize-SQ) is complete and unaffected; the id-*path* surface is out of its reach. **Fix:** sanitize/validate the
id for path safety (reject path separators / `..`), or build the path from a sanitized id.

**F-PROV — taxonomy-misclassification false-green (broadest blast radius).** Adding a mutating command (e.g.
`set_parm`, `create_node`) to `_READ_ONLY_COMMANDS` (`handlers.py:204`) silently disarms provenance via the
**blessed** `invoke()→wrap()` path (`_is_read_only` returns True → `self._record(...)`/`write_report` skipped;
also skips the C5 lock + integrity envelope + `_submit_logs`). Verified first-hand: injected the names into the
real `handlers.py` → `check_provenance_not_bypassed` **still returns True** ("every mutating command routes through
the FloorGate…"). This defeats the gate's *stated core guarantee* ("RED the moment a mutation can reach `hou.*`
with no provenance record") — which the docstring claims is impossible (it enumerates only dispatch-outside-invoke
or gut-the-gateway). A **demonstrated-real, recurring** vector: `handlers.py:242` already carries the
"cops_temporal_analysis is NOT read-only" hand-correction proving a mutating command was previously misfiled here.
**Fix (cheap, deterministic):** a 4th static leg asserting `{create_node,set_parm,connect_nodes,delete_node,
set_usd_attribute,set_keyframe,…} ∩ _READ_ONLY_COMMANDS == ∅`. *(Also B1/B2: two-line get-and-call and dict-
dispatch bound handler evade the static leg-3 regex — same class, lower blast radius.)*

**F-BEAT — inconclusive-fallback false-green.** Leg-3's behavioural proof returns structural GREEN ("INCONCLUSIVE",
`checks.py:2076-2081`) when the proof subprocess cannot run (`ran=False`), and that path is **code-triggerable**:
keep both grep legs GREEN + a hollow beat, then add an unguarded failing import above the guarded block so
`from synapse.server import runtime_beat` raises → no `BEHAVIOR` sentinel → GREEN. Verified first-hand: hollow beat
+ broken proof import → `check_runtime_owns_heartbeat` **ok=True (INCONCLUSIVE)**. A regression that hollows the
beat *and* breaks the proof reads green. **Fix:** treat a proof that cannot run on a full-package tree as a hard
RED (or a distinct blocking state), not structural GREEN.

**F-GATE — S5 checks release PRESENCE, not release-to-claim MATCH.** `has_release` (`bus.py:84-97`) greens on any
non-empty `body.release` from the frm; it never compares the released file-set to the leg's claim (unlike
`open_claims` in the same file, which matches by file-set). Verified first-hand on the live bus: W6-QUOTE
`has_release=True` while its claim reads **still-open** in `open_claims` (release file-set ≠ claim file-set); even
`{"release":"yep"}` passes (only `{"release":[]}` fails). So a leg can satisfy S5 with *any* release, and the
gate's own comment (`orchestrate.ps1:191`, "a RELEASE line for this leg's claim") over-claims a claim-linkage the
code does not implement. **Note:** every *lived* S5 instance was total-absence (which the gate does catch); this
gap is the never-lived mismatched-release variant. **Fix (cheap):** require the release file-set to match an open
claim, or minimally that no open claim from the frm remains.

**F-MANDATE-1 / F-MANDATE-2** — see §6c (W6-BEAT no RELEASE; W6-GATE receipt uncommitted).

---

## 9 · for_ruling (Joe) & spawn

**for_ruling:**
1. **F-PROV (highest leverage):** add the 4th static leg (mutating-set ∩ read-only-set == ∅) — closes a
   demonstrated-real, broad-blast false-green cheaply.
2. **F-QUOTE:** validate/sanitize `$leg.id` for path safety before it reaches the runner filename + exec target.
3. **F-BEAT:** a full-package proof that cannot run should RED (or block), not fall back to structural GREEN.
4. **F-GATE:** tighten S5 to claim↔release file-set parity, or accept presence-only and correct the over-claiming
   comment at `orchestrate.ps1:191`.
5. **F-MANDATE:** commit `W6-GATE.json` + post BEAT/GATE bus releases before merge (or operator-harvest per R135).

**spawn (class `probe`, within `spawn_classes`):**
- `W6-HCRX-S1` (probe): AST provenance side-door + read-only-set-intersection detector fixture (planted taxonomy
  misfile + two-line/dict dispatch → RED).
- `W6-HCRX-S2` (probe): S5 claim↔release file-set reconciliation probe; and a QUOTE id-path-safety fixture (a
  traversal id must be refused before write/exec).

---

## 10 · Verdict

**`green_with_findings`.** All four gates were re-attacked first-hand on a cleanly-composed combined scratch tree;
each **fails closed on its target defect and on every lived instance of its class** (QUOTE parse-clean under 17
fresh metachar names; PROV RED on a fresh M1 bypass; BEAT behavioural RED on a hollow beat; GATE exact-message
refusals on forged non-HEAD + decoy-release). 108/108 builder acceptances re-pass; the ratchet holds (+67, 0
regressions); product-caused guardrail violations = none; the HARDENING-SPEC mapping is complete with no row
laundered. Adversarial completeness (this leg + an independent 4-critic pass, every finding verified first-hand)
surfaced one confirmed false-green per gate in the gates' *stated* scope (F-QUOTE/F-PROV/F-BEAT/F-GATE) plus two
sibling legs not yet closed per the mandate (F-MANDATE) — real, net-positive defences with cheaply-closable
coverage gaps, all routed to `for_ruling`. No gate is invalidated. **Merge remains Joe's word per leg.**
