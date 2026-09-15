# BUILD REPORT — Wave 1, four fixes against the SYNAPSE product contract

**Date:** 2026-09-14 · **Base for all four:** `bd65e4b6` (master tip) · **Nothing merged, nothing pushed, master untouched.**

Read §4 and §7 first if you are deciding today. §4 is the decision-relevant one and its premise turned out to be wrong in your favour.

---

## 1. What landed

All four worktrees share the prefix `C:\Users\User\SYNAPSE\.claude\worktrees\`. Branch name equals worktree name in every case.

| Fix | Status | Worktree / branch | Commit | Files touched (line ranges as reported by the builder) |
|---|---|---|---|---|
| **migrate-wiring** | COMMITTED — but **HELD**, see §7 | `wf_8a870870-1d5-3` | `42ae6899` — *fix(memory): upgrade a legacy agent.usd instead of dropping its decisions* | `python/synapse/memory/scene_memory.py` new block **325-432**, edits **469-498** · `python/synapse/host/graph_synth_runtime.py` **114-137** *(verified: three-name import at 114-118, UNKNOWN default at 125)* · `tests/test_scene_memory.py` appended **1049-1168** |
| **prompt-fallback-loud** | COMMITTED | `wf_8a870870-1d5-4` | `99e5d0e5` — *fix(panel): announce the system-prompt fallback instead of substituting silently* | `python/synapse/panel/synapse_panel.py` **3145-3148**, **3167-3177**, new helper **3179-3211** · `tests/test_panel_prompt_fallback.py` **1-176** (new) |
| **journal-datestamp** | COMMITTED | `wf_8a870870-1d5-5` | `0c98c6a0` — *fix(panel): date-stamp every session journal entry* | `python/synapse/panel/session_journal.py` **10**, **139-158** · `harness/notes/econ/econ_call_evidence.py` **71-79**, **172-181** · `tests/test_session_journal_datestamp.py` **1-153** (new) |
| **decision-writer-widen** | COMMITTED | `wf_8a870870-1d5-6` | `7b055a6d` — *fix(memory): stop log_decision silently discarding out-of-schema payload keys* | `python/synapse/memory/agent_state.py` **548-639** (replaces old 547-592) · `tests/test_agent_state.py` **657-722** |

**Nothing is PARTIAL and nothing is uncommitted.** Every commit is atomic, on its own branch, with a clean working tree at report time.

**COMMITTED does not mean mergeable.** migrate-wiring carries a severity-4 finding from two independent attack lenses (§5). It is committed and held, not committed and ready.

---

## 2. The test evidence

### Every one of the four was watched failing

No fix in this wave claims a test it did not run red first. Two builders caught their *own* decorations and said so.

| Fix | Test | Failure condition | Observed failing pre-fix? |
|---|---|---|---|
| migrate-wiring | `tests/test_scene_memory.py::TestLegacyAgentUsdUpgrade` (5 tests) | log_decision returns `""` on a pre-2.0.0 store; version stays `0.1.0`; `agent_usd_schema` key absent from the returned dict | **Yes** — 5F. Signatures: `assert ''` + live `memory/decisions prim missing` warning; `'0.1.0' == '2.0.0'`; `KeyError: 'agent_usd_schema'` ×3 |
| prompt-fallback-loud | `tests/test_panel_prompt_fallback.py` (5 tests) | Either fallback branch substitutes the overlay without a ≥WARNING record naming `branch=` and the exception, or without one chat notice per degradation | **Yes** — 4F/1P. Signatures: `assert []` (zero log records) ×3, `assert 0 == 1` (zero chat calls) |
| journal-datestamp | `tests/test_session_journal_datestamp.py` (3 tests) | Bracketed stamp does not `strptime` as `%Y-%m-%d %H:%M:%S%z`; date search returns nothing; econ regex rejects a dated line | **Yes** — 3F. Signature: `ValueError: time data '10:49:22' does not match format` |
| decision-writer-widen | `tests/test_agent_state.py::TestMemoryDecisionsWithMockPxr` (3 new of 5) | An out-of-schema payload key produces no attribute, no WARNING, and no `synapse:unrecognizedKeys` declaration | **Yes** — 3F/2P. Signatures: `assert None is not None` ×2, `assert False` on empty warning list |

The 1P and 2P in the right column are controls, not passes-by-luck. prompt-fallback's fifth test is the over-fix guard (a healthy turn must stay silent); decision-writer's two are the pre-existing round-trip tests proving the six ratified attributes were undisturbed.

### Two self-caught decorations, disclosed rather than hidden

**migrate-wiring:** the first draft of `test_upgrade_happens_and_is_additive` asserted only "prior history survived" — which passes vacuously against unfixed code, because nothing runs today and nothing can destroy history. The builder strengthened it to assert the version bump before quoting any result.

**journal-datestamp:** the first draft of the econ-reader test built its dated sample *from the journal's own output*, which was still legacy-format pre-fix, so the old regex matched it and the test went green while proving nothing. Caught on the first red run ("2 failed, 1 passed"), repaired with a literal `DATED_LINE`.

Both are the behaviour the lens exists to reward. Neither builder had to tell you.

### The one that must not be buried: migrate-wiring's tests do not run on the merge gate

All five sit under a class-level skip at **`tests/test_scene_memory.py:1051`** — verified directly:

```
@pytest.mark.skipif(not _pxr_available, reason="pxr required for agent.usd schema tests")
```

Stock GitHub runners have no OpenUSD (`.github/workflows/ci.yml:93` says so in those words), and no `usd-core` appears in requirements or pyproject. The module is not auto-marked `needs_houdini` — `tests/conftest.py:845-856` detects at module level, and this file's pxr import is a nested try with class-level gates. So CI **collects the file and reports 5 SKIPPED**.

Net effect: the merge gate executes **zero assertions** against `_upgrade_agent_usd`, the verify-don't-trust logic, the backup gate, or the new `agent_usd_schema` key.

The sharpest instance is `test_no_pxr_reads_unavailable_not_success` — its subject *is* the pxr-absent path, and it is gated off precisely where pxr is absent. It only needs pxr for its fixture; `_upgrade_agent_usd` returns UNAVAILABLE on its first branch before touching pxr, so a bare `open(agent_usd,'w')` fixture would make it CI-runnable today.

This is not a Law 6 violation — the skipif is the file's existing convention (same pattern at `tests/test_scene_memory.py:427` and `:615`). It is a durability hole under a fix whose entire value is honest reporting. **Both crosscheck reviewers verified fail-first locally and neither asked where these tests run.**

### Law 6 is clean across the wave

`git show --numstat HEAD -- tests/` on all four: **120/0, 186/0, 153/0, 66/0**. Zero deleted test lines. Zero xfail. One skipif added (house convention). Nothing rewritten to pin less than before.

---

## 3. INTENT conformance

### migrate-wiring → §6

> "Each completed or interrupted operation MUST have a record connecting the engagement and proposal to its actual changes, execution route, verification results, and recovery status. Unsupported or unmeasured behavior remains `UNAVAILABLE` or `UNKNOWN`, as appropriate." — `INTENT.md:200-203`

**Letter: satisfied.** The contract phase pre-registered three cheats and the diff avoided all three. The caller is on the real hot path — `ensure_scene_structure` is reached from `server/handlers_memory.py`, `server/handlers.py`, `server/websocket.py`, `mcp/session.py`, `session/tracker.py`, `panel/shot_login.py`, `synapse_shelf.py` and `graph_synth_runtime.py`, spanning both the live `/synapse` and `/mcp` paths. `migrate_to_v2`'s boolean return — which cannot distinguish "already current" from "could not" — is never branched on. The backup runs before the migration, under the module's existing process lock.

**Clause: violated, and by the honesty mechanism itself.** Two lenses independently reproduced it on this host.

The verify does not re-read the store. It re-reads the **process-cached `SdfLayer`**. `_upgrade_agent_usd` binds `layer = Sdf.Layer.FindOrOpen(agent_usd)` for the cheap check; Python has no block scope, so that layer stays alive in the frame across the lock, across `migrate_to_v2`, and across the verify. `migrate_to_v2`'s `Usd.Stage.Open(path)` resolves to the same registered layer, mutates it, and calls `stage.GetRootLayer().Save()` at **`python/synapse/memory/agent_state.py:227`** — *return value discarded* (verified directly; the attack cited `:228`, which is the following `logger.info` line). The verify then opens the same cached, already-mutated layer, sees `2.0.0` and a valid decisions prim, and returns `"2.0.0"`.

So a Save that fails silently — read-only store, full disk, dropped share — still verifies as success. And the cross-process case is worse: a stale-at-0.1.0 cached layer backs up the *other* process's post-migration file (including its decision record) to `.bak`, saves the stale layer over it, destroys the record, and hands `"2.0.0"` to all eight callers. Reproduced sequentially with no lock contention at all — a lock serialises in time; it does not make a cached layer coherent.

The test meant to pin this (`test_unmigratable_store_reads_unknown_not_success`) makes `migrate_to_v2` lie by doing *nothing*, which leaves the cached layer at 0.1.0 so the verify catches it. The real failure is the opposite shape — migration succeeds in memory, only the disk write fails — and that case cannot be caught by that test's construction.

**Second clause inversion, same fix.** The report says the pxr-less stub branch reports UNAVAILABLE. True only on the second and later calls. `ensure_scene_structure` sets `agent_usd_schema = _usd_schema_version()` (`= "2.0.0"`) up front at `scene_memory.py:470`; the UNAVAILABLE assignment lives in an `except ImportError:` at `:472-486` that fires only when the *module* is unimportable. With pxr merely absent, the import succeeds, `initialize_agent_usd` writes a text stub, no exception is raised — and the constant stands. Reproduced: **call 1 on a fresh store returns `'2.0.0'`, call 2 on the identical store returns `'UNAVAILABLE'`**, and `log_decision` returns `''` both times. The first call is the one that happens at session start.

### prompt-fallback-loud → §6 / §4 / §7

> "Unsupported or unmeasured behavior remains `UNAVAILABLE` or `UNKNOWN`, as appropriate." — `INTENT.md:200-203`
> "The planner MUST distinguish observed facts, assumptions, proposed actions, expected effects, and verified outcomes." — `INTENT.md:121-122`
> "The ordinary interface should answer four questions: What help is engaged? What is it doing? What can it change? How do I take control back?" — `INTENT.md:221-222`

**Letter and clause: both satisfied, on the announce half.** The three pre-registered cheats were all refused explicitly. Not `logger.debug` — `logger.warning` at `synapse_panel.py:3194`, and the test's `records` fixture captures at DEBUG-and-above *specifically so* a debug cheat would land in the list and still leave every WARNING assertion red. Not log-only — the notice goes to `self._chat.append_system_message`, confirmed a real artist-facing method at **`python/synapse/panel/chat_display.py:581`**. Not a hardcoded prompt substitution — both branches still `return overlay` unchanged, pinned by explicit assertions, and the scope_refused section names and rejects the substitution alternative as strictly worse.

**Where the letter outruns the clause.** §6 asks for a **record**; this delivers an **announcement**. The only durable trace is a Python log line. The only artist-facing trace is a transient chat message gated on `self._prompt_fallback_reason`, an in-memory instance attribute that dies with the panel. Nothing lands in `agent.usd`, the journal, or any queryable surface, so an artist cannot afterwards establish which turns ran degraded.

Second, undisclosed: the dedupe signature is `(branch, reason)` where `reason` embeds `str(exc)` — `synapse_panel.py:3179-3211`. If the exception message varies per turn (a path, an id, a timestamp), "once per degradation, not once per turn" silently becomes chat spam. If it is constant, every later degraded turn is invisible in chat. Which one ships depends on exception-message stability, which nobody measured.

Third, §3's lifecycle never actually reads `Unavailable` — the degraded turn still executes. The builder disclosed this and correctly refused to change it here.

### journal-datestamp → §9 / §6 / §3

> "Time to an accepted, editable result" · "Measured dispatch-stop and actual-control-return latency, including failures" — `INTENT.md:279, 283`
> §6 record clause — `INTENT.md:200-203` · §3 engagement Identity requires scene/session identity — `INTENT.md:70`

**Letter and clause: satisfied.** Both pre-registered traps avoided. The stamp is **per entry**, not a file-open header — which matters because `journal.log` is append-only and never rotated, so a header leaves every post-midnight line exactly as ambiguous as before. The format carries an explicit UTC offset (`datetime.now().astimezone()`), so elapsed-time math survives a DST boundary and the stamp never has to be assumed local-or-UTC.

The reader audit holds under independent grep: every other journal consumer in the repo (`_s1_reconcile.py`, `h8/build_ledger.py`, `harness/progress.py`, `blackbox_recover.py`) reads `journal.jsonl` — a different artifact. `job_events.get_journal()` is a genuinely different journal.

**Where the letter outruns the clause — one spot, in the evidence tooling.** The econ note rewrite replaces one unearned claim with another. The new text at `harness/notes/econ/econ_call_evidence.py:172-181` is a **hardcoded string literal** inside `_scan_journals`' return dict: *"Entries written from 2026-09-14 carry a full local date plus UTC offset, so they CAN be ordered and bounded by day."* Nothing measures that. It emits on any host, at any time — including a host whose installed `session_journal` predates this commit, or a journal with zero dated lines. `_scan_journals` already walks every line applying `JOURNAL_TOOL_RE`; one counter would make the claim measured. Same shape as the defect the commit message says it removes, and a Law 2 violation (a claim in an evidence artifact with no producer behind it).

### decision-writer-widen → §6 / §4

> §6 record clause — `INTENT.md:200-203`
> "Structural validation, native execution results, and artist acceptance are distinct forms of evidence and MUST be reported separately." — `INTENT.md:150-151`

**Letter and clause: satisfied, with the benefit deferred honestly.** Both pre-registered cheats avoided. Extras land as individually-queryable `synapse:ext:<key>` String attributes — **not** a JSON blob nothing can query. And the builder explicitly *declined* to add named `route`/`verification`/`recovery` attributes, because no caller populates them: adding them now would author empty placeholders on every record, a schema that *looks* like it carries verification evidence and is fed by nothing. That is the exact §6 violation the contract phase pre-registered ("claims a state it has not earned").

`synapse:unrecognizedKeys` is always authored, even when empty — so `""` honestly means "nothing arrived outside the schema" rather than leaving a reader unable to distinguish that from "this record predates the declaration."

**The honest part.** The practical benefit is deferred. No production caller sends route/verification/recovery today — `python/synapse/host/graph_builder.py:278-285` passes exactly the six ratified keys — so today's records on disk are unchanged in substance, gaining only one empty attribute. The fix removes the barrier; it does not by itself produce a §6-complete record. Disclosed by the builder, confirmed by the crosscheck.

Two behaviour changes the report's "byte-identical" claim does not cover:

- `created_paths` passed as a bare **string** used to be joined character-by-character with newlines (`"\n".join(payload.get("created_paths") or [])`). `_decision_str` now returns it unchanged. Better output, not byte-identical, and nothing pins either shape.
- The old code raised `TypeError` on a non-str element inside the list — and `log_decision` has no try/except, so that raise propagated. It is now coerced. A silent widening of the writer's contract.

Also: the new WARNING has no rate limit and fires once per record carrying extras. Harmless today (never fires). On the day a caller widens the payload — which is the whole point of the fix — every build emits a WARNING naming every extra key, on the build path. Worth a bound before, not after.

**Untested new code path:** the commit message claims *"two distinct keys that sanitize alike are disambiguated with a trailing `_` rather than silently overwriting each other."* The three new tests pass only `execution_route` and `receipt` — keys that need no sanitizing and cannot collide. The `while attr_name in used` loop has zero coverage. A fix whose thesis is "stop claiming what you did not measure" ships a commit-message claim about anti-overwrite behaviour that nothing measures. One stock-Python test with `{'a-b': 1, 'a_b': 2}` closes it, no pxr required.

---

## 4. The collision

### The premise is wrong, and wrong in your favour

**Two builders did not edit `memory/agent_state.py`. One did.**

The contract phase predicted a collision there, and migrate-wiring's builder read that prediction and routed around it deliberately — the migration caller, the verification, and the UNKNOWN/UNAVAILABLE reporting all live in `scene_memory.py`, which already owns the `agent.usd` lifecycle through `ensure_scene_structure`. **Zero lines of `agent_state.py` are in commit `42ae6899`.**

Verified three ways by the reviewers, not merely asserted:

| Check | Result |
|---|---|
| `git show --stat` on both commits | `42ae6899` → `scene_memory.py`, `graph_synth_runtime.py`, `tests/test_scene_memory.py`. `7b055a6d` → `agent_state.py`, `tests/test_agent_state.py`. Zero shared files. |
| `git diff 42ae6899^ 42ae6899 --numstat` | No `agent_state.py` hunk exists at all |
| `git merge-tree <base> worktree-3 worktree-6` | Clean "merged" result, no conflict markers |
| Hand-built combined tree, both suites | **147 passed, 10 skipped** (the 10 are pre-existing `evolution.py deprecated` skips, unrelated to either diff) |
| `git merge-base 42ae6899 7b055a6d` | `bd65e4b6` — both forked from the identical master tip, so no rebase hazard is baked in |

**All four commits are file-disjoint.** Each of the four builders independently cross-checked the other three file lists. No file, no function, no line range is touched twice anywhere in the wave.

### So what is the real coupling?

Two things, both real, neither textual.

**(a) A one-directional semantic dependency, and it holds.**

migrate-wiring's `graph_synth_runtime.py:133` does `if not log_decision(agent_usd, payload):` — it depends on `log_decision`'s truthy/falsy return contract. decision-writer-widen rewrote the body of that function.

The contract survived: `log_decision` still returns `""` on `not PXR_AVAILABLE` and on `not parent.IsValid()`, and the non-empty prim name on success. The rewrite only changed what happens *between* the parent-valid check and the final `return name`. Pinned by the two pre-existing tests (`test_log_decision_roundtrip`, `test_log_decision_noop`) that stayed green through the change, and independently exercised by migrate-wiring's own test 1, which drives the `""`-on-invalid-parent path.

migrate-wiring also calls `agent_state.migrate_to_v2`, `agent_state.PXR_AVAILABLE` and `agent_state.SCHEMA_VERSION` — none touched or renamed by the sibling.

**(b) A concurrency collision that is NEW, and both builders mislabelled it "pre-existing."**

This is the part that is decision-relevant.

Before `42ae6899`, `ensure_scene_structure` performed **zero writes** to an existing `agent.usd` — `os.path.exists` + `os.makedirs` + seed-on-absence, nothing more. `migrate_to_v2` had zero production callers; the commit message says so itself.

After it, a **whole-layer `Usd.Stage.Open` → mutate → `Save()` rewrite** sits on the path taken by every memory operation, reachable from at least eight modules across at least two processes (panel-in-Houdini and the stock-Python MCP server both call it).

That rewrite is serialised by `scene_memory._get_file_lock` (`python/synapse/memory/scene_memory.py:85`) — which protects it against *other `ensure_scene_structure` calls only*. `agent_state.py` has **no lock of any kind**: grep for `_get_file_lock|FileLock|threading.Lock` in that file returns nothing. `log_decision`, `log_routing_decision`, `log_handoff`, `log_integrity`, `create_task`, `update_task` all go straight to `Usd.Stage.Open`/`Save`.

So the migration and the writers it exists to unblock are **unsynchronised against each other**, and the migration is the one that rewrites the entire layer.

Related, smaller: `migrate_to_v2` replaces `customLayerData` **wholesale** at `agent_state.py:223-226`, so migrating a store seeded by `scene_memory._seed_agent_usd_stub` silently drops its `synapse:status` key. Small data loss on a store that was intact.

decision-writer-widen adds 2+ attributes per record to the unlocked writers. That widens the window marginally; it does not create it.

### Can both land, in which order, and what breaks if the order is wrong?

| Question | Answer |
|---|---|
| Can both diffs land? | Textually, yes — clean merge in either direction, proven by combined-tree test run |
| Does order matter for correctness? | **No.** decision-writer first → migrate-wiring's upgraded stores also carry `synapse:unrecognizedKeys` and `synapse:ext:*` on new records; additive, invisible to migrate-wiring's verify (which checks only `/SYNAPSE/agent` version and `/SYNAPSE/memory/decisions` validity, never individual record attributes). migrate-wiring first → nothing in decision-writer branches on whether a store was freshly upgraded |
| What breaks if the order is wrong? | **Nothing.** There is no wrong order between these two |
| Should both land? | **No — and not for collision reasons.** decision-writer-widen is clean. migrate-wiring carries the §3 severity-4 verification inversion and should loop to Pass 3 for its own subtree, independently of the sibling |

**The one real ordering caution is not between the diffs — it is against reality.** If migrate-wiring lands as written, it puts a whole-layer rewrite on the hot path alongside four unlocked appenders, and its self-verification cannot detect a failed disk write. That is the merge decision. The collision that was predicted did not happen.

### One correction to the crosscheck record

Three crosscheck reports vouched for migrate-wiring's "verified rather than trusted" claim. The intent-conformance lens measured it to be false. **The crosscheck round should not be treated as independent verification of that diff** — the reviewers reproduced the fail-first runs correctly and then accepted the risk narrative at face value.

---

## 5. What the attacks found

Three lenses ran. Severity is as the lens reported it (1-4, where 4 = showstopper). **Nothing has been corrected in the tree** — the attacks ran after the commits and no revise pass followed, so every finding below is OPEN or CONTESTED. This report is the record.

### Lens: intent-conformance (§3/§4/§6/§9)

| # | Finding | Fix | Sev | State |
|---|---|---|---|---|
| I1 | Verify re-reads the process-cached `SdfLayer`, not the store. A silently-failed `Save()` still verifies as `"2.0.0"`. Cross-process case destroys a live decision record and reports verified success | migrate-wiring | **4** | **OPEN — showstopper** |
| I2 | Fresh-init with pxr absent reports `'2.0.0'` on call 1 and `'UNAVAILABLE'` on call 2, same store. The session-start call is the lying one | migrate-wiring | **3** | **OPEN** |
| I3 | Migration-vs-writer race is new, not pre-existing; one locked whole-layer rewriter now shares `agent.usd` with four unlocked appenders | migrate-wiring + decision-writer | 2 | OPEN |
| I4 | econ note rewrite is a hardcoded literal asserting a capability the host may not have; replaces one unearned claim with another | journal-datestamp | 2 | OPEN |
| I5 | Announce ≠ record. Only durable trace is a log line; chat notice dies with the panel. Dedupe signature embeds `str(exc)`, so "once per degradation" is unmeasured | prompt-fallback-loud | 2 | OPEN (first and third points self-disclosed) |
| I6 | **Refuted by the attacker's own probes**, logged so nobody re-spends budget: `synapse:ext:` from arbitrary payload keys does NOT raise under real pxr; migrate's verify DOES correctly report UNKNOWN on permission-denied; no second author of the same decision record exists | — | 1 | CLOSED — refuted |

Verdict on this lens: **SHOWSTOPPER for `42ae6899` only.** The other three are keep-and-document.

### Lens: test-honesty

| # | Finding | Fix | Sev | State |
|---|---|---|---|---|
| T1 | All five tests — the only pin on the entire migration — are SKIPPED on the merge gate (`tests/test_scene_memory.py:1051` + `.github/workflows/ci.yml:93`). Neither crosscheck reviewer asked where they run | migrate-wiring | **3** | **OPEN** |
| T2 | The `while attr_name in used` collision loop has zero coverage; a commit-message claim nothing measures. Adjacent: `mock_pxr` accepts any attribute name, so "individually queryable" is true-by-construction under the fake | decision-writer-widen | 2 | OPEN |
| T3 | The test *injects* a logger by name rather than observing the module's, so a logger mismatch is undetectable; `SLICE` hardcodes the private helper name, so a rename ERRORs instead of failing with a diagnostic; `_chat` is a `Mock()` so "the artist is told" is method-name matching only | prompt-fallback-loud | 2 | OPEN (latent — names match today at `synapse_panel.py:47` and `chat_display.py:581`) |
| T4 | The "regex still discriminates" claim rests on a probe pasted into the build report, not an assertion. Three positive assertions, zero negative ones. Two lines fix it | journal-datestamp | 1 | OPEN |
| T5 | Law 6 clean across all four; fail-first real in all four; two self-caught decorations | — | — | CLOSED — held |

### Lens: blast-radius

| # | Finding | Fix | Sev | State |
|---|---|---|---|---|
| B1 | Same as I1, found independently by a second lens with a different mechanism trace (`layer` stays bound in the function frame; `Save()` return discarded at `agent_state.py:227`) | migrate-wiring | **4** | **OPEN — showstopper, two-lens confirmation** |
| B2 | Widened import couples provenance to two brand-new constants atomically (`graph_synth_runtime.py:114-118`). A stale-deployed `scene_memory` turns a *working* provenance write into a total skip, logged as "provenance write failed" not "your module is old". Same shape at `:125`, where `paths.get(..., AGENT_USD_SCHEMA_UNKNOWN)` makes any dict lacking the new key skip a write that previously succeeded | migrate-wiring | **3** | **OPEN** |
| B3 | "Cached, returns immediately" is an assertion, not a measurement — the layer handle drops on return, so the next memory op may re-parse `agent.usd` in full. `agent.usd` is append-only and never pruned, so cost scales with session history. On an unmigratable store, `shutil.copy2` of the whole file runs on *every* call | migrate-wiring | **3** | **OPEN** |
| B4 | Same as I3, found independently | both memory diffs | 3 | OPEN |
| B5 | **The "no channel to the artist" scope refusal rests on a false premise.** `ensure_scene_structure`'s dict is already returned whole across the WS boundary — verified at `python/synapse/server/handlers_memory.py:197` then `:212-213`. `agent_usd_schema='UNKNOWN'` already ships to the panel at every session start; it is simply not rendered. Surfacing it needs a *display*, not a return-contract change to `graph_builder`. Also: the caller hunt covered test files referencing `ensure_scene_structure` by name, not anything pinning the `project_setup` **response shape** | migrate-wiring | 2 | OPEN — retriage the follow-up to the panel, not `graph_builder` |
| B6 | Two unenumerated behaviour changes (bare-string `created_paths`; swallowed `TypeError`) and an unbounded WARNING that fires exactly when the fix starts being useful | decision-writer-widen | 2 | OPEN |
| B7 | Journal reader audit **reproduced clean** under independent repo-wide grep — one positional parser, already fixed. `_build_system_prompt` runs on the main thread inside `_timed_phase("send")` (`synapse_panel.py:3246-3260`), so the chat append is thread-legal; no other caller found | journal, prompt-fallback | — | CLOSED — held |

### Contested

**Nothing is contested.** No finding was rejected by a builder — the attacks ran after commit, and no builder has answered them. Three findings (I1/B1, I2, B2) directly contradict statements in the migrate-wiring build report's own risk section; those statements are **superseded by measurement**, not disputed.

One anchor correction of my own, from direct verification: the `Save()` inside `migrate_to_v2` is at **`python/synapse/memory/agent_state.py:227`**; `:228` (cited in the blast-radius lens) is the following `logger.info`. The finding is unaffected — the return value is discarded either way.

---

## 6. The fold slope, settled

### What the contract phase established

**The climb in `first_call_input_tokens` is conversation-context accumulation. It is not task-family difficulty.**

The two were never actually competing hypotheses once the driver is visible — and the driver is the harness design, not the tasks.

| Evidence | What it shows |
|---|---|
| `harness/v2-20260913/artifacts/v2-baseline/manifest.json` — 53-step GUI-automation trace | Exactly **one** `"action":"open-chat"` in the entire run (step 10, before exp-02). Tasks 3-10 (steps 15-51) go straight to focus/type/send/read with no reset action between them |
| Same file — lease and window records | One attended lease held start to finish (`18:22:23Z` → `19:21:00Z`), one Houdini window (`window.id 132836`, same PID throughout) |
| `exp-01_usage_resume.json` vs `step13_usage.json` | `session.input_tokens` **357418 → 397526 = 357418 + 40108, exactly**, with `session.tasks` incrementing 1→2. Counters carried forward across the task boundary instead of resetting. A fresh process per task would reset both |
| `first_call_input_tokens` 40108 → 139991 | The provider's own reported prompt size (ollama `last_prompt` on deepseek-v4-flash:cloud), not a synthetic count. A rising **real API payload** from one unreset thread is accumulation by construction |

### Why it read as a tie

`contract.yaml:92-133` pre-registers the ten tasks in exactly the order they appear in `baseline.csv` and in the executed step sequence — the harness's own simple→complex family grouping. The run then executes them in that order inside one never-reset chat. **Turn-position and task-family are perfectly collinear in this dataset by design.**

Nothing in `baseline.csv`'s ten columns can separate them. `manifest.json`'s step trace and the usage-sink snapshots are the only artifacts that can, and they show the accumulation mechanism is structurally guaranteed — one thread, one process — not merely correlated with complexity.

### The two "non-corroborating" siblings, reconciled

`model_round_trips` is non-monotone (11, 8, 8, 5, 9, 11, 8, 8, 7, 14) and per-task summed `input_tokens` dips at top-01 (325350 after exp-03's 447306). Both are driven by how many round trips **that task's own problem-solving** needed — a per-task effort variable riding *on top of* the rising per-call floor. A 5-round-trip task can have a lower summed total than a preceding 8-round-trip task while every individual call in it costs more than the calls before it. Orthogonal signal, not a competing cause.

### The residual, stated plainly

The panel's Token tab exposes exactly the line item that would decompose "resent prior turns" from "this turn's own bigger payload" — `system prompt` / `tool surface` / `scene grounding` / `conversation`, visible in `step10_post.json`'s accessibility dump (`system prompt 3727`, `tool surface 29220`, `scene grounding UNKNOWN`).

The numeric `conversation` value was **never captured populated** in any `step*_post.json` or `step*_usage.json` in this run. It appears unpopulated in step05, step07, step10 and nowhere else.

So you cannot say from this artifact set what fraction of the ~+12.5K/row slope is pure resend versus bigger task-specific payload. That needs a live conversation-token readout at each task's first call, or a raw request-payload log. Neither exists.

Also on the record, from `REPORT.md:10` in the operator's own words: *"exp-01 first-call input is UNKNOWN; five later first-call values are explicitly derived from two-call totals in the manifest."* Several of the ten first-call numbers are arithmetic derivations from the same cumulative ledger, not independent per-task measurements.

### Can the C3 fold decision now be made?

**Yes for the mechanism question. No for anything that needs a difficulty signal.**

- **Settled:** the baseline climb is a one-process, one-unreset-chat artifact. Any fold decision that rested on "is the climb real accumulation or is it noise/difficulty?" can be made now — it is accumulation, structurally guaranteed.
- **Not settled, and not settleable from this run:** the split between resent history and per-turn payload growth.
- **Explicitly out of bounds:** this baseline must not stand in for a difficulty comparison across exp/top/sop/ari/ctx. By its own design it could never have shown anything but a climb.

**The one change that makes a future baseline comparable:** open a fresh chat — ideally a fresh process — per task, so `first_call_input_tokens` starts from the same floor every time. That is the whole fix.

---

## 7. Merge order

All four are file-disjoint, so order is functionally immaterial among the three that are clean. The ordering below is a risk ladder, not a dependency chain.

### 1 — journal-datestamp (`0c98c6a0`)

Lowest blast radius in the wave. One product file, one evidence-tooling file, one new test. The only reader that could break was found and fixed in the same commit, and the reader audit reproduced clean under independent repo-wide grep. Highest-severity finding against it is a **1**. Land it first because nothing you learn from the other three changes your decision about it.

### 2 — prompt-fallback-loud (`99e5d0e5`)

Pure panel-side reporting. Touches no persistence, no memory, no scene. Both branches still return exactly what they returned before, pinned by assertions that were already true against unfixed code. Highest finding is a **2**, and the two real ones (no durable record; unmeasured dedupe frequency) are follow-up work, not defects in this diff. Second because it is the next-smallest surface.

### 3 — decision-writer-widen (`7b055a6d`)

Clean on every axis the attacks probed. Its one code-quality gap (the untested collision loop) is closable with a single stock-Python test that runs in CI today. Third rather than first only because it is the diff that touches `agent_state.py` — the file migrate-wiring's eventual rework will need to coordinate against — so landing it last among the clean three leaves the smallest window of divergence.

**Note before you merge it:** it is a barrier removal, not a benefit. Today's records are unchanged in substance. The §6 record does not become complete until someone widens `graph_builder._emit_projection`'s payload at `python/synapse/host/graph_builder.py:278-285`. That is a separate, unbriefed wave.

### 4 — migrate-wiring (`42ae6899`) — **HOLD. This is the one that must not go first, and should not go at all yet.**

Two independent attack lenses, using different mechanism traces, reached the same severity-4 conclusion: **the diff's headline honesty claim is false.** The verify reads its own write buffer. A migration that fails to reach disk still reports `"2.0.0"` to all eight `ensure_scene_structure` callers, and in the cross-process case it destroys a persisted decision record while doing so.

That is the exact failure class the fix exists to eliminate, reproduced inside the fix's own honesty mechanism.

It also carries three further severity-3 findings — the CI skip (T1), the atomic import coupling that converts a working provenance write into a silent skip on a stale install (B2), and an unmeasured per-call cost on the hottest path in the memory module (B3).

**What Pass 3 needs, scoped:**

| Item | Fix shape |
|---|---|
| I1 / B1 — cache-coherent verify | Reload or drop the cached layer before verifying; or verify against a freshly-opened `SdfLayer` outside the frame. Probe: read-only `agent.usd` under real pxr must return UNKNOWN |
| I2 — fresh-init lie | Assign UNAVAILABLE when `agent_state.PXR_AVAILABLE` is False, not only on `ImportError` |
| B2 — atomic import | Import `ensure_scene_structure` alone; resolve the two constants defensively |
| T1 — CI blindness | Rewrite `test_no_pxr_reads_unavailable_not_success` with a pxr-free fixture and lift it out of the class gate. Optionally add `usd-core` to the CI matrix to recover the other four |
| B5 — retriage | The artist-visible channel already exists at `handlers_memory.py:212-213`. The follow-up belongs in the panel, not in `graph_builder` |

None of that is blocked by the other three merges. migrate-wiring can rework and re-enter while the clean three are already in.

---

## 8. What stays human

Nothing in this wave crossed any of these. Every one is yours.

| Gate | State |
|---|---|
| **Merge** | Not crossed. Four commits on four worktree branches. `master` is at `bd65e4b6` and untouched — confirmed by reading `python/synapse/memory/agent_state.py` in the main tree, which still carries the pre-fix `migrate_to_v2` and the six-key `log_decision` |
| **Push** | Not crossed. No builder pushed. Standing hazard worth restating: `origin` is a **public** GitHub repo and `orchestrate.ps1 Backup-Branches` auto-pushes feature branches while an orchestrator runs. "Local-only" is never safe to assume here |
| **Tag** | Not crossed. No tag minted, no `scripts/tag_release.py` run, no `gh release create` |
| **VERSION** | Not crossed. No version bump in any diff. Current is v5.68.0 |
| **The frozen seam** | Not crossed by any of the four. `cognitive/graph_proposal.py`, `recipes/contracts.py`, the worker policy table and `OPERATION_GATES` were never opened. All four builders stated this independently |
| **INTENT.md** | Not edited by anyone |
| **Full test suite** | Not run by anyone — targeted neighbour sweeps only, per the brief. Someone must run it before merge |
| **Live Houdini seat** | Never used. No builder spawned `hython` or launched Houdini |

### Live-seat runs still owed

| Fix | What a seat would establish | Pinned command |
|---|---|---|
| migrate-wiring | Migration against a **real artist-authored** `agent.usd` carrying genuine `routing_log`/`handoff_chain` history. The synthetic v5.4.0 fixture does not have it; `migrate_to_v2` is additive-only *by inspection*, which is not proof | `SYNAPSE_HYTHON="C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"` then that hython `-m pytest tests/test_scene_memory.py::TestLegacyAgentUsdUpgrade -q` |
| prompt-fallback-loud | That an artist in a live session actually notices the chat notice, and that the degraded prompt behaves as the docstring describes. Make `synapse.panel.system_prompt` unimportable, then read the panel chat and `~/.synapse/logs/synapse.log` | Same `SYNAPSE_HYTHON` pin, attended seat |
| journal-datestamp | Cosmetic only — that the `/journal` panel surface renders the 30-char stamp acceptably. Not correctness | Same pin |
| decision-writer-widen | That the resulting `agent.usd` composes under real pxr. **Largely refuted as a risk** by the attacker's own probe: real pxr accepted `synapse:ext:café`, `synapse:ext:p_2nd_route`, CJK keys and `9lives` with no exception, and all four records round-tripped | `SYNAPSE_HYTHON` pinned, `hython -m pytest tests/test_agent_state.py -q` |

**Always pin `SYNAPSE_HYTHON`.** This host has both 22.0.400 and 22.0.429 installed and the shim picks the newest.

---

## 9. What was refused

Every refusal below was the right call, and each one is a place a builder could have quietly grown the diff instead.

### migrate-wiring

| Refused | Why it was right |
|---|---|
| Touching `agent_state.py` at all — zero lines | The predicted collision was avoided by construction rather than negotiated. This is why §4's premise turned out to be wrong in your favour |
| Adding locking to `agent_state`'s writers | Took `scene_memory`'s existing `_get_file_lock` around the migration only — the hazard *this* change introduces. The pre-existing hazard across the four appenders is a separate fix in the file another builder was in |
| Widening `log_decision`'s payload keys | That was the sibling brief |
| Threading the provenance outcome into the build result | `graph_builder._emit_provenance` is fire-and-forget by design; changing that is a return-contract change. **Note:** B5 shows the *reasoning* was wrong — a channel already exists — but the refusal itself was correct |
| Reconciling `panel/routing_log.py`'s dormant competing writer | Flagged by the contract phase, out of brief |

### prompt-fallback-loud

| Refused | Why it was right |
|---|---|
| Changing which branch is chosen or what either returns | The brief forbade it, and two assertions pin it. The genuinely larger defect — that an empty prompt is shipped to the model at all — is a separate gated decision |
| Substituting a different hardcoded prompt | The contract phase named this as a **strictly worse** violation of the same clause: a silent prompt substitution |
| `logger.debug` or log-only | Both pre-registered cheats, both refused explicitly, and the test fixture is built to catch the first one |
| Editing any bound, minimum or contract number | The one red assertion hit was in the builder's *own* new test (`ImportError` vs `ModuleNotFoundError`). They corrected the **test** rather than making the code misreport the true exception class — then re-ran fail-first against unfixed source to re-earn the claim |

### journal-datestamp

| Refused | Why it was right |
|---|---|
| Backfilling the 2,667 undated lines | There is no honest source for their day. Inventing one is exactly the failure class the fix exists to remove |
| Rewriting `harness/notes/econ/E1_SURFACE.md:366` | A frozen findings artifact, accurate when written. Fixing a *producer* that re-emits a claim every run is a different act from rewriting a historical audit's conclusions |
| Adding a "legacy lines stay readable" test | It passes identically before and after, so it cannot fail — a decoration under Law 1. Verified by direct probe and reported instead |
| Widening the econ regex past the two real formats | A regex matching everything would pass the compatibility test while destroying the discrimination the producer depends on |

### decision-writer-widen

| Refused | Why it was right |
|---|---|
| Adding named `proposal`/`expected`/`observed`/`route`/`receipt`/`scene-identity`/`spend` attributes — **the literal job item** | No caller populates them. Every record would carry empty placeholders: a schema that *looks* like it carries verification evidence, fed by nothing. The contract phase named exactly this as the way to satisfy the letter while violating §6. The passthrough delivers the same practical outcome honestly |
| A catch-all JSON blob | The other pre-registered cheat. Nothing can query `execution_route` out of an unindexed string, especially with zero existing readers |
| Fixing `graph_builder.py:286-287`'s bare `except Exception: pass` | **The real Law 3 defect in the chain** — `BUILT` is returned at `:190` over a lost record with no mention. Second file, outside the briefed defect, during a known collision. Escalated as a finding rather than grown into the diff |
| Changing `log_decision`'s return type to report failure | Would break the contract pinned by two existing tests and force an edit in a second file. The brief's condition was "written **or** the caller is told" — the key now gets written |

**One refusal I would flag as worth revisiting:** decision-writer's escalation of `graph_builder.py:286-287` is the most consequential unaddressed item in the wave that nobody owns. A build whose provenance never landed still reports `BUILT`. Two builders independently identified it and both correctly declined it. It needs a brief.

---

## 10. Unknowns

Labelled honestly. Nothing here is a soft version of a known thing.

**UNVERIFIED — line ranges for migrate-wiring's `scene_memory.py` block.** The builder reports the new block at 325-432 and edits at 469-498. I verified the `graph_synth_runtime.py` side directly (import at 114-118, UNKNOWN default at 125) and `handlers_memory.py:197/212-213`, but did not open the worktree `scene_memory.py` to confirm those two ranges. Carried as builder-reported.

**UNVERIFIED — the `synapse:ext:` non-ASCII round-trip through usda text export.** Real pxr accepted `CreateAttribute` for a non-ASCII key and the stage reopened, but `Tf.IsValidIdentifier` says such a name is not a valid USD identifier. Text-export round-trip was not tested. Payload keys are developer-authored today, so the attacker rated this informational only.

**UNVERIFIED — whether anything pins the `project_setup` response shape.** migrate-wiring adds a key to a dict that ships whole across the WS boundary (`handlers_memory.py:212-213`). The builder's caller hunt covered test files referencing `ensure_scene_structure` by name; it did not cover `tests/test_cto_mcp_contract.py`, MCP tool output schemas, panel-side handshake parsing, or any golden/receipt fingerprint. The in-code comment at `handlers_memory.py:203` says *"Result keys are purely additive"* — that is a comment, not a measurement.

**UNVERIFIED — prompt-fallback's dedupe frequency in practice.** Whether the chat notice fires once or once-per-turn depends on whether `str(exc)` is stable across turns for the real exception classes. Nobody measured it. Both outcomes are plausible and they are opposite failure modes.

**UNVERIFIED — the real-world cost of `_upgrade_agent_usd` on the hot path.** "Cached, returns immediately" is an assertion. The layer handle drops when the function returns, so whether USD's weak registry keeps it alive across memory operations is unmeasured. `agent.usd` is append-only and `_counter_suffix` (`agent_state.py:50-55`) walks every child, so if the layer is *not* retained, per-call cost scales with session history. INTENT §9 governs: this is an unmeasured performance claim on a path the report itself calls hot.

**UNKNOWN — the resend-vs-payload split in the fold slope.** See §6. Not recoverable from the v2-baseline artifact set; the `conversation` token field was never captured populated. Needs a live conversation-token readout at each task's first call, or a raw request log.

**UNKNOWN — the calendar day of every journal line written before 2026-09-14.** Genuinely unrecoverable. 2,667 lines. The first §9 measurement window can only begin at the first dated line.

**OPEN, unowned, not in any brief:** `panel/routing_log.py:102-163` (`RoutingLog._write_native_usd`) independently opens `agent.usd` and **rewrites the entire `/SYNAPSE/agent/routing_log` subtree** from its own in-memory list — the identical prim path `agent_state.log_routing_decision` (`agent_state.py:492-520`) incrementally appends to. Whichever writer runs last clobbers the other. Currently dormant: `write_to_usd()` has zero production callers, and `CLAUDE.md`'s own status table marks Routing Log Persistence as Phase 5. It is a live, code-proven instance of the exact competing-writer pattern §6 forbids, already built once in this repo. **Delete it or reconcile it before anyone wires `write_to_usd()` into production.**