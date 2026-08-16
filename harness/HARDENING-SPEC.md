# HARDENING-SPEC — the canonical failure-class ledger

*Produced in-wave by **W6-FORGE** (team-lead leg, 3-reader fan-out), 2026-08-16, on
`wave6/forge`. The first-principles artifact of the W6 hardening pass: **standards
derived from lived failures, not invented.** One row per failure **class**, never
per instance. Every row cites an evidence anchor (a receipt path, a `file:line`, or
a commit sha). A class with no lived instance is marked **PREEMPTIVE**; history is
never invented to fill a row. Anchors were **verified first-hand** by this leg (see
the Verification appendix) — nothing is inherited on a reader's word.*

**Consumers.** This ledger IS the shared spec for the four builder legs
(**W6-QUOTE / W6-PROV / W6-BEAT / W6-GATE**) and the attack list for the crucible
(**W6-HCRX**, whose brief names this file: *"HARDENING-SPEC rows each mapped to a
now-wired defense or an honest open row"*). Read your rows; the **target gate**
column is your work order.

---

## Governing law — how to read `current defense`

The failure this whole wave exists to kill is the **meta-class**: a rule that was
*ordered* but never *built*, then cited as if it were enforced. `CTO_RULINGS_01.md`
H8-F8 states it flat — *"nine rulings explicitly order a check into `checks.py` or
the check set. None of the nine exists."* Hard census (`RULING_AUDIT.json`):
**`rulings_with_no_mechanism_on_this_branch = 41`**, `UNENFORCED 31/78`,
`enforcement.none = 37`.

The honesty rule for this ledger's `current defense` column is **R80 clause 3**
(`CTO_RULINGS_01.md:2220-2243`), adopted verbatim:

> *"No ruling may use the word 'adopted' for a rule with no mechanism. 'Adopted'
> implies enforcement. `PROPOSED` is the honest word until a check exists."*

Exactly one token per row:

| token | meaning |
|---|---|
| **WIRED** | a machine gate/test enforces it **and can fail** (Law 1) |
| **WIRED-BUT-HOLLOW** | a gate runs and is cited PASS, but reads a *proxy* (a source string, a file's existence) — greenable by a decoy |
| **WARN-ONLY** | the check runs but returns `ok:None` / never blocks (declared, not faked) |
| **CRUCIBLE-ONLY** | re-checked per wave by a human-dispatched crucible; **no standing machine gate** — dormant between waves |
| **PROSE-ONLY** | a rule in a brief/ruling/SPEC; nothing enforces it |
| **NONE** | no defence of any kind |
| **PREEMPTIVE** | no lived instance yet |

**Quality bar for every new gate this wave ships** — Law 1
(`AGENT_CONSTITUTION.md:60-80`): *"state the condition under which this fails. If
you cannot, you have not written a check — you have written a decoration."* W6-HCRX
will simulate each original defect and require the new gate to read **RED**. A gate
that cannot be shown failing is not WIRED here.

**Not every open row is a defect (R84 caveat).** Some NONE/PROSE rows are honest
deliberate gaps — e.g. R94: *"Claiming merges are fenced when they are not is worse
than the gap."* A PROSE-ONLY row is a *candidate* for wiring, not an automatic bug.

---

## Part A — the eight seeded classes (the builders' shared spec)

| # | Failure class | First occurrence (anchor) | Instances (lower-bound) | Current defense | Target gate | Owner |
|---|---|---|---|---|---|---|
| **S1** | **unquoted-interpolation** — an uncontrolled string (leg name, path, prompt, branch) enters a quoted PS/git/shell context and shreds it | **2026-06-24 `0522ad0e`** (`shell:true` ate the backslashes in the `--settings` path → silent fallback to the global API key) — **not** 2026-07-26 | **6**; 3 mechanisms (backslash-eaten path, quote-split arg, apostrophe parse-bomb), 2 surfaces (`harness/run.ts`, `harness/orchestrate.ps1`). Costliest `943e5375` 2026-07-26 (2000-char brief split at first `"`; two legs ran 2.5h truncated, wrote no receipt). **No receipt covers it — evidence is git bodies only; never through a crucible** | **NONE** — point fixes only (`safeName` at `orchestrate.ps1:243` used at :257/:359/:362/:365; delivery-by-file-reference `943e5375`). `tests/test_harness_quoting.py` **ABSENT** (verified) | **W6-QUOTE**: `Sanitize-SQ` PS helper + python twin; `test_harness_quoting.py` adversarial-name dry-run matrix through the PS Language Parser; `.ps1` lint | **W6-QUOTE** (`harness/**`) |
| **S2** | **unwired-provenance-guardrail** — the provenance check is registered and runs but cannot fail | **2026-06-06 `c6769992`** (RFC §7.1: 3 of 5 ledger writers aspirational) | **9+ receipts** — `L0.json` F2 (*"'provenance or it didn't happen' … unmet on the live path"*), `LEDGER.json` F4/F6 (*"the same SPECIES — mechanism built, writer never wired"*), `S2.json` thesis + F15, `W5-SHELF.json` F4, `E0.json` F11 (`_note_usage` zero callers, ×4 legs). Flagship of M1 | **WARN-ONLY** — `harness/verify/checks.py:371-378` returns `{"ok": None, "detail": "ADAPT: … Warn-only until then."}` **by construction** (verified); law it fails to enforce = `harness/CLAUDE.md` *"Provenance or it didn't happen"* | **W6-PROV**: wire fail-closed in task verdicts; legitimate-exception path explicit + test-pinned; a forced bypass in a scratch tree must fail the verdict | **W6-PROV** (`harness/verify/`) |
| **S3** | **grep-only-gate (heartbeat)** — the gate greens on a marker *string* in source, not on the behaviour | **2026-07-26 `943e5375`** (the staleness detector scanned its own log dir → "0m ago" forever); the heartbeat gate named F5 at `b3de8192` | **1 direct + 4 same-class** — `W5-LCRUX.json` F5 (`checks.py:1842`), F7 (regex pin); `V0.json` F10 (*"textual, not transitive"*); `C0.json` F9 (pin covers one file). Flagship of M2 | **WIRED-BUT-HOLLOW** — `check_runtime_owns_heartbeat` passes if `# RUNTIME_BEAT_SOURCE`/`def ensure_beat_started` appears in source (verified grep-only); *"a hollow … comment with no real beat would green it"* | **W6-BEAT**: start runtime headless, attach then destroy a panel-proxy, assert the beat continues + session store survives; point the machine gate at the behaviour (folds spawn W5-LCRUX-S1) | **W6-BEAT** (`server/`) |
| **S4** | **receipt-without-commit (CRX0)** — a receipt asserts commit-state (a HEAD sha, "done") that does not exist; the state machine treats a receipt *file* as completion | **2026-07-26 `bd178702`** (Q1/Q2/H2/H3 receipts untracked). Origin ruling **R93** (`CTO_RULINGS_01.md:2552`); **CRX0 named** `fe1dcd2c` | **~12 — the most-evidenced class (4 waves).** `W4-CRUX.json` CRX0 (systemic wave-4), `W2-CRUX.json` B1, `W5-HCRUX_verdict.md` F1/F2/F3 (mandate 2/4), `F1.json` R4 (5/10 legs green-uncommitted), `T0.json` D1. Recurrence `362d5755`; operator close-passes `c7a6a08d`/`76ca94a0` vs self-commit `b4bbb562` | **PROSE-ONLY + CRUCIBLE-ONLY** — `_template.md:47-64` two-part mandate; crucible re-checks per wave. State machine **actively permits it**: `orchestrate.ps1:151` `if ($leg.receipt -and (Get-ReceiptPath $leg)) { return 'done' }` — no commit/HEAD/RELEASE check (verified). Root = M11 | **W6-GATE**: `done` requires receipt file on branch **AND** receipt commit **IS** HEAD **AND** a bus RELEASE line; else hold at `closing` with an exact-missing Notify | **W6-GATE** (`orchestrate.ps1` close-state) |
| **S5** | **missing-bus-RELEASE** — legs post `claim` but never the matching `status {release}`; claims stay open forever | **~2026-08-09 `W2-CRUX.json` B1-S5** (*"NO bus release ever posted for the open synapse_panel.py claim (n=18cb66061adfa40c)"*) — **earlier than LCRUX**; systematized 2026-08-16 `b3de8192` (F2/F3). **NO FIX COMMIT EXISTS** | **2 receipts** — W2-CRUX B1-S5 (verdict FAIL), W5-LCRUX F2 (no wave-5 leg released, all claims open) + F3 (over-broad never-released claim). The `open_claims()` mechanism is **correct**; legs simply never call release | **PROSE-ONLY** — `_template.md:40-41` release instruction (agent must remember). `bus.py:71` `open_claims()` computes it (verified present) but **nothing consumes it as a gate** | **W6-GATE**: RELEASE required before `done` — the same close gate as S4 | **W6-GATE** (`bus.py` + `orchestrate.ps1`) |
| **S6** | **claim-without-observation (face_token family)** — a receipt/figure asserts a conclusion stronger than any probe observed | **2026-06-23 `d511e0b8`** (a pytest *skip* exits 0 → counted as passing). Canonical **R127** `88236997`: *"I published a wrong number and my verifier passed it"* | **11+ receipts, deepest family after CRX0** — `FID.json` F1 (*"'Fidelity 1.0' … before a single operation had been observed"*)/F2/F4/F6, `S2.json` F3 (100% fidelity for 5 errored calls), `L3.json` F2 (*"consent theatre"*), `H3b.json` F6 (halt that doesn't halt), `W1-HSTRIP.json` F2 (hardcoded `healthy=True`), `W5-PANEL.json` F2 (`face_token`). face_token is now the class's **best-behaved** consumer (`7c8cbec2`) | **WIRED (narrow) + PROSE-ONLY (agent claims)** — `tests/panel/test_gate_fidelity_unknown.py` fails on a two-arg `.get("session_fidelity", …)` for that one key/widget; law at `face_token.py:32` (**R162**); verifiers-read-committed-path (R127) PROSE-ONLY | Defended by the **crucible** (nothing inherited) + receipts-over-claims; see M11, M17. No dedicated W6 builder | crucible / panel product |
| **S7** | **UNKNOWN-laundering** — an unobtainable/unmeasured result is recorded as zero, an estimate, or a pass instead of UNKNOWN | **2026-08-03 `2a6bbe7a`** (a self-clearing fidelity floor would hide its evidence). Canonical `026fe875`: *"the scorer must not report 0.0 when nothing was measured."* Word **"laundered"** enters `b1a09924` | **~13** — HCRUX F2 (a receipt laundered the mandate "honored" while untracked), `L1.json` F2 (degenerate 218/218=100% coverage), `9bd298c4` hero-gauge, `5320da97` audit. **Discipline holds** in W3-DIM/W2-S4/W5-UNDO/W5-PANEL/W1-MTFIX/W2-CRUX acceptance rows | **SCHEMA-WIRED (admission) + CRUCIBLE-CHECKED + one code gate** — `autorevise/SPEC.md:53-54` (`gui_required`→UNKNOWN); `result_telemetry.py::gui_metric_verdict` (W1-MTFIX) is the **only** code-level UNKNOWN gate; product-side WIRED (V2 *"unmeasured is not zero"*) | No new W6 gate — schema + crucible; **W6-HCRX** enforces *"UNKNOWNs never laundered"* | `mission_schema.py` + crucible |
| **S8** | **PS-5.1-BOM / encoding-landmine** — PowerShell 5.1 writes a UTF-8 BOM / cp1252 mojibake / CRLF that silently breaks a downstream parser or hash | **2026-07-25 `12e43fce`** (R26: BOM in `relay-settings.json`). **Severe:** `121894d9` — a BOM on the live Houdini `synapse.json` made the package fail to load **silently** | **7 receipts** — `V0.json` F13 (PS 5.1, `$LASTEXITCODE` unchecked), `I0.json` F2 (BOM ate 32 directives), `M2-CRUX.json` BLK-1 (relative bus path), `WARN.json` F3 (em-dash→UnicodeEncodeError), `H1_SECOND` F7 + `I1.json` F12 + `E1.json` F8 (CRLF-in-a-hash). **LIVE-OPEN:** `base_control/resolved_lines.json` fails `json.loads` (verified); **53/54** files in `prompts/` carry a BOM + mojibake (verified) | **PARTIAL + NONE** — one wired defence `bom_audit.py` scoped to **JSON only** (misses `.py`, CRLF hashes, cp1252 stderr, `$LASTEXITCODE`). **R26** ordered *"assert every JSON under `harness/` parses with `json.load`"* — **never built** (verified: no `check_json`) | **W6-QUOTE** target 4: *"JSON writes BOM-free"* lint pinned in tests | **W6-QUOTE** (`harness/**`) |

---

## Part B — newly-mined classes (the extend)

Deduped across all three readers; each a genuinely distinct **mechanism** with a
verified anchor. Grouped by theme. `→ Sn` marks a seed that is a specific instance
of the general class.

### Group I — a green can lie (gate integrity)

| id | Class | First occurrence (anchor) | Current defense | Disposition / owner |
|---|---|---|---|---|
| **M1** | **built-and-connected-to-nothing** — a mechanism is built, correct, has zero callers (`→ S2`); the repo's *dominant* finding | R173 `39f38007` (*"a check whose result does not gate the action is a log line"*); *"the week's dominant finding"* `CTO_RULINGS_01.md:3692`; `Release-LegLock` zero call sites `afe83e07` | **NONE** (general). Disposition rule exists: **retire-or-wire, never dormant** (`175732b4`/`cfc52d8c`, pinned by `test_router_internals.py::TestPromotionRetired`) | all builders: ship no mechanism with no caller |
| **M2** | **a-check-that-cannot-fail (decoration)** — no negative control / self-referential input (`→ S3`); largest class in the corpus | Law 1 `AGENT_CONSTITUTION.md:60`; `L2.json` N7 (*"a documentation test wearing a verifier's name"*), `RES.json` F3, `GUARD.json` F1, `S1.json` F1 (`importorskip("hou")` gates nothing) | **PROSE-ONLY** (Law 1); antidote named = mutation testing | **the quality bar for all four builders' new gates** (HCRX: regression-sim goes RED) |
| **M3** | **instrument-defect** — the meter *can* fail but is pointed at the wrong quantity; caught only by its own two-sided controls or an adversarial pass | `H7.json` F12 (*"would have shipped 46 false deprecations … every one a confident, plausible result"*), `E0.json` D9 (*"perfectly calibrated and still pointed at the wrong quantity"*), `H3a.json` F4, `H5.json` oracle-defect | **PROSE-ONLY** (two-sided-control + adversarial-pass practice) | crucible discipline / any measuring leg |
| **M4** | **wrong-success-signal** — an exit-code, a skip, or a file's *presence* read as a pass | `d511e0b8` (skip=pass); `state_of()` done on any receipt file `55371c96` (`→ S4` root); headless skip = pass in ratchet `W5-LCRUX_verdict.md:88` (F8); R301 `CTO_RULINGS_03.md:13` (*"the suite summary LINE, never an exit code, is the floor"*) | **PARTIAL** — R31 baseline-is-a-tuple WIRED; R301 PROSE-ONLY; **headless-skip accounting NONE** | test infra / orchestrator; mark ratchet-skip **OPEN** |
| **M5** | **silent-degradation** — a fallback path reports as the normal path, no log line distinguishing them | `E0.json` F13 (import failure → 93-tool subset, 35% smaller, no signal), `H6.json` F4 (inverted message), `W3-DIM.json` (live seat degraded 384→256 dim) | **NONE → WARN-ONLY** (H6 M12–M14 wired for one arm) | product; a fallback must emit a distinguishing signal |
| **M6** | **environment-dependent-verdict** — green depends on which interpreter / checkout / line-ending asked | `Q2.json` F5 (CI py3.14 vendor-inactive), `SR1.json` R-2 (worktree `.pth` tests the primary tree), `V3.json` F6 (empty-string API key shadows `.env`), `M5.json` F1 (cwd-dependent `$HIP` baseline) | **WARN-ONLY** (W5-STATWT landed one structural fix `a77b5baf`) | test infra; baselines must record the environment that produced them |

### Group II — concurrency & fences

| id | Class | First occurrence (anchor) | Current defense | Disposition / owner |
|---|---|---|---|---|
| **M7** | **liveness/state-from-a-filesystem-proxy (not a mutex)** — completion/concurrency inferred from files/mtime, not the authoritative lock | R156 `8cb94622` (*"a live lock means running. Ask the lock, not the filesystem"*); R134 concurrent-writer | **WIRED** — R134 dispatch lock (`orchestrate.ps1:135+`), `test_orchestrate_liveness.py`; extended to subagent transcripts `630459ba` | orchestrator (largely closed) |
| **M8** | **parallel-writer-collision (Article V)** — parallel agents edit shared files/worktrees; writes can survive `TaskStop` | `H1.json` D2 (*"writes continued ≥4 min after TaskStop"*), `H6.json` F7 (two impls, last binds; "flaky test" was the wrong diagnosis), `I1.json` F8 (2nd occurrence in 2 days), `H2b.json` F2 (11 worktrees at master, not HEAD) | **PROSE-ONLY** (Article V); snapshot-before-fan-out is detection not prevention | orchestrator / any fan-out leg |
| **M9** | **instruction-fence-not-structural** — a read-only *instruction* does nothing while the agent holds write tools; **8× recorded** | `H2b.json` F1 (*"Prose is advisory to a model; a deny-list is not"*), `S2.json` D2 (*"seventh recorded instance"*), `S3.json` D7 (*"eighth … reading the tree is read-only; importing it is not"*) | **PROSE-ONLY** — fix is a structural tool-permission deny + snapshot | orchestrator / roster (agent-definition fence) |
| **M10** | **fence-matches-command-form-not-capability** — a deny-list keyed on a command *form* is bypassed by an equivalent form; **probe-confirmed porous** | `F1.json` R1 (*"`git -C <path> merge` … same binary, opposite outcomes … CONFIRMED BY PROBE for both merge and push; do not cite any of them as a safety guarantee"*) | **NONE** (the fence is advisory). Counter-example that works: `pre-push` hook keyed on capability + `SYNAPSE_GATE_C=1` (`U1.json` F7) | **security — for-ruling**; gate on capability, not form |

### Group III — provenance, copies & durability

| id | Class | First occurrence (anchor) | Current defense | Disposition / owner |
|---|---|---|---|---|
| **M11** | **two-copies-one-claim / two-authorities-one-surface** — a verifier/reader reads a *draft* or a divergent copy while the claim rests on another; **root of S4** | R127 `88236997`; *"three subsystems, one shape: a second copy nobody declared"* `CTO_RULINGS_01.md:3615`; `S3.json` F10 (committed S2 is the pre-adversarial draft), `LEDGER.json` F1 (two Moneta copies) | **PROSE-ONLY** — R127 clause 2 (*"verifiers read the COMMITTED path, never a worktree glob"*) | verifiers / W6-GATE (`commit==HEAD` closes the worktree-draft half) |
| **M12** | **gitignored-evidence** — the producer/artifact a receipt cites cannot be committed; Law 2 satisfied on paper, void in the tree | `I1.json` F7 (`.gitignore:50 _*.py` makes producers uncommittable), `Q1.json` F10 (swallows a `tests/_*.py` helper), `H4.json` F13 (blanket `*.png` would drop 32 images) | **NONE** | Law-2 discipline; a producer path must be a committable path |
| **M13** | **readonly-leg-product-destroyed** — the fence denies commit, so the leg's *work itself* is lost (distinct from S4, where only the receipt over-claims) | `S2.json` R-S2-2 (*"S0/S1 artifacts DESTROYED mid-run by a housekeeping pass … no blob in any ref"*), `S3.json` R-S3-6 (recovered from a transcript, "recurrence guaranteed"), `H8.json` F4 (`git worktree remove` would destroy 11 rulings' evidence) | **PROSE-ONLY** (R103 amendment unlanded); in tension with M20 | for-ruling / orchestrator harvest design |
| **M14** | **stale-evidence-rendered-fresh** — a figure from a *different commit* shown as current; age is the wrong axis when the tree moves | `445e174c` (statusline showed "5307 ok 17m" green for a commit 2 behind HEAD) | **WIRED (statusline)** — suppress age on drift; class not gated elsewhere | **PREEMPTIVE** for other telemetry surfaces |

### Group IV — corrupt work order

| id | Class | First occurrence (anchor) | Current defense | Disposition / owner |
|---|---|---|---|---|
| **M15** | **brief-premise-error** — the work order asserts a fact already false when written; the leg burns a run against it | `cto_relay_drift.md:137` (D1), `W5-LCRUX_verdict.md:84` (F4, ROPE premise), `W5-HCRUX_verdict.md:113` (F4, self-contradictory predicate) | **CRUCIBLE-ONLY** — caught only after the leg ran | mission compiler (validate premises pre-dispatch) |
| **M16** | **phantom-governing-document** — the brief cites an authority (a doc it must "read end to end") that does not exist in the tree | `FRZ.json` D-FRZ-1 (*"the file has never existed in this repository"*), `W1-MTFIX.json` F2, `V2.json` F8 (blueprint absent, section numbers uncheckable), `W3-{MIGRATE,STORE,PAPER}` (one absent spec, three legs) | **PROSE-ONLY** (Article VI escalation) | mission compiler (resolve `source.doc` before dispatch) |
| **M17** | **control-pinned-to-brief-figure** — a check whose expected value is copied from the doc under test (`→ S6`); it passes green while locking the error | `I1.json` F2 (*"control P6 asserted len==161 … passed green while the extractor undercounted by 10"* — was really 171), I0 Q3 same blind spot | **PROSE-ONLY** — fix = a 4-line blind control reproducing the alternative reading (I1-R3) | any leg building a reader; the crucibles' re-derive predicate (R131) |
| **M18** | **uninstructable-standing-rule** — a rule a leg can neither obey nor disobey, because another mechanism controls the outcome | `U1.json` F7 (*"the backup daemon pushed this leg's commit 22s after it was made … a bare `pushed:false` reports inaction, not state"*), `F1.json` D1 (profile denies the merge the brief orders), `M5b.json` D-M5b-1 (fix-your-own-base unexecutable — all of reset/merge/rebase denied) | **NONE — actively false** | for-ruling; mission compiler must not order the unexecutable |

### Group V — merge & close

| id | Class | First occurrence (anchor) | Current defense | Disposition / owner |
|---|---|---|---|---|
| **M19** | **merge-time coupling & collision** — two changes must land together (a fix + its baseline), or two legs promote adjacent lines needing a deterministic union | `W5-LCRUX_verdict.md:81` (F1, LIFE∩SHELF collision), `W5-CRUX.json` F-CRUX-3 (corpus + ledger flip coupled), `Q2.json` R1 (reader + baseline must be one commit) | **NONE** (manual per merge). R92 touches-refusal **PARTIAL** (field populated, refusal unbuilt) | orchestrator (R92) / human merge |
| **M20** | **rule-in-tension / operator-rescue** — two live rules contradict; an act is simultaneously "the standing answer" and "the forbidden failure mode" | R135 `CTO_RULINGS_01.md:3895` (third-party commit = standing answer) **vs** `_template.md:58` (operator rescue = failure mode); `362d5755` did the first while labelling itself the second | **NONE** — needs a **ruling**, not a gate | for-ruling (Joe). W6-GATE's self-commit gate makes rescue unnecessary in practice — but must not wire a refusal that contradicts R135's standing answer |

### Group VI — process hygiene & safety

| id | Class | First occurrence (anchor) | Current defense | Disposition / owner |
|---|---|---|---|---|
| **M21** | **unrun / capped adversarial pass** — verdicts ship unrefuted because fan-out agents died on a token limit or a budget cap | `S1.json` status_note (*"8 of 10 fan-out agents died on a session token limit, so 31 carried verdicts are UNREFUTED"*), `L5.json` F1 (*"one model's unattacked judgement"*), `S3.json` R-S3-7 (25 capped) | **NONE** | orchestrator; a capped adversarial pass must be recorded, never silently treated as complete |
| **M22** | **pytest-pollutes-production-telemetry** — a test run writes into the operator's real log/store; later reads it back as production evidence | `RSI0.json` F8 (*"4,795 'Epoch N complete' records … ALL FALSE … this audit's first pass read them as production traffic and had to reverse"*), downstream warning `PRST.json` | **NONE** — fingerprint test-authored records before trusting the log | product (test-mode log/store isolation) |
| **M23** | **unbounded-destructive-op** — a destructive command with machine-wide blast radius | `Q2.json` incident (*"`taskkill /F /IM python.exe /T` killed EVERY python process … including the concurrent harness and the MCP servers"*) | **NONE** — the mirror (`H1.json` D2) shows the permission classifier *did* deny one such attempt | roster/permissions; scope kills to the leg's own PID tree |
| **M24** | **prohibition-without-a-channel** — a surface is fenced with no sanctioned path around it → the need persists, the *evidence* of it vanishes (silent drift) | R81 `CTO_RULINGS_01.md:2247-2267` (*"a prohibition with no channel produces silent drift"*) — `RULING_AMENDMENTS.md` never created (13 `SUPERSEDED_UNMARKED`) | **NONE** — the amendments channel is still absent | for-ruling / meta |
| **M25** | **held-spawn-accumulation** — an adversarially-proven fix is parked because its class is outside `spawn_classes`; a known remedy with no owner | `W4-KNOW.json` S1 (*"proven to lift P@1 0.755→0.99"*, held), `W5-LCRUX.json` S1, `W2-S4.json` (*"adversarially verified sound"*, unapplied), `W3-HARDEN.json` S1/S2 | **PREEMPTIVE / by-design** — the fence is intended; but the ledger should carry the standing backlog | for-ruling (Joe promotes; W6-BEAT/GATE already fold two held spawns) |

---

## Part C — the meta-class

| id | Class | Anchor | Defense |
|---|---|---|---|
| **META** | **ordered-check-never-built** — a rule is ordered into the check set and cited as "adopted," but the check does not exist. **This is why HARDENING-SPEC exists.** | H8-F8 `CTO_RULINGS_01.md:2231-2233`; census `RULING_AUDIT.json` → **41 no-mechanism**, `UNENFORCED 31/78`, `enforcement.none 37` | **NONE** — the whole W6 wave is the remediation: it moves the highest-leverage lived classes from PROSE-ONLY / CRUCIBLE-ONLY / WIRED-BUT-HOLLOW to **WIRED**. This ledger's R80 vocabulary rule (top of doc) is the standing guard against reopening the class |

---

## Builder crosswalk (read your rows)

- **W6-QUOTE** → **S1** + **S8** primary; **M9/M10** (fences) and **M23** (blast
  radius) are adjacent `.ps1`/permission concerns. Live-open proof already on the
  branch: `base_control/resolved_lines.json` fails `json.loads`; 53/54 prompt files
  BOM'd. Coordinate the `orchestrate.ps1` line overlap with **W6-GATE** on the bus.
- **W6-PROV** → **S2** (warn-only → fail-closed). General class **M1**; disposition
  = retire-or-wire.
- **W6-BEAT** → **S3** (grep-only heartbeat → behavioural pin). General class **M2**
  (a-check-that-cannot-fail); your regression-sim-goes-RED is that bar. Folds
  held spawn W5-LCRUX-S1.
- **W6-GATE** → **S4** + **S5** as one close gate; you also close the root **M11**
  (worktree-draft-as-truth) and **defuse M20** (operator rescue) — but must not wire
  a refusal that contradicts R135's standing third-party-harvest answer. GATE owns
  the `orchestrate.ps1` close-state region only. Folds held spawn W5-HCRUX-GATE.
- **W6-HCRX** → the attack list is this whole ledger. Every Part-A/B row maps to a
  now-wired defence, a ruling, or an honest open row. The expected honest-open set
  after this wave: **M15/M16/M18** (work-order integrity), **M13/M20** (durability
  tension), **M21/M22/M23** (process safety), **M24** (amendments channel) — none of
  which a single builder wave closes.

---

## Verification appendix (receipts over claims)

This leg inherited no anchors. Verified first-hand in `.claude/worktrees/w6-forge`
before publishing:

- **26 anchor shas resolve** to real commits with matching subjects: `0522ad0e
  c6769992 d511e0b8 943e5375 bd178702 12e43fce 121894d9 88236997 39f38007 8cb94622
  26094653 2a6bbe7a 026fe875 cafc513c 43d0ea71 445e174c 55371c96 175732b4 cfc52d8c
  b3de8192 fe1dcd2c 362d5755 b4bbb562` (+ `630459ba a77b5baf a5603b60` cited inline).
- **S2** `checks.py:371-378` returns `{"ok": None}` (grep + `sed`).
- **S3** `check_runtime_owns_heartbeat` matches marker strings in source (grep).
- **S4** `orchestrate.ps1:151` `Get-LegState` returns `'done'` on receipt-file
  existence, no commit check (grep).
- **S5** `bus.py:71` `open_claims()` present, no gate consumer; the earlier
  instance quote confirmed in `W2-CRUX.json` (B1-S5).
- **S8** `json.load` on `base_control/resolved_lines.json` → `Unexpected UTF-8 BOM`;
  BOM scan of `prompts/*.md` → **53/54**.
- **S1** `tests/test_harness_quoting.py` absent (`ls`).
- **M10** fence-form-not-capability confirmed by the F1-R1 probe quote (`git -C`).
- **bus-dedup was RE-DERIVED, not inherited:** M2-CRUX flagged a second-granularity
  `read()` collapse; `bus.py:58` now keys on the nonce `n` first
  (`m.get("n") or m.get("ts")`, added `e6d421ea`), so the class is **FIXED** — it is
  deliberately **not** carried as an open row.

**Reader team:** ReaderA (92 receipts), ReaderB (verdicts/rulings/SPECs, incl.
`RULING_AUDIT.json` census), ReaderC (git-log forensics, all shas verified) — 3
parallel readers, held until all three reported; findings cross-checked against this
leg's independent reads and the git/gate verifications above.

**Known limitation (Law 2):** `instances` counts are lower-bound tallies from the
three sweeps, not an exhaustive census; each is anchored to at least one verified
commit/receipt, and the *first occurrence* per class is the load-bearing figure, not
the total. `CTO_RULINGS_01.md` (5,649 lines) was read by targeted section, not end
to end, so R-number anchors are spot-verified, not exhaustively audited.
