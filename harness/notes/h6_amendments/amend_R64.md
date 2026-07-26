
---

### AMENDMENT to R64 — 2026-07-26, authorised by the human this session

*Appended, not rewritten. The claims above are left standing because the record of what the
ruling said is the point (Article VI). Everything below is `REFUTED-LIVE`, which outranks any
claim above it (Article II).* Probed by a 6-agent read-only fan-out plus direct probes on both
interpreters. The H6 leg landed at `1fbbcd8` and reached the same conclusions independently;
this amendment corrects the **ruling**, which that commit did not touch.

**1. The predicted live state does not reproduce.** R64 predicts `registered: True,
in_use: False`. Measured: **`registered = False` on BOTH interpreters.** Nothing in Moneta or
in SYNAPSE ever sets `PXR_PLUGINPATH_NAME`; `import moneta` does not self-register; and the
wheel ships no `schema/` at all (`packages = ["src/moneta"]`,
`C:/Users/User/Moneta/pyproject.toml:52`). Registration is reachable only by setting the
variable by hand.

**2. The interesting cell is the INVERSE of the one named.** Prims are authored **typed**
today — `prim_spec.typeName = "MonetaMemory"`, unconditional, landed 2026-04-27 in `f7b6253`
(`C:/Users/User/Moneta/src/moneta/usd_target.py:318`). So the live cell is
**`!registered && in_use`**: the type name is on disk and the runtime does not know what it
means. Sdf authoring is schema-blind — with no plugin path a prim reports
`GetTypeName() == "MonetaMemory"` while `IsA(Usd.Typed)` is **False**. Any check asserting only
`typeName` measures authoring and never registration; `IsA(Usd.Typed)` is the discriminating
signal.

**3. The premise R64 inherited was stale.** `DEEP_THINK_BRIEF_codeless_schema.md:15` is a
*pre-implementation* design document. It was committed the same day as the migration it
proposes and never updated; its "today, prims are authored as untyped `def`" describes the
morning of 2026-04-27. Its locked-premises attribute table is stale the same way — it still
lists snake_case names and `prior_state` as `Int`, where live code authors `attendedCount` /
`protectedFloor` / `lastEvaluated` and `priorState` as a **Token**. Do not source attribute
truth from that file.

**4. A fourth condition is false for a reason R64 did not consider.** SYNAPSE authors **zero**
USD through Moneta. `MonetaBackedStore.from_storage_dir` builds `MonetaConfig` without
`use_real_usd` (`python/synapse/memory/moneta_store.py:215-227`) and the default is `False`
(`C:/Users/User/Moneta/src/moneta/api.py:136-137`), so the handle runs `MockUsdTarget`; with
`mock_target_log_path` also unset it appends to an in-process list that dies with the process.
Conditions 4 and 5 are therefore structurally false **for SYNAPSE** regardless of Moneta's
migration. Corroborated: the one real snapshot holds 39 rows and **every `usd_link` is `None`**,
and **zero `cortex_*.usda` files exist anywhere under `C:/Users/User`**.

**5. Ruling item 2 rested on a shape that was itself broken.** R64 item 2 says to reuse "the
shape `store.py:830` already uses to distinguish not-installed from installed-but-broken." That
discrimination was **inverted**. Moneta-absent raises `RuntimeError` from
`python/synapse/memory/moneta_store.py:207`, not `ImportError`, so the `except ImportError` arm
at `python/synapse/memory/store.py:817` was dead for the case it was written for, and the
surviving arm logged *"installed but failed to initialize … not a missing dependency"* — the
exact inverse of the truth. Law 3. VERIFIED-RUNTIME under hython 22.0.368. **Closed in
`1fbbcd8`**, which stopped inferring the cause from an exception type.

**Positive control (R64 item 5) — DEMONSTRATED**, gate python 3.14.2 (pxr 0.26.5) and hython
22.0.368 alike: `PXR_PLUGINPATH_NAME` unset → `FindConcretePrimDefinition('MonetaMemory')` is
`None`; set to `C:/Users/User/Moneta/schema` → a `PrimDefinition` carrying
`['attendedCount','lastEvaluated','payload','priorState','protectedFloor','utility']`.
The check discriminates; it is not a decoration.

**The five conditions as measured, 2026-07-26:**

| # | Condition | Gate (py 3.14.2) | Shipping (hython 3.13.10) |
|---|---|---|---|
| 1 | module imports | True | True only via `$MONETA_SRC`; False without |
| 2 | same module both interpreters | **False** — wheel `76da067` vs worktree `2965e5d` | same |
| 3 | schema registered with USD | **False** | **False** |
| 4 | prims authored typed | **False in SYNAPSE** (mock target) | same |
| 5 | round-trips typed | **False in SYNAPSE** (no USD authored) | same |

`moneta_available()` returns **True** while four of the five are false. R64's thesis is confirmed
and is *stronger* than written — the boolean hides more than it supposed.

**Producers (Law 2):** gate suite `python -m pytest -q -p no:cacheprovider` → 4881 passed /
0 failed / 129 skipped, measured before the leg. Selector `-k "moneta or schema or provenance"`
→ 153 passed / 0 failed / 4 skipped. Ratchet floor at `git merge-base master HEAD` = `7268490`
→ 4275.
