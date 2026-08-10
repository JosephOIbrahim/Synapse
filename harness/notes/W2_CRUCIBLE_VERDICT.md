# W2 CRUCIBLE VERDICT — `fix/moneta-schema-registration` @ ff5ebe36

**FINDINGS (16)** — 1 BLOCK · 8 SHOULD · 7 NOTE

Reviewer: crucible (TRUST band). Read-only pass. No code changed, nothing committed.
Verification tier is stated per finding: **STATIC** = read from the tree;
**PLAUSIBLE** = depends on runtime behavior I could not execute (shell sandbox denied
`pytest` / `hython` / `python -c` in this session), with the discriminating experiment named.

**Credit where it is due, so the findings read in proportion:** the probe uses
`IsA(Usd.Typed)` as the discriminator, which is exactly the signal
`.claude/remediation_ticket.md:166` (F5) established as the only one that separates
*authoring* from *registration* — a naive `typeName` check would have been the bug.
The negative control exists and fired honestly
(`runs/w2_moneta_registration_live/`, `pluginpath_set=false`), satisfying R64 item 5.
`moneta_schema_for` requires an observed `plugInfo.json` rather than asserting a path.
`SUPPORT_MATRIX.md:66` states GUI as **pending** and says "never inferred from the
headless pass." The surfaces are honest at the field level. Every finding below is
about the layer *above* the fields — what the fields are said to mean.

---

## BLOCK

### B1 — The receipt asserts a conclusion about `MonetaBackedStore` that no probe observed, and that the store's own fallback could never have gated

**Where:** `harness/notes/receipts/W2_registration_22.0.400.json:38` (durable receipt) ·
`harness/autoresearch/missions/w2_moneta_registration.json` (`note`, authored) ·
propagated to `harness/autoresearch/runs/*/lop_truth_22.0.400.json`

**The attack.** The note ends:

> "All four true = the deployed package env is doing its job **and MonetaBackedStore's
> `use_real_usd=True` init has what it needs**."

Three separate asserted-not-observed links in one sentence.

1. **The probe never touches `MonetaBackedStore`.** `probe_usd_schema`
   (`harness/autoresearch/probes.py:418`) imports `pxr` only. It never imports
   `moneta`, never constructs `MonetaConfig`, never instantiates the store. The
   conclusion is about a code path the probe did not execute.

2. **"has what it needs" was never gated on registration in the first place.**
   `python/synapse/memory/moneta_store.py:279-296` wraps `mr.Moneta(cfg)` in
   `try/except Exception` and retries with `use_real_usd=False`. But the code's own
   comment at `moneta_store.py:272-275` says an unregistered schema makes USD writes
   "schema-blind and produce dead bytes" — it does **not** raise. So with the schema
   unregistered, `mr.Moneta(cfg)` **succeeds**, the fallback never fires, and the store
   authors untyped prims. The init "had what it needed" before this branch landed and
   after it; registration changes the *bytes*, not the *init*. The receipt credits the
   fix with an outcome that was never the failing signal.

3. **It skips the only condition R64 calls dangerous.** `python/synapse/memory/moneta_runtime.py:19-31`
   and `harness/notes/CTO_RULINGS_01.md:1684-1691` define **five** conditions, not four:

   ```
   1 module imports              2 SAME module on both interpreters
   3 schema REGISTERED  <- all four of W2's "conditions" live here
   4 prims AUTHORED with that type   (schema_in_use)
   5 a memory ROUND-TRIPS typed      (a real memory, not a probe's temp prim)
   ```

   W2's four "conditions" are four sub-facets of condition **3**, plus a synthetic
   condition 5 run on a prim the probe authored itself in a temp file. Conditions 1, 2
   and 4 are unobserved. `CTO_RULINGS_01.md:1718` names the resulting state exactly:
   *"`registered: True, in_use: False` — **the cell that reports healthy and means the
   migration is half-done**."* W2 has flipped `registered` to true and narrated
   `in_use` as satisfied. That is the house's five-bug root cause, in the receipt of
   record, on the surface built to prevent it.

   The mission note also calls these "the four `moneta_runtime.py` conditions."
   `moneta_runtime.py` documents five and names neither four nor this decomposition.
   The citation is wrong about its own source.

**Failure scenario.** Schema registers (true). `MonetaBackedStore` initializes with
`use_real_usd=True` (it would have anyway). Moneta's USD target writes to
`.moneta/usd/` under a code path SYNAPSE has never observed authoring a single prim
(`remediation_ticket.md:152`, F3: *"zero `cortex_*.usda` exist anywhere under
`C:/Users/User`"*). A reader of `SUPPORT_MATRIX.md:65` → the receipt concludes the
memory substrate is live. `schema_in_use` is still false. The next session flips the
`use_real_usd` REVIEW gate the capsule parks at `W2_MONETA_REGISTRATION_CAPSULE.md:52-54`
on the strength of a claim about it that was written before it was observed.

**Fix.** Two edits, both cheap, neither requires new machinery:
1. Truncate the note at what was observed: *"…= the MonetaMemory schema is registered
   in this hython process (R64 condition 3). Conditions 1, 2, 4 and 5-for-a-real-memory
   are not observed by this probe."* Delete the `MonetaBackedStore` clause.
2. Add a second question observing condition 4 — `moneta_runtime.schema_in_use()` and
   `moneta_provenance()` already exist and already return tri-state with reasons
   (`moneta_runtime.py:372`, `:571`). A `moneta_provenance_probe` kind that records all
   five fields verbatim is a smaller change than the one already shipped, and it is the
   probe R64 actually ruled for.

---

## SHOULD

### S1 — In-process registration check contradicts a ratified ruling; env provenance is unrecorded, which is the GUI false-positive route

**Where:** `harness/autoresearch/probes.py:426` (`_os.environ.get("PXR_PLUGINPATH_NAME")`),
`:446`, `:453-454`

**The attack.** `CTO_RULINGS_01.md:1730-1734`, RULING 64 item 4, ruled:

> **"Reuse Moneta's isolation pattern, do not reinvent it.** `tests/_schema_gate_subprocess.py`
> runs under `subprocess.run` with `PXR_PLUGINPATH_NAME` pointed at `schema/`, because USD
> plugin registration is **process-global** and cannot be tested in-process without
> contaminating the run. That is careful work already done."

`probe_usd_schema` tests it in-process, from the ambient environment, and records **no
provenance for that environment**. `pluginpath_entries` records the *value*; nothing
records *who set it*.

**Exact conditions for `roundtrip_typed=true` with a GUI session still unregistered:**

- The operator (or any parent shell, `houdini.env`, a prior debugging session, a wrapper
  script, or `Start-AutoResearch` inheriting an exported var) has `PXR_PLUGINPATH_NAME`
  in the shell environment that launched `hython`. `hython` inherits it; a GUI Houdini
  launched from the Start menu / desktop shortcut does not. All four fields read true;
  the GUI seat is schema-blind.
- Or: the deployed package sits in a pref dir `hython` resolves but the GUI build does
  not (the capsule at `W2_MONETA_REGISTRATION_CAPSULE.md:34-36` documents this seat
  hitting exactly that trap once already — `C:/Users/User/houdini22.0` vs the OneDrive
  redirect).

I checked `drive_autoresearch.ps1` — it sets no USD env vars, and run 1 recorded
`pluginpath_set=false` in the same session family, which is *corroborating* evidence the
value came from the package. But that inference lives in a human's head, not in the
artifact. The probe is reusable; the next run has no such corroboration.

**Fix.** Record provenance alongside the value — all read-only, all `os`-level:
`HOUDINI_PACKAGE_DIR`, `HOUDINI_USER_PREF_DIR`, and whether a deployed
`<pref>/packages/synapse.json` carries the same `PXR_PLUGINPATH_NAME` value. Better, and
what R64 already ruled: re-probe in a `subprocess.run` with a **scrubbed** env
(`PXR_PLUGINPATH_NAME` removed) — if the subprocess still reports registered, the
package supplied it; if not, the shell did. That one extra field is the difference
between "registered here" and "registered for anyone who launches this build."

### S2 — `note` is model-authored text landing in the evidence record with no provenance marker

**Where:** `harness/autoresearch/runner.py:113-114` · surfacing at
`receipts/W2_registration_22.0.400.json:38`

**The attack.** This is the wave's `policy_overrides`-class lever. Mission JSON is
model-authorable. `execute_question` reads `q.get("note", "")` and `record()` writes it
into the entry as a sibling key of `value`, `probe`, `build`, `ts` — every one of which
is machine-produced. Nothing in the schema, the entry, or the receipt distinguishes
"observed by a probe" from "asserted by whoever wrote the mission." B1 is one instance;
the lever is structural and survives B1's fix.

The mission author cannot fake a `value` — probes produce those. It can write any
conclusion it likes into `note`, and that note travels verbatim into the durable receipt
that `SUPPORT_MATRIX.md:65` cites as evidence.

**Fix.** Rename the key on the way into the record: `entry["author_note"]`, or keep
`note` and add `entry["note_source"] = "mission"`. One line in `runner.py:113-114`,
applies to every probe kind, and makes the boundary machine-readable rather than
convention.

### S3 — `roundtrip_typed` is a same-process reopen presented as a "fresh reopen," and is near-entailed by condition 3

**Where:** `harness/autoresearch/probes.py:476` (`Usd.Stage.Open(tmp.name)`) ·
claim text at `receipts/W2_registration_22.0.400.json:38` and `docs/SUPPORT_MATRIX.md:65`
("survived author→save→**fresh-reopen**")

**The attack, two parts.**

*(a) It is not fresh.* `Usd.Stage.Open` resolves its root layer through
`SdfLayer::FindOrOpen`, which returns an already-open layer with that identifier if one
is alive. `del stage, prim` at `probes.py:474` drops the Python references, but nothing
**observes** that the layer left the registry — and a lingering reference (a traceback
frame, an exception path, a future edit that keeps a handle for diagnostics) silently
converts the round trip into an in-memory no-op that never reads the bytes on disk.
`roundtrip_typed=true` would then be a PASS-shaped value for a disk round trip that
did not happen. **PLAUSIBLE** — CPython refcounting probably does release it today; the
finding is that the probe does not *observe* that it did, so the guarantee rests on an
implementation detail rather than on evidence.

*(b) Even when it is fresh, it is near-tautological.* The schema registry is
process-global and already loaded. Given `type_registered=true` in this process,
authoring a prim and reopening it *in the same process* will be typed. Condition 4 is
not independent evidence of condition 3; it is a restatement. The "four conditions, all
true" framing implies four independent observations and gets three-and-a-restatement.

**Fix.** Both parts collapse into one change: do the reopen in a `subprocess.run`
(which S1 already needs), which makes it genuinely fresh *and* genuinely independent.
If that is too heavy, the one-line honest version is to read the saved `.usda` text back
and record that `typeName = "MonetaMemory"` is present in the serialized bytes — that is
a real disk observation — and rename the field to `roundtrip_typed_same_process` so the
claim matches the method. Drop "fresh" from both the receipt note and `SUPPORT_MATRIX.md:65`.

### S4 — An exception in the round trip destroys the conditions 1–3 evidence already gathered

**Where:** `harness/autoresearch/probes.py:467-491` · `harness/autoresearch/runner.py:198-200`

**The attack.** The round-trip block has a `finally` that unlinks the temp file but **no
`except`**. Any raise inside it — `Usd.Stage.CreateNew` failing on a locked/read-only
`TMP`, `DefinePrim` raising `Tf.ErrorException` on a token-invalid `schema_type`, a
permissions error on `Save()` — propagates to `execute_question`, whose handler at
`runner.py:198-200` replaces the **entire** entry value with `{"error": traceback}`.

Everything already observed and stored in `out` — `pluginpath_set`,
`pluginpath_entries`, `pluginfo_on_disk`, `plugin_registered`, `type_registered`,
`is_concrete` — is discarded. A run that successfully observed three of four conditions
records zero of them. That is the opposite of the module's stated discipline at
`probes.py:5-7` ("a missing type is an answer, not an exception").

**Failure scenario.** CI or a farm seat with a read-only `TEMP`. The probe observes the
schema registered, then dies on the temp file. The evidence file shows a traceback, the
operator re-reads it as "the probe failed" and re-runs, and the three good observations
are never banked.

**Fix.** Wrap `probes.py:469-486` in `try/except Exception as e`, set
`out["roundtrip_typed"] = "UNKNOWN"` and `out["roundtrip_error"] = f"{type(e).__name__}: {e}"`,
and `return out`. Partial observation is the whole point of the UNKNOWN posture.

### S5 — `check_schema_env` is build-unaware; it mis-buckets in both directions

**Where:** `scripts/install_synapse_package.py:462-507`, called at `:517`

**The attack.** `check_package_file` takes `targets=pref_names_for(installs)`
(`:516`) precisely because *"what decides whether the panel appears is whether the pref
dir belonging to the INSTALLED build is wired"* (`:307-310`). `check_schema_env` is
called with no such argument and iterates every wired pref dir equally.

- **False FAIL.** Seat: `houdini22.0` (the installed build) wired and schema-ok;
  `houdini21.0` wired from a pre-fix deploy and schema-blind. `bad = ["houdini21.0"]` →
  **FAIL** at `:502-505`, exit 1, message *"MonetaMemory prims will be untyped"* — for a
  build that is not installed. The operator's actual seat is correct.
- **False PASS.** Seat: `houdini21.0` wired and schema-ok; `houdini22.0` (installed) not
  wired at all → `package_points_here` false → `continue` at `:489` → never enters `bad`
  → **PASS** printing *"1 wired pref dir(s) register the MonetaMemory schema"* while the
  build that will actually run sees nothing. The `package file` row FAILs separately, so
  the exit code is right, but the one-screen report carries a green line asserting
  registration for a seat that has none. `:453-454` says manual rows are *"NEVER inferred
  from a green probe"* — this is a green probe row inferring across builds.

**Fix.** Give it the same argument: `check_schema_env(repo_root, prefs, pref_names_for(installs))`,
and scope both the `bad` list and the PASS text to pref dirs whose name is in `targets`.
Report non-target pref dirs as an informational suffix, not as the verdict.

### S6 — `check_schema_env` PASSes on *any* plugInfo-bearing dir, then claims MonetaMemory specifically

**Where:** `scripts/install_synapse_package.py:491-495`, PASS text at `:506-507`

**The attack.**

```python
vals = [e.get("value") for e in data.get("env", []) if e.get("var") == "PXR_PLUGINPATH_NAME"]
ok = any(isinstance(v, str) and (Path(v) / "plugInfo.json").is_file() for v in vals)
```

`ok` is true if the deployed package registers *any* directory that happens to contain a
`plugInfo.json`. It is never compared against `schema` — the path
`moneta_schema_for()` observed three lines earlier at `:473` — and the `plugInfo.json`
is never opened to confirm it declares `MonetaMemory`. The PASS text then states
*"register the MonetaMemory schema"*: a claim strictly stronger than the observation,
which is the finding class this whole branch exists to close.

**Failure scenario.** Two Moneta checkouts on the seat (`../Moneta` and `../Moneta-wip`,
routine during a schema regen). The deployed package registers `../Moneta-wip/schema`,
whose `plugInfo.json` is mid-`usdGenSchema` or declares an older type name. `ok` is
true, the row PASSes, `--verify` exits 0, and the seat's `MonetaMemory` is unregistered
— the exact 2026-08-09 disease, now with a green light in front of it.

**Fix.** `ok = any(isinstance(v, str) and Path(v).as_posix() == schema for v in vals)`.
For the stronger version, `json.loads` the `plugInfo.json` and confirm `MonetaMemory`
appears in its declared types — the file is small and already being stat'd.

### S7 — A real seat lands in a permanent FAIL whose stated remedy cannot fix it

**Where:** `scripts/install_synapse_package.py:63-78` vs `:473-477`

**The attack.** `build_package` nests the entire Moneta trio — including
`PXR_PLUGINPATH_NAME` at `:77` — inside `if moneta:` where `moneta = moneta_src_for(repo_root)`,
i.e. gated on `../Moneta/**src**` being a directory (`:37-40`). `check_schema_env` gates
only on `moneta_schema_for` (`:473`), i.e. on `../Moneta/**schema**/plugInfo.json`.

**Seat: `../Moneta/schema/plugInfo.json` present, `../Moneta/src` absent.**
- `build_package` authors no `PXR_PLUGINPATH_NAME` and no `SYNAPSE_MEMORY_BACKEND`.
- `check_schema_env` proceeds, finds the deployed package lacks the var, → **FAIL** at
  `:502-505` advising *"re-run the installer (no --dry-run)."*
- Re-running the installer authors nothing. The FAIL is permanent and the advice is
  unactionable.

This is not hypothetical for this project: `remediation_ticket.md:149` (F2) records that
the Moneta **wheel ships no `schema/` at all** (`packages = ["src/moneta"]`). A seat that
pip-installs moneta and hand-places the schema directory from the repo — the documented
way to get the schema — produces exactly `schema` without `src`.

**Fix.** Decouple the two vars: author `PXR_PLUGINPATH_NAME` on
`moneta_schema_for(...)` alone, and `MONETA_SRC`/`SYNAPSE_MEMORY_BACKEND` on
`moneta_src_for(...)` alone. They answer different questions and are already computed
independently. Failing that, make the FAIL message name the real blocker
(*"no ../Moneta/src — the installer cannot author this var"*) rather than prescribing a
no-op.

### S8 — Parity is pinned by variable **name** only; `method`, value shape, and top-level keys are all unpinned

**Where:** `tests/test_install_package_parity.py:55-97` (all four tests)

**The attack.** `test_resolver_env_names_match_tracked_package` compares
`{e["var"] for e in ...}` against `{e["var"] for e in tracked}`. The drift class that
actually bit on 2026-08-09 was a missing name, and the tests close exactly that class
and no other. Drifts the four tests would **not** catch:

1. **`method` divergence — the highest-severity gap.** `packages/synapse.json:15` sets
   `"method": "prepend"` on `PYTHONPATH`; `install_synapse_package.py:61` sets it too.
   Delete that key from either surface and the var is **replaced** instead of prepended,
   discarding Houdini's own `PYTHONPATH`. All four tests stay green. The same gap covers
   `PXR_PLUGINPATH_NAME` (see N3).
2. **Top-level keys.** The tests read `data["env"]` only. `hpath`, `load_package_once`,
   `enable`, `name` are never compared. `hpath` is the H22-sensitive keyword the code
   comments flag twice (`install_synapse_package.py:86-87`, `packages/synapse.json:5`);
   a revert to the deprecated `path` on one surface passes all four tests.
3. **Value shape.** Only `PXR_PLUGINPATH_NAME` has its value asserted (`:89-97`).
   `PYTHONPATH` order, `SYNAPSE_MEMORY_BACKEND == "moneta"`, and `SYNAPSE_ROOT`'s
   resolution are unpinned.
4. **Duplicates.** Set equality cannot see a var emitted twice. Only
   `PXR_PLUGINPATH_NAME` has a `len(vals) == 1` assertion.
5. **`check_schema_env` has zero coverage.** The new verify row — the surface carrying
   S5, S6 and S7 — is not touched by any of the four tests, nor by anything else in
   `tests/`. The bucket logic most likely to mis-bucket is the one thing unpinned.

**Fix.** Compare `(var, method)` pairs rather than bare names; add a top-level-key
equality assertion for everything except `comment` and the resolved-vs-`$`-var values;
add `check_schema_env` cases for the seat states in S5/S6/S7 using the existing
`_fake_seat` fixture (it already builds tmp seats — the incremental cost is small).

### S9 — `SUPPORT_MATRIX` cites an untracked directory as the receipt of record

**Where:** `docs/SUPPORT_MATRIX.md:65`

**The attack.** The "verified" row cites
`harness/autoresearch/runs/w2_moneta_registration_live2/lop_truth_22.0.400.json`. That
directory is **untracked** — `git status` shows both W2 run dirs as `??` at
`ff5ebe36`. Sibling run dirs *are* tracked
(`git ls-files harness/autoresearch/runs/` returns `fixture_verify_*`, `scout_*`), so
this is a break from the established convention, not a directory-wide ignore.

A fresh clone cannot resolve the citation. Per the doc's own header — *"Rows are dated
receipts"* (`:4`) — the row's receipt does not exist in the repository.

Compounding: the committed receipt (`harness/notes/receipts/W2_registration_22.0.400.json`)
carries **only the after-picture**. The negative control — run 1, `pluginpath_set=false`,
which is what makes the check discriminating rather than decorative and which R64 item 5
(`CTO_RULINGS_01.md:1735-1737`) makes **mandatory** — exists only in the untracked
directory. The strongest evidence produced by this wave is the piece not committed.

**Fix.** Commit both run dirs (they are 3 small files each), or repoint `:65` at the
committed receipt. Either way, add the run-1 entry to
`receipts/W2_registration_22.0.400.json` as the paired negative control — a receipt
showing only the pass is the shape R64 item 5 exists to forbid.

---

## NOTE

### N1 — `roundtrip_typed = False` is asserted, not observed (live instance in the committed evidence)

**Where:** `harness/autoresearch/probes.py:462-465`

When `type_registered` is false the probe returns `roundtrip_typed = False` with
`roundtrip_note = "type not registered; authored prims would be untyped"` — a
**prediction**, without running the round trip. The value is observable: nothing
prevents authoring the prim anyway. Per the house UNKNOWN rule this must be `"UNKNOWN"`
or actually observed; a hardcoded `False` sits in the evidence file indistinguishable
from a measured one.

This is not theoretical — it is already in the artifacts:
`runs/w2_moneta_registration_live/lop_truth_22.0.400.json` records
`"roundtrip_typed": false` for a round trip that never executed. The direction is
FAIL-shaped so the blast radius is small, but the rule is symmetric, and this probe is
the one being adopted as the pattern for future kinds.

There is also a real inversion available: `FindConcretePrimDefinition` returns `None`
for abstract and API schemas, so `type_registered=false` does not mean "not registered"
— it means "not registered *as concrete*." For a non-concrete schema the asserted
`roundtrip_typed=False` could contradict what a run would actually show.

**Fix.** Run the round trip unconditionally and record what happens — it costs one temp
file and turns a prediction into evidence. If skipping is preferred, emit `"UNKNOWN"`
with the reason. Separately, rename `type_registered` → `concrete_type_registered` so
the field name stops over-claiming.

### N2 — `is_concrete = False` asserted when `prim_def` is `None`

**Where:** `harness/autoresearch/probes.py:456`

`bool(reg.IsConcrete(schema_type)) if prim_def else False` — when `prim_def` is `None`,
`IsConcrete` is never called and `False` is written anyway. `IsConcrete` is callable
regardless of `FindConcretePrimDefinition`'s result. Same class as N1: an unobserved
value rendered as a definite one.
**Fix.** Call `reg.IsConcrete(schema_type)` unconditionally.

### N3 — `PXR_PLUGINPATH_NAME` is authored without `method`, silently clobbering any pre-existing value

**Where:** `scripts/install_synapse_package.py:77` · `packages/synapse.json:22-25`

Both surfaces author the var as a plain `{"var", "value"}` entry. The sibling
`PYTHONPATH` entry in the same files explicitly carries `"method": "prepend"`
(`packages/synapse.json:15`, `install_synapse_package.py:61`) — which is itself the
evidence that a bare entry replaces rather than accumulates.

Consequence: on any seat that already registers USD plugins through
`PXR_PLUGINPATH_NAME` (studio schemas, a renderer's USD plugin, a second Moneta), the
SYNAPSE package **unregisters all of them** for that Houdini session. This is a shared
defect, not drift, so S8's name-parity test would not have caught it either.
**Fix.** `"method": "append"` on both surfaces, and pin `(var, method)` pairs per S8.

### N4 — `plugInfo.json` is assumed to live *inside* a directory entry

**Where:** `harness/autoresearch/probes.py:430-433` ·
`scripts/install_synapse_package.py:48`, `:493-494`

All three sites test `<entry>/plugInfo.json`. `PXR_PLUGINPATH_NAME` also accepts an entry
that *is* a `plugInfo.json` file path. Such an entry registers correctly with USD but
reads as absent here — a false negative in `pluginfo_on_disk`, and a **false FAIL** in
`check_schema_env` for a correctly-registered seat. The same site is blind to a list-valued
`PXR_PLUGINPATH_NAME` (`isinstance(v, str)` at `:493`), which is legal in a Houdini package
and is what an `append`-method fix (N3) may produce.
**Fix.** Accept both shapes: `p if p.name == "plugInfo.json" else p / "plugInfo.json"`,
and normalize a list value to its elements before testing.

### N5 — `DONE`'s `failures` count cannot see UNKNOWN or degraded results

**Where:** `harness/autoresearch/runner.py:125-127`, written to `DONE` at `:132-137`

`failures()` counts only entries whose `value` dict has an `"error"` key. A run where
`pxr` failed to import — `probes.py:436-441`, which sets three fields to `"UNKNOWN"` and
returns normally — writes `DONE` with `"failures": 0`. Both W2 runs report
`"failures": 0`, including the all-false one; the sentinel a poller reads first cannot
distinguish "observed false" from "could not observe."
**Fix.** Add `unknowns` to the `DONE` payload, counting entries whose value contains
`"UNKNOWN"` at any depth.

### N6 — `mission_schema` docstring lists four kinds; `VALID_KINDS` has six

**Where:** `harness/autoresearch/mission_schema.py:6-13` vs `:21-22`

The module docstring documents `type_discovery`, `type_existence`, `parm_probe`,
`chain_hash`. `VALID_KINDS` also contains `fixture_hash` and `usd_schema_probe`. The
docstring is the schema's own documentation and it is now two kinds stale — including
the one this branch adds.
**Fix.** Add both lines, with their field signatures, matching the existing format.

### N7 — `plugin_path` is absent rather than `"UNKNOWN"` on the not-asked path

**Where:** `harness/autoresearch/probes.py:445-450`

When `plugin_name` is empty, `plugin_registered` is correctly set to `"UNKNOWN"`, but
`plugin_path` is **not set at all** — the key is simply missing from the result, whereas
on the asked path it is present-and-`None`. Three states (observed value / observed
absent / not asked) render as two shapes across runs, so a consumer diffing evidence
files sees a schema change rather than a posture change.
**Fix.** Set `out["plugin_path"] = "UNKNOWN"` in the `else` branch at `:450`.

---

## Summary of the attack surface, against the brief

| Requested attack | Result |
|---|---|
| PASS-shaped value reported without observing it | **B1** (store conclusion), **S6** (any-plugInfo PASS), **S3(b)** (near-tautological condition 4), **N1/N2** (asserted falses) |
| `roundtrip_typed` true while GUI sees unregistered | **S1** — shell-supplied env inherited by `hython`, not by a GUI launch; provenance unrecorded. Also **S3(a)** — same-process reopen may never read disk |
| LLM-reachable lever beyond read-only observation | **S2** — model-authored `note` enters the evidence record unmarked and reaches the durable receipt. Lesser: `roundtrip:true` makes the probe library's first disk write (bounded to `tempfile`) |
| Parity blind spot the four tests miss | **S8** — `method`, top-level keys, value shape, duplicates, and `check_schema_env` entirely |
| UNKNOWN-rule violations | **N1**, **N2**, **N7**; inverse direction (claim rendered UNKNOWN that was observable) — **N1** is exactly this |
| `check_schema_env` wrong bucket | **S5** (build-unaware, both directions), **S6** (false PASS), **S7** (unfixable FAIL), **N4** (false FAIL on a legal env shape) |

**Bottom line.** The code is careful and the field-level honesty is real — `IsA(Usd.Typed)`,
the observed-`plugInfo` requirement, the negative control, the `pending` GUI row. The
defect is one layer up and it is the house's signature one: a set of narrow, correct
observations about R64 **condition 3** is narrated in the durable receipt as a verdict
about conditions 4 and 5 for a store the probe never instantiated. B1 is a text fix plus
one already-written function (`moneta_runtime.schema_in_use()`); everything else is
SHOULD or NOTE.
