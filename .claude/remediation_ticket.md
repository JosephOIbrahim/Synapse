# REMEDIATION TICKET — H6 substrate truth

**Filed** 2026-07-26 · **By** interactive ORCHESTRATOR session (model `claude-opus-5[1m]`)
**Blocker class** Article V violation — two agents writing one worktree
**Status** WRITE PATH STOPPED. Recon complete and preserved. Human decision required.

---

## The blocker

**Two independent executions of leg H6 are running against
`.claude/worktrees/h6-substrate-truth` on branch `repair/h6-substrate-truth`.**

1. An **orchestrator-launched run**, started `16:07:34` (marker `.claude/.orch_launched`).
   It has already written `python/synapse/memory/moneta_runtime.py` (+~390 lines:
   `_schema_registered_detail`, `schema_registered`, `_resolve_usd_root`,
   `_schema_in_use_detail`, `schema_in_use`, `moneta_provenance(usd_root=...)`) and
   `python/synapse/server/doctor.py` (+105 lines: `_check_moneta_substrate` at :301).
   Last observed write `16:22:32`. **Live, not stale.**

2. **This interactive session**, launched by the human with the same brief
   (`harness/prompts/h6.md`) and told to execute it end to end.

Both were writing `moneta_runtime.py`. For roughly three minutes the file carried **two
competing implementations**; because Python binds the last definition, this session's
`schema_registered` / `schema_in_use` **silently shadowed** the orchestrator run's.
That is precisely the failure Article V names: *"Two agents in one directory produce
interleaved commits, a corrupted suite baseline, and findings that cannot be attributed."*

## What this session did about it

- **Backed its own block out**, byte-exactly (binary read/write per the H1-F7 CRLF trap),
  restoring the orchestrator run's file to 399 lines with only its own definitions present.
- Verified both files still `ast.parse` cleanly.
- **Preserved the removed implementation** at
  `…/scratchpad/h6_orchestrator_block.py` (341 lines). Nothing was deleted.
- Wrote no test, no battery, no receipt. **No commit was made. Nothing pushed, merged or tagged.**

## Why it stopped rather than continuing

Choosing which of two concurrent runs owns a leg is a value judgement between defensible
options, which Article I routes to the human, not to the agent. Continuing would have
multiplied an already-real corruption. Law 4 applies to the other run's work as much as to
files: classify before you delete.

**Assessment, offered as evidence not as a verdict:** the orchestrator run's implementation
is sound and is *better than this session's in two specific respects* —
(a) it deliberately does **not** cache the registry answer, because a cache cannot observe a
subprocess that sets `PXR_PLUGINPATH_NAME`, which is the only honest way to test it;
(b) it opens `cortex_root.usda` **composed**, because memory prims live in sublayers
(`cortex_protected.usda` / `cortex_YYYY_MM_DD.usda`) where a flat per-layer scan reports a
false negative. Recommendation: **let the orchestrator run finish; discard this session's block.**

## What must NOT be lost — recon findings that refute the brief

These were established by a 6-agent read-only fan-out and direct probes. They are independent
of whose code lands, and three of them contradict the leg brief and R64 as written.

| # | Finding | Tier | Anchor |
|---|---|---|---|
| F1 | `DEEP_THINK_BRIEF_codeless_schema.md:15` is **STALE**. Prims are authored **TYPED** today — `prim_spec.typeName = "MonetaMemory"`, unconditional. Migration landed 2026-04-27 (`f7b6253`); the brief was committed the same day, pre-surgery, never updated. | VERIFIED-STATIC | `C:/Users/User/Moneta/src/moneta/usd_target.py:318` |
| F2 | **`registered=True, in_use=False` (h6.md:24, R64:1718) will not reproduce.** Live state is `registered=FALSE` on **both** interpreters. Nothing in Moneta or SYNAPSE ever sets `PXR_PLUGINPATH_NAME`; `import moneta` does not self-register; the wheel ships **no** `schema/` at all (`packages = ["src/moneta"]`). The dangerous cell is the **inverse**: `!registered && in_use`. | VERIFIED-RUNTIME | `C:/Users/User/Moneta/pyproject.toml:52` |
| F3 | **SYNAPSE authors zero USD through Moneta.** `from_storage_dir` builds `MonetaConfig` without `use_real_usd`; the default is `False` → `MockUsdTarget`, and with `mock_target_log_path` also unset it writes to an in-process list that dies with the process. Conditions 4 and 5 are structurally false *for SYNAPSE* regardless of the migration. Corroborated: the one real snapshot has 39 rows, **every `usd_link` is `None`**; **zero `cortex_*.usda` exist anywhere under `C:/Users/User`**. | VERIFIED-RUNTIME | `python/synapse/memory/moneta_store.py:215-227`; `C:/Users/User/Moneta/src/moneta/api.py:136-137` |
| F4 | **`store.py:817`'s `except ImportError` is dead code, and the surviving branch lies.** Moneta-absent raises **`RuntimeError`** from `moneta_store.py:207`, not `ImportError`, so the "quiet jsonl fallback" arm never fires and the ERROR arm logs *"installed but failed to initialize … not a missing dependency"* — the exact inverse of the truth. Law 3. Verified live under hython 22.0.368. | VERIFIED-RUNTIME | `python/synapse/memory/store.py:817` |
| F5 | `typeName` is written to disk **whether or not the schema is registered** — Sdf authoring is schema-blind. With no plugin path: `GetTypeName()=="MonetaMemory"` but `IsA(Usd.Typed)` is **False**. Any check asserting only `typeName` measures authoring, never registration. `IsA(Usd.Typed)` is the discriminating signal. | VERIFIED-RUNTIME | `C:/Users/User/Moneta/tests/_schema_gate_subprocess.py:120` |
| F6 | **Condition 2 confirmed false, with SHAs.** Gate python 3.14.2 imports a pip wheel (`C:/Python314/Lib/site-packages/moneta`, pinned github `76da067`, v1.2.0-rc2). hython 3.13.10 cannot import moneta at all without `$MONETA_SRC`, then resolves the **git worktree** at `2965e5d` — *ahead* of the wheel. `version` is `None` there (no dist-info), so `file` is the only discriminating field. | VERIFIED-RUNTIME | `python/synapse/memory/moneta_runtime.py:37-58` |

### Positive control (h6.md:41 / R64 item 5) — DEMONSTRATED, both interpreters

```
PXR_PLUGINPATH_NAME unset                          -> FindConcretePrimDefinition('MonetaMemory') = None
PXR_PLUGINPATH_NAME=C:/Users/User/Moneta/schema    -> <pxr.Usd.PrimDefinition>, props =
    ['attendedCount','lastEvaluated','payload','priorState','protectedFloor','utility']
```
Confirmed on gate python 3.14.2 (pxr 0.26.5) **and** hython 22.0.368. The check discriminates; it is not a decoration.

### The five conditions, as measured

| # | Condition | Gate (py 3.14.2) | Shipping (hython 3.13.10) |
|---|---|---|---|
| 1 | module imports | **True** | **True** only via `$MONETA_SRC`; False without it |
| 2 | same module both interpreters | **False** — wheel `76da067` vs worktree `2965e5d` | same |
| 3 | schema registered with USD | **False** (True only if `PXR_PLUGINPATH_NAME` is set by hand) | **False** (same) |
| 4 | prims authored typed | **False in SYNAPSE** (mock target) — True in Moneta's own path | same |
| 5 | round-trips typed | **False in SYNAPSE** (no USD authored at all) | same |

`moneta_available()` returns **True** while four of five are false.

## Baselines measured this session (producers named, Law 2)

- gate suite **4881 passed / 0 failed / 129 skipped** — `python -m pytest -q -p no:cacheprovider` (108.19s)
- oracle selector **153 passed / 0 failed / 4 skipped** — same command `-k "moneta or schema or provenance"`
- binding ratchet floor: `git merge-base master HEAD` = `7268490`, whose `suite_baseline.json` reads **4275**
  (pre-Q2 shape). The brief's "4881+" matches the measured *before*, not the committed floor.

## Decision required

1. **Which run owns H6?** (Recommendation: the orchestrator run. Discard the preserved block.)
2. Should the orchestrator run be handed findings F1–F6 — in particular **F3**, which changes what
   the leg can honestly claim, and **F4**, a live Law-3 defect on the seam the brief names?
3. **R64 and `harness/prompts/h6.md:24` need amending**: the predicted `registered=True, in_use=False`
   is refuted. Amendments commit before the work they govern (Article VII / F3).
4. Standing question for the harness: `harness/verify/checks.py::check_doctor` is green only when
   `summary['fail'] == 0`. A `moneta_substrate` check that returns `fail` on a seat where
   `packages/synapse.json` sets `SYNAPSE_MEMORY_BACKEND=moneta` would turn that gate red for every
   future leg. Whether that red is wanted is a product call, not a code call.
