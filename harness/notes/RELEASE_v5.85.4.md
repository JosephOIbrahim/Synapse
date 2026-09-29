# Release preparation: v5.85.4

Publish three commits on top of v5.85.3 (`a0ad330d`). Joe's word: "Yes", to
"Should I push those three and release v5.85.4, or keep going down the queue?"
(2026-09-29).

| Commit | What it does |
|---|---|
| `4904709e` | BP12 item 1, part 1: `add_durable_many_if_absent()` on both stores, `UsdCortexStore.deferred_save()`, and the lifecycle carry uses the batch; 6 tests |
| `d3f82193` | BP12 item 1, part 2: each untitled launch binds its own `sessions/<id>` store; 3 address tests re-pinned; 4 tests |
| `8201e7b6` | BP12 item 9: `MemoryStore.clear()` saves after releasing the writer lock; `tests/test_scout.py` unconfigures the machine's SideFX library; 1 test |

## Evidence

- **Item 1, the cause.** The carry paid a strict scan, a full Moneta snapshot and a
  full `cortex_root.usda` save per record. At 30 records the old code wrote 34
  snapshots, 35 scans and 34 cortex saves; the new code writes 5 snapshots and 6
  scans at any size.
- **Item 1, the receipt.** `hython` on Houdini 22.0.400, Moneta, real `pxr`,
  1,458 records (`hython_save_freeze_probe_v1.py`): 309 s on the v5.85.3 code,
  3.2 s with a session holding them, 0.09 s with them left in the shared root
  and one new record. The embedder was the default one, which in Houdini's
  Python on this machine falls back to hashing (BP12 item 19). The commit
  message of `d3f82193` calls it "the production minilm embedder"; that names
  the id the store records, not the model that ran.
- **Item 1, legacy records.** The 1,458 records stay untouched at
  `%TEMP%\houdini_temp\untitled\.synapse` (`snapshot.json`, 11,079,309 bytes).
- **Item 9, the deadlock.** `clear()` held `_lock.write_lock()` and called
  `save()`, which takes the same non-reentrant `ReadWriteLock`. Lock order in
  the fix matches `save()`: `_lock`, then `_write_lock`.
- **Item 9, mutation.** HEAD's `store.py` with the new test fails only on
  `finished.wait(10)` (1 failed, 10.35 s) and the process exits. HEAD's
  `test_scout.py` without the fixture fails 2 here
  (`test_domain_vex_filters_to_vex_entries`,
  `test_real_but_undocumented_resolves_true`) and the new one passes 37.
- **Skips.** Nothing in `pytest.ini`, `conftest.py`, `.github/workflows` or
  `scripts/` skipped `test_scout.py`; only the seat's own suite command did.
- **Tests.** The `tests/` suite passed on Windows with Python 3.14 with the
  Houdini-only tests deselected: 10,171 passed, 457 skipped, 119 deselected,
  5 xfailed, 2 xpassed, 0 failed (341 s). The except ratchet is unchanged
  (`broad_total=1379`, `silent_total=995`).
- **Advice.** Fable 5.1 reviewed the save-freeze approach and the item 9 change
  before and after. Jev was not used: batch size, folder binding, lock order and
  a test fixture are exact questions.
- **Known, not fixed.** BP12 items 18 (notes and store in different folders),
  19 (embedder id without the model), 20 (Clear All Memories is silent on
  Moneta) and 21 (a flusher append can follow a save).

This record does not claim that the later CI, push or publication steps have
completed. They are checked after publication.
