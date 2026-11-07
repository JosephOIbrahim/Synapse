## What

Hand-retyped salvage of the two hunks from `feat/scene-model` that are still real on master. Pointer: `harness/notes/closeout-2026-09-15/PLAN.md` -> **feat/scene-model** (Salvage 1 + Salvage 2) and `harness/notes/first-principles-2026-09-15/AUDIT.md` scene-model row (which replaced the vacuous `-k audit` gate and demanded the session-id uniqueness test). Nothing else is taken from the branch: no `claude_worker.py`, no read ledger, no turns ledger, no `current_session_id()` accessor.

**1. `python/synapse/core/audit.py` -- session-id collision.** `AuditLog.__init__` seeded the session id from `id(self)` + the constructing thread's ident through `deterministic_uuid`, which has no entropy of its own. `id()` is only unique among *live* objects, so once an `AuditLog` was collected the next one built on the same thread could mint the same session id, and every consumer keyed on it (`AuditEntry.session_id` at the `log()` site, `export_session`'s target filter) silently merged the two sessions. The seed now also carries `time.time_ns()` (separates process restarts -- the branch's fix) **and** a process-wide `itertools.count` class attribute (separates back-to-back constructions inside one process even on a coarse clock -- `time_ns` alone did not guarantee that on a 15.6 ms Windows clock). One id per instance is preserved (pinned by `test_session_id_is_stable_within_one_instance`).

**2. `python/synapse/server/handlers.py` -- `render_farm_status` joins `_READ_ONLY_COMMANDS`** next to `render_farm_cancel`. Verified the handler body (`handlers_render.py::_handle_render_farm_status`): `dict(self._render_farm.get_status())` plus a render-session summary -- pure Python-side reads, no `hou.*`, no undo entry. Mutating-classified it took the C5 mutation lock off-main, so while a farm render held that lock the status polls queued behind it. Master's own rationale for cancel/stop/halt/processes (`handlers_render.py` ~L1677-1681) applies verbatim; status had been skipped. The branch's comment sentence tying it to `read_ledger.INFRA_READ_COMMANDS` is dropped, as PLAN.md requires (master has no such module). Side effect worth knowing: read-only classification also skips the generic mutating audit record for each status poll; no in-handler audit was added because a status read is not an action.

**3. `tests/test_audit_session_id_unique.py` -- the failing-then-passing test** the original branch never had. Reads the session id the way consumers do (logged entry -> `export_session()[0]["session_id"]`), not off the private attribute. The collision test pins `id` inside the audit module so both constructions see the same object identity; that reproduces the post-GC condition deterministically.

## Evidence

- New test against master's `audit.py` (before the fix): `python -m pytest tests/test_audit_session_id_unique.py -q` -> **1 failed** (`test_distinct_session_ids_when_object_identity_recycles`), 2 passed, 1 skipped.
- Same file after the fix: -> **3 passed** in 0.29s.
- Named gate: `python -m pytest tests/test_core.py tests/test_v5_features.py tests/test_resilience_fixes.py -k "hash_chain or export_session or audit" -q` -> **17 passed, 172 deselected**.
- Consumers of the read-only set: `python -m pytest tests/test_live_integrity_envelope.py tests/test_handler_mutation_lock.py tests/test_render_farm_handler.py -q` -> **50 passed**.
- Allocator probe (why the GC-path variant was dropped): object is freed after `del` (weakref dead) but `id()` was reused **0 of 20** rebuilds on CPython 3.14.2/Windows; a real-GC test would only ever skip here, so the deterministic `id` pin is the gate.
- `git log master..HEAD --oneline` -> one commit `f022f894`; `git show --stat HEAD` -> 3 files, +87/-1; `git status --short` -> clean.

## Ruling needed

none

## Not checked

- Master advanced `d8ebb74a -> 329bd5b3` during the session (one docs commit adding `harness/design_review/2026-09-14/RULINGS-OPEN.md`). The branch is based on `d8ebb74a`; no rebase was attempted and no test-merge was run (disjoint files, so no conflict is expected, but that is inferred not demonstrated).
- Full stock suite and the hython seat suite were not run (per the parallel-agent law); only the named files plus the three read-only-set consumer files.
- `tests/test_live_integrity_envelope.py:323-325` has a comment listing `render_farm_status` among commands "NOT in `_READ_ONLY_COMMANDS`"; the assertions there are on `ENVELOPE_SKIP_COMMANDS` only and still pass, but that comment is now one word stale. Left untouched (outside the named scope).
- Whether any other process-lifetime consumer relied on the old session id being stable across AuditLog re-instantiation (grep found no `_current_session` reader outside `audit.py`; behaviour of `get_instance()` singleton is unchanged).
- The salvage was verified on Python 3.14.2 (the local stock interpreter), not under hython 3.13.

🤖 Generated with [Claude Code](https://claude.com/claude-code)