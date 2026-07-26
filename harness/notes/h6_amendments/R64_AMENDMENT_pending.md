# PENDING AMENDMENT — R64 + harness/prompts/h6.md

**Status** BLOCKED BY FENCE. Text is final and ready to append; this session cannot write it.
**Authorised** by the human this session ("Amend before more work lands"), Article VII / F3.
**Blocked by** `harness/**` is denied to this session's settings profile. Article I corollary:
*"If a task requires writing outside the grant, that is a ruling item, not a permission problem."*
No bypass was attempted.

**Two destinations:**

1. **Append to `harness/notes/CTO_RULINGS_01.md`**, directly after its current last line
   (`**The interesting cell is `registered && !in_use`.** It is the only one that looks like success.`, line 1739).
2. **Append to `harness/prompts/h6.md`** (55 lines) — the short block at the bottom of this file.

Appending, not rewriting, is deliberate on both counts. The record of what the document said is
the point (Article VI), and `h6.md` is the brief a **live orchestrator run is executing right
now** — silently changing a spec under an executor is its own defect.

---

## BLOCK 1 — append to `harness/notes/CTO_RULINGS_01.md`

### AMENDMENT to R64 — 2026-07-26, before the work it governs (Article VII / F3)

*Appended, not rewritten. The claims above are left standing because the record of what the
ruling said is the point (Article VI). Everything below is `REFUTED-LIVE`, which outranks any
claim above it (Article II).* Probed by a 6-agent read-only fan-out plus direct probes on both
interpreters.

**1. The predicted live state does not reproduce.** R64 predicts `registered: True,
in_use: False`. Measured: **`registered = False` on BOTH interpreters.** Nothing in Moneta or
in SYNAPSE ever sets `PXR_PLUGINPATH_NAME`; `import moneta` does not self-register; and the
wheel ships no `schema/` at all (`packages = ["src/moneta"]`, `C:/Users/User/Moneta/pyproject.toml:52`).
Registration is reachable only by setting the variable by hand.

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

**5. Ruling item 2 rests on a shape that is itself broken.** R64 item 2 says to reuse "the shape
`store.py:830` already uses to distinguish not-installed from installed-but-broken." That
discrimination is **inverted**. Moneta-absent raises `RuntimeError` from
`python/synapse/memory/moneta_store.py:207`, not `ImportError`, so the `except ImportError` arm
at `python/synapse/memory/store.py:817` is dead for the case it was written for, and the
surviving arm logs *"installed but failed to initialize … not a missing dependency"* — the exact
inverse of the truth. Law 3. VERIFIED-RUNTIME under hython 22.0.368. **Open defect, not closed
by this amendment.**

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
0 failed / 129 skipped. Selector `-k "moneta or schema or provenance"` → 153 passed / 0 failed /
4 skipped. Ratchet floor at `git merge-base master HEAD` = `7268490` → 4275.

---

## BLOCK 2 — append to `harness/prompts/h6.md`

    === AMENDED 2026-07-26, after probing. READ THIS BEFORE LINE 24. ===

    Line 24 predicts "registered=True, in_use=False". That is REFUTED-LIVE on both
    interpreters. The brief was right to say "CONFIRM THAT - do not assume it", and the
    confirmation came back negative:

      registered = FALSE  - nothing sets PXR_PLUGINPATH_NAME, `import moneta` does not
                            self-register, and the wheel ships no schema/ at all.
      in_use     = TRUE in Moneta's own authoring path (usd_target.py:318, typed since
                   f7b6253, 2026-04-27) but FALSE for SYNAPSE, which builds MonetaConfig
                   without use_real_usd and therefore runs the pxr-free MockUsdTarget and
                   authors no USD at all.

    So DEEP_THINK_BRIEF_codeless_schema.md:15 IS stale, which line 24 named as the finding
    condition. The dangerous cell is the INVERSE of the one at line 35: it is
    `!registered && in_use` - a typeName on disk that the runtime cannot resolve.

    Also: line 33's premise is broken. store.py:817's `except ImportError` is dead code -
    Moneta-absent raises RuntimeError from moneta_store.py:207, and the arm that does fire
    logs the exact inverse of the truth. Fixing that is in scope for item 2.

    Full evidence: .claude/remediation_ticket.md and the R64 amendment.
