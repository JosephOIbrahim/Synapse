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
