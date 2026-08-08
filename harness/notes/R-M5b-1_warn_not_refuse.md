# R-M5b-1 — warn, not refuse

**Ruled:** 2026-08-07 by Joe Ibrahim · `harness/NEXT_SESSION.md:68` (commit `1f18ab46`)
**Escalated:** 2026-08-06 · `harness/notes/receipts/M5b.json:221-228` (`for_ruling[0]`), finding `M5b-F8`
**Committed:** 2026-08-08 · this note + `python/synapse/cognitive/tools/scout.py`
**Scope:** scout only. Tier VERIFIED-STATIC unless marked otherwise.

---

## 1. The ruling

Escalated question (`M5b.json:224`):

> Should scout's phantom gate REFUSE (or warn) in a genuinely external process —
> CI, a farm node, stock python — where there is no running Houdini and the
> committed H21 table currently loads as authority reporting `stale=false`?

Ruled (`NEXT_SESSION.md:68`):

> **R-M5b-1** (ruled warn-not-refuse, never committed). One-line scout change:
> external/no-Houdini process should WARN not refuse on the phantom gate.

Grounding stays armed. The change is that the authority stops claiming a
freshness nothing checked.

---

## 2. What was actually there (the estimate's premise was wrong)

The brief that dispatched this work already carried the correction, made in the
CTO session of 2026-08-08: **the external path never refused.** It did the
opposite — it silently served the committed H21 table as membership authority
and reported `stale=false`.

The mechanism, at `scout.py::_load_symbol_table`:

- `_running_build()` returns `""` (no injection, no `HOUDINI_VERSION`)
- so `expected = _running_build() or _pkg_table_version()` — the **committed
  table's own stamp**
- `stamp != expected` is therefore false **by construction**: the table is being
  compared against itself
- the gate passes, `stale` stays `False`, `loaded` stays `True`

That is a Law-1 defect in the small: a check that cannot fail. It reported
healthy continuously while proving nothing — exactly what M5b-F8 recorded, and
what R-M5-4 fixed one layer up for the *in-Houdini* uninjected case.

So the ruled change is not "stop refusing". It is **"keep grounding, add the
warning, and report the authority honestly."**

---

## 3. The change

`python/synapse/cognitive/tools/scout.py:615` — a new `elif` branch on the
already-existing mismatch check inside `_load_symbol_table`, plus a dedupe set
at `:434` and two docstring lines (`:579`, `:827`).

```python
        elif not _running_build():
            status["verified_against_running_build"] = False
            status["reason"] = (
                f"no running Houdini to verify against - membership authority is "
                f"the committed Houdini {stamp or 'unstamped'} table; verdicts hold "
                f"for {stamp or 'that build'}, not for the build you will run on. "
                f"Regenerate on the target host: hython host/introspect_runtime.py")
            _WARN.append(f"[scout] {status['reason']}")
            if key not in _WARNED_EXTERNAL_AUTHORITY:
                _WARNED_EXTERNAL_AUTHORITY.add(key)
                warnings.warn(f"SYNAPSE scout: {status['reason']}",
                              RuntimeWarning, stacklevel=3)
```

Two channels, deliberately different cadences — the same split
`_warn_build_mismatch` already uses:

| Channel | Cadence | Who reads it |
|---|---|---|
| `_WARN` → `result["warnings"]` | every call | the MCP caller reading the JSON |
| `warnings.warn(RuntimeWarning)` | once per table path per process | CI logs, pytest, a farm process's stderr |

**Not one line: +28 / -1 in `scout.py`** (20 of them the new branch, 8 of those
comment; producer: `git diff --numstat`), **+80 / -0 in `tests/test_scout.py`**.
§5 says why.

---

## 4. Why `stale` was NOT flipped — the load-bearing finding

The obvious encoding of "report the authority as stale" is
`status["stale"] = True`. **That would have refused.**

`stale` is the `DRIFT_POLICY` trigger, and the default is fail-closed:

- `scout.py:129` — `DRIFT_POLICY = os.environ.get("SYNAPSE_SCOUT_DRIFT_POLICY", "refuse")`
- `scout.py:850-853` — `if table_status["stale"]: ... if DRIFT_POLICY == "refuse": raise ScoutError(...)`

Flipping `stale` on the external path would raise `ScoutError` in **every** CI
run, farm node and stock-python process by default — the literal refusal the
ruling rejected, and a direct breach of the brief's *"no disarming of external
grounding."* In this module `stale=True` is also structurally coupled to
gate-down: both existing sites that set it also set `loaded=False` and return
`None`.

A second, independent confirmation from the tree: `tests/test_scout.py:188`
asserts a fresh corpus emits **no warning containing the word "stale"**. The
`stale` token is reserved for the corpus-drift axis. The R-M5b-1 signal needed
its own name in both the status dict and the message text.

Hence `verified_against_running_build`, a separate field on a separate axis.
It answers a different question than `stale` does:

- `stale` — *is this authority usable at all?* (no → gate down → refuse/warn per policy)
- `verified_against_running_build` — *was it checked against the build we are on?*
  (no → still usable, but say so)

---

## 5. Why the ~10-minute / one-line estimate missed

Not scope creep — the one-line shape was unavailable, for reasons only visible
from the tree:

1. **The single-line target was booby-trapped.** The natural one-liner
   (`stale=True`) is the refuse trigger (§4). The honest encoding needs its own
   field, its own message, and a dedupe set.
2. **Two warn channels already exist** and the module's precedent
   (`_warn_build_mismatch`) uses both with different cadences. Matching that is
   the reason for the `if key not in _WARNED_EXTERNAL_AUTHORITY` guard.
3. **Law 1 owes a test.** A ruled behaviour change shipped unpinned is a
   decoration. The new tests state their failure condition and carry a control
   proving the check can fail (`+2` tests, 35 → 37 in `test_scout.py`).

Per the brief's instruction 3, this is the **smallest honest diff** — stopped
here, not expanded to make the estimate fit. Nothing was refactored, no other
caller was adjusted, no adjacent finding was repaired.

---

## 6. Why scout scope only

- **The ruling is scout-scoped.** It names the phantom gate, whose sole
  implementation is `scout._load_symbol_table`.
- **The panel cannot be affected.** `python/synapse/panel/gate_stamp.py` mirrors
  the staleness logic but calls `_read_symbol_table` / `_symbol_table_path`
  directly — never `_load_symbol_table` — and returns early unless `import hou`
  succeeds. Neither touched.
- **The harness guardrail is unaffected.** `harness/verify/checks.py:548`
  branches on `table_syms is None`. The external path still returns symbols, so
  `check_phantom_clean` behaves exactly as before.
- **In-Houdini is structurally untouched.** The new branch is guarded by
  `not _running_build()`, which is false whenever a build is injected or
  `HOUDINI_VERSION` is set. Every pre-existing line in `_load_symbol_table` is
  byte-unchanged, and the key is added on the external path *only* — so the
  in-Houdini status dict keeps its exact prior shape. Pinned by the control
  branch of `test_external_process_warns_that_its_authority_is_unverified`
  (`tests/test_scout.py:566-575`).

---

## 7. Evidence

| Claim | Tier | Anchor |
|---|---|---|
| External path served H21 as authority reporting `stale=false` | VERIFIED-STATIC | `M5b.json:206-210` (M5b-F8) |
| `stale` is the refuse trigger; default policy is `refuse` | VERIFIED-STATIC | `scout.py:129`, `scout.py:850-853` |
| "stale" is reserved for the corpus axis in the warning channel | VERIFIED-STATIC | `tests/test_scout.py:188` |
| Panel gate does not use `_load_symbol_table` | VERIFIED-STATIC | `python/synapse/panel/gate_stamp.py:19-31` |
| Harness guardrail keys on `table_syms is None` | VERIFIED-STATIC | `harness/verify/checks.py:548-549` |
| Grounding still armed + warned, not refused, under `DRIFT_POLICY=refuse` | VERIFIED-DERIVED (pytest) | `tests/test_scout.py::test_external_process_is_not_refused_under_the_fail_closed_policy` |
| In-Houdini shape unchanged | VERIFIED-DERIVED (pytest) | `tests/test_scout.py:566-575` (control branch) |

Suite: `tests/test_scout.py` 35 → 37 passed. The 20 scout-touching test files
(322 tests) pass. Full-suite numbers are in
`harness/notes/receipts/WARN.json`.

---

## 8. What this does NOT do

- It does not disarm external grounding. CI, farm and stock-python callers still
  receive a real introspected membership authority and real
  `exists_in_runtime` verdicts.
- It does not change any in-Houdini behaviour.
- It does not make the external verdicts *correct for the target build* — it
  makes them **labelled**. A verdict cut on the committed H21 table is valid for
  21.0.671 and now says so. Closing that gap properly means a table for the
  build you will run on, which is a regeneration act on a host
  (`hython host/introspect_runtime.py`), not a scout change.
