# RULING — migrate-wiring (Pass 3 input)

**Date:** 2026-09-14 · **Branch:** `worktree-wf_8a870870-1d5-3` @ `42ae6899`
**Ruled against:** master `fcf0cf3b`
**Method:** every claim below re-measured in this session under **real `pxr`**
(`C:\Python314\Lib\site-packages\pxr`), not read from the Pass-2 report.

---

## The ruling in one line

**The severity-4 that held this branch splits in two: half is refuted, and the
half that survives is not this branch's defect — it is `agent_state.py`'s, it is
on master today, and `log_decision` already does it.**

---

## Sub-claim A — "a migration that never reaches disk still reports 2.0.0"

**REFUTED, on the falsifier the review itself specified** (*"read-only `agent.usd`
under real pxr must return UNKNOWN"*).

```
CONTROL  writable store    returned '2.0.0'    disk 2.0.0    agrees
ATTACK   read-only store   returned 'UNKNOWN'  disk 0.1.0    honest
```

`Sdf.Layer.Save()` on a read-only file raises `pxr.Tf.ErrorException`, which
propagates out of `migrate_to_v2` and is caught by `_upgrade_agent_usd`'s
`except Exception`, which returns `AGENT_USD_SCHEMA_UNKNOWN`. The reported
mechanism is real — `Usd.Stage.Open` *does* return the cached layer — but on
this failure path the exception beats the stale read to the answer.

Producer: `<scratchpad>/probe_migrate.py`.

---

## Sub-claim B — "in the cross-process case it destroys a persisted record"

**CONFIRMED, and reproduced.** A second process writes a record to disk; the
process holding the cached layer then runs the upgrade:

```
disk before upgrade : version=0.1.0   other-process record present=True
_upgrade returned   : '2.0.0'
disk after  upgrade : version=2.0.0   other-process record present=False
VERDICT             : RECORD DESTROYED while reporting '2.0.0'
```

Producer: `<scratchpad>/probe_migrate_stale.py`.

### But it is not this branch's defect

Every writer in `agent_state.py` is `Usd.Stage.Open(path)` → edit →
`GetRootLayer().Save()`. That shape clobbers a concurrent writer whenever the
layer is cached and stale. Tested against **master's** `agent_state`, no branch
code loaded:

```
log_decision  (production writer)   other process's record: CLOBBERED
create_task   (production writer)   other process's record: CLOBBERED
```

Producer: `<scratchpad>/probe_writers_stale.py`.

`log_decision` is the writer this branch exists to protect. It already destroys
concurrent records, on master, today.

Two further facts, both measured by grep over `python/synapse/`:

- **`agent_state.py` takes no lock of any kind.** The only hit for `lock` in that
  file is the word "block" inside a docstring.
- **Nothing in `python/synapse/` ever calls `.Reload()`.** The stale-cache hazard
  is unmitigated everywhere it exists.

So `_upgrade_agent_usd`, which takes `_get_file_lock` and makes a backup before
touching anything, is **the most careful writer in the module** — and it was held
for a hazard the unlocked, never-reloading production writers have always had.

---

## The review's prescribed fix is in the wrong place

The Pass-2 fix table says: *"Reload or drop the cached layer before verifying; or
verify against a freshly-opened SdfLayer outside the frame."*

**That is too late.** The record is destroyed by `migrate_to_v2`'s `Save()` of the
stale layer, which happens *before* any verify. A corrected verify would detect
the damage after the fact and report UNKNOWN — honest, and the record is still
gone.

Measured, the fix that works is a reload **before the migrate**:

```
reload the cached layer, then migrate
  -> other process's record on disk: True      (survived)
  -> version: 2.0.0                            (migration still landed)
VERDICT: FIX HOLDS
```

`Sdf.Layer.Find(path)` then `.Reload(force=True)`, ahead of `migrate_to_v2`.

---

## Pass 3, rescoped

| Item | Pass-2 shape | Ruling |
|---|---|---|
| I1 / B1 | reload before the **verify** | **Wrong placement.** Reload before the **migrate**; measured to preserve the record and still land the bump. Verify-side reload is a second, separate correctness fix |
| I2 fresh-init lie | assign UNAVAILABLE on `PXR_AVAILABLE` False | **Stands.** Unexamined here |
| B2 atomic import | import `ensure_scene_structure` alone | **Stands.** Unexamined here |
| T1 CI blindness | pxr-free fixture, lift out of the class gate | **Stands, and is now the bigger finding** — see the seat note below |
| B5 retriage | belongs in the panel | **Stands.** Unexamined here |
| **NEW — M1** | — | The module-wide clobber is master's. It wants its own leg: a reload-before-write (or a lock) in `agent_state.py`'s writers, `log_decision` first. **Not migrate-wiring's to carry** |

**Disposition.** The branch does not merge as-is — I2/B2/T1 are unexamined and
still owed, and the B1 fix needs the corrected placement. But the reason it was
held is now measured to be **half wrong and half not its own**. It should re-enter
on that basis rather than as a branch that "reproduced the failure class it exists
to eliminate".

---

## What this ruling does not say

It does not re-examine I2, B2, T1 or B5 — each was taken from the Pass-2 report
and is marked unexamined. It does not claim the read-only path is the only way a
save can fail; disk-full and permission-change-mid-write were not tested. It does
not measure how often two processes touch one `agent.usd` in practice — only that
when they do, master destroys the record. And it does not rule on whether M1 is
worth building; it says the finding belongs there rather than here.
