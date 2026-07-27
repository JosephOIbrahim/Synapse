# CTO RULINGS — CTO-RELAY-01

**Ruled** 2026-07-25 · **Authority** Joe, "approved. you are CTO."
**Consumed by** L5. These are decisions, not proposals. Where a ruling reverses or narrows a
question as posed, the reasoning is stated — a ruling that only answers the question asked is
not doing the job.

---

## RULING 1 — Gate 0.1 is SPLIT. The question as posed is half-answered already.

**Posed:** sidecar vs abi3 for the cp311 vendored seam. Open since drop week, brief written,
decision never committed.

**Evidence that reframes it.** `_vendor` ships cp311 **and cp313**. `drop.json` pins the host at
Python **3.13.10**. So inside Houdini 22.0.368, the cp313 wheels *match* — the vendor tree is
live and correct on the surface that ships. The suite that reported 4716/0 ran on **3.14.2**,
where nothing matches and the vendor tree is inactive.

The live defect is therefore **not** the architecture fork. It is that the test interpreter is a
Python the product never runs on. Every green run has been exercising pip-installed
pydantic/anthropic instead of the artifact artists receive.

**Ruled:**
- **1a — immediate, non-architectural.** Pin the suite to the host's Python 3.13. This is a CI
  and tooling change, not a fork, and it needs no architecture gate. Until it lands, no suite
  result may be cited as evidence about vendored behaviour. Label such results
  `VERIFIED-RUNTIME (non-shipping interpreter)`.
- **1b — the fork stays a human gate**, and becomes materially less urgent once 1a lands,
  because the vendor tree will finally be under test. Do not force it now. A fork chosen to
  escape a problem that was actually test-environment drift is a fork chosen for the wrong
  reason.

**Anti-ruling:** do not "fix" this by re-vendoring for 3.14. That chases the test environment
instead of the shipping one.

---

## RULING 2 — D2 ∪ D3 is canonical. D1 is retired.

D1 is 100% by construction: `verified_connectivity_22.0.368.json` contains the entire live
catalogue, so D1 = 218/218 and cannot report anything else. It is not an optimistic number, it
is a number structurally incapable of being false.

**Ruled:** the grounded-coverage denominator is **D2 ∪ D3**. LOP stands at **40/218 = 18.3%**.
D1 is struck from every artifact, dashboard and claim. Any surviving D1 reference is a defect.

**Standing rule, adopted from L1.R5 and applied to myself:** no number enters a governing
document without a producer path beside it. The relay's own "39 of 218" had none, sat in a CTO
document, and was within one node of correct — which is worse than being wrong, because luck is
not a method.

---

## RULING 3 — `Cop` is the target surface. `Cop2` is maintenance-only.

384 live Copernicus types, 0 deprecated, 167 generators, against 169 legacy Cop2 types.

SYNAPSE's moat is access parity with the host. SideFX put H22's centre of mass in Copernicus;
betting the next year of COP work on the legacy surface forfeits parity by choice.

**Ruled:**
- `Cop` (384) is the target. All new COP grounding, emission and semantic work goes here.
- `Cop2` (169) freezes at its current 13.6%. Bugs only. No new coverage investment.
- Coverage reporting states the category explicitly. "COP coverage" as a bare phrase is banned —
  it has meant two different denominators in the same document today.

**Accepted cost:** studios still on COP2-era pipelines get nothing new. `drop.json` targets
22.0.368; that is the bet already placed.

---

## RULING 4 — Author the grounding gate. Highest leverage item in the set.

There is no grounding check for either context. `emitted_node_types.json` has exactly one
consumer in the tree and it is a rigging phrase-scan. The oracles the relay named
(`lop_emission_grounded`, `no_phantom_api`) do not exist.

This is the machinery whose absence let an unsourced number sit in a governing document and
survive to dispatch.

**Ruled:** author both checks into `harness/verify/checks.py`. Per L1, the halves already exist —
`harvest_lop_catalog.py` is a one-symbol swap from a COP harvester and the extractor is
category-agnostic. Scope: emit a coverage integer per category against the live catalogue, and
fail on any emitted type absent from it.

**This is not gap closure and is not gate-refused.** It builds the instrument, not the coverage.

---

## RULING 5 — C.0 stays frozen. The gate is not the blocker; the catalogue is.

L1 delivered the census. Gap *closure* is gate-refused at `flywheel_queue.json:80`
(`ratified:false`), which sits inside the deny fence.

**Ruled: do not flip.** Flipping C.0 alone would close gaps against C.1–C.6, which are armed off
an **H21-vintage capability catalogue for a Houdini build that is no longer installed**. The gate
is not what is stopping good work — a stale base is. Sequence:

1. Re-ratify the context catalogues against 22.0.368 (the LOP and COP catalogues now exist).
2. Then flip C.0.
3. Then close gaps, `Cop`-first per Ruling 3.

The flip remains one boolean and remains yours. I am not reaching into it, and this ruling means
you do not need to today.

---

## RULING 6 — Provenance (task 2.5) blocks the panel change.

Writers are built and dormant — no live callers. Cutting the Review surface (Amendment A1)
removes the only place a decision's reasoning currently appears to a human.

**Ruled: 2.5 wires before L4 ships.** Not "alongside" — before. Shipping A1 first would produce a
panel that is cleaner and tells the artist less about why the agent did what it did. That trade
is unacceptable and it is one I introduced.

If 2.5 cannot land in this relay, L4 ships **without** removing the credit block, and the Review
tab's removal waits. The design is not worth the regression.

---

## RULING 7 — Deprecated LOP emission is a bug, not a flywheel deposit.

`karma` and `karmarenderproperties` are the build's only two deprecated LOPs and SYNAPSE emits
both — the latter in ≥11 places.

**Ruled:** fix as a defect in L2's slipstream, not as a candidate deposit. It is mechanical and
bounded. **Condition:** the successor type must be confirmed by live `dir()` before substitution.
Replacing a deprecated literal with an assumed one converts a decay clock into a phantom, and
that is the failure class this project has already been burned by.

---

## RULING 8 — Namespace the ledger IDs. Live footgun.

`tasks.json` C.3/C.4 (COP/TOP gaps, blocked) collide with `flywheel_queue.json`
C.3-H22-neural-cops / C.4-H22-scaffold-rebuild (`ratified:true`). Same IDs, different work,
opposite gate states. Any dispatch citing "C.3" resolves differently by ledger — and L1 just
worked in that exact namespace.

**Ruled:** prefix flywheel cycle IDs (`FW-C.3`) or task IDs (`T-C.3`). Either, consistently, this
relay. Cheap now; a mis-dispatch later is not.

---

## RULING 9 — `ui/` goes. Rewrite the pin, don't weaken it.

`python/synapse/ui/` (8 files, 1,076 LOC) is dead but held alive by `tests/test_v5_features.py:54`.
Commandment 7 forbids weakening a test to make work pass.

**Ruled:** the test is pinning the wrong thing — it asserts a location, not a behaviour. Rewrite
it to assert the behaviour at its current home in `panel/`, confirm green, then remove `ui/`.
Test count holds or rises. C7 is satisfied in spirit and letter; deleting the test would satisfy
neither.

---

## RULING 10 — Token collision blocks the palette pass. Confirmed.

Already standing in `design/cto_relay_01/L4_COHERE_SPEC.md`. Restated as a ruling: finish the
Mile 7 de-cyan (11 remaining `t.SIGNAL` sites), then make `panel/tokens.py` re-export from
`designsystem/tokens.py` rather than redeclare. One authority. No Cohere rule proceeds first.

---

## RULING 11 — The WS bridge defect outranks everything else in this relay.

L1.F1, `REFUTED-LIVE`: `bridge.json` current (pid 61208, port 9999, today), port Established,
**9 of 9 WebSocket upgrades returned `InvalidStatus`**. Every indicator reads green and the
transport is dead. L1 got its census only by falling back to direct `hou` import.

**Ruled:** L2 diagnoses this before its seam work. It is in the transport layer L2 already
touches, and it is the failure mode with the widest blast radius in the system — a health signal
that reports healthy while the surface it describes is unreachable is worse than an outage,
because it defeats the check that would have caught it.

Escalate to a blocker on the release track. `synapse_doctor` (task 1.5, open) must detect this
exact condition or it is not doing its job.

---

## What is NOT ruled here

- **Gate C — merge to main.** Yours. Untouched.
- **Gate 0.1b — the sidecar/abi3 fork.** Deliberately held per Ruling 1. Ask me again after 1a.
- **`drop.json` MODE flips.** Yours by constitution.

Nine of eleven ruling items are now decided. The two that remain open are open on purpose.

---

# ADDENDUM — L2 SOLARIS RULINGS

**Ruled** 2026-07-25 · standing authority. L2 found two root causes and seven symptoms.
Ruling on symptoms first would repair code nothing can reach, tested by tests that never run.

---

## RULING 12 — The Solaris tool family is ALIVE, but the claim is struck until it is reachable.

**F1:** all five tools sit in `synapse/mcp/tools/solaris/` — a tree **outside** the installable
`python/synapse/` package — and none appear in `_tool_registry.py`. No `/mcp` or `/synapse` path
can invoke any of them. The tree's own conftest concedes it.

**F11:** `pyproject.toml:102` sets `testpaths = ["tests"]`. The five Solaris test files live at
`synapse/tests/solaris/` — outside that root. **They have never run in the gate suite.** They
also drive a `MagicMock` `hou`, so collecting them would assert nothing about real Houdini.

That is the causal chain, stated plainly: *tests that never run, and would prove nothing if they
did, over code nothing can call.* F7 and F9 are not bad luck. They are what that arrangement
produces.

**Ruled — roots before symptoms, in this order:**

1. **One tree.** Move `synapse/mcp/tools/solaris/` into `python/synapse/mcp/tools/solaris/` and
   register all five in `_tool_registry.py`. Root-level `synapse/` is already flagged as a
   namespace-package shadow (L0.F5); this removes the reason it exists.
2. **Collect the tests.** Fix `testpaths` so they run in the gate suite.
3. **Delete the MagicMock `hou` fixture.** This is the load-bearing one. A mock-`hou` test
   asserts your assumptions back at you — it cannot fail when reality disagrees, which is
   precisely how a tool that raises `PermissionError` on every invocation stayed green.
   Replace with hython-gated live tests that **skip** without Houdini rather than pass.
4. Only then repair F3–F10. They become visible, and provable, once 1–3 land.

**Until 1–3 land, the Phase-2 claim that five Solaris tools were delivered is struck from every
document.** They were built, not delivered. The distinction is the whole finding.

**Anti-ruling:** do not quarantine and delete. `scene_template` composes 14 prims live with no
node errors, and `set_purpose`'s host chain composes clean. The scaffolding works. What failed
was the path to it and the proof of it.

---

## RULING 13 — F9 blocks `import_megascans` registration absolutely.

`geo_node.createNode("usdimport", ...)` targets a `componentgeometry` — a locked HDA. Live:
`hou.PermissionError: Cannot create a node inside a locked asset`. **The tool cannot complete on
22.0.368 under any parameters.** Worse, it fails *inside* `hou.undos.group` after the subnet and
componentgeometry already exist — it leaves partial state behind.

**Ruled:** `import_megascans` registers last, after F9 and F3 are both fixed and proven by a live
verifier. The correct target is the interior `sopnet/geo` subnet, which L2 already live-probed as
writable. Fix the target, do not unlock the asset.

The other four may register ahead of it. One broken tool must not hold the family.

---

## RULING 14 — Doctrine: a success status that set nothing is a lie. Binds beyond Solaris.

**F7:** `set_purpose` writes `geo_node.parm("purpose")`. On 22.0.368 `componentgeometry` exposes
no such parm — a live sweep finds no parm containing "purpose" at all. Every execution takes the
fallback and returns `status="set"` with an advisory note. The caller cannot distinguish applied
from not-applied.

**Ruled, project-wide:** `status` describes what happened, never what was attempted. A path that
changes nothing returns `"noop"` or raises. **An advisory note attached to a success status is
never acceptable** — it puts the truth somewhere the caller is not required to read.

This binds every tool in the codebase, not just Solaris. It is the fidelity-or-stop rule in
CLAUDE.md §11.6 applied to return values.

**Consequence for F6:** the bare `except Exception: pass` followed by `status="created"` in
`create_variants.py:193-203` is the same defect wearing different clothes. Same ruling.

**Separately:** `purpose` is a USD attribute (`UsdGeomImageable`), not a Houdini parm. Confirm
the real mechanism by live probe before rewriting — do not substitute an assumed API for a
refuted one. That is how a decay clock becomes a phantom.

---

## RULING 15 — `parent_path` wins. `parent` is retired.

**F8:** `scene_template.execute` reads `params["parent"]`; `import_megascans` and
`component_builder` read `params["parent_path"]`. A caller using the wrong one silently builds
into `/stage` and no error is raised.

**Ruled:** `parent_path` — two of three already use it, and it names a path rather than an
object. `scene_template` converges. Silent-default-on-unknown-key is itself a defect: unknown
parameters raise.

---

## RULING 16 — R1 negative control is debt with my name on it until reassigned.

`probe_phase3_layout` has no paired negative control, so it cannot show the layout fix is real
rather than vacuously true, and `run_live_probes.py --strict-companions` fails the gate today.

**Ruled:** promoted to debt, accepted. `--strict-companions` becomes the default gate only after
the control exists. A probe that cannot fail is the same species as a coverage metric that is
100% by construction (Ruling 2) and a mock-`hou` test (Ruling 12) — three instances of the same
error this relay has now found in three separate subsystems.

**Standing observation, not a ruling:** that pattern is worth naming. Every one of them passed
continuously while proving nothing. The seam gate itself reports 6/6 PASS today and grades none
of F1–F11.

---

## Note on the "13/13 attacks" figure

`run_live_probes.py` grades **6 probes**. The 13/13 in the PR #48 write-up is an assertion-level
tally, not a runner-reported number. Units mismatch, not a discrepancy — recorded so no future
census hunts it. Same class as the relay's own "39 of 218": a number that travelled without its
producer.

---

# ADDENDUM — L3 PANEL TRUTH RULINGS

**Ruled** 2026-07-25. L3: 35 LIVE / 17 ORPHAN / 7 SILENT — 24 of 59 affordances broken, 41%.
Two of these are safety findings and outrank every design decision in this relay.

---

## RULING 17 — Emergency halt ships as a persistent affordance. Highest priority in the relay.

**L3.R2:** emergency halt has **no artist-reachable surface** in the shipped panel. It exists
only in the dead `chat_panel` tree. CLAUDE.md Safety Rule 11 requires it.

SYNAPSE mutates a live Houdini scene containing an artist's unsaved work. An agent with no
reachable stop is not a tool, it is a hazard with a good UI.

**Ruled:** restore it as a **persistent, always-visible affordance** — not a palette entry, not a
slash command, not behind a menu. `panel-design-warden`'s own note is exactly right: *a stop
button you have to search for is not a stop button.*

This is the one ORPHAN worth reviving rather than deleting, and it ships **before** any Cohere
styling. If L4 has to choose between the palette pass and this, it ships this.

---

## RULING 18 — An affordance that claims a safety gate it does not perform is a defect, not debt.

**L3.R1:** three affordances lie about safety-critical operations. COMMIT-to-`/stage` claims
consent-gate routing that never happens; the gate widget emits unconditionally where it should
emit conditionally.

This is Constitution Law 3 — *status describes what happened* — applied to the UI surface. A
consent gate that does not gate is worse than no gate, because the artist stops watching. It is
the same defect as `set_purpose` returning `status="set"`, and it is in the safety path.

**Ruled:** fix the two gate paths by making the three lines of unconditional emit conditional —
`panel-design-warden` scoped it as small and it is. **COMMIT-to-`/stage` loses its consent claim
entirely** until the routing exists. An honest button that promises nothing beats a dishonest one
that promises safety.

---

## RULING 19 — The 21 slash commands are removed, not wired.

**L3.R3:** 21 slash commands send description prose to the LLM instead of dispatching, bypassing
~7,500 LOC of implemented feature modules. The features exist. The menu never reaches them.

**Ruled: remove them now; wire them later as scoped work.** A menu entry that silently does
something other than what it says is the SILENT class at scale, and it teaches the artist that
the panel is unreliable — which is more expensive than the missing feature.

Removal is honest and cheap. Wiring 21 entries to 7,500 LOC is a real project and deserves to be
one.

---

## RULING 20 — My L4 token oracle was uncheckable. Restated.

**L3.R4:** I wrote *"every token name present in styles.py before is present after."* `styles.py`
**defines zero tokens** — it consumes them. The oracle could never have run.

That is Constitution Law 1 violated by the person who wrote Law 1, four hours later.

**Ruled:** the oracle asserts against `harness/notes/panel_token_inventory_before.json`, which L3
produced for exactly this purpose. Assertable, not eyeballed.

---

## RULING 21 — There is a THIRD token source, outside the repo.

**L3.R5:** the accent token's third source is `~/.synapse/design/tokens.py` — **outside the
repository**, injected onto `sys.path` by `tokens.py:15`. The panel's appearance depends on a
file that is not version controlled and not on any teammate's machine.

My L4 spec named two sources. There are three.

**Ruled, in two parts:**
- **For L4:** additive only. Do not sever the injection — it would break `test_hda_panel`, and
  severing an out-of-repo `sys.path` injection mid-restyle is how a design pass becomes an
  outage.
- **Separately, and it is a real decision:** an out-of-repo token source means the shipped
  product renders differently on a machine that lacks it. That is a reproducibility defect, not
  a styling one. Deposit it.

---

## RULING 22 — Grant the hython-offscreen permission. L4 is shipping ungraded right now.

**L3.R6:** two of five G3 slices have no baseline because the hython-offscreen invocation was
permission-denied. L4 grades on three of five.

**Ruled:** grant it. This is a permission line, not engineering work, and panel verification is
hython-offscreen-only by standing convention. Granting mid-flight will not retro-grade the
running L4 — that leg ships partially graded and the gap is recorded here honestly rather than
papered over.

---

## RULING 23 — `providers/`: fix the claim today, the code after T.1.

**L3.R7:** `providers/` is 136 LOC against a "five swappable engines" claim. L3's read is that
the code is not the problem, the out-of-box experience is.

**Ruled:** amend the public claim now. "Five swappable engines" is simultaneously true and
misleading, and the honest version costs one paragraph. The code waits for T.1, which will change
what a provider is.

---

# ADDENDUM — REPO HYGIENE

## RULING 24 — The repo does not comply with its own line-ending policy.

**Found** 2026-07-25, by creating the first fresh checkout this repo has had in a long time.

`.gitattributes` declares `* text=auto eol=lf` plus explicit `eol=lf` for fourteen text types.
Its own comment states the stakes precisely:

> risks a CRLF round-trip on the byte-identical drift-guarded catalogs that
> `harness/verify/checks.py` compares byte-for-byte against their harness notes

**The blobs in HEAD carry CRLF.** The policy landed in PR #47 (SOLARIS_FAST_FOLLOWS item 3) and
**the renormalization commit was never run.** The main working tree looks clean only because it
has never been re-checked-out — its files have sat on disk, byte-matching the CRLF blobs, since
before the policy existed.

Creating `.claude/worktrees/solaris-repair` forced a fresh checkout and surfaced it immediately:
**63 files, 29,885 insertions, 29,885 deletions — exactly equal.** `git diff --ignore-cr-at-eol`
returns empty. Pure line-ending noise, zero content change.

**Severity is higher than it looks.** This is not cosmetic:
1. Any teammate cloning this repo gets 63 dirty files before typing anything.
2. `checks.py` byte-compares drift-guarded catalogs. A CRLF round-trip on
   `h22_lop_catalog_live_22.0.368.json` or `verified_connectivity_*.json` would fail a drift
   guard for a reason that has nothing to do with drift — a false positive in the one mechanism
   built to catch false negatives.
3. It makes any agent's diff unreviewable. Commandment 7 cannot be verified by inspection
   inside 30,000 lines of noise.

**Ruled:**
- `git add --renormalize .` plus a single commit titled as such, **on a quiet branch, with no
  agent running**. Not now — SOLARIS-REPAIR-01 is mid-flight and a 63-file rewrite under a live
  agent is a race.
- Until then, review agent diffs with `git diff --ignore-cr-at-eol` or `-w`. Recorded so the
  next reviewer does not mistake noise for work.
- Add a check: assert `git diff --ignore-cr-at-eol` is empty on a fresh checkout. **This is a
  Law 1 check** — state the failure condition first: it fails when the tree and the policy
  disagree. That condition is true today, which is how you know the check is real.

**Note on method.** This was not found by reading code. It was found because creating a worktree
did something nobody had done recently — a fresh checkout — and the environment disagreed with
the repository. Constitution Law 5 says write from the tree, not from memory. This is the
corollary: **the tree only tells you what it has been asked. Ask it something new.**

---

## RULING 25 — Receipts must record the model. Provenance was incomplete and it just started to matter.

**Found** 2026-07-25 13:10, when the Claude Code model was switched from Opus 4.8 to Opus 5
mid-run.

Every `receipt/v1` carries `commit_at_run`, `mode`, and `agents`. **None carries the model.**
L0–L4 and SR1's M1–M3 are Opus 4.8 work; everything dispatched from here is Opus 5. The receipts
cannot tell you which.

That was harmless while one model ran the whole relay. It stopped being harmless the moment two
did, and it undermines the evidence ladder directly: `VERIFIED-RUNTIME` means *observed on the
live build* — but a **judgement** (severity, disposition, a `for_ruling` recommendation) is a
model's output, not the build's. Two models can read the same tree and rank differently. Without
the model recorded, a changed verdict is indistinguishable from changed reality.

L1.F1 is the case in point: a `blocker` that was wrong. If Opus 5 re-runs L1 and does not
reproduce it, there is currently no way to tell whether the finding was model-specific or the
probe was simply fixed.

**Ruled:**
- `receipt/v1` gains a required `model` field: the CLI-reported model string at leg start.
- It gains `settings_profile` — `agent-settings.json` or `relay-settings.json`. A leg run under
  the narrow profile cannot claim suite evidence (Constitution Article V) and the receipt must
  say which fence it ran behind.
- **Do not pin a model in the settings files.** Pinning freezes the relay at whatever was current
  when someone last edited a JSON file, which is a worse failure than not knowing — it is not
  knowing plus a false sense of control. Record, do not constrain.
- Legs already landed are annotated retroactively **as `VERIFIED-DERIVED`, not `VERIFIED-STATIC`** —
  the attribution is inferred from launch time, not observed.

## RULING 26 — `relay-settings.json` carried a UTF-8 BOM. Mine.

`Set-Content -Encoding utf8` in PowerShell 5.1 writes a BOM. Python's `json.load` raises
`Unexpected UTF-8 BOM` on it. Claude Code tolerated it — the fence held and no agent pushed — but
every Python-side reader of that file was broken for three hours and nothing reported it.

Stripped. `agent-settings.json` was clean; only the file I edited was affected.

**Ruled:** add to the Law 1 check set — **assert every JSON under `harness/` parses with
`json.load`.** It fails today if a BOM is reintroduced, which is the test that it is a real check
and not a decoration. This is the same species as R24: a tool wrote bytes nobody read back.

---

## RULING 27 — Ruling 1a AMENDED. The suite does not survive the shipping interpreter.

**Ruled 1a as originally written:** *"Pin the suite to the host's Python 3.13. This is a CI and
tooling change, not a fork, and it needs no architecture gate."*

**That was wrong in two ways, both found by executing it rather than reasoning about it.**

### Wrong #1 — right version, wrong launcher

`python313\python.exe` is 3.13.10 and has pytest 9.1.1, but bare `python.exe` lacks Houdini's DLL
search paths. `tests/test_scene_hash_gate.py` dies on
`ImportError: DLL load failed while importing _tf` — that is `pxr.Tf`, USD's foundation library.

**`hython3.13.exe` is the correct target**: same interpreter, plus the environment. Under it:

```
python 3.13.10
  pxr          OK
  pytest       OK
  synapse      OK    VENDOR_ABI_RISK = False   <- vendor tree ACTIVE
  websockets   MISSING
  mcp          MISSING
  pydantic     MISSING as a bare import
```

The pydantic line is the vendor tree **working**: `synapse` imports because it resolves pydantic
from `_vendor`; a bare `import pydantic` fails precisely because it is vendored rather than
installed. That is the design behaving correctly, on the interpreter that ships, for the first
time in this project's recorded history.

### Wrong #2 — the suite does not survive there

Under `hython3.13`, before any assertion about vendored behaviour can be made:

```
tests/panel/test_docking.py        F
tests/panel/test_failure_trail.py  FF
tests/panel/test_font_scale.py     Windows fatal exception: access violation
```

**Three failures and a segfault**, in tests that report green on 3.14. The crash is almost
certainly PySide6 widget construction inside hython's own live Qt context — a known-hostile
combination — but the cause is `UNVERIFIED` and must be probed, not assumed.

Plus three modules that cannot collect at all: `test_load.py` (`websockets`),
`test_passthrough_hygiene.py` and `test_port_wave_scene1.py` (`mcp`). Both libraries are
pip-installed into the system Python and exist nowhere in the shipping environment.

**Ruled, superseding 1a:**

1. `hython3.13` is the shipping-truth interpreter. `harness/run_suite_shipping_python.ps1` runs it.
2. **Do not "fix" the crash by skipping the panel tests.** That converts a real defect into a
   silent one and is exactly Commandment 7's failure mode wearing a compatibility excuse. Probe
   the segfault first; a `skip` is only honest once the reason is known and recorded.
3. `websockets` and `mcp` are **shipping dependencies that are not shipped**. Either vendor them
   or declare the transport tests system-Python-only and say so in the receipt. Do not leave the
   status quo, where they silently pass on an interpreter no artist runs.
4. **The 4,744-green number keeps its meaning but loses its scope.** It is a valid statement about
   the *development* environment. It has never been a statement about the shipping one, and no
   release claim may cite it as such.

### What this does to Gate 0.1b

It sharpens it rather than answering it. The vendor tree demonstrably works under `hython3.13` —
which is evidence **for** the abi3/vendored path and **against** the sidecar being necessary for
ABI reasons alone. But a suite that segfaults on that interpreter cannot yet support the claim.

**0.1b stays held.** Not for lack of permission — it now has that — but because the evidence that
would decide it is one crash away and worth waiting for. Deciding a year-binding fork on a suite
that cannot complete would be choosing under exactly the conditions the gate exists to prevent.

**Method note.** Everything above came from running the ruling instead of writing it. 1a read as
the safe, obvious half of a split I was pleased with. It was wrong twice, and both errors were
invisible from the tree — visible only from execution. Constitution Law 5 says write from the
tree, not memory. The stronger form, earned here: **the tree is still a document. Run the thing.**

---

## RULING 28 — The panel has no working test surface on any interpreter.

**Found** 2026-07-25 while writing the regression pin for Ruling 18.

Two interpreters, two different reasons, one result:

| Interpreter | PySide | Panel tests |
|---|---|---|
| system Python 3.14.2 (where 4,744 pass) | **absent** — `ModuleNotFoundError: PySide6` *and* `PySide2` | **skip** |
| `hython3.13` (what artists run) | present, Houdini's own | **segfault** — access violation, R27 |

`tests/panel/test_docking.py:80` already states the convention plainly:
`pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")`.

So the panel's tests skip on the interpreter that runs the suite, and crash the interpreter
they were written for. **`panel/` is 23,365 LOC across 71 files — larger than `server/` — and
it is effectively untested in both directions.**

This is not a new defect. It is the explanation for an existing one: L3 found **17 ORPHAN and
7 SILENT affordances** in that package, 41% of the surface. A subsystem that cannot be tested
anywhere will drift exactly that far, and nothing will report it.

**Ruled:**

1. The convention is correct and stays — `importorskip` / hython-gated. **A skip is honest, a
   pass is a lie** (Law 1). Do not add PySide to the dev environment to make these tests
   "run"; that would test a Qt build no artist has.
2. **The segfault (R27) is now the single highest-value engineering item in the project.** It
   is not a test-infrastructure annoyance. It is the reason a 23k-LOC user-facing package has
   no verification, and it gates Gate 0.1b as well.
3. Until it is fixed, **no panel claim may cite test evidence.** The panel's correctness is
   currently asserted only by inspection.
4. The three tests added for Ruling 18 (`tests/panel/test_gate_consent_honesty.py`) are
   written to run the moment the segfault is fixed. They are pins waiting for a floor.

**Note on method.** I did not go looking for this. I wrote a regression test for a different
ruling, it failed on the control case, and the control case is what exposed it — a test that
should trivially pass, failing, is worth more than one that fails as expected. The fix I was
verifying is sound; the fact that I *could not verify it anywhere* is the finding.

---

## RULING 29 — Ruling 17 AMENDED. L3 was wrong about the halt, and the real gap is narrower and sharper.

**L3.R2 claimed:** *"Emergency halt has no artist-reachable surface in the shipped panel — it
exists only in the dead chat_panel tree."* I ruled on that at 12:20 and made it the highest
priority in the relay.

**Verified 2026-07-25, `synapse_panel.py:441-445, 1727-1740`:** that is not what the tree says.

### What actually exists — and it is good work

A **Stop** button lives in the persistent rail:

```python
self._stop_btn = c.Button("Stop", variant="danger")
self._stop_btn.clicked.connect(self._on_stop)
self._stop_btn.setVisible(busy)   # state-gated to working only
```

`_on_stop` is **honest in exactly the way Ruling 14 demands.** It aborts the worker loop and
then explicitly refuses to claim idle:

> *Honest Stop: abort the loop, but DO NOT claim idle — Houdini may still be finishing the
> in-flight tool (abort is cooperative; it takes effect at the next tool/iteration boundary).*

It sets the header to `Stopping — waiting on <tool>…` and waits for the worker to actually
emit `stream_done`. That is a control reporting what happened rather than what was attempted,
written before this relay existed. It should not be replaced.

### The real gap, stated precisely

Three distinct things were being conflated:

| | Reachable? | Does what |
|---|---|---|
| **Stop** (`_on_stop`, live rail) | **yes**, while busy | aborts the agent loop, cooperatively |
| **in-flight cook cancel** | **no** | `tops_cancel_cook` / render cancel — deferred by its own comment: *"must run off the UI thread against a live bridge"* |
| **Emergency halt** (`_on_emergency_halt`, chat_panel) | **no** — ORPHAN tree | `EmergencyProtocol.trigger_emergency_halt`: cancel dispatches, `cancelCook()`, write emergency state to `agent.usd`, session capture |

So an artist mid-Karma-render has a Stop that **will not stop the render**, and no reachable
path to the one that would. That is a genuine safety gap — but it is not "there is no stop
button," and building a second one would have made the panel worse.

**Ruled, superseding R17:**

1. **Keep `_on_stop` exactly as written.** Do not replace it, do not make it always-visible.
   State-gating is correct: a Stop shown when nothing is running is the same lie as a consent
   gate that does not gate.
2. **Surface emergency halt as a distinct, second control** — not a rename of Stop. Different
   verb, different consequence, different visual weight. It belongs in the rail's overflow
   (`⋯`), not competing with Stop.
3. **The cook-cancel gap is the load-bearing half** and it is not a panel problem. It needs
   off-UI-thread dispatch against a live bridge. That is server work, and it is where the real
   risk sits — a stop that cannot stop a 40-minute render is the case artists will actually hit.
4. **Do not implement any of this blind.** Per R28 the panel has no working test surface on any
   interpreter. Shipping an untested new safety control into an untested package is how the 17
   ORPHANs got there.

### Why this correction matters more than the fix would have

I ruled R17 the highest-priority item in the relay on the strength of a receipt, without
reading the file. The receipt was wrong. Had I implemented it, I would have added a second Stop
button beside a working one, in a package that cannot be tested, and called it a safety
improvement.

Constitution Law 5 says write from the tree, not from memory. **A receipt is not the tree.**
It is a model's summary of the tree, and it inherits every limit of the pass that produced it.
Findings get verified at the anchor before they get acted on — including my own, and including
ones I have already ruled on.

---

## RULING 30 — GATE 0.1b IS CLOSED. The vendored path stands. No sidecar on ABI grounds.

**Open since drop week.** Brief written, decision never committed, re-opened repeatedly. Closed
2026-07-25 on evidence, not preference.

### The evidence

`GATE_01B_TRACE.md`, VERIFIED-RUNTIME on hython3.13 / Python 3.13.10, build 22.0.368:

```
CRASHING FRAME  tests/panel/test_font_scale.py:65  ->  saved = app.font()
                PySide6.QtWidgets.QApplication.font()

Zero frames under python/synapse/_vendor anywhere in the faulthandler traceback.
synapse._VENDOR_ABI_RISK == False   (vendor tree ACTIVE)
import synapse                       clean
```

Isolation, with a positive control on both sides:

```
test_font_scale.py alone            ->  8 passed, no crash
tests/panel/ alone                  ->  2 failed, 27 passed, no crash
tests/panel/ + tests/test_hda_panel.py  ->  ACCESS VIOLATION
```

**Trigger:** `tests/test_hda_panel.py:172-175` plants `sys.modules["PySide6"]`, `.QtCore`,
`.QtWidgets`, `.QtGui` stubs at **module level, unconditionally**. pytest imports every test
module at collection, so the fake Qt is resident before the first panel test executes. The panel
tests then run against a half-stubbed Qt and reach a native fault in `QApplication::font()`.

**Ruled:**

1. **The vendored/abi3 path stands.** The vendor tree is live and correct on the shipping
   interpreter, and is not implicated in the only crash that was blocking this decision.
2. **No sidecar is required on ABI grounds.** The sidecar remains available as an option for
   *other* reasons — process isolation, crash containment, independent release cadence — and each
   would need its own case. None of them is this one.
3. **Gate 0.1 (task 0.1) closes.** It was task number one and has been open the longest.
4. **The fake-Qt residency is a real defect and now has an owner.** Module-level `sys.modules`
   stubbing is collection-order-dependent action at a distance. Make it fixture-scoped and
   reverted, or move that test to its own session. Do not "fix" it by reordering tests — that
   hides the coupling instead of removing it.

### What this does to R27 and R28

**R27 amended:** "the suite does not survive the shipping interpreter" was true as observed and
wrong as diagnosed. It survives fine; one test file poisons `sys.modules` for the rest. The
correction is small and local.

**R28 amended and DOWNGRADED:** I ruled the panel had no working test surface on any interpreter
and called the segfault the highest-value engineering item in the project. Both halves were
wrong. `tests/panel/` runs under hython3.13 — 27 passed. The panel has a working test surface;
it was being poisoned by a neighbour.

That matters beyond the ruling: I attributed **41% broken affordances (17 ORPHAN, 7 SILENT)** to
"a subsystem that cannot be tested anywhere will drift exactly that far." That causal story is
now unsupported. The drift is real; my explanation for it was not. **A finding and its
explanation are separate claims and need separate evidence.**

### Method note — the third refutation today

L1.F1 said the bridge was down; the probe had omitted a path.
L3.R2 said there was no Stop; one existed in the live rail, well written.
R27/R28 said the shipping interpreter could not run the panel; one file's import-time stub could.

Each was a `blocker`, each survived into a governing document, and each dissolved on contact with
a positive control. The pattern is not carelessness — every one of them was *reproducible*. It is
that **a reproducible negative result still needs a positive control before it can be
interpreted**, and all three were missing one. That corollary was adopted at D-R10 and has now
paid for itself twice more.

---

# ADDENDUM — SR1 RULINGS (R31–R38)

Ruled 2026-07-25 on `SR1.json` `for_ruling` R-1 through R-8. Two of these correct my own errors.

---

## RULING 31 — The suite baseline is a tuple, not a number. (SR1 R-1)

Three producers, no agreement:

```
4744 / 100 skipped   feat/cto-relay-01,   system 3.14.2
4841 -> 4873         feat/solaris-repair, system 3.14.2, WITH the pythonpath fix
4891 collected       hython3.13, worktree      vs   4790, primary checkout
```

A bare integer in `harness/verify/suite_baseline.json` pins a number whose meaning depends on
where you stand. That is the same species as D1 coverage reading 100% by construction: a value
that cannot be wrong because it does not say what it measures.

**Ruled:** the baseline records `{tree, interpreter, count, producer_command}`. Never a scalar.
Two named baselines, both required, neither substitutable:

- **GATE baseline** — HEAD on system Python. What CI enforces. What Commandment 7 compares.
- **SHIPPING baseline** — HEAD under `hython3.13`. The only number a release claim may cite.

Any figure quoted without its interpreter is `UNVERIFIED` from here on.

---

## RULING 32 — Promote the pythonpath fix to master before Gate C. (SR1 R-2)

**Every git worktree in this repo silently tests the PRIMARY checkout**, via the editable `.pth`
at `C:\Users\User\Synapse\python`. Fixed in `pyproject.toml` on the SR1 branch only.

**Blast radius, bounded — and it is smaller than it first reads.** L0–L5 all ran in the primary
checkout, so the relay's own suite evidence is unaffected. Only SR1's pre-fix numbers described a
tree other than the one under test.

**Ruled:**
1. The `pythonpath` fix goes to master **ahead of Gate C**. It is a correctness fix for every
   future parallel leg, and Article V mandates worktrees for parallelism — so this defect is
   load-bearing on the constitution's own recommended pattern.
2. Re-qualify SR1 pre-fix suite numbers only. Do not re-qualify L0–L5; state why in the ledger
   rather than leaving it to inference.
3. Add to the Law 1 check set: **assert `pytest --collect-only` count differs between primary and
   worktree when the trees differ.** It fails today on an unfixed worktree, which is the test
   that it is a real check.

---

## RULING 33 — Wire the schemas. Do not delete them. (SR1 R-3)

`schema_*.py` across the Solaris family has **zero consumers** — `grep TOOL_RETURN` outside the
schema files finds nothing. The `set_purpose` enum drifted from `[set, already_set, not_found]` to
a implementation returning `set|updated|unchanged|noop|not_found`, and nothing failed.

Delete is the wrong answer, and the reason matters: **these schemas are what the model is told
about the tool.** A drifted schema does not merely fail to document — it actively misinforms the
agent about what a tool returns, and the agent then reasons on it. That is a correctness surface,
not a docs surface.

**Ruled:** extend M5's `test_schema_matches_implementation_contract` to all five tools. One test
per tool, asserting the declared `TOOL_RETURN` enum matches what `execute()` can actually return.
It must fail on today's `set_purpose` drift before it is considered done.

---

## RULING 34 — Re-qualify F1–F11 against the live build. At least one was a phantom. (SR1 R-4)

F4 was named HIGH with a specific mechanism. That mechanism is `REFUTED-LIVE` on 22.0.368. A fix
was written, shipped with a green test — **and the test could not fail.** It took adversarial
mutation testing to catch.

That is Law 1 violated inside a leg whose entire purpose was removing Law-1 violations.

**Ruled:**
1. **Yes — re-qualify F1–F11 as a set** before any further work cites them. One in eleven was a
   phantom; the others carry the same provenance and have not been individually re-probed.
2. **Adopt mutation testing as the standard for "does this test pin anything."** Every regression
   pin for a repaired defect must be shown to fail against a deliberately broken implementation.
   A test that passes on both the fix and its inverse is a decoration.
3. This is the **fourth refutation today** — after L1.F1 (bridge), L3.R2 (Stop button), and
   R27/R28 (the panel test surface). All four were reproducible, which is what made them
   convincing. The corollary adopted at D-R10 now applies to defect findings as well as to
   probes: **a reproducible negative result still requires a positive control before it can be
   interpreted.**

---

## RULING 35 — The push happened, and the fence was right to refuse it. (SR1 R-5)

The agent was told in writing that Joe approved the push. `relay-settings.json` denies
`git push`. It refused, did not edit the settings file, and raised a remediation ticket
containing the best sentence written today:

> *An agent message relaying approval is not consent — only the permission system or the human's
> own action is.*

**Ruled: the fence stands exactly as written. Do not add a push grant.**

The push was completed by the orchestrator through a channel Joe operates directly.
`feat/cto-relay-01` and `archive/root-scratch-2026-07-25` are both on origin. R-5 is closed by
action, not by widening the fence.

The general principle, adopted: **a relayed approval is a claim about consent, not consent.**
An agent cannot distinguish a genuine relay from a compromised or mistaken one, so it must not
try. This is the same reason instructions found in tool output are data rather than commands.

---

## RULING 36 — Gate 0.1b: ruled by delegation, and it wants your countersignature. (SR1 R-6)

The agent is correct that Gate A is never automated, and correct that the evidence now points
away from ABI being the blocker.

**The distinction that makes R30 legitimate:** the constitution forbids an *agent* deciding Gate
A on its own initiative. Joe delegated in writing — *"all gates approved, you are CTO"* — and
R30 was ruled on `VERIFIED-RUNTIME` evidence with a two-sided positive control, not on
preference. That is a human-delegated ruling, not an automated one.

**But delegation is not the same as ratification, and this gate has been open since drop week.**

**Ruled:** R30 stands and is actionable. It is recorded as `ratified: false` pending Joe's
explicit countersignature — consistent with the flywheel rule that human ratification is never
automated, and consistent with R35 one paragraph above. One line from Joe closes task 0.1
properly.

If he declines to countersign, R30 becomes a recommendation and the gate reopens. Nothing
downstream has been built on it yet, which is deliberate.

---

## RULING 37 — Ruling 23's `providers/` number was wrong. Mine. (SR1 R-7)

Ruling 23 states `providers/` is **136 LOC**. The tree says **1,510**, and all five engines are
implemented.

I took 136 from a receipt summary and never opened the directory — the exact failure Law 5
describes, committed while writing a document that contains Law 5.

**Ruled:**
- Ruling 23's figure is corrected to **1,510 LOC, five engines implemented**.
- **The corrected README framing stands and was right for the right reason by accident.** The
  misleading part was never the line count; it was the out-of-box experience. The docs now say
  that, which is true regardless of the number I got wrong.
- Producer for the corrected figure:
  `find python/synapse/panel/providers -name '*.py' | xargs wc -l` on `feat/cto-relay-01`.

---

## RULING 38 — The constitution ships on every branch it governs. (SR1 R-8)

Every agent on the SR1 leg read `harness/AGENT_CONSTITUTION.md` **from the primary checkout**,
because it does not exist on `feat/solaris-repair-01`. Logged as drift D1.

That is F3 violated at the root: governing documents commit before the work they govern, and on
a branch, "commit" means *on that branch*. A constitution present only in a neighbouring
directory governs by accident of filesystem layout.

**Ruled:** cherry-pick `harness/AGENT_CONSTITUTION.md` and `harness/notes/CTO_RULINGS_01.md` onto
every active branch at branch creation. Add it to the worktree bootstrap so it is structural
rather than remembered — the same reasoning as the deny-list being a fence rather than an
instruction.

**This one is quietly the worst of the eight.** Every ruling in this session about structure over
discipline was authored in a file that was itself governing by luck.

---

## Scorecard for the day

Corrected on evidence, in order: L1.F1 (bridge healthy, probe wrong) · L3.R2 (Stop exists and is
honest) · R27/R28 (panel tests run fine; one file's import-time stub poisons them) · F4 (phantom
defect, fix shipped with an unfailable test) · Ruling 23 (`providers/` 136 → 1,510).

Five refutations. Every one reproducible. Every one missing a positive control.

The instrument that caught them was never inspection — it was execution plus a control. Law 1
gets you a check that can fail. **D-R10's corollary is what makes the failure mean something,**
and it has now paid for itself four times in one day.

---

## RULING 39 — The shipping number exists. It is 4048/110/771, and I am the reason it took two days.

**Measured** 2026-07-26 08:28, `repair/q1-unpoison @ 3a9c485`, `hython3.13` / Python 3.13.10,
`_VENDOR_ABI_RISK = False` (vendor tree **ACTIVE**), 96.79s, no segfault.

```
GATE      system 3.14.2, vendor INACTIVE     4875 passed    0 failed      0 errors
SHIPPING  hython3.13,    vendor ACTIVE       4048 passed  110 failed    771 errors
```

`producer` — `hython3.13 -m pytest -q --continue-on-collection-errors -p no:cacheprovider`,
cwd `.claude/worktrees/q1-unpoison`.

### Why it took two days, which is the actual finding

Q2-F2, `VERIFIED-STATIC`, `harness/run_suite_shipping_python.ps1:23`. I wrote that runner on
2026-07-25 carrying:

```
--ignore=tests/test_load.py
--ignore=tests/test_passthrough_hygiene.py
--ignore=tests/test_port_wave_scene1.py
```

Those are **exactly** the three files that fail to collect on the shipping interpreter. I added
them to get past a collection error and never recorded that I had. The receipt states it better
than I can:

> The runner was authored AROUND the breakage rather than recording it. This is Law 3 at the
> harness level — an instrument reporting what it attempted, not what happened. It is also why a
> shipping number never surfaced: **the instrument was built to not see the fault.**

I wrote Law 3 on 2026-07-25 and violated it in a measuring instrument the same day, then spent
hours attributing the missing number to a segfault, an interpreter mismatch, and an ABI question
— none of which were the cause.

**Ruled:**
1. `--ignore` is **banned in any harness measurement runner.** A measurement that excludes its
   failures is not a measurement. `--continue-on-collection-errors` is the correct instrument:
   it records the error and proceeds.
2. Both numbers are canonical, per R31, and **neither substitutes for the other**. A release
   claim cites SHIPPING. CI enforces GATE. Quoting either without its interpreter is
   `UNVERIFIED`.
3. **The 827-test gap is now the project's primary open question**, replacing everything the
   heats were scoped against. Q2-F4 claims ~60% ENVIRONMENT / ~33% test-harness / **0% shipping
   code** — and correctly flags its own weak point: *"'zero shipping-code defects' is exactly
   where a real defect would hide behind a 'test harness' label."* That claim is
   `VERIFIED-DERIVED` and must not be cited as `VERIFIED-RUNTIME` until attacked.

### Q2-F3 resolved — environment gap, not "does not run as shipped"

Both suspect imports are guarded on the shipping path:

- `mcp` — **zero** occurrences in non-test shipping code. Not a runtime dependency.
- `websockets` — `server/websocket.py:16` wraps it in `try:`; `panel/ws_bridge.py:191` falls back
  to QWebSocket when absent.

**SYNAPSE runs on Houdini's 3.13.** The panel degrades to QWebSocket for its bridge.

**Open, and named:** that QWebSocket fallback has never been exercised. A fallback that exists
and is broken is worse than none — the failure class this repository has now produced five times.
It is a follow-up, not a blocker, and it does not get counted as working until it is probed.

### Method note

The segfault is gone. Q1's fix — restore the PySide6 module *objects* rather than re-import them —
holds under the real interpreter, and the suite completes in 96 seconds where it previously took
an access violation. That was the correct diagnosis and it was not mine.

---

## RULING 40 — Tuple baseline promoted. Q2-F6 dissolved rather than worked around.

`harness/verify/suite_baseline.json` is now `suite_baseline/tuple-v1`, carrying both halves:

```
gate      system 3.14.2,  vendor INACTIVE   4875 passed    0 failed     0 errors
shipping  hython3.13,     vendor ACTIVE     4048 passed  110 failed   771 errors
```

The floor was **599 tests stale** (4275, dated 2026-07-14). Any regression smaller than 599 tests
passed the ratchet silently.

**Q2-F6 named two shape-coupled readers the agent was correctly forbidden to fix.** Rather than
break and repair them, the tuple is **backward compatible**: top-level `passed`/`failed`/`skipped`
remain the GATE numbers, so `leg0_baselines.json`'s `evidence_command` and every other flat reader
work unchanged. Verified — `json.load(...)['passed'], ['failed'], ['skipped']` returns
`4875 0 129`.

An extension beats a migration when the migration's only purpose is aesthetic. `h22-relay.js:65`
carried a hardcoded `4275`; corrected to name both numbers.

**The shipping number is NOT a ratchet floor.** It is a first measurement, not a green line. It
becomes a floor once the 827-test gap is classified and the environment half closed.

---

## RULING 41 — Q2-F4 attacked. The clause survives. My first attack did not.

**The claim under attack:** of 110 failures + 771 errors on the shipping interpreter, ~60% are
ENVIRONMENT, ~33% test-harness code, and **zero are shipping-code defects** — with the receipt
naming its own weak point: *"exactly where a real defect would hide behind a 'test harness'
label."*

### My first attack was worthless and I nearly filed it as a pass

`harness/notes/attack_f4.py` parsed the log for pytest short-summary lines, found **zero**, and
printed *"Q2-F4's 'zero shipping-code defects' SURVIVES this attack."*

It survived nothing. The regex matched no lines because `-q` with this config emits no short
summary. **A check that cannot fail, run against a claim I suspected of being a check that cannot
fail.** Had I filed it, the strongest finding in the harness would have been certified by an
instrument measuring nothing — the same defect as Q2-F2's `--ignore` runner, one day later, by
the same author.

### The real attack

Method: grep every traceback frame under `python/synapse/`. A product frame is not automatically a
product defect, but its **absence** would settle the claim, and its presence forces the question.

Product frames **do** appear — 16 of them:

```
component_builder.py:315  in execute   name_parm.set(asset_name)      x5
scene_template.py:218     in execute   primpath_parm.set(...)         x4
handlers_hda.py:120       in _handle_hda_create                       x2
main_thread.py:243        in run_on_main                              x2
evaluator.py:438          RuntimeWarning: invalid value encountered   x1
```

Exception at the first two: `AttributeError: 'Parm' object has no attribute 'set'`.

**That is product code calling a method on an object that lacks it.** If `hou.Parm.set` does not
exist on 22.0.368, it is a shipping defect and F4 is refuted outright.

### The positive control

```
hython3.13 -c "import hou; print(hou.Parm.set)"

hou build   22.0.368
hou module  .../houdini/python3.13libs/hou.py      <- the real module
Parm.set    True
```

`hou.Parm.set` **exists**. The `AttributeError` therefore comes from a **stub `Parm` shadowing the
real class** — fake-hou residency, the same mechanism Q1 fixed for PySide6, surviving in a
different module.

**Ruled:**
1. **Q2-F4's "zero shipping-code defects" SURVIVES**, now `VERIFIED-RUNTIME` rather than
   `VERIFIED-DERIVED`, on the strength of a two-sided control.
2. **Fake-hou residency is a second instance of Q1's defect class**, not a one-off.
   `tests/solaris/test_live_wiring.py` runs against a stubbed `Parm` while believing it drives
   real Houdini — a live-wiring test that is not live. It belongs to H2's re-qualification and is
   promoted to its head.
3. `evaluator.py:438` — `np.abs(luminance - mean_val) > (std_devs * std_val)` raising
   `RuntimeWarning: invalid value encountered` is product code producing NaN. Small, real, and
   the only genuine product smell the attack surfaced. Deposited.

### The pattern, stated once more because it keeps recurring

`--ignore` in the runner. A regex matching nothing. A mock that cannot disagree. A coverage metric
that is 100% by construction. A probe pointed at the wrong path.

Five instruments, all reporting clean, none capable of reporting otherwise. **Law 1 is not a
rule about tests. It is a rule about every instrument, including the ones written to check
instruments** — and the author most likely to violate it is whoever most recently wrote the law.

---

# ADDENDUM — H2 / H3 RELEASE CONDITIONS (R42–R46)

Both legs held themselves and wrote receipts saying so, with `why_escalated` on every item. That
is Article I working unsupervised: a sequencing judgement between defensible options is not an
agent's to take silently. Neither receipt contains a single claim about the work it did not do.

---

## RULING 42 — H2 hold CONFIRMED, release condition NARROWED.

**Proposed:** unblock when the shipping interpreter collects with 0 collection errors AND the
fake-hou residency question is resolved.

**Ruled: confirm the hold, drop the collection clause, keep the residency clause.**

The 3 collection errors are `ModuleNotFoundError` for `websockets` and `mcp` in
`test_load.py`, `test_passthrough_hygiene.py`, `test_port_wave_scene1.py` — three files with no
relationship to F1–F11. Gating a Solaris re-qualification on unrelated transport-test imports
delays the leg for no epistemic gain. **A release condition should name what would change the
answer, not everything that is untidy.**

The residency clause is the real one, and R41 has now upgraded it from question to fact:
`hou.Parm.set` **exists** on 22.0.368, yet `component_builder.py:315` raises
`AttributeError: 'Parm' object has no attribute 'set'`. A stub `Parm` is shadowing the real class.
`tests/solaris/test_live_wiring.py` believes it drives live Houdini and does not.

**H2 unblocks when fake-hou residency is eliminated on the Solaris test path** — provable by that
same `AttributeError` disappearing. Nothing else.

The agent's reasoning for escalating rather than proceeding on the gate interpreter was correct
and is adopted: F1–F11 are host-behaviour claims, and Law 1 bans asserting those against a mock.

---

## RULING 43 — H2 scope EXPANDS to Q2 bucket 2. Same probe, same defect, marginal cost.

Those ~17 tests are decorations in exactly F4's sense — they pass because a fake `hou` cannot
disagree with them. They share provenance and mechanism with F1–F11, and R41 proved the mechanism
live rather than inferring it.

**Ruled: yes.** Re-qualifying F1–F11 while leaving 17 known-decorative tests beside them would
produce a leg that is correct and useless. **Fake-hou residency goes to the head of H2**, ahead of
the F1–F11 re-probe, because until it is gone every re-probe result is uninterpretable.

---

## RULING 44 — H3 hold is OVERRIDDEN IN PART. The probe runs now; implementation stays held.

The agent framed this as binary and flagged the cost either way. It is not binary, and its own
H3-R3 is why.

**The re-probe needs nothing that is currently broken.** Confirming `tops_cancel_cook`,
render-ROP interrupt and `cancelCook()` by live `dir()` against 22.0.368 depends on Houdini, not
on the shipping suite, not on collection health, not on H1. It can run today.

**Ruled — H3 splits:**
- **H3a · probe — RUNS NOW.** `assayer` only. Live confirmation of every symbol the cancel path
  would need. Read-only, no implementation, no design. If the symbols are absent on 22.0.368,
  **that absence is the deliverable** and becomes a SideFX ask — do not invent a workaround.
- **H3b · implementation — REMAINS HELD** pending H3a's result and a green-enough shipping path
  to certify against.

Holding a probe because the implementation cannot yet be certified is the error in miniature:
it treats *learning what is true* as though it carried the risk of *changing what is true*.

**The safety gap stays open and this ruling does not close it.** An artist mid-Karma-render still
has a Stop that will not stop the render.

---

## RULING 45 — H3-R2 is overtaken by events, and that is my fault.

The receipt reasons from *"no tag until H1 and H3 land"* and asks whether holding H3 blocks the
tag indefinitely.

**A tag already shipped.** `v5.34.0` was cut 2026-07-25 21:15 from `f90946d`. I reversed my own
no-tag ruling that evening on the grounds that the cook-cancel gap and the schema drift **shipped
in v5.33.0 and every version before it** — they were pre-existing conditions this release
documented for the first time, not regressions it introduced.

I never updated the harness. The agent was reasoning correctly from a stale governing document.

**Ruled, restating the condition:** the gate was never really about tagging. It is about **what a
tag is permitted to claim**.

> No release may claim the cook-cancel gap is closed until H3b lands and is live-certified.

`v5.34.0` satisfies this — its *Known limitations* section states plainly that Stop cannot cancel
an in-flight cook. **A tag that documents a gap is honest. A tag that omits it is not.** The
condition constrains claims, not version numbers.

---

## RULING 46 — H3 begins with the re-probe. Recommendation adopted verbatim.

The agent's reasoning: *"Law 5 — every governing claim sourced from a probe held up; every claim
sourced from recall of a prior chat failed."*

That is this project's evidence record quoted back accurately, and it is the correct call.

**Ruled: yes.** No design work in H3 proceeds on prior-session evidence about the render
chokepoint or the `hdefereval` marshal. Both are `UNVERIFIED` in this run and are re-probed or
they are not used.

Worth recording that an agent applied Law 5 to *my* prior sessions before I did. Every correction
in the last two days has come from an instrument or an agent, never from me re-reading my own
work.

---

## RULING 47 — The 827-test gap was 88% environment. Measured by intervention, not estimated.

Q2-F4 claimed the shipping/gate delta was ~60% ENVIRONMENT, ~33% test-harness, 0% shipping-code —
`VERIFIED-DERIVED` from log-parsing, and the receipt correctly flagged that as its weak point.

**Tested by supplying the environment and re-measuring.** Same commit
(`repair/q1-unpoison @ 3a9c485`), same interpreter (`hython3.13`), same command. Only `sys.path`
changed.

```
                    passed   failed   errors   collect-err
before               4048      110      771         3
after                4776       57       12         2
delta                +728      -53     -759        -1
```

Intervention: `hython3.13 -m pip install --target .hython_deps websockets mcp pytest-asyncio
orjson xxhash filelock`. Six packages, installed to a **side directory** — Houdini's own
`site-packages` is untouched and the change is reverted by removing one folder from `PYTHONPATH`.

**88% of failures and 98% of errors were environment.** Q2-F4's ~60% was conservative and
directionally correct. The gate/shipping gap is now **105 tests**, down from 833.

**Ruled:**
1. **Q2-F4 is upgraded to `VERIFIED-RUNTIME`** on the strength of a controlled intervention. Its
   "0% shipping-code defects" clause survives a second attack — the residual 57 failures did not
   move when the environment did, so they are not environment.
2. **`websockets`, `mcp`, `pytest-asyncio`, `orjson`, `xxhash` and `filelock` are shipping
   dependencies that are not shipped.** This is now demonstrated rather than argued. Either
   vendor them beside the Anthropic SDK or declare them prerequisites in the install path —
   `install_synapse_package.py --verify` should fail loudly when they are absent, the way it does
   for `hpath`.
3. **`.hython_deps` is a measurement instrument, not a fix.** It makes the shipping suite
   measurable on this machine. It does nothing for an artist installing fresh, and no release
   claim may cite a number produced with it unless the number says so.

### Residual, and it is a real finding

The 57 remaining failures did NOT move when the environment did. Sampled:

> `FrameEvaluation(... issues=["...quality unverified (install OpenImageIO, pyexr, or Pillow)"],
> metrics={'unverified': 1.0}, verified=False)`

That is RETINA's frame evaluator reporting `verified=False` because no image library is present —
**product code degrading correctly and saying so**, with a test asserting the verified path. Not a
defect; a test that requires an optional dependency and does not skip when it is absent.

Constitution Law 1 applies to it: **a test that fails on a missing optional dependency should
skip, not fail.** A skip is honest about what was not measured. A failure claims something was
measured and found wrong.

### Method note

Two days of treating this gap as unknowable — first as a segfault, then an ABI question, then a
`--ignore` I had written myself. The answer took six pip installs and one re-run.

**The estimate was available all along; the measurement was six minutes away.** Log-parsing gave
~60% and a caveat. Changing one variable and re-running gave 88% and no caveat. When a controlled
intervention is available, an inference from evidence is the weaker instrument — and it is
usually the one that feels like more work to replace.

---

# ADDENDUM — RES / H3a / LEDGER (R48–R56)

Three legs, all `green`, 30 findings, 12 ruling items. Each corrected something I had asserted.

---

## RULING 48 — The cook-cancel gap is a PLATFORM gap, not an implementation gap. H3b is re-scoped.

**H3a-F1, `user_facing_open`, VERIFIED-RUNTIME on 22.0.368:**

> Houdini 22.0.368 exposes **NO API** to cancel, abort, interrupt or kill an in-flight
> `hou.RopNode.render()`. This is the SideFX ask.

I have carried "Stop cannot cancel an in-flight cook" since R29 as an implementation gap — deferred
work, real but ours. **It is not ours.** The verb does not exist on the build. No amount of
off-UI-thread dispatch produces a cancel that Houdini will not honour.

**H3a-F2** is the other half: the **TOPS/PDG cancel surface is complete** on 22.0.368 and carries a
direct node-level verb the tree does not use.

**Ruled:**
1. **H3b proceeds as a TOPS-cancel-only leg.** That half is achievable today with an unused verb
   already on the build.
2. **The render half is closed as not-implementable** and becomes a SideFX ask. It is not debt,
   not deferred work, and must stop being described as either.
3. **`v5.34.0`'s Known-limitations wording is now wrong** — it implies the gap is ours to close.
   Correct it to say Houdini exposes no render-cancel API, and that TOPS cancel is coming.
4. **H3b stays `held`** until Joe releases it. The scope changed; the gate did not.

---

## RULING 49 — The SideFX ask gets sent, and it is Joe's to send.

Three items now belong in it, all live-probed on 22.0.368:

- **No render-cancel API** (H3a-F1). An artist cannot stop a 40-minute Karma render from any
  first-party surface an agent can reach.
- **`hdefereval.executeInMainThread` does not exist** (H3a-F3). Re-probed and reproduced, not
  repeated from memory — R46 satisfied. `CLAUDE.md 1.7` and `shared/bridge.py` cite a deprecated
  `dirtyAllTasks` alongside it.
- **Stable integer object-ID render vars** across Karma CPU/XPU — the standing RETINA ask.

**Ruled:** I draft it; Joe sends it. A vendor ask carries the sender's reputation, and every claim
in it must survive SideFX re-probing it on their own build. All three do.

---

## RULING 50 — H3a-F4 is the most valuable finding in the leg, and it is about method.

> Five ABSENT verdicts in the first pass were artifacts of MY probe asking the wrong class, not
> absences on the build. Corrected in-run.

A probe that reports ABSENT for a symbol that exists is the same defect as the WS probe that
reported a dead bridge (L1.F1) and the regex that matched zero lines (R41). **Third instance, and
the first one caught by its own author mid-run.**

**H3a-F5** generalises it correctly: the `hdefereval` marshal layer is **unprobeable under headless
hython**, so a headless probe of it must return `UNVERIFIABLE`, never `ABSENT`.

**Ruled, adopted into the constitution:** **`ABSENT` requires a positive control on the same
class.** Where no control is possible, the verdict is `UNVERIFIABLE`. "I looked and did not find
it" and "it is not there" are different claims, and only the second licenses a SideFX ask.

---

## RULING 51 — RES found the actual root cause, and it is not what I ruled in R41.

I ruled the `AttributeError: 'Parm' object has no attribute 'set'` was "a stub Parm shadowing the
real class." **RES-F1 is more precise and more useful:**

> `hou.py` must never execute twice in one process. A second execution re-registers the SWIG type
> map to a half-built `Parm` class.

Not a stub winning over the real class — **the real class, rebuilt and left half-initialised** by a
second module execution. That is why `hasattr(hou.Parm,'set')` was True in a fresh interpreter and
False in the suite.

Four more that each refute a prior assumption, three of them mine:
- **RES-F2** — the agent's own documentation was wrong: `importlib.reload(hou)` reaches
  `sys.meta_path`, so the finder is not consulted "only when hou is absent".
- **RES-F3** — the residency guard **returned early under hython**, the one interpreter where
  residency matters. A guard that disables itself exactly where it is needed.
- **RES-F4** — a third evictor no static census had found, caught by the new gate on its first run.
- **RES-F5** — the census matched `sys.modules['hou'] = X` assignments only, so `pop`, `del` and
  `monkeypatch.delitem` were invisible to it.

**Ruled:** RES-F1 supersedes R41's mechanism. R41's *conclusion* stands — Q2-F4's "zero
shipping-code defects" survives, because a half-built SWIG registration is still a test-harness
defect. The reasoning was wrong; the verdict was right, and I record both.

---

## RULING 52 — LEDGER FR1: pin Moneta for release, keep the worktree for development.

Recommendation adopted as stated. The two are not in tension if the package pins and a documented
env override restores the worktree.

**LEDGER.F2 is why this is now urgent rather than tidy:** the revision walk was **unbounded**, so
Moneta resolved from inside any enclosing git repo reported *that repo's* HEAD as the Moneta
revision. Provenance was not merely absent — it was **confidently wrong**, which is worse.

**Ruled:** pin for release. Development keeps `MONETA_SRC` via a documented override. Not this
leg — the brief forbade it and the agent correctly reported rather than acted.

## RULING 53 — FR2: build the reconciler. FR3: wire recall.

**FR2** — Moneta rows live in memory until `close()`/`atexit`; the per-record JSON files are
durable and nothing rebuilds from them. A crash loses substrate rows **silently while the files
survive**. This repo keeps a crash harness precisely because hard exits happen, and today produced
one. Build it.

**FR3** — the seam deposits into a store nothing reads. The agent's own framing decides it:

> the seam is verified-but-unused — the same shape as the defect this leg closed, one level up.

**Ruled: wire it, federated read across both stores.** Merging into one URI would reintroduce the
single-owner lock contention the design avoids (LEDGER.F11).

## RULING 54 — FR4: env var with repo-relative default. FR5: dedupe at read time.

**FR4** — `agent_usd_path` must not import `hou`; `ledger.py` is deliberately zero-hou and that
contract is worth more than per-scene exactness in the default. Resolve it the way `ledger_dir()`
already resolves its root. **Where `$HIP` is available the caller passes it explicitly** — that
keeps per-scene provenance correct in production and headless probes working.

**FR5** — accept duplicates, dedupe by `Memory.id` at read. A write-time check is an O(n) scan on
the hot path. Unbounded growth is real but bounded by backfill frequency, and SHOW-tier protection
is a separate decision from write cost.

## RULING 55 — FR6: not a new problem. Do not cite the gate number as substrate evidence.

The 4917-pass gate number was produced on 3.14.2 against a **pip-installed** Moneta. Artists run
hython 3.13.10 against the `MONETA_SRC` worktree. **LEDGER.F1: the two interpreters load different
Moneta copies.**

**Ruled:** this is the gate-vs-shipping split already recorded in `suite_baseline.json`, not a new
finding. Adding a hython leg to the seam pins would measure the real substrate at the cost of a
Houdini dependency in CI — **not now**, and recorded as the reason.

## RULING 56 — LEDGER.F3 and F4 are both corrections to me, and F4 is the sharper one.

**LEDGER.F3:** *"18/18 mutations caught" was a number whose producer had come to disagree with it.*
The battery anchor was hardened after the number was recorded, so the figure survived its own
producer changing underneath it. That is R31's disease — a number whose meaning depends on when it
was taken — inside the mutation standard I created to prevent exactly this.

**LEDGER.F4 refutes a prediction I made yesterday.** I wrote that the ledger seam "very likely
shares a root with open task 2.5." It does not:

> Task 2.5 is anchored at `agent_state.py` and concerns USD projection. This is `ledger.py` and
> concerns substrate deposit. Different anchors, different mechanisms.

And **LEDGER.F5** corrects the finding I built that prediction on: *"provenance writers have NO
live callers"* is **stale** — 3 of 5 are dormant, not 5 of 5.

**Ruled:** task 2.5 stays open and separate. The agent was briefed with my prediction as context
and **checked it instead of inheriting it.** That is Article II working — a claim in a brief is
evidence at the tier of whoever wrote it, and mine was `UNVERIFIED`.

---

## RULING 57 — RES's three, ruled together.

- **4 tests pin H21 constants while running on H22** (unmasked by RES-F7). **Fix in H2**, not here.
  They are re-qualification work by definition, and H2 is running now with F1–F11 in scope.
- **`check_suite_baseline` ignores pytest's return code** (RES-F9). **Fix the ratchet.** A guard
  abort that the ratchet cannot see is Law 1 in the ratchet itself — third instance this week.
- **`shot_layers/` written to repo root by the solaris live tests** (RES-F11). **Redirect to
  `tmp_path`.** Gitignoring it hides a test writing outside its sandbox; the write is the defect,
  not its visibility.

---

## RULING 58 — H3a-F1 CONFIRMED against SideFX's own documentation before the ask ships.

Joe's call, and the right one: **search the vendor's documentation before sending the vendor an
ask that says "your API does not do X."** A negative claim to a vendor is the highest-stakes kind
this project makes — checkable by them in minutes, and being wrong costs credibility that took two
days of probes to build.

**Method:** `sidefx.com/docs/houdini/hom/hou/RopNode.html`, fetched 2026-07-26, full method list
read rather than keyword-searched. Complete public surface:

```
addRenderEventCallback  bypass  inputDependencies  isBypassed  isLocked
setLocked  removeAllRenderEventCallbacks  removeRenderEventCallback  render
```

No cancel, abort, interrupt, stop or kill — on `RopNode` or inherited from `OpNode`, `Node`,
`NetworkMovableItem`, `NetworkItem`. `render()` takes no timeout, no handle, and no callback that
can refuse continuation.

**Two near-misses, both checked and rejected:**
- `hou.InterruptableOperation` — real, documented for 22.0, but wraps *your own* Python block and
  polls `updateProgress()`. No reach into a `render()` already blocking in C++. Adjacent, not
  applicable.
- `addRenderEventCallback` — delivers `ropRenderEventType` notifications. Observation, not control.

**Verdict: H3a-F1 stands**, now on two independent methods — `VERIFIED-RUNTIME` (live `dir()` on
22.0.368) and `VERIFIED-WEB` (published reference, read in full).

**Caveat, load-bearing for the vendor conversation:** the fetched page's breadcrumb reads
**Houdini 21.0** at the current docs URL. The ask must cite the **live probe** as primary evidence
and the docs as corroboration, never the reverse — otherwise the first response is a version
objection.

R50 extends to vendor correspondence: **ABSENT requires a positive control, and reading the
complete method list is that control.** I wrote that rule for probes four hours earlier and had
not thought to apply it here.

---

## RULING 59 — H5 compat: cross-reference the codebase against the H22 reference. New leg.

**Why this is not redundant with live probing**, which is the whole case for it:

> `dir()` tells you a symbol EXISTS on this build. It cannot tell you the symbol is DEPRECATED.

R7 found SYNAPSE emitting `karma` and `karmarenderproperties` — the build's only two deprecated
LOPs, `karmarenderproperties` in ≥11 places. Every live probe reported them present and healthy.
H3a found `dirtyAllTasks` cited in `CLAUDE.md 1.7` and `shared/bridge.py`, also deprecated, also
invisible to introspection.

**A phantom API breaks loudly. A deprecated one works perfectly until the release that removes it.**

### The instrument — a four-quadrant matrix

Two independent axes: EXISTS (live `dir()`) x DOCUMENTED STATUS (H22 reference).

```
                   documented current   documented DEPRECATED   undocumented
    exists         fine                 DECAY CLOCK             PRIVATE API RISK
    absent         version mismatch     already removed         phantom
```

Only the top-left is safe. **Today's harness produces exactly one column.** The three interesting
cells are invisible to it.

- **DECAY CLOCK** — works today, breaks on upgrade, nothing in CI sees it coming.
- **PRIVATE API RISK** — `dir()` finds it, SideFX never documented it. It can vanish in a point
  release with no deprecation notice, because it was never promised.

### Three agents, because it is three different jobs

- **`cartographer`** — enumerate every `hou.*` SYNAPSE touches: call sites, emission corpus, RAG
  corpus, `CLAUDE.md` citations, docstrings. **The RAG corpus matters** — U.6 found 15 phantom
  light `createNode` sites there, outside the emission gate, re-teaching phantoms via
  `knowledge_lookup`.
- **`librarian`** — fetch the H22 reference per symbol. **Read the full method list, never
  keyword-search** (R58's control).
- **`h22-adjudicator`** — assign the quadrant. This is where the judgment lives: *"not on the page
  I read"* and *"not documented"* are different claims.

### The trap it must handle first

The docs URL fetched for R58 served a page whose breadcrumb read **Houdini 21.0**. So "the H22
documentation" may not be cleanly addressable.

**Establish which docs version is authoritative before classifying anything against it.** If the
answer is that SideFX serves 21.0 at the current URL, **that is a finding**, not an obstacle to
route around — it changes what "documented for H22" can mean, and it changes how every vendor ask
must be worded.

### Output

A ledger keyed by symbol: quadrant, `file:line` call site, docs URL, truth tier. Plus a
`checks.py` gate that **fails when a deprecated symbol appears in the emission corpus** — which
would have caught `karmarenderproperties` in eleven places.

**Read-only, disjoint from H1 and H2, gated on nothing.** Runs alongside.

---

# ADDENDUM — H1 (R60–R63)

`green`. Two drifted schemas repaired, both proven by mutation. One of its three ruling items is
a control-plane defect in my own dispatch.

---

## RULING 60 — H1-F6 is the finding. It calibrated the instrument the checks depend on.

I asked for pins that fail against a broken implementation (R34). H1 asked a harder question:
**what if the reader that inspects the implementation is itself blind?**

> The reader every pin depends on was itself uncalibrated — zero controls. If `_string_values`
> had collapsed `set_purpose`'s three-arm ternary, the repaired enum would have encoded the
> reader's blind spot and **ALL FIVE enum pins would have passed vacuously.**

And it proved the calibration rather than asserting it. Mutation: delete the
`| _string_values(node.orelse, where)` arm, and three tests go red together —
`test_schema_reader_recovers_every_arm_of_a_nested_ternary`,
`test_schema_reader_actually_sees_five_statuses_in_set_purpose`, and
`test_schema_return_status_enum_matches_implementation[set_purpose]`.

**Ruled, adopted into the mutation standard (R34):** a pin's **reader** requires its own control.
Mutation-testing the implementation proves the pin notices a broken *product*. It says nothing
about whether the pin can see the product at all. **A blind reader produces five green pins and
zero information**, and it is indistinguishable from five correct ones.

That is the deepest instance this week of the recurring defect, and the first found *before* it
fired rather than after.

---

## RULING 61 — R-2: read-only legs get FENCED, not asked. This is my defect.

**Drift D2, and it is serious:**

> A read-only extraction fleet **edited five schema files and twice rewrote a test file,
> including overwriting the orchestrator's own work**, and kept writing for **four minutes after
> the workflow was stopped**.

Every read-only leg I have dispatched — H3a, H5, and every `cartographer` and `assayer` pass —
was read-only **by instruction only**. The brief said "read-only". Nothing enforced it.

That is precisely the distinction Article I draws and I failed to apply: *enforcement in the
definition, not the instruction.* I wrote that rule about the deny fence, then spent two days
dispatching read-only legs with write tools in hand.

**Ruled, all three asks answered:**

**(a) Yes — fence it.** A leg declared read-only in `legs.json` dispatches under a narrow
profile, not the relay profile. Add `harness/readonly-settings.json`: `Read(**)`, `Bash(git log|
status|diff|rev-parse)`, `WebFetch`, `WebSearch`, and `Edit(harness/notes/**)` **only** — a
read-only leg still needs to write its own receipt. Everything else denied. The orchestrator
picks the profile from a `readonly: true` field, so it is a property of the leg rather than a
promise in prose.

**(b) Yes — Article V extends to any fan-out.** The worktree rule was written for "parallel
agents", meaning ones I intended to write. A read-only fleet that turns out to hold write tools
is a writer whether I intended it or not. **Every fan-out gets a worktree**, and the 11
`worktree-wf_*` trees that appeared at 15:09 are the same lesson from the other direction.

**(c) `TaskStop` not terminating in-flight subagents is a platform limitation**, not ours to fix —
same class as R48's render-cancel. It is recorded for the SideFX/Anthropic asks respectively, and
until then **stopping a leg does not mean it has stopped.** Any post-stop verification must
re-read from disk, never trust that writing has ceased.

**Consequence I must state plainly:** H3a and H5 were both briefed as read-only and both had
write tools. H3a's receipt claims `suite: not run — H3a wrote no product code`. That claim was
made in good faith and is **unverified** by anything structural. It should be checked against the
branch diff before H3a's findings are cited further.

---

## RULING 62 — R-1: declare every key. Make the pin bidirectional.

Seven keys are returned and undeclared across four tools: `message`, `reason`, `configure_node`,
`prim_path`, `usd_purpose`, `strategy`, `primitive_paths`.

The pins currently assert `declared ⊆ producible`, which catches a phantom declared key but not
an undeclared real one.

**Ruled: declare them, then make the pin an equality.** The schema is what the model is told a
tool returns (R33). An undeclared key is a payload field the agent has no reason to read and will
not reason about — the same failure as a phantom, inverted. A one-directional pin leaves half the
surface open, and the half it leaves open is the half that silently loses information.

---

## RULING 63 — R-3: R33's scope was incomplete, and the reason matters more than the miss.

`create_variants` declared an `extended` status `execute()` has never returned — the same defect
class as `set_purpose`'s `already_set`, in a tool R33 did not name. Found by reading all five
implementations rather than only the one cited.

**No decision needed; the lesson is the ruling.** R33 named a specific drifted enum. **Followed
literally, it would have repaired one phantom and left the other in place.**

What caught the second was not diligence but shape: `test_every_schema_return_contract_is_pinned`
is a **structural** pin that enumerates all schemas, rather than a check for the named instance.

**Adopted:** where a finding names an instance, the ruling should ask what class it belongs to
and pin the class. **A ruling scoped to its evidence is scoped to whatever happened to be looked
at first.**

---

## RULING 64 — H6 substrate truth. `available` is one boolean carrying five independent claims.

**First principles.** For Moneta to be genuinely working as SYNAPSE's USD substrate, five
conditions must hold. They are independently falsifiable and they are currently collapsed into
`moneta_available() -> bool`, which tests exactly the first:

```
1  the module imports                      <- the only one measured today
2  the SAME module on both interpreters    <- LEDGER.F1: they load DIFFERENT copies
3  the schema is REGISTERED with USD       <- plugInfo on PXR_PLUGINPATH_NAME
4  prims are AUTHORED with that type       <- the migration actually happened
5  a memory ROUND-TRIPS typed              <- written and read back as MonetaMemory
```

Any link can break with the boolean still reading `True`, because it only ever tested link 1.

**This is the week's recurring shape, in a fifth subsystem.** `dir()` says a symbol exists and
cannot say deprecated (H5). A suite is green on an interpreter the product never runs (R39).
`bridge.json` reports healthy while the transport refuses every upgrade (L1.F1). Each is one
signal standing in for several claims.

### What is actually true today, verified 2026-07-26

`C:\Users\User\Moneta\schema\plugInfo.json`:

```json
"MonetaMemory": { "schemaKind": "concreteTyped", "bases": ["UsdTyped"], "autoGenerated": true }
```

`generatedSchema.usda` carries six documented attributes. **The schema is real, codegen'd, and
`concreteTyped`** — so `Usd.SchemaRegistry().FindConcretePrimDefinition("MonetaMemory")` is the
correct API. My earlier caution that it might be an applied API schema was wrong: the design brief
weighed `MonetaMemoryAPI` and locked IsA.

**But `DEEP_THINK_BRIEF_codeless_schema.md:15` says memory prims are authored today as untyped
`def` prims**, with the typed migration listed as "the next surgery."

So the live state is `registered: True, in_use: False` — **the cell that reports healthy and means
the migration is half-done.** A registry check alone would pass while every memory is untyped.

**Ruled:**

1. **Decompose the boolean.** `moneta_provenance()` gains `schema_registered` and `schema_in_use`
   alongside `available` and the git SHA LEDGER is adding. Five conditions, five fields.
2. **Do not raise.** `_make_store`'s contract is that the flag *"can never break startup"*. A
   memory backend must not prevent Houdini's panel loading. Loud degradation: refuse the Moneta
   backend, log at ERROR, fall back to jsonl — the shape `store.py:830` already uses to
   distinguish not-installed from installed-but-broken.
3. **Measure on both interpreters.** LEDGER.F1 established gate and shipping load different
   Moneta copies. A schema registered under 3.14.2 says nothing about hython 3.13.10.
4. **Reuse Moneta's isolation pattern, do not reinvent it.** `tests/_schema_gate_subprocess.py`
   runs under `subprocess.run` with `PXR_PLUGINPATH_NAME` pointed at `schema/`, because USD plugin
   registration is **process-global** and cannot be tested in-process without contaminating the
   run. That is careful work already done.
5. **Positive control mandatory.** The check must be demonstrated firing with
   `PXR_PLUGINPATH_NAME` unset. A registry check that has never seen an unregistered schema is
   the decoration Law 1 keeps finding.

**The interesting cell is `registered && !in_use`.** It is the only one that looks like success.

---

# ADDENDUM — H2b / H5 (R65–R71)

Both `green`. 20 findings, 17 ruling items. H5 answered the question R58 left open and found a
live defect in the security boundary. H2b independently confirmed R61 and refuted Ruling 15.

---

## RULING 65 — H5's census. The two invisible cells were 67 symbols wide.

```
OK 796   DECAY_CLOCK 19   PRIVATE_API 48   PHANTOM 40
MISATTRIBUTED 28   VERSION_MISMATCH 2   ALREADY_REMOVED 1   UNVERIFIABLE 1267
```

And the line that settles whether R59 was rhetoric:

> Before H5, `grep -ci deprecat harness/verify/checks.py` was **0**.

**67 symbols sat in cells no instrument in this repository could see.** Not because anyone was
careless — because every check we had measured the EXISTS axis, and `dir()` cannot report
deprecation. 1267 `UNVERIFIABLE` is the honest remainder and it is the right verdict for anything
without a documented axis; it is not a failure of the leg.

---

## RULING 66 — H5-F1 AMENDS R58. Use the pinned URL. Every vendor ask depends on this.

> A version-pinned H22 docs URL **does** exist — `https://www.sidefx.com/docs/houdini22.0/` — but
> the UNPINNED URL is not a stable citation: it served "Houdini 21.0" for R58.

R58 recorded the breadcrumb mismatch as a caveat and told the ask to cite the live probe as
primary. **That was the right instinct and the wrong remedy.** The remedy is the pinned URL.

**Ruled:**
1. **Every SideFX citation uses `/docs/houdini22.0/`.** The unpinned path is banned in any
   governing document, ruling or vendor ask — it is a URL whose meaning changes underneath you.
2. **R58's verdict stands unchanged.** `hou.RopNode` still has no cancel; that was verified by
   live `dir()` on 22.0.368 independently of the docs.
3. **The SideFX ask must be re-checked against the pinned URL before it is sent.** One fetch. The
   whole point of R58 was not sending a negative claim on a shaky citation, and the citation was
   shakier than R58 knew.

---

## RULING 67 — H5-F3 is a LIVE DEFECT in the security boundary, and the doc is worse than the code.

> `shared/bridge.py:1718` calls `top_node.dirtyAllTasks(remove_files=remove_files)`. The live
> 22.0.368 signature is `dirtyAllTasks(self, remove_outputs)`.

`shared/bridge.py` is the S.2 security boundary and is deliberately human-authored. The call sits
in it with a keyword the API does not accept.

**And `CLAUDE.md 1.7` documents `dirtyAllTasks(remove_files=...)` — behaviour that has never
occurred.** The documentation describes a call that cannot have worked, which means anyone
reasoning from it has been reasoning from fiction.

**Ruled:**
1. **Fix the doc NOW, separately from the code.** A doc describing behaviour that never occurred
   is actively misinforming, and it costs one line. Do not wait for the code fix.
2. **The code fix is human-authored** — `shared/bridge.py` stays out of agent hands by standing
   rule. Joe or a human-reviewed patch.
3. **It does not block the release**, and I want the reasoning recorded: this defect shipped in
   v5.34.0 and every prior version, so it is a pre-existing condition this work documents rather
   than a regression — the same test I applied to the cook-cancel gap. It goes in Known
   limitations, not into a hold.
4. **It IS a blocker on any claim that PDG dirty-propagation works.** Nothing may cite that path
   as functional until the signature is corrected and probed.

---

## RULING 68 — H5-F4: do NOT regenerate the emission corpus first. The order is the ruling.

> The corpus is STALE (174 commits behind HEAD) **AND** regenerating it with today's extractor
> could DROP the headline symbol and turn the new gate green while the defect is untouched.

That is the sharpest trap in the receipt. A stale corpus and a blind extractor together produce a
repair that **erases its own evidence** — the gate goes green, `karmarenderproperties` stops being
listed, and nothing changed in the product.

**Ruled, in this order, no reordering:**
1. Fix the extractor's blindness. H5-F5 gives one concrete instance: the corpus records a **test
   allow-list membership** as an emission (`duplicate`, sourced to
   `tests/test_setdressing_recipe.py:60`).
2. Prove the fixed extractor reproduces today's headline symbols from today's tree.
3. **Only then** regenerate.
4. The gate's staleness guard stays armed throughout. It exists because of exactly this.

---

## RULING 69 — H2b-F1 independently confirms R61. Two legs, same conclusion, neither told the other.

> Instruction-level read-only fences do not hold. **THREE separate delegated attempts** at Part A
> ended with agents editing shared source in the orchestrator's worktree.

H1 found this (drift D2) and I ruled R61 and built `readonly-settings.json`. **H2b found it
independently, three more times, with no knowledge of H1's finding.**

Two legs converging on the same structural conclusion from different evidence is the strongest
signal this harness has produced. R61's fence is not a precaution — it is a response to six
observed violations.

**H2b-F2 explains the 11 stray worktrees I cleaned up at 15:13:** the Workflow tool's
`isolation: 'worktree'` created all eleven at **`f90946d` — master / v5.34.0, NOT the
orchestrator's branch HEAD.** So a fanned-out agent works from a tree that is silently behind the
leg that spawned it.

**Ruled:** R61's fence is confirmed and extended — **any fan-out must be verified to branch from
the dispatching leg's HEAD, not from master.** Add it to the F1 integration checks: a worktree at
an unexpected base is a finding, not a curiosity.

---

## RULING 70 — H2b-F5: Ruling 15 did not close the harm it named. My ruling was incomplete.

> **F8's NAMED HARM SURVIVES ITS OWN REPAIR.** The parent-key divergence is fixed — all three
> parent-taking tools share `PARENT_KEYS` — but `_resolve_parent_path` still falls back silently
> to `/stage` on an unknown key.

Ruling 15 said: *"converge on `parent_path`... Silent-default-on-unknown-key is itself a defect:
unknown parameters raise."*

The convergence happened. **The raise did not.** I named the real harm in the same ruling and the
repair addressed only the first half — so a caller using a wrong key still silently builds into
`/stage`, which is the entire user-visible symptom F8 described.

**Ruled: unknown parameter keys raise.** Not warn, not default. And the pin must demonstrate the
raise against an unknown key, or it is pinning the convergence rather than the harm.

**The lesson, and it is about how I write rulings:** Ruling 15 stated the mechanism and the harm
in one sentence, and the mechanism got fixed. **A ruling that names two things gets read as
naming one.** Where a harm and its mechanism are both in scope, they need separate numbered
clauses with separate oracles.

---

## RULING 71 — H2b-F3 is the method finding, and it is the same shape as H1-F6.

> My own mutation instrument produced **two FALSE 'surviving-mutation' verdicts** before it was
> corrected. The control ran the TARGET subset while the mutated run used a different one.

H1 calibrated its AST *reader* before trusting its pins (R60). H2b caught its *mutation harness*
comparing two different test subsets — so a pin appeared to survive mutation when the mutation was
never applied to what the control measured.

**Two legs, two instruments, same defect: the tool that verifies was itself unverified.**

**Ruled, promoted into the mutation standard:** a mutation run must assert that **control and
mutant execute the identical selection**. Report the selection in the receipt. A mutation result
where the two runs differ in scope is not a weak result — it is **no result**, and it reads
exactly like a strong one.

---

## Deferred, explicitly

The remaining ruling items from both receipts — the corpus/RAG gate extension, `apex::buildfkgraph`
quarantine, matrix schema versioning, promoting H5's producers into `scripts/`, the `pytest -k
solaris` interpreter ambiguity — are real and none are blocking. They go to F1's ruling block
rather than being decided here on a first read.

---

## RULING 72 — The local H22 references. Two sources, two axes, and neither is sufficient alone.

Joe supplied `C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache` and pushed back when
I dismissed it. He was right, and the pushback produced the most useful documentation finding of
the leg.

### What I got wrong

I tested the cache against `hou.RopNode` and `hou.TopNode`, found neither, counted 101 HOM
symbols, and concluded "browsing cache, not an oracle." **That conclusion is correct for the HOM
axis and says nothing about the node axis.** The cache holds **1,588 node docs** — I had looked
only at `hom/`.

`karmarenderproperties` is a NODE TYPE. It is H5's headline `DECAY_CLOCK` symbol, and `hom.zip`
cannot adjudicate it at all.

### Two sources, established by control

| Source | Covers | Control result |
|---|---|---|
| `<install>\houdini\help\hom.zip` | HOM Python API, 967 `.txt`, 62 mention deprecation | **PASSES both** — `RopNode.txt` has no cancel verb; `TopNode.txt` carries `dirtyAllTasks(self, remove_outputs)` and its deprecation notice verbatim |
| `<userprefs>\config\Help\cache` | node docs, 1,588 files, 48 LOP, 207 mention deprecation | serves the node axis; **useless for HOM** — 101 symbols, browsed pages only |

**`hom.zip` ships with 22.0.368, so it is version-pinned by construction.** No robots restriction,
no breadcrumb ambiguity, no URL whose meaning changes underneath a citation. H5-F1's hazard
disappears because there is no version to get wrong.

### The finding that matters, and it inverts the assumption

> **AMENDED BY R86 (2026-07-26).** The two character counts below are STRUCK — H7-F6 established
> they reproduce under none of five measures, a Law 2 violation in this ruling. The authoritative
> figure is `lop/karmarenderproperties.txt`, **56,325 chars**, measured against the build-shipped
> `nodes.zip`. **The conclusion below is CONFIRMED on that stronger evidence**, and H7 adds the
> part that makes it matter: SYNAPSE emits these two node types **123 and 31 times**.

Both `nodes/lop/karmarenderproperties.json` (69,921 chars) and `nodes/lop/karma.json` (95,777
chars) are present, substantial, current — and **neither mentions deprecation.** The runtime flags
both; that is how H5 found them.

**This is H5-F2 confirmed on its headline instance:** node-type deprecation has two independent
expressions and they disagree.

I had assumed documentation would supply the authority `dir()` could not. Here the reverse holds —
**the authored help is less informative than the runtime**, and an artist reading the docs has no
way to learn these node types are decaying.

**Ruled:**

1. **`hom.zip` is the HOM documentation oracle.** Local, version-pinned, control-passed. It
   replaces network fetches for HOM symbols entirely.
2. **The help cache is a SECOND source for the node axis, never the authority.** A node absent
   from it means "nobody browsed that page" — the same trap that made my first dismissal wrong,
   pointed the other way.
3. **Deprecation is the UNION of runtime `deprecationInfo()` and authored help, and disagreement
   between them is itself a finding.** A doc-only oracle would have reported
   `karmarenderproperties` clean. A runtime-only oracle misses anything deprecated in prose but
   not flagged in code. **H5's `DECAY_CLOCK` count of 19 is a floor, not a total.**
4. **Add a `doc_silent_deprecation` sub-cell** to the compat matrix: runtime says deprecated,
   authored help does not. It is the most dangerous cell, because every human-facing surface says
   the symbol is fine.

### Method note

Three times today a two-sided control changed the answer: the WS bridge that was healthy, `--effort
banana` proving the flag validates, and this. **Each time the first result was plausible and
wrong.**

And the correction here came from Joe declining to accept a fast dismissal. The scout took one
run. The dismissal took one run too — the difference was entirely in which axis got tested.

---

## RULING 73 — The SideFX ask was WRONG. Joe caught it. Rewritten, not sent.

**The claim as drafted:**

> Houdini 22.0.368 exposes **NO API** to cancel, abort, interrupt or kill an in-flight
> `hou.RopNode.render()`.

**Refuted.** A full sweep of the local H22 reference — 966 HOM entries plus the render-adjacent
node docs — surfaced four candidates the draft did not account for. Runtime settled each:

```
hou.ActiveRender            ABSENT at runtime      docs say #status: ni  -> ni is accurate
hou.activeRenders()         ABSENT at runtime      same
hou.IPRViewer.killRender    PRESENT                real, and not marked ni
rps    hscript              EXISTS   "Lists background render processes"
rkill  hscript              EXISTS   "Stop or pause/unpause a render"
hou.RopNode                 no cancel verb         the NARROW claim still holds
```

**`rkill` stops a render.** It is an hscript command, reachable from Python through
`hou.hscript()`, and it has been there the whole time. `hou.ActiveRender` — documented as its HOM
replacement, `#replaces: /commands/rkill /commands/rps` — is `#status: ni` and genuinely absent,
which is why the sweep's most promising hit was a false lead and the runtime probe was what
settled it.

### What I did wrong, precisely

I verified **"`hou.RopNode` has no cancel method"** — twice, by live `dir()` and by the full
method list in `RopNode.txt`. Both correct.

Then I wrote an ask claiming **"Houdini exposes no way to cancel a render."**

**Those are different claims, and I only tested the narrow one.** R50 — which I wrote this morning
after H3a caught five of its own wrong-class ABSENT verdicts — says `ABSENT` requires a positive
control **on the same class**. The class the ask spoke about was the whole render surface. My
control was one class.

**Third instance of that error today, and the only one addressed to a third party.** SideFX could
have refuted it with a single search of their own docs, and one wrong item makes the other two
read as careless.

### A third documentation state

`#status: ni` is neither "documented current" nor "documented deprecated" nor "absent". It is
**documented-but-unimplemented** — a published API surface that does not exist at runtime.

It is the mirror image of `doc_silent_deprecation` (R72): there, runtime knows something the docs
do not; here, the docs describe something runtime does not have.

**Ruled: the compat matrix gains `DOC_ONLY_NI`.** H5 and H7 must treat `#status: ni` as its own
cell. Any symbol read from documentation without a runtime probe can land in it, and a codebase
written against the reference alone would call it and fail.

### The rewritten ask — narrower, and better

The honest, defensible version:

1. **`hou.RopNode` has no cancel method.** True, twice-verified, and the real friction: a Python
   integrator holding a `RopNode` has nothing to call.
2. **`hou.ActiveRender` is `#status: ni`.** The documented HOM replacement for `rkill`/`rps` is
   absent at runtime. **This is the actual ask** — implement it, or mark the docs so integrators
   do not build against it.
3. **`rkill` works and we should use it.** Not an ask at all. It is what SYNAPSE should call, and
   H3b's scope changes accordingly.

That is a better message than the original: it asks for something specific and achievable, it
concedes what exists, and every claim survives their own verification.

### R48 is amended

R48 closed the render half as **not-implementable**. That was wrong in the same way. The
implementable path is `hou.hscript("rkill ...")` — process-level, blunt, and needing care around
scene state, but real.

**H3b's scope widens:** TOPS cancel *and* an `rkill`-based render stop, with an explicit finding
on what `rkill` does to a partially-written frame. The safety gap is narrower than I ruled.

### Method note

Joe asked one question — *"the ask wasn't resolved by the documentation?"* — and it exposed a
claim about to go out under his name. The sweep took two runs.

**Every control I have written this week has been about instruments. This one was about the scope
of a claim**, and it is the same failure wearing different clothes: an oracle that answers a
narrower question than the one being asked will answer it correctly, and the answer will still be
wrong.

---

# ADDENDUM — H6 (R74–R78)

`green`. 7 findings, 6 ruling items, suite 4881 → 4915 (+34, 0 failed). **R64 was wrong in both
directions and the leg proved it rather than inheriting it.**

---

## RULING 74 — R64 AMENDED. Both halves of my predicted state were false.

**R64 predicted:** `registered=True, in_use=False` — "the only cell that looks like success while
the substrate does nothing typed."

**H6-F1:** prims are authored **TYPED today.** `usd_target.py` sets
`prim_spec.typeName = 'MonetaMemory'` **unconditionally, in both Moneta copies.** Moneta's own
`DEEP_THINK_BRIEF_codeless_schema.md:15` — which says prims are untyped `def` and the migration
is "the next surgery" — **is stale**, and I inherited that staleness straight into a ruling.

**H6-F2:** `schema_registered` is **FALSE on both interpreters** in the default environment.

So the real state is the exact inverse of my prediction: **`registered=False, in_use=True`.**
Prims carry the type name; USD does not know the type. I had the cells backwards.

**Ruled:**
1. R64's predicted state is struck. The measured state stands.
2. `h6.md`'s premise section is corrected — a brief asserting a stale premise teaches the next
   agent the same wrong thing.
3. **Moneta's design brief is flagged stale in Moneta**, not silently worked around. Article VII:
   amendments commit before the work they govern.
4. **The lesson is the ruling.** R64 cited Moneta's brief as evidence and did not probe it. A
   design document describes intent at the time of writing; **it is a claim about the future, and
   it ages into a claim about the present without anyone editing it.** Design briefs are
   `UNVERIFIED` by default, whatever their provenance.

---

## RULING 75 — H6-F5 is the epistemics finding, and it invalidates the check I asked for.

> `schema_in_use` is NOT evidence of a working substrate on its own. **Sdf authoring is
> schema-blind: `typeName` is written to disk with or without a registered schema.**

I asked H6 to measure `schema_in_use` as "are prims authored with that type." It measured it, and
then established that the measurement **cannot mean what I wanted it to mean.**

Writing `typeName = 'MonetaMemory'` through Sdf succeeds whether or not USD has ever heard of
`MonetaMemory`. The string lands on disk either way. So a prim reporting the type name proves
authoring happened — and proves **nothing** about registration, validation, or whether the
attributes conform.

**Ruled:** `schema_in_use` alone is banned as evidence of substrate health. It is only meaningful
**paired with `schema_registered`**, and the pair `registered=False, in_use=True` — which is
today's actual state — is precisely the dangerous cell: **prims that look typed and are not
validated by anything.**

This is R72's `doc_silent_deprecation` in a different subsystem. A single signal standing in for a
conjunction, reporting healthy because it can only report one thing.

---

## RULING 76 — H6-F4: dead code reporting the inverse of the truth, on the exact seam I pointed at.

> `store.py`'s `except ImportError` arm was **DEAD CODE**, and the surviving arm reported **the
> exact inverse of the truth.**

I sent H6 to that seam citing `store.py:830` as the good pattern — the one that "distinguishes
not-installed from installed-but-broken." **It did the opposite of what I praised it for.**

Two failures compounding: an unreachable branch, and a reachable branch whose message was
backwards. Nothing failed, because a wrong message is not an exception.

**Ruled:** fixed as part of this leg's product change, which it was. And recorded as the fourth
Law 3 violation found this week — `status` describing what was attempted rather than what
happened, this time in the diagnostic that exists to report the truth about the substrate.

**I cited it as exemplary without reading it.** That is the same error as R64's stale premise, one
layer down: I inherited a belief about the code from its docstring.

---

## RULING 77 — H6-F3: conditions 4 and 5 are structurally unreachable, and that is the finding.

> **SYNAPSE authors ZERO USD through Moneta.** Conditions 4 and 5 are not half-migrated — they are
> structurally unreachable on SYNAPSE's live path.

R64 framed five conditions as a chain where "any link can break." H6 found two links **not
connected to the chain at all** on SYNAPSE's side. Moneta authors typed USD; SYNAPSE never invokes
that path.

**Ruled:** this reframes the Moneta integration honestly. `SYNAPSE_MEMORY_BACKEND=moneta` routes
*memory storage* through Moneta. It does **not** mean SYNAPSE writes USD, and no claim may say or
imply that it does.

The USD substrate is real, typed, and authored — **by Moneta, on Moneta's own path.** SYNAPSE's
relationship to it is currently storage, not authoring. That is a smaller claim than the
architecture documents imply, and it is the true one.

---

## RULING 78 — H6-F7: Article V was violated ON THIS LEG, and my fix was already right.

> TWO independent sessions executed `harness/prompts/h6.md` against this one worktree and branch
> **concurrently, and both held write tools.**

That is the double-dispatch race I caught at 16:05 and fixed at 16:07 with the `.orch_launched`
marker — H6 dispatched at 16:05:01 and again at 16:05:56, and I killed the duplicate at 16:06.
**Both ran for roughly 55 seconds, and H6 observed it from the inside.**

Its ruling question asks whether the orchestrator should refuse to dispatch a leg whose worktree
already carries a live marker. **That is exactly what the marker now does** — confirmed by an
independent observer that did not know the fix existed.

**Ruled:**
1. The marker fix stands, now validated from inside the affected leg.
2. **Extend it to interactive sessions.** The marker currently guards orchestrator dispatch only.
   A human opening `claude` in a leg worktree while a leg runs there hits the identical hazard,
   and the marker is already the right signal — it just needs reading by something other than the
   dispatcher.
3. **Any leg that ran concurrently with another session has its receipt flagged.** H6's findings
   held up, but "two writers, one worktree" is a condition under which a receipt's provenance is
   not clean, and it should be visible rather than inferred.

---

# ADDENDUM — H8, THE RULING AUDIT (R79–R84)

`green`. The audit passed sensitivity **and** specificity, found two known-wrong rulings beyond
the four planted, and returned the hardest numbers in this document.

```
SOUND                22   (28%)
UNENFORCED           31   (40%)
SUPERSEDED_UNMARKED  13
EVIDENCE_FAILS       12
CONTRADICTED / SCOPE_ERROR / UNFALSIFIABLE   0 primary, 4/3/1 on any-basis
```

---

## RULING 79 — The audit is ACCEPTED, and its specificity is why.

> **specificity — PASS.** R14, R35, R60, R75 returned SOUND unanimously. *A method that flagged
> all twelve would have "caught" all four and proved nothing (Law 1 applied to the audit).*

I asked for sensitivity: catch the four planted. **It supplied specificity unprompted** — proof
that it could also return SOUND, which is the half that makes the other half mean anything. An
audit that flags everything detects nothing.

It also found **R50 and R70** independently, neither planted. **Six rulings are known wrong, not
four.**

**Ruled: accepted in full.** Every verdict below rests on a method that demonstrated it can both
fire and hold fire.

---

## RULING 80 — 31 UNENFORCED. Forty percent of this document is intention.

I predicted "not a small number" and guessed low. **31 of 78 rulings create a rule with no
mechanism.**

This document argues, repeatedly and at length, that structure beats intention. The deny fence
held where "read-only" as an instruction did not. The launch marker held where killing a window
did not. The pre-push hook held where a deny rule matching command form did not.

**And 40% of the rulings that established that principle are themselves pure intention.**

**H8-F8 makes it concrete and unarguable:** *nine rulings explicitly order a check into
`checks.py` or the check set. **None of the nine exists.*** I ordered nine checks across two days
and built zero.

**Ruled:**
1. **Triage all 31, and the default is WITHDRAW, not build.** A rule nobody enforces and nobody
   misses is spent — it cost attention when written and costs more every time it is read as
   binding.
2. **The nine ordered-but-absent checks are the priority set.** Each was ordered because something
   broke. Build them or strike the ruling that ordered them — leaving an order unexecuted is worse
   than either, because the document reads as though the check exists.
3. **No ruling may use the word "adopted" for a rule with no mechanism.** "Adopted" implies
   enforcement. `PROPOSED` is the honest word until a check exists.

---

## RULING 81 — H8-F1: my own fence guarantees the defect it is blamed for.

> Unmarked supersession is **structurally guaranteed, not an author oversight.**
> `Edit(harness/notes/CTO_RULINGS_01.md)` is denied in BOTH agent profiles, so no leg agent can
> mark a ruling it supersedes.

13 `SUPERSEDED_UNMARKED` — and the reason is a fence I wrote. Article VII correctly stops an agent
editing the rulings. The consequence is that supersession can only be marked **if I remember**,
which is the exact failure mode the whole document exists to eliminate.

Today alone: R73 refuted R48, R74 inverted R64, R66 replaced R58's remedy, R70 corrected Ruling 15
— and in every case a reader of the original sees text that still reads as current.

**Ruled — the ruling question is answered YES.** An append-only
`harness/notes/RULING_AMENDMENTS.md` that agents MAY write, referenced from the head of
`CTO_RULINGS_01.md`. The fence stays exactly where it is: an agent still cannot edit a ruling, but
it can now **record that one is contradicted**, and the record is where a reader will see it.

**The general form, and it is the sharpest thing in this audit:** *a prohibition with no channel
produces silent drift.* Fencing a surface without providing a sanctioned path around it does not
prevent the need — it hides the evidence that the need existed.

---

## RULING 82 — H8-F4: the evidence for 40% of this document is not on the branch.

> The evidence base for rulings 48–78 is not on the branch that carries them. **`H7.json` was
> never written at all.**

Thirty-one rulings cite receipts that are not in version control on this branch — `LEDGER.json`,
`H5.json`, `H2b.json` — and one cites a receipt **that does not exist**.

This is Law 5 at document scale. A ruling whose anchor cannot be opened by the next reader is not
a ruling; it is a recollection with a number on it.

**Ruled:**
1. **Commit the receipts. Before the merge, not after.** They are evidence, and F1's own brief
   ordered exactly this consolidation.
2. **H7 must be re-run or its rulings downgraded.** I read H7 findings into R65–R71 from a receipt
   that H8 says was never written. Either it exists and F1 moved it, or I ruled on something I
   cannot now produce — **and I must determine which before those rulings stand.**
3. **A ruling may not cite an uncommitted anchor.** Add it to the check set — the same set that is
   currently empty.

---

## RULING 83 — H8-F3 and F6: the document breaks its own laws in the act of stating them.

**H8-F3:** *the document violates its own R66 in the file that issues the ban.* R66 banned the
unpinned SideFX URL; the ruling that bans it uses it.

**H8-F6:** *R50 reports what was attempted, not what happened — Law 3 violated in the act of
adopting a law.*

**H8-F5:** R70's factual premise is refuted by an executed two-sided control.

Three separate instances of a rule being broken **in the sentence that establishes it.** Not
carelessness in application — carelessness in authorship, at the moment of maximum attention to
the rule in question.

**Ruled:** all three corrected. And recorded as the strongest available argument for R80's third
clause: **stating a rule is not evidence of following it**, and the author is least able to see
this in the paragraph where they are most certain.

---

## RULING 84 — H8-F7 is the one to sit with.

> **An unexecuted ruling is the only reason the released documentation is correct.**

A ruling nobody carried out is load-bearing for a public artifact. Had it been executed, the shipped
docs would be wrong.

I am not ruling this into a principle, because I do not think it generalises — it is luck, and
reading it as vindication would be exactly the error. It is recorded because **the 31 UNENFORCED
rulings are not uniformly inert**, and a blanket withdrawal would have removed this one.

Triage each on its own evidence. R80's default stands; this is why the default is a default and
not a rule.

---

## RULING 85 — R82 is WITHDRAWN. H8-F4 is refuted, and the reason matters more than the correction.

R82 accepted H8-F4's claim that *"the evidence base for rulings 48–78 is not on the branch"* and
that *"`H7.json` was never written at all."* I ruled that H7 must be re-run or its rulings
downgraded.

**Verified 2026-07-26 22:5x, one command:**

```
harness/notes/receipts/H7.json          26 KB, present
git ls-files harness/notes/receipts/    23 receipts, ALL TRACKED
git status --porcelain                   only F1.json modified
```

`H7.json` exists, is committed, and F1's consolidation completed correctly. **R65–R71 rest on a
receipt that is in version control.** R82 is withdrawn in full.

### Why H8 got it wrong, and why that is not a failure of the audit

H8 ran while F1 was consolidating receipts from thirteen worktrees into the main tree. It read a
tree mid-move. **The finding was true when observed and false by the time it was written.**

This is the third distinct instance today of a *state machine reading a signal that is only true
eventually* — the receipt watcher pointed at the wrong tree, the double-dispatch race between
launch and `settings.local.json`, and now an audit observing a consolidation in flight.

**Ruled, and this is the generalisable part:** a finding about the *state of the tree* must record
**when** it was observed and what else was running. `VERIFIED-STATIC` is not a timeless tier when
another leg holds a write lock on the same paths. Receipts already carry `commit_at_run`; findings
about tree state need the same discipline.

### And the correction is itself the argument for R81

I ruled R82 from H8's receipt without opening `H7.json` — the anchor was one command away and I
took the finding on trust because the audit had just passed a rigorous control.

**An instrument that passes its control is not thereby correct on every claim.** The control
proved H8 could distinguish sound rulings from unsound ones. It proved nothing about whether a
given file existed at a given moment.

I have now made this error twice in one session: citing `store.py:830` as exemplary without
reading it (R76), and ruling R82 on an unopened anchor. **Both times the source was credible and
that was exactly why I did not check.**

---

# ADDENDUM — H7, COMPAT RE-ADJUDICATION (R86–R90)

`green`, 12 findings, 8 ruling items. **596 of H5's 1,267 UNVERIFIABLE resolved (47%).** 671
remain, each with a *named* reason rather than a shrug.

---

## RULING 86 — R72's numbers are STRUCK. Its conclusion is CONFIRMED on better evidence.

**H7-F6:** *R72's two help-cache character counts are not reproducible. 69,921 and 95,777 match
none of five measures.*

I cited those figures in R72 as evidence that `karmarenderproperties` and `karma` carry large,
current documentation that never mentions deprecation. **They came from a script whose output I
did not pin, and they cannot be reproduced.** That is Law 2 — no number without a producer path —
violated in a ruling, by me, one day after H1 caught the same class of defect in a receipt.

**H7-F2 confirms the conclusion against the authoritative source:** `lop/karmarenderproperties.txt`
in the build-shipped node reference, 56,325 chars, deprecation absent. And it adds the part that
makes it matter: **SYNAPSE emits these two node types 123 and 31 times.**

**Ruled:**
1. **R72's character counts are struck** and replaced with H7's reproducible measure against
   `nodes.zip`. The ruling's text is amended in place, not silently corrected.
2. **R72's conclusion stands, on stronger evidence.** The doc-silent deprecation cell is real, and
   it is the dangerous one exactly as ruled — every human-facing surface says these are fine while
   the product emits them 154 times.
3. A number in a ruling carries the same Law 2 obligation as a number in a receipt. **The document
   has been holding its own agents to a standard it did not meet.**

---

## RULING 87 — The DECAY_CLOCK floor is 41, not 19. A 2.2x correction to a governing number.

**H7-F3:** the floor rises to **41** as the union of runtime `deprecationInfo()` and authored help
— 39 of them `doc_only`, where the help deprecates and the runtime does not.

R72 already ruled that deprecation is the union of both sources and that 19 was a floor. **This is
that ruling cashed out**, and the size of the correction is the argument for having made it: more
than half of the deprecated surface was invisible to the runtime axis alone.

**Ruled:** 41 is the current figure, with the 12 conditional rows recorded as **leads, not
verdicts** — they are bound by owner-invariance rather than direct evidence and must not be
counted as confirmed.

---

## RULING 88 — Two reader defects in H5, and both would have produced confident wrong answers.

**H7-F4:** H5's authored-help reader **did not follow the `:include /composite/_old_cops_deprecated:`
banner**, so the *entire* deprecated old-COPs surface read as current. A whole vendor-deprecated
subsystem scored OK on the doc axis.

**H7-F5:** H5 bound the bare leaf `expandString` to the **new** owner `hou.text.expandString`, then
took the deprecation notice from the **old** symbol's page — **marking the replacement deprecated.**
Acted on, it would have sent a migration to the symbol it was migrating away from.

Both were caught by controls H7 wrote for the purpose (C17 requires the banner shape to fire).
Neither was visible in H5's output, which reported clean.

**Ruled:** these are `R60` in a new place — **a reader that resolves a reference must be controlled
on the resolution, not only on the parse.** H5's reader parsed correctly and *bound* incorrectly,
and a parse-level control cannot see that. Any future doc reader needs a binding control:
given a known leaf with a known owner change, does it attach the notice to the right symbol?

---

## RULING 89 — H7-F7: the largest residual is a CENSUS defect, not a documentation gap.

**528 of the 671 remaining** are bare method names with no dotted owner — `xRes`, `saveImage`,
`allPixels` — and **335 are OpenUSD**. They are unresolvable not because documentation is missing
but because the census emitted a leaf without recording what it hangs off.

**Ruled: this is the highest-yield fix available to the next compat pass**, and it is cheap
relative to its effect — 528 rows is 79% of the residual. It is a `scripts/` change, outside H7's
fence, and it belongs to whoever runs the next census.

**The general form:** *a measurement's largest unknown bucket is worth interrogating for
instrument defects before it is treated as a knowledge gap.* H5 reported 1,267 unknowns. Roughly
half were reachability (R59/H7) and 40% of the remainder are census kind. **Very little of it was
ever an actual gap in what is knowable.**

---

## RULING 90 — H7-F8: two live spelling defects. Fix these.

SYNAPSE writes `hou.NodeEventType.InputRewired` and `hou.NodeEventType.ParmTupleChanged`. Neither
is the build's spelling. Each has one execution-context occurrence.

**Ruled: fix both.** Wrong-owner is actionable where undecidable was not — these are two-line
corrections with live call sites, and they are exactly the class of defect the whole compat
exercise was built to surface. They go into the next repair leg, not into a ruling block to be
considered.

Also recorded: `docs/sprint_freeze/marshal_map.md:527` cites
`hdefereval.executeInMainThreadWithResultAndDelay`, **not defined anywhere in the build's shipped
source.** A governing document citing a symbol that does not exist — the same class as
`CLAUDE.md`'s `dirtyAllTasks(remove_files=...)`, which documented a call that raises on every
invocation.

---

## Deferred to the ruling block, not decided here

The `pxr` corpus-ownership question (79 rows), the `cop2net` category conflict (60 occurrences),
the 104 node types absent from the reference and never probed, and whether the deprecation-marker
vocabulary should be promoted out of `harness/notes/` into a reusable checker. All real, none
blocking, and none should be decided on a first read at midnight.

---

# ADDENDUM — F1's INTEGRATION FINDINGS (R91–R94)

F1 found these because integration did what no leg did: **put ten branches in one tree.** None
appear in any receipt.

---

## RULING 91 — F1-A: LEDGER and H6 collided because I dispatched a composition as two
independent legs. My error, and it stranded four decided rulings.

**What happened.** `repair/ledger-moneta-seam` reported `status: green` with
`commits: [], merged: false, pushed: false`. **Literally true** — 504 lines across four product
files sat *uncommitted* in its worktree. F1's own housekeeping step would have destroyed them. F1
committed the work on its own branch (`eb25abe`, 2,012 insertions, 8 files) and did not merge it.

**Why it could not merge, `git merge-tree` VERIFIED-RUNTIME:**

```
HEAD + LEDGER   ->  clean
LEDGER + H6     ->  CONFLICT  python/synapse/memory/moneta_runtime.py
                              docs/studio/DEPLOYMENT.md
```

**The mechanism is my design error, stated plainly.** R64 specified five conditions and said the
function would *compose*: *"`moneta_provenance()` gains `schema_registered` and `schema_in_use`
alongside `available` and the git SHA LEDGER is adding."*

I described a composition — and then dispatched it as **two legs, both `deps: []`, both rewriting
the same function from the same base, in ignorance of each other.** Neither branch has all five
fields. LEDGER has `available` + `revision`; H6 has `available` + `schema_registered` +
`schema_in_use`.

`legs.json` carries a `deps` field. It is the exact mechanism for expressing *"H6 after LEDGER"*
and I did not use it.

**The consequence, which is worse than the conflict.** LEDGER's ruled items **R52, R53, R54 and
R55 are all DECIDED** — and implemented *only* in that stranded code. **Four rulings I closed are
currently un-shipped**, and every further change to `moneta_runtime.py` widens the gap LEDGER's
patch must cross.

**Ruled:**
1. **The union is AUTHORED, not merge-resolved.** No automatic strategy produces a five-field
   function. It gets a leg with a precise brief, and it carries the mutation pins both sides
   already wrote.
2. **LEDGER's half lands as part of that union**, not before it. Merging LEDGER first would block
   a gate leg behind a conflict, which is what F1 correctly refused to do.
3. **F1's judgement is endorsed.** *"H6's work was committed and green; LEDGER's was never
   committed at all. H6 went in."* Given a fence forbidding it to fix forward through a conflict
   into product code it had not read, that is the correct call and it preserved both halves.

---

## RULING 92 — The manifest must express FILE collisions, not just leg dependencies.

The dependency graph is only as good as what is put into it, and I put file-level collisions
nowhere. Two legs modifying one function is not an exotic case — it is the *ordinary* case for a
repair harness, and it was invisible until integration.

**Ruled:** `legs.json` gains a `touches: [paths]` field. Before dispatch, the orchestrator
**refuses to run two legs whose `touches` intersect unless one declares the other in `deps`.**
That is a check that can fail today — LEDGER and H6 would both have named
`python/synapse/memory/moneta_runtime.py` — and it is one of the nine ordered-but-absent checks
R80 requires be built or struck. **This one gets built.**

---

## RULING 93 — F1-C: `green` with zero commits must be impossible. Five of ten legs did it.

LEDGER's receipt was **honest** — it reported exactly what happened, and Law 3 is satisfied. The
defect is that the terminal condition permits it: **a leg can write `status: green` while its
entire product sits uncommitted in a worktree**, one prune away from gone.

**Ruled: a leg's terminal condition requires its product COMMITTED on its own branch.** A dirty
worktree at receipt time is `amber` at best and the receipt must say so. `green` asserts the work
exists somewhere durable; five of ten legs asserted it while it did not.

This is the same class as R78's "a leg that has written its receipt is done" — **the terminal
condition was underspecified, and agents behaved correctly against a specification that permitted
the wrong outcome.**

---

## RULING 94 — F1-G: the fence hole is CONFIRMED by execution, not by inspection.

> `git -C <path> merge` walks straight through `Bash(git merge:*)`. **F1 did it eight times.**

F1 did not report a theoretical bypass. It **performed** the bypass eight times in the course of
doing its job, while a deny rule sat there matching a command form nobody was using.

The `pre-push` hook installed tonight closes the push half by capability. **The merge half is still
open** — a hook cannot intercept a local merge the way `pre-push` intercepts a push.

**Ruled:** the honest statement is that **local merges are not fenced and cannot be by this
mechanism.** What is fenced is the thing that matters — nothing reaches origin's master without
`SYNAPSE_GATE_C=1`. A local merge on a feature branch is recoverable; a push to master is what
Gate C exists to stop.

Record it as a *known limitation of the fence*, not as a hole to be patched with more patterns.
**Claiming merges are fenced when they are not is worse than the gap.**

---

# ADDENDUM — H9, DOC GROUNDING (R95–R98)

`green`, 7 findings, 5 ruling items.

---

## RULING 95 — H9-F6: retire "D2" and "D3". They name swapped concepts in two governing documents.

> L1 — **the producer of the 18.3% and 6.2% baselines** — defines D2 as literal-emission and D3 as
> semantic. The rulings document uses D2 as semantic and D3 as behavioural.

So every statement I made about "docs lift D2, not D3" used the letters in the opposite sense from
the document that produced the numbers being discussed. **The reasoning survives; the labels do
not.**

**Ruled: the letters are retired.** Three words, used literally, everywhere:

```
emission     the type appears in what SYNAPSE writes
semantic     what the type is FOR - parameters, intent      <- docs supply this
behavioural  what it does when cooked                       <- only probes supply this
```

A single-letter label with two incompatible definitions across governing documents is worse than
no label — it reads as precision and carries none. **This is the third naming collision this week**
after the C.3/C.4 ledger IDs and `tools/` vs `tool_impls/`, and the pattern is the same: a short
identifier reused in a second context by someone who did not know about the first.

---

## RULING 96 — H9-F4: the honest number is 37.9%, not 83%.

> 83% of live LOP types have a page, but **only 37.9% of live LOP parameters are documented.**

This is exactly the gap I asked H9 to report and told Joe to watch for: *"has a page"* is not
*"is grounded."* A page naming a node and describing three of its twenty parameters is real, and
it is not semantic coverage.

**H9-F3 sharpens it further:** Cop2 documentation carries almost no parameter identifiers — 7.7%
of its parameter records have an explicit `#id:`, and only **13 of 139 pages have even one.**

**Ruled:**
1. **Parameter-level coverage is the reported figure.** Type-level coverage may be reported
   alongside it, never instead of it, and never as the headline.
2. The projected lift is therefore **substantial but not transformative** — from 18.3% to
   something in the high thirties on the semantic axis, not to 90%. I told Joe to expect 60–80%
   after a quality gate. **The real answer is lower than my guess**, and the guess was already
   hedged downward from the raw coverage number.
3. That is still a large improvement on 18.3%, achieved from a file that ships with the product.

---

## RULING 97 — H9-F1: the corpus is keyed on LABELS, not ids.

> **385 documented parameter ids are wrong as names**, while their labels resolve correctly.

A corpus keyed on `#id:` would carry 385 entries that cannot be matched to any live parm. Keyed on
label, they resolve.

**Ruled: label is the join key.** The `#id:` field is recorded as evidence and is not authoritative.
**And a corpus keyed on the wrong field is not a partially-correct corpus — it is a corpus that
silently fails to match**, which is the same failure shape as H5's reader binding a leaf to the
wrong owner (R88).

---

## RULING 98 — H9's ruling question is R81 again, and this time it caught me by name.

> `harness/legs.json` carries **the unreproducible 179/198 and 460/491 figures** in H9's note, and
> **it is deny-listed from agent edit.**

Those are my numbers, from the first-pass coverage script, written into a governing file as though
established. H7 already struck two of my figures for the same reason (R86). **This is the third
Law 2 violation of mine this week, and the second in a file an agent is fenced from correcting.**

The agent found the error, could not fix it, and escalated — which is the correct behaviour and
also the exact cost R81 named: *a prohibition with no channel produces silent drift.*

**Ruled:**
1. `legs.json`'s H9 note is corrected to H9's reproducible figures with a producer path.
2. **The append-only `RULING_AMENDMENTS.md` channel from R81 extends to `legs.json`.** An agent
   that finds a wrong number in a fenced file must have somewhere to record it that a human will
   see. Escalation via `for_ruling` worked here only because I read the receipt within the hour.
3. Recorded plainly: **I have now written unreproducible numbers into three governing artifacts** —
   R72, `legs.json`, and the H9 note. Every one was a figure I generated, glanced at, and typed
   onward without pinning the producer. The rule I keep enforcing on agents is the one I keep
   breaking myself, and it has never once been caught by me.

---

## RULING 99 — SYNAPSE is running on H22 and thinking in H21. Three layers, all diverged.

Joe caught it in a live response: *"I haven't memorized every single **H21.0.671** LOP node
parameter name."* SYNAPSE has been on 22.0.368 since 15 July.

**Investigated from first principles: is the host version PROBED or REMEMBERED?** The answer
differs per layer, and that is the finding.

### Layer 1 — data SELECTION is version-aware, and is dead code

`scout.py:424-435` is correctly designed:

```python
major = str(EXPECTED_HOUDINI_VERSION or "").split(".", 1)[0]
if major.isdigit():
    candidate = _PKG_SYMBOL_TABLE.with_name(f"h{major}_symbol_table.json")
    if candidate.is_file(): return candidate
return _PKG_SYMBOL_TABLE          # H21 fallback
```

**`EXPECTED_HOUDINI_VERSION` is declared `= None` at line 141 and NOTHING IN THE CODEBASE EVER
ASSIGNS IT.** The docstring says *"host-injected — mcp_server only sets it when `hou` imports."*
No such injector exists. `git grep` finds only the declaration and its own readers.

**VERIFIED-RUNTIME under hython3.13:**

```
running build              22.0.368
EXPECTED_HOUDINI_VERSION   None
table selected             h21_symbol_table.json
```

So `major` is `""`, `isdigit()` fails, and **every session takes the H21 fallback.**
`h22_symbol_table.json` is **1,287 KB and has never been loaded.**

The version-aware branch is unreachable. It was written, committed, and has never once executed —
a per-major authority mechanism that authorises nothing.

### Layer 2 — two other corpora have no version logic at all

> **AMENDED 2026-07-27 — THIS LAYER IS FALSE AND IS WITHDRAWN.**
>
> `wiring.py` and `lop_knowledge.py` **both probe correctly.** Each resolves its per-major catalog
> through its own guarded `_running_houdini_major()`, which imports `hou` and reads
> `applicationVersion()[0]`. VERIFIED-RUNTIME under hython3.13: `wiring._pkg_catalog_path()` →
> `connectivity_22.json`, `lop_knowledge._pkg_catalog_path()` → `lop_solaris_knowledge_22.json`.
> **Both were already loading the H22 files.**
>
> I saw hardcoded `_21` filenames in the module-level constants and concluded from what I **saw**
> rather than what **executes** — the same error as R104's grep-for-one-token-name. A resolver
> function overrode both constants and I did not open it.
>
> **The correct pattern already existed in this codebase. Scout was the outlier, not the rule** —
> and the fix for scout was to build the injector that `wiring.py`'s equivalent has always had.


```
core/lop_knowledge.py:44   data/lop_solaris_knowledge_21.json    HARDCODED
core/wiring.py:46          data/connectivity_21.json             HARDCODED
```

`connectivity_22.json` (151 KB, vs 21's 93 KB) and `lop_solaris_knowledge_22.json` (14 KB, vs 7 KB)
are committed and **have no loader whatsoever.** Not a stale selection — no selection.

**All three H22 corpora exist, are larger than their H21 predecessors, and are entirely inert.**

### Layer 3 — the prose, which is what the model actually reads

```
scout.py:5    "scouts the Houdini 21.0.671 documentation RAG"
scout.py:6    "returning real H21 reference"
scout.py:15   "The model's priors for H21.0.671 are frequently wrong"
scout.py:52   "the CANONICAL H21 corpus is the repo rag/ tree"
rag/skills/houdini21-reference/     <- the corpus DIRECTORY NAME
```

There is no `houdini22-reference`. **This is the layer that produced Joe's quote.** An LLM reading
a docstring that says *"H21.0.671"* will say H21.0.671, whatever the data layer selected — and
here the data layer agreed with it anyway.

### Why this matters more than a version string

The H22 catalogues built during this relay — **218 LOP types, 384 Copernicus types** — are the
first evidence of what H22 actually contains. Copernicus barely existed in H21. **A model reasoning
from an H21 corpus about a COP graph is reasoning about a different product.**

And it explains a number I ruled on twice: COP grounding at 6.2% is not merely thin, it is
grounding measured against a corpus that predates the subsystem.

**Ruled:**

1. **The injector is the fix, and it is small.** Whoever imports `hou` sets
   `scout.EXPECTED_HOUDINI_VERSION = hou.applicationVersionString()`. One line, at the seam where
   `hou` is already known to be present.
2. **`lop_knowledge.py` and `wiring.py` get the same per-major selection** scout already has.
   Three loaders, one rule.
3. **A check that FAILS when the loaded corpus major differs from the running major.** This is the
   defect's own detector, and it can fail today — it fires on the current tree, which is what
   makes it a check rather than a decoration (R80).
4. **The prose is corrected wholesale, including the corpus directory name.** `houdini21-reference`
   → per-major, or a name that does not assert a version it cannot guarantee.
5. **Nothing is deleted.** H21 remains the correct fallback for a headless or stock-python process
   with no host to probe. The defect is that the fallback is the *only* path, not that it exists.

### The pattern, one more time

A mechanism that reads a variable nobody sets. A guard that silently degrades instead of failing.
Three corpora committed and inert. **Every layer here was built correctly and connected to
nothing** — and it reported healthy for twelve days, because falling back to H21 produces plausible
answers rather than errors.

That is the same shape as the `--ignore` runner, the mock `hou`, the 100%-by-construction metric,
and the stall detector watching its own log. **This one is the largest instance found, and it was
caught by a human noticing one wrong number in a sentence.**

---

# ADDENDUM — V1 / H4 (R100–R106)

---

## RULING 100 — V1: the scoped-delta primitive CANNOT be built on Karma 22.0.368 as designed.

**V1-F1, `blocker-for-V3`, settled with controls:**

> **No usable per-object integer ID mask exists on Karma 22.0.368 via any path probed.** `primid`
> is per-polygon; `element` is finer; `ray:objectid` returns **one value for two distinct
> objects.**

**V1-F2:** `primid` **collides across objects** — solo-left and solo-right spheres produced 50 ids
each with **49 shared.** One, two and three spheres gave 30/53/57 distinct ids against a fixed
ceiling. It is not an object identifier and using it as one would have produced masks that were
confidently wrong.

**V1-F4:** Karma **refuses** an integer render-var format outright — `format=int32` fails the
render with *"Unsupported image data format int32 in RenderVar."* So an ID AOV can only ever be
float, and F3 shows the shipped `primidfilter` default blends **7.4% of pixels, 91.9% of those on
prim boundaries** — precisely where a mask boundary lives.

**Ruled: RETINA-VERIFY's V2–V4 do not exist as designed.** The mask is the primitive's foundation
and Karma does not supply one. I wrote that harness this morning asserting the ID-AOV path was
merely *unverified*; it is **refuted**, and the leg I gated it behind is the reason we know that
rather than discovering it three miles in.

This is the second time in one day a leg refuted the premise of the harness that dispatched it
(V0 was the first). Both were probes. **The probe-before-build rule has now paid for itself twice
before lunch.**

---

## RULING 101 — V1-F5 is the finding that goes to SideFX, and it is the week's pattern inside Karma.

> The `ray:` namespace prefix is **REQUIRED** on a custom render-var `sourceName`. Bare
> `objectid` / `primid` / `Ci` / `C` / `color` each emit **a correctly-named EXR part FILLED WITH
> ZEROS, SILENTLY.**

A correctly-named, correctly-shaped, entirely empty AOV. No error, no warning. **Any pipeline
reading that part gets zeros and has no way to know it asked wrong.**

That is the exact shape this repository has spent five days cataloguing — an instrument reporting
healthy while measuring nothing — occurring inside the renderer rather than in our code.

**Ruled: this goes into the SideFX ask as item 1**, ahead of the `ActiveRender` request. It is
more serious, it is trivially reproducible, and a silent-zero failure mode costs every integrator
who hits it the same day of debugging it cost us.

---

## RULING 102 — Copernicus readback is CONFIRMED. Close that SideFX ask.

> `hou.CopNode.layer()` → `hou.ImageLayer.allBufferElements()` → bytes. **Exact round-trip,
> byte-deterministic, 7.74 ms at 1920×1080.**

*"Documented Copernicus buffer-to-numpy readback path"* has been a standing SideFX ask. **It
exists, it works, and it is fast enough to run per-mutation.**

**V1-F7** completes it honestly: `hou.CopNode` carries **none** of the legacy `Cop2Node` readback
verbs — `allPixels`, `planes`, `getPixel`, `xRes` all ABSENT — and that verdict is licensed by
those same spellings **resolving on `hou.Cop2Node` in the same run.** A same-class positive
control, exactly as R50 requires.

**Ruled:** the readback ask is **withdrawn** from the SideFX draft. It was answered by probing
rather than by asking, which is the cheaper of the two and should have been tried first.

**And it reopens the primitive from a different direction.** Karma cannot supply a mask — but if
COP can compute one from geometry rather than from a render AOV, the delta becomes tractable
again. That is a real V2 candidate and it did not exist before this probe.

---

## RULING 103 — V1-F9 and V1-F10 are live product defects outside their leg's fence.

**V1-F9:** SYNAPSE's `enable_denoiser` control **writes five phantom spellings, of the wrong type,
and reports success.** Three separate Law 3 violations in one control — phantom API, wrong type,
false status.

**V1-F10** refutes a belief that is load-bearing in **four shipped artifacts, one of which is a
safety guard** (`foreground_guard.py`).

**Ruled:** both are repair legs, not ruling items. **F10 first** — a safety guard resting on a
refuted belief outranks a broken denoiser toggle. Neither belongs to V1, which was fenced
read-only and correctly reported rather than fixed.

**And V1's own ruling question is answered: no.** R93 says commit before the receipt; the
read-only fence denies `Bash(git commit:*)`. **The fence wins.** A read-only leg's product *is*
its receipt, and R93 is amended to say so rather than the fence being widened.

---

## RULING 104 — H4: my brief undercounted the collision by an order of magnitude.

I wrote H4's brief this morning citing **11 cyan sites versus 21 blue** and *"two token modules."*

**H4.F1:** the collision was **15 divergent names, not one** — beyond `SIGNAL` it covered six
neutrals, `VOID`, `NEAR_BLACK`, `CARBON`, `GRAPHITE`, `SLATE`, `SILVER`.

**H4.F2:** there were **NINE colour-declaring sites, not two** — the bridge, the design system,
the off-repo `~/.synapse/design` file, and **six call-site `except ImportError` arms.**

**H4.F3:** those fallback arms are **REACHABLE**. Loading `panel/apex_recipes.py` by path with
`synapse` off `sys.path` executes the arm. They were live third states, not dead code.

**H4.F4:** and they were **not faithful copies** — `NEAR_BLACK` is `#3A3A3A` in the fallback and
`#3C3C3C` in the live off-repo file. A fallback that silently renders a different colour than the
thing it stands in for.

**Ruled: the leg is right and my brief was wrong.** My figures came from a `grep` for one token
name, which is exactly the shape of measurement this document keeps ruling against — **a count
whose producer answers a narrower question than the claim it supports.**

---

## RULING 105 — H4.F6 is the method finding, and it hit two readers I wrote.

> L4's own token oracle `assert_panel_tokens.py` matched **ALIAS-QUALIFIED strings** (`'t.VOID'`),
> so an alias change alone satisfied it.

**The oracle in H4's own brief has the same defect.** I wrote `grep -c 't\.SIGNAL' -> 0` as the
acceptance clause. It returns 12, and the leg's ruling question is that **the clause measures the
wrong thing** — an alias-qualified grep passes when the alias is renamed and the collision
survives.

**Ruled: the leg's reading is correct and the oracle clause is struck.** The right measure is
**how many modules DECLARE a colour**, not how many sites reference one alias. Nine declaring
sites is the number; zero grep hits was never going to be evidence.

R60 said a pin's *reader* needs calibration. **This extends it: an oracle written into a brief is
a reader too**, and mine has now been wrong twice in one day — here and in V1's premise.

---

## RULING 106 — H4.F7: my R18 consent tests cannot run on the shipping interpreter.

> Three consent-honesty checks could not run at all on the shipping interpreter.
> `tests/panel/test_gate_consent_honesty.py` used `object.__new__(GateWidget)`; **a Shiboken type
> refuses it.**

I wrote those pins on 2026-07-25 for R18 — the consent gates that announced decisions which never
landed. I gated them with `importorskip` so they would *skip* on the dev interpreter and *run*
under hython.

**They skip on both.** The construction technique that made them cheap on the dev box is refused
by the real Qt binding, so the fix that stops SYNAPSE claiming false consent has **never been
verified on the interpreter artists run.**

**Ruled:** rewrite them against a real `GateWidget` under hython, or against a seam that does not
require constructing one. **This is R18's pin, not H4's**, and it is the highest-priority item in
H4's block — a safety fix whose test has never executed is a safety fix nobody has checked.

---

# ADDENDUM — THE TWO SELF-ASSESSMENTS (R107–R110)

Two documents supplied 2026-07-27: SYNAPSE's own health report, generated 08:39 today, and a
He2025 consistency audit dated 2026-02-07 scoring **100/100**.

**Both are self-assessment**, and that is the lens. This week measured what self-assessment
reports: five instruments healthy while measuring nothing, 40% of rulings unenforced, nine ordered
checks never built. Not cynicism — the measured base rate.

---

## RULING 107 — Four version numbers, and I created the newest divergence this morning.

```
VERSION file                5.35.0     shipped and tagged today
python/synapse/__init__     5.33.0     what the RUNNING CODE reports
git tag                     v5.35.0
install stamp               5.23.0     per the health report
```

I bumped `VERSION`, committed, tagged and pushed `v5.35.0` — and **never touched `__version__`.**
The health report reads `__version__`, which is why it says 5.33.0 while the repo says 5.35.0.

The report flagged the 5.33/5.23 pair as *"needs reconciliation"* and could not see the third and
fourth numbers because it only reads one of them.

**Ruled:**
1. `__version__` is corrected to match `VERSION`, and **a check asserts they agree.** This is one
   of R80's nine ordered-but-absent checks; it gets built, and it fires on today's tree.
2. **The release procedure was underspecified and I followed it correctly to a wrong outcome** —
   the same shape as R93's `green`-with-zero-commits. `harness/finalize.ps1` bumps `VERSION` and
   nothing else. It gains `__version__`.
3. The install stamp is a fourth authority. **One of these four is canonical and the others derive
   from it**; that decision is owed and has never been made.

---

## RULING 108 — The health report's "Symbol Table ✅ OK" checks a table nothing loads.

The report:

> **Symbol Table ✅ OK** — Stamp 22.0.368 == Running 22.0.368 (35,903 symbols match)

VERIFIED-RUNTIME, same interpreter, minutes later:

```
scout._pkg_symbol_table_path() -> h21_symbol_table.json
```

**The health check validates a stamp; scout loads a different file.** Both statements are true and
they are about different objects. A green tick on the thing not in play.

This is R99 confirmed from a second direction — and worse than R99 stated, because R99 established
the *selection* was dead code. **This shows the health surface actively reporting OK about it.**

**Ruled:** the symbol-table check is rewritten to assert **the table scout ACTUALLY RESOLVES**, not
a stamp beside it. Its producer must be `scout._pkg_symbol_table_path()` — the function under
test — and the check must fail today, which it will.

**The general rule, and it is the sharpest form this week has produced:** *a health check must
call the same function the product calls.* Anything else is a check on a neighbour.

---

## RULING 109 — The health report confirms three open findings, and its own scores have no producers.

**Confirmed in production, independently:**
- *"MonetaMemory schema NOT registered. `PXR_PLUGINPATH_NAME` is unset."* — **H6-F2 exactly.**
- *"grounding LOP node types against the live **H21** runtime"* and *"COPs is **Houdini 21's**
  GPU-accelerated image processing context"* — **R99's prose leak**, in a document generated today.
- *Three tools are explicit SCAFFOLDS* — `reaction_diffusion`, `pixel_sort`, `bake_textures`
  "create the node topology but don't execute." **Built and connected to nothing**, self-reported.

**And the scores are Law 2 violations throughout.** *"ALIGNMENT RATING: 8/10"*, *"7/10"*, a
ten-row scorecard — **not one carries a producer path.** They are judgements presented in the
grammar of measurements, which is the more misleading of the two forms.

**Ruled:** the health report is a **useful instrument with an unearned summary**. Its per-check
rows are real and three of them independently confirmed open findings. **Its ratings come out** —
or each gets a producer, which for "8/10" means defining the denominator, and that definition is
the actual work.

---

## RULING 110 — A 100/100 self-audit is the exact artifact H8 was built to attack.

The He2025 audit scores **100/100**, *"All issues resolved"*, dated **2026-02-07 — five months
stale**, and authored by the same hand as the code it audits.

H8 audited 78 rulings by their author and returned **28% SOUND**. It caught six known-wrong
rulings including two nobody planted, and it passed a **specificity** control proving it could
also return SOUND. That is what an audit looks like when the auditor is not the author.

**This document has no control.** It lists fixes as completed — *"replaced with monotonic counters
(v5.1)"*, *"process-stable ID (v5.2)"* — and **nothing re-verified them.** Its own Issue 3 is
struck through as `FIXED` with no producer.

**Ruled:**
1. **The 100/100 is withdrawn as a claim** pending an independent pass. Not because it is wrong —
   its per-claim analysis is careful and several verdicts are well argued — but because *a score
   an author gives their own work is not evidence*, and this repository has now measured that
   twice.
2. **It gets the H8 treatment**, with a blind positive control: plant known-broken determinism
   cases and require the audit to catch them before any verdict is trusted.
3. **Its listed fixes are re-verified against HEAD.** Five months and roughly a dozen releases
   have passed. `router.py:421` either uses a monotonic counter today or it does not, and that is
   one grep.

**The pattern across both documents:** SYNAPSE reports on SYNAPSE, and the report is good at
specifics and unreliable at summaries. **Every concrete row in the health report was checkable and
three were true. Every aggregate was a judgement wearing a number.**

---

## RULING 111 — R99 layer 2 WITHDRAWN. R107 grows from four locations to seven.

**R99's layer 2 is false.** I claimed `wiring.py` and `lop_knowledge.py` had "no version logic at
all." Both probe correctly through their own guarded `_running_houdini_major()`, and both were
already loading the H22 catalogues. VERIFIED-RUNTIME:

```
scout       h21_symbol_table.json         <- the only broken one
wiring      connectivity_22.json          <- already correct
lop_knowledge  lop_solaris_knowledge_22.json  <- already correct
```

I grepped for hardcoded `_21` filenames in module constants and concluded from what I **saw**
rather than what **executes**. A resolver overrode both and I did not open it. **Same error as
R104**, four days apart, in a ruling written to catalogue that error.

**The correct pattern already existed here. Scout was the outlier**, and the fix was to build the
injector `wiring.py`'s equivalent has always had.

### And my first fix was worse than the bug

I made scout import `hou` directly. A test caught it in one run:

> `synapse.cognitive.*` must be host-agnostic — ZERO hou imports.

**So the injection design was not over-engineering.** It was the correct response to an
architectural boundary, and the only defect was that nobody built the injector. I had called it
*"the design that failed"* twenty minutes earlier. It was the design working, incompletely.

**Ruled:** a mechanism that looks over-built is worth understanding before it is simplified. The
boundary it respects may not be visible from where the defect is.

---

## RULING 112 — Seven version locations. I knew four; a test written before me found the rest.

```
VERSION · __version__ · pyproject.toml · __init__ docstring · CLAUDE.md banner · git tag · install stamp
```

`tests/test_phase0c_doc1_version_conformance.py` already enforced the chain
`pyproject == __version__ == docstring == banner`, and it **walked me through the three I did not
know about, one failing assertion at a time.** Its own docstring names the incident that caused it:
*"the v5.8.0-vs-5.10.0 banner the CTO review flagged."*

**Ruled:**
1. All seven are enforced by `harness/verify/version_agreement.py`, wired into `finalize.ps1`
   step 7. It fails on an unfixed tree — demonstrated, not asserted.
2. **`VERSION` is canonical**; the others derive. That decision was owed in R107 and is made here.
3. The install stamp remains outside this check because it is written at install time rather than
   authored. **It is a seventh location that this check cannot see**, and saying so is better than
   implying coverage the check does not have.

**The observation worth keeping:** every location I did not know about was found by a test somebody
wrote first, in response to an earlier version of this exact drift. **The check I wrote today is
the second answer to a question already answered — and it only found more because the first one
told it where to look.**

---

# ADDENDUM — C1 / C0: THE POSITIONING'S SPINE IS REFUTED (R113–R118)

---

## RULING 113 — "Cost stays flat, even on huge scenes" is REFUTED. It comes off the document.

**The claim under test**, marked Shipping, leading the positioning page, and the sentence every
other differentiator hangs off:

> *"Sends only what changed — cost stays flat, even on huge scenes."*

**C1 verdict: REFUTED.** Measured across a six-rung ladder, 13 → 25,850 nodes:

```
arm A grounding payload   443 -> 113,411 tokens        256x
+ measured tool prefix    14,380 (panel) / per turn
arm B ablation            443 -> 1,234,946 tokens    2,788x
```

**Cost is not flat. It rises 256-fold.** It rises *far less steeply* than the ablation — that part
is real and it is the thing worth saying — but "flat" is not a description of a 256x curve, and a
studio running its own version of this test would find that in an afternoon.

**Ruled: the claim comes off the document in its current wording**, and what replaces it is R114.

---

## RULING 114 — C1-F4 is the honest reframe, and it is harder than the claim it replaces.

> Against the ablation, arm A's apparent cost advantage is **essentially ALL reduced coverage and
> essentially NONE tighter encoding.** Raw advantage at the top rung is 10.89x; per node it
> largely disappears.

Single-call scene coverage by rung: **100, 100, 73, 51, 10, 11 percent.**

**SYNAPSE is cheaper on large scenes because it sees less of them, not because it describes them
better.** That is a real architectural property and it is defensible — bounded-depth grounding is
the right design for an agent that can re-inspect on demand, and completeness *within its own
depth window* is 100% at every rung.

But it is a different sentence, and the honest one:

> **Cost scales with what you ask about, not with the size of your scene.** A 25,000-node scene
> costs what the part you are working on costs.

**Ruled: that is the claim, and it is testable.** It also has to be said alongside the coverage
number, because "sees less" is the mechanism and hiding it would be the same defect one layer up.

---

## RULING 115 — C1-F6: "sends only what changed" has NO MECHANISM. This is the worse half.

> There is **no delta path anywhere in the grounding surface** — every inspect is a full re-read.
> The dirty-flag inspect cache is explicitly [not wired].

The refuted claim has two halves. "Cost stays flat" is wrong by degree. **"Sends only what
changed" is wrong by kind — the named mechanism does not exist.**

That is the more serious finding. A quantitative claim that overstates is a calibration error; a
mechanism claim for machinery that was never built is the defect this repository has spent five
days cataloguing, in the marketing rather than the code.

**Ruled:** the phrase is struck immediately and unconditionally. **It does not return until a
delta path exists and is measured.** If the dirty-flag cache is wired later, this becomes a real
and strong claim — but it is a roadmap item today and belongs in the Roadmap column, which is
honest by construction.

---

## RULING 116 — C1-F3: `houdini_network_explain` SEGFAULTS on SideFX's flagship scene.

> Reproducibly on both runs, `rc=139`, on `karma_user_guide.hip` — **the largest scene SideFX
> ships.** Dies inside `_get_non_default_par...`.

A hard crash of the hython process, on a public SideFX scene, in a tool an artist would reach for
on exactly the kind of scene where grounding matters most.

**Ruled: this is the highest-priority product defect open.** It outranks the panel redesign and
the RSI audit. A segfault takes the interpreter with it — there is no error to report, no graceful
degradation, and on a live session it takes the artist's unsaved work.

**And it gates the release.** Not because a release cannot ship with known defects — v5.35.0
shipped with five — but because this one is reproducible on a scene anyone can download, and the
first thing a technical evaluator does is point the tool at the biggest scene they have.

**C1-F10 is adjacent and probably the same class:** `inspect_selection`'s depth argument is
agent-supplied, **clamped nowhere**, over a recursion with **no visited set** — 2^depth. Its
sibling `network_explain` clamps at 5. Fix both together.

---

## RULING 117 — C0: zero of four Shipping claims are SUPPORTED, and one correction is mine.

```
SUPPORTED 0   PARTIALLY_SUPPORTED 3   UNSUPPORTED 1
```

**C0-F3 corrects me directly.** Four hours ago I wrote that *"the positioning document's fourth
claim is verified — `_check_boot_gate` requires `hou.isUIAvailable()`."* C0:

> **CLAIM 4 is UNSUPPORTED as worded.** The gate is real and fires; it guards a component with
> **zero production callers**, while the shipping surfaces boot and mutate headless.

I verified the gate **exists**. I did not verify it guards **what the claim says it guards**. That
is R104 again — concluding from what I saw rather than from what executes — and I made it while
writing a ruling about instruments that report on neighbours.

**C0-F4 is worse and more useful:** *the repository already shipped the correctly-scoped version
of claim 4, and deleted it.* The true, narrower sentence existed and was replaced by a broader
false one.

**C0-F1 is a scope finding that changes how this leg is read:** the positioning document **is not
in the repository and never has been.** C0 graded a transcription. Every verdict is against text
pasted into a chat, not a versioned artifact — which is itself the problem, because a claim with
no file has no producer and no history.

**Ruled:** the positioning document enters the repository under version control before any further
audit of it means anything. **C0's verdicts stand as findings about the text as transcribed**, and
are re-run against the committed artifact.

---

## RULING 118 — C1-F2 and C1-F13: what this benchmark could NOT establish.

**C1-F2:** *no model was in the loop and none could be.* The Anthropic key authenticates; **the
account has no credits.** Both `messages.create` and `messages.count_tokens` return HTTP 400. So
every figure is a **proxy-tokenizer payload measurement**, not an exact token count from the model
that would serve the turn.

**C1-F13:** *a genuine outside-in arm was never built — both wide-margin arm-B variants are
SYNAPSE calling SYNAPSE.* The comparative half of the claim is **not established either way.**

**Ruled, and this is why the leg is `green` rather than compromised:** it stated both limits
plainly rather than presenting a comparison it had not earned. A benchmark that names what it
could not measure is worth more than one that quietly measures something adjacent — which is
precisely what an ablation against your own serializer would have been if left unlabelled.

**Consequence:** no release may cite a token figure as a *comparison* until a real outside-in arm
exists. The within-SYNAPSE numbers stand as what they are: a coverage-and-payload profile of our
own grounding surface.

**And fund the account.** An exact tokenizer is one API call away and every number in this leg
carries an asterisk without it.

---

## RULING 119 — H21X WITHDRAWN. The corpus is not mislabelled; it is H21 documentation.

I dispatched a leg to migrate 108 "stale" H21 references in `rag/` to H22 or version-neutral
wording. **Joe stopped it: the corpus IS H21 documentation. H22 docs have not been converted to
RAG yet.**

**So every reference I classified as FIX was accurate**, and the leg would have relabelled true
content as something it is not — making the corpus lie about its own provenance. That is precisely
the harm the brief's own control was written to prevent, aimed at the wrong 108 references.

**Killed before it wrote anything.** Verified: 0 commits on its branch, 0 files modified under
`rag/`. Worktree removed, branch deleted locally and on origin, leg withdrawn from the manifest.

### What I got wrong, and it is a familiar shape

I saw `"Complete OpenCL kernel reference for Houdini 21 Copernicus"` in a repository running
22.0.368 and concluded the label was stale. **I never asked what the file contained.** The label
was a true description of H21 content; the mismatch I detected was real and I attributed it to the
wrong side.

**R104, R111 and now this** — three instances of concluding from what I saw rather than from what
was there. The first two were about code that executes differently from how it reads. This one is
about a *label being right and the content being what I did not check*.

**And the model's answer was CORRECT.** SYNAPSE said *"SideFX ships with Houdini 21"* because it
retrieved H21 documentation and reported its version accurately. I read that as a leak. **It was
the system being honest about its own knowledge**, which is the behaviour this project has spent a
week trying to produce.

### What the real gap is

```
scout symbol table   h22_symbol_table.json   H22, fixed this morning (R99)
wiring / lop_knowledge   _22 catalogues      H22, always were
rag/ corpus          H21 documentation       ACCURATE, and not yet converted
```

**The corpus is not stale-labelled. It is H21 content, correctly labelled, awaiting conversion.**
That is a content-generation task — ingest H22 documentation — not a text migration, and it is
substantially larger than the leg I wrote.

**Ruled:**
1. **`rag/skills/houdini21-reference` keeps its name until it holds H22 content.** The name is
   currently the most honest thing about it. Renaming it version-neutral, as my leg proposed,
   would have removed the one signal telling a reader which build the knowledge describes.
2. **The gap is worth surfacing, not hiding.** SYNAPSE reasons about H22 symbols from H22 tables,
   and retrieves prose written for H21. A reader should be able to see that — it is a real
   limitation with a real consequence for Copernicus, which barely existed in H21.
3. **H22 RAG conversion is its own project**, sized honestly, and it is the thing that closes
   R99's third layer. Not a relabelling pass.

### The rule I should have followed

**Before ruling a label stale, read what it labels.** A version string that disagrees with the
running build is evidence of a mismatch. It is not evidence of *which side* is wrong.

---

# ADDENDUM — S0 / S1 / RSI0 (R120–R124)

---

## RULING 120 — S0-F1 REFUTES THE POSITIONING'S OPENING PREMISE. There is no AI floor in H22.

The positioning document opens:

> *"In Houdini 22, an AI that writes VEX and runs on a local model is standard equipment — SideFX
> ships a version in the box. The floor just rose."*

**S0-F1, and the absence is proven rather than assumed:**

> **Houdini 22.0.368 registers NO LLM, agent, assistant, copilot, or MCP surface.**

**S0-F2:** SideFX publicly demonstrated an AI-assisted authoring surface **and scoped it OUT of the
shipped release in the same sentence.**

**S0-F3:** the H21→H22 floor moved toward **task-specific neural inference in the node graph and
APEX rigging** — not toward any agent surface.

**S0-F4:** trade press asserts MCP/LLM capability in H22 that **neither SideFX's own pages nor the
live build corroborate.** Recorded unresolved rather than decided, which is correct.

**Ruled: the opening premise is struck.** It was almost certainly taken from trade coverage, which
S0 has now shown is unsupported by the vendor and the binary.

**And the correction improves the position rather than weakening it.** The document argued SYNAPSE
competes *one layer above* a commoditised floor. **There is no floor.** The honest framing is
stronger and more specific:

> H22 added neural inference for specific tasks — denoise, rig transfer, and similar. It did not
> add an agent, an assistant, or an MCP surface. That slot is empty.

**A studio's TD can verify that in five minutes**, which is exactly why it must be stated as an
absence we probed rather than a gap we assumed.

---

## RULING 121 — S1-F2 is a demo risk: `synapse_inspect_scene` does not return.

> Called live twice; **ran 1800s and was aborted by the MCP idle timeout.**

Not slow — non-returning, on a shipped tool with an inviting name. An artist asked to "look at my
scene" reaches for exactly this.

**Ruled: fence it before the demo.** A tool that hangs is worse than one that refuses — the
session stalls with no error, which is the failure signature this project has spent a week
eliminating. Either bound it or make it decline on scenes above a measured size, with a message
naming the alternative that works.

**S1-F4** is adjacent and separately real: `synapse_scout` fails on **SQLite thread affinity** —
*"not a hang, slow then a hard error. Mechanism found, not inferred."*

---

## RULING 122 — S1-F1: the fake `hou` makes `importorskip("hou")` gate NOTHING.

> A canonical **FAKE `hou` is planted into `sys.modules` at collection time**, so `import hou`
> always succeeds under plain pytest and `pytest.importorskip("hou")` gates nothing anywhere.

Every test written to skip off-host runs instead — **against a mock.** That is the five-unreachable-
Solaris-tools mechanism, still live, in the guard designed to prevent it.

**S1-F6 names the cure, and it already exists in this repository:**

> The Solaris family is the ONE family with honest host evidence, and the mechanism is worth
> naming: **the mock fixtures were DELETED** under Law 1, and the tests gate on host identity.

**Ruled: that pattern is the standard** for any tool an artist actually reaches for. Deleting the
mock is what made the difference — not adding an assertion.

---

## RULING 123 — RSI0: the loop is wired, never runs, is fed a constant, is read by nothing, and its logs say otherwise.

Four findings, and together they are the most complete instance of this week's pattern:

**F1** — the routing RSI loop **has never run in production.** In the live Houdini process the
entire `synapse.routing` package is **absent from `sys.modules`.** The class was never imported.

**F2** — the reward signal is a **hardcoded constant `True`.** All eight `_record_metric` call
sites pass two positional arguments; the success parameter takes its default. **An optimiser
maximising a constant.**

**F3** — the adapted thresholds are **consumed by nothing.** Tier selection reads static
`RoutingConfig` fields; the adapted dict's only readers are `stats()` and unit tests.

**F4** — `OutcomeTracker` is **unreachable code**, not a None-valued field. `AgentExecutor` has
**zero production construction sites.**

**F5 is the one that would have fooled me, and nearly did:**

> **4,357 "Epoch complete" lines sit in the OPERATOR'S REAL log directory, 550 written today.**
> Every one is unit-test-generated.

I asked RSI0 for *evidence of execution, not wiring*. **Had it read the log rather than
`sys.modules`, it would have found 4,357 lines of exactly that, and been wrong.** The logs assert
the loop runs. It has never run.

**Ruled, answering the leg's own question — CONNECT or DELETE:** neither today. **Label it.** The
`synapse/routing` and `synapse/agent` trees are not live product and must say so at the top of
each module, because the next reader will otherwise reason from 4,357 log lines and a plausible
class name.

**And the tests stop writing to the operator's real log directory.** That is a `conftest` fix and
it is the immediate action — a test suite polluting an operator's diagnostics with false evidence
of a loop that has never run is worse than the dead loop.

---

## RULING 124 — Both research legs died on a session limit. Their numbers are floors.

**S0-F5:** *315 claims gathered, none adversarially attacked — both verifiers died on a session
limit.* **S0-F6:** the WebSearch budget is a **shared pool** consumed by the fan-out and ran out
mid-run, losing an entire research angle.

**S1** reports **31 UNREFUTED verdicts and 5 UNKNOWN** for the same reason.

**Ruled:**
1. Both legs are `amber` and correctly so. **Their verdicts are unrefuted, not confirmed**, and S2
   must treat them that way.
2. **Cap concurrent researchers on future research legs.** A shared budget silently consumed by
   fan-out is a resource collision of the same class as R92's file collisions, and the fix is the
   same: declare it before dispatch.
3. Re-run the verifiers when the limit resets. **Not before the demo** — an unrefuted claim
   labelled unrefuted is honest; a rushed re-run is not.

---

## RULING 125 — S1-F2's mechanism is REFUTED twice, and the demo path is not affected.

S1-F2 reported `synapse_inspect_scene` hanging the full 1800s MCP idle timeout, twice, on a
9-node empty scene. The observation is solid and reproduced. **Both proposed locations are wrong.**

**Candidate 1, carried by S1, REFUTED by measurement:**

> *"`_node_issues` calls `node.errors()` (introspection.py:184), which forces cooks."*

`_node_issues` over 12 real LOP nodes from `karma_user_guide.hip`: **0.00s total.** It is free.

**Candidate 2, S1's own anchor (`introspection.py:278`), REFUTED by direct call.** `inspect_scene`
invoked directly, bypassing `run_on_main` and the bridge:

```
EMPTY SCENE
  root=/       depth=1      ok   0.00s
  root=/stage  depth=1      ok   0.00s
karma_user_guide.hip, 130 /stage children
  root=/stage  depth=1      ok   0.01s
  root=/       depth=3      ok   0.08s      <- the default
```

**The function is not slow. It is instantaneous.**

### Where it actually is, and the reasoning that was wrong

S1 argued the bridge was healthy because `synapse_ping` answered instantly in the same session.
**`synapse_ping` does not marshal.** A trivial health check answering fast says nothing about
whether `run_on_main`'s queue is being drained — so the evidence that exonerated the marshal never
touched it.

**The remaining suspects are `run_on_main` and the MCP transport**, and `_handle_inspect_scene`
wraps the call in exactly the former.

### Why this matters for tomorrow, and it is the practical point

**S1 tested through the MCP surface. The panel uses the WebSocket bridge.** Those are different
transports, and R-day evidence separates them: a 5,764-node explain ran through the panel twice
today, in seconds, on the same machine.

**Ruled:**
1. **Not a demo blocker.** The path an artist uses is demonstrated working on the largest scene
   available. The path that hangs is the external MCP surface.
2. **It IS a release-notes item**, because an external MCP client is a supported way to reach
   SYNAPSE and it does not work for this tool.
3. **Root-cause is `run_on_main` under MCP, not introspection.** Anyone picking this up should
   start there and should NOT re-test `errors()` or `inspect_scene` — both are settled.

### The method note, and it is the third time this week

S1 found a real defect and attributed it to the wrong layer, because the exonerating evidence
(`ping` is fast) did not exercise the thing it exonerated. **That is the same shape as R108's
health check validating a stamp the product does not read**, and as my own R99 layer-2 error.

**A control only rules out what it actually exercises.** `ping` proved the process was alive. It
was read as proving the marshal was working.

---

## RULING 126 — Housekeeping, and the fresh-clone review nobody had run.

### Housekeeping

```
worktrees        18 -> 5      (main + 2 live legs + 2 holding unmerged work)
local branches   59 -> 16
leg windows       7 -> 2      five stale, from legs finished hours earlier
scratch           8 dirs/files removed
```

**`shot_layers/` was among the scratch** — that is R57, from Saturday: tests writing into the
repository root instead of `tmp_path`. I ruled it, recorded it, and never fixed it. It has been
regenerating on every run since. **The directory is gone; the test still needs redirecting.**

### Four branches held unmerged work. Two landed, two did not.

**Merged — `v0-m2-reconcile`**, its receipt only. R82's lesson: a ruling citing an uncommitted
anchor is a recollection.

**Merged — `q2-baseline`**, the tuple baseline reader. R40 promoted the suite baseline to a tuple;
**the reader that understands it was written, mutation-tested, and never landed.** It worked only
because I made the tuple backward-compatible on purpose, so the flat keys returned the gate
numbers and the ratchet kept functioning on half the data. **Built, correct, connected to
nothing** — found during a housekeeping pass, which is where that pattern surfaces when nobody is
looking for it.

**Not merged — `h1-schemas-b`.** Genuinely unique R33 work with a 364-line contract test not
present on HEAD. Conflicts on a receipt, so it is authoring rather than a merge. Preserved on
origin, follow-up.

**Not merged — `ledger-moneta-seam`.** U1 already authored the union from it; merging would fight
the deliberate composition. Superseded, preserved.

---

### The fresh-clone review, and why it had never been run

**Every verification this week ran from a tree with everything already configured** — `.env`
present, package deployed, dependencies resolved, Houdini pointed at it. That is the least
representative environment there is, and a producer's technical person will clone the repo.

Measured against a real `git clone` from origin, stock Python 3.14, nothing installed:

```
clone            2,668 files, 1,280 python
.env             ABSENT            <- no secret in a public repo
VERSION          5.36.3
import synapse   OK, version 5.36.3
version_agreement / bom_audit / heats_status   all present, all run
tests collected  5,166
tests/test_agent.py   62 passed
```

**It works.** A stranger can clone it, import it, and run its tests without configuring anything.

### Three observations worth keeping

**The ABI warning is exemplary and should be the model for the rest.** On a stock interpreter it
fires loudly, names the exact mismatch (`cp311 + cp313` wheels against Python 3.14.2), states the
consequence (*"the brain will fail later with a cryptic deep ImportError"*), and gives **two**
remediations with file paths. That is what a diagnostic should do, and most of this codebase's
other failure paths are quieter than this one.

**The installer's two FAIL lines are the verifier working**, not a defect: it detected the clone
is not the installed checkout and said *"run the installer."* Correct, and the message is
actionable.

**`bom_audit` exits 1 on a fresh clone** because `drop.json` is absent — and `drop.json` is MODE-B
gating that a human creates. The audit reports it as `unreadable, NOT clean`, which is the right
call by its own rule (a missing file is not a pass) and the wrong outcome here. **A first-time
user runs a README-documented command and gets a failure that is expected.** Either the audit
excludes files that are legitimately absent pre-install, or the README says so.
