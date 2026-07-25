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
