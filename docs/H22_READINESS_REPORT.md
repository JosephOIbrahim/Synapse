# SYNAPSE → Houdini 22 Readiness Report

**Prepared:** 2026-06-26 · **Drop ETA:** mid-July 2026 (~3 weeks) · **Current:** SYNAPSE v5.15.0 on Houdini 21.0.671, Python 3.11, PySide6
**Grounding:** code at `C:/Users/User/SYNAPSE`, H21 reference docs at `G:/HOUDINI21_RAG_SYSTEM`. Every claim carries `file:line` (code) or a file path (G:\ docs). All counts live-grepped.

---

## 1. Executive summary + readiness verdict

**Verdict: infrastructure-ready, decision-blocked. SYNAPSE will *not* break on drop day if a human crosses three gates first — but it ships today with one hard import-failure cliff and two real bugs that the existing harness does not yet catch.** The migration machinery is genuinely built: a self-verifying harness (`harness/`), a version-stamped phantom-API gate (`scout.py` + the symbol table), a documented 4-step runbook (`docs/studio/UPGRADE.md`), and a written decision brief on the critical blocker (`harness/notes/gate-0.1-sidecar-vs-abi3.md`). Drop day is "verification, not surgery" **only if** H22 keeps Python 3.11; if it bumps to 3.12/3.13, the vendored Anthropic SDK fails to import and the brain does not wake. That single unknown — SideFX has not announced H22's Python version — is the hinge the whole report turns on.

**Top 3 blockers (ranked by blast radius):**

1. **Vendored-SDK ABI lock → total import failure if Python bumps.** Two native wheels are pinned `cp311-cp311-win_amd64` (NOT abi3): `_vendor/pydantic_core/_pydantic_core.cp311-win_amd64.pyd` (5.0 MB) and `_vendor/jiter/jiter.cp311-win_amd64.pyd` (444 KB). The activation gate at `python/synapse/__init__.py:52` is a hard equality `version_info[:2] == (3, 11)`. On 3.12+ the `.pyd` files are unloadable → `ImportError` → daemon boot fails. This is THE blocker; the sidecar-vs-abi3 decision (`harness/notes/gate-0.1-sidecar-vs-abi3.md`) is unresolved.
2. **Symbol-table skew → phantom-API gate goes inert.** `python/synapse/cognitive/tools/data/h21_symbol_table.json` is stamped `21.0.671` (33,255 symbols, blake2b `ae7688f80a7076dc1c5b9fb3c05ab53d`). The instant H22's `applicationVersionString()` differs, `gate_stamp.py:31-33` reports stale and every `synapse_scout` verdict flips to `null` (gate disarmed) until regenerated. SYNAPSE's #1 failure class (phantom APIs) goes unguarded during the exact window H22 introduces new/renamed APIs.
3. **USD punycode parm encodings → silent Solaris write misses.** The H21 docs prove these encodings *already shifted once* (`xn__inputsexposure_fya` → `xn__inputsexposure_vya`, `G:/…/solaris_reference/lighting.md` "Common Mistakes" block). SYNAPSE ships a hardcoded alias→encoded map keyed on `xn__inputsintensity_i0a` / `xn__inputsexposure_vya` etc. If H22's USD bumps the encoding again, every light/camera parm write silently misses with no error.

**Two bugs the harness should catch but doesn't yet** (both surface *before* H22, both headless-fixable now): the symbol-table regen reproduces a `dir()` blind spot for lazily-imported `hou` submodules (`hou.qt` / `hou.text` / `hou.secure`), and Phase-0 task 0.2 (build the probe harness) has been BLOCKED for 7 rounds (`harness/state/claude-progress.md:52-59`) — meaning the drop-day API-delta detector is itself unbuilt.

---

## 2. The migration surface

SYNAPSE's H-API footprint cross-referenced against what the G:\ H21 docs actually document vs. leave undocumented. **Breadth:** 67 files import `hou`; ~666 `hou.*` call-sites, 44 `pdg.*`, 175 `pxr/Usd/Sdf` refs; 89 distinct `createNode()` type-strings.

### Documented + stable (low migration risk)
These are documented in the G:\ reference and are core USD/Solaris primitives unlikely to churn:

| Surface | Doc grounding | Why stable |
|---|---|---|
| LIVRPS composition arcs (`edit`/`reference`/`sublayer`/`inheritsfrom`/`variantset`) | `solaris_reference/usd_stage_composition.md:17-30`, `usd_operations.md:123-146` | LOP-type names are USD-canonical; SideFX has held them across releases |
| Karma delegate IDs `BRAY_HdKarma` (CPU) / `BRAY_HdKarmaXPU` (XPU) | `api_reference/hydra-delegates.md:220-233` | Plugin IDs, registered via plugInfo.json; renaming breaks every third-party delegate too |
| `pxr.Usd/Sdf/UsdGeom/UsdShade` core authoring | signatures throughout `solaris_reference/` | The `pxr.Usd` *core* path is version-coupled but API-stable; the fragile part is compiled schemas, not core |

### Undocumented / fragile (the migration payload)
The docs either pin behavior to "Houdini 21" explicitly, or don't cover SYNAPSE's heaviest surface at all:

| Surface | Code site | Doc signal | Risk |
|---|---|---|---|
| **USD punycode parm names** — `xn__inputsintensity_i0a`, `xn__inputsexposure_vya`, `xn__karmasubdivisionmesh_beb`, … | UsdLux/Karma authoring; alias map | `lighting.md` Common-Mistakes block documents a *prior* `_fya`→`_vya` shift; `troubleshooting/common_errors.md:39` lists the mappings SYNAPSE depends on | **Highest functional-break probability.** A namespace-encoding change in H22's USD silently misses every light/parm write |
| **Legacy COP2 node types** `cop2net` (6 sites), `vopcop2gen` (11 sites) | `server/handlers_cops.py` (verified counts) + `routing/recipes/pipeline_recipes.py:1124` | The G:\ COP doc (`cops_compositing.md`) describes **legacy COP2 only** — H20+ Copernicus (`copnet`, GPU COPs) is **not documented at all**, yet SYNAPSE's heaviest API usage is `hou.Cop*` (301 refs) | **Top deprecation risk.** SideFX is mid-migration COPs→Copernicus; the cop2 types are the most likely removal. Most call-sites have no fallback |
| **`usdrender` vs `usdrender_rop`** | single-entry alias `server/solaris_compose.py:46` (`{"usdrender": "usdrender_rop"}`) | Docs use both names interchangeably (`solaris_nodes.md:70-72`); bare `usdrender` is already a phantom | Must be re-validated on H22; the alias map is one hardcoded entry |
| **`SchemasForRenderers` / string-based `HasAPI`** | compiled-schema path (not SYNAPSE's core) | `usd-schema-registration.md:278` verbatim: *"Karma does NOT use SchemasForRenderers in Houdini 21 — Houdini handles the mapping internally"* — behavior **pinned to "21"** | Behavioral carve-out explicitly flagged version-dependent; may flip in H22 |
| **`houdini21.0` pref-dir / `PXR_PLUGINPATH` path pins** | install/discovery guidance SYNAPSE inherits | 42 version-pinned path occurrences across 15 G:\ files; `pxr-pluginpath.md:97` hardpins `…\Houdini 21.0.512\bin\usdGenSchema.cmd` + `$HOUDINI_USER_PREF_DIR=…/houdini21.0` | Pref dir becomes `houdini22.0`; any path-derivation logic must not hardcode `21.0` |
| **`hou.qt` / `hou.text` / `hou.secure`** | panel + `host/auth.py`, `host/daemon.py` (`hou.secure` used at 45 sites verified) | Not in the symbol table — lazily-imported submodules `dir()` empty at introspection time | These read as phantoms *today*; see §3 symbol-table axis |

**Version pins that must be bumped on drop:** `memory/ledger.py:63` (`CUTOVER_BUILD = "21.0.631"`), the symbol-table stamp, and `daemon.py:355-367` (`WindowsSelectorEventLoopPolicy` — a Python-3.11-specific workaround).

---

## 3. H22 risk matrix

| Axis | Risk | Likelihood | Blast radius | Evidence |
|---|---|---|---|---|
| **Vendored ABI / Python version** | `cp311` `.pyd` won't load on 3.12+ → `ImportError` → brain dead | **Medium** (H20.5/21.0/21.5 all 3.11; H22 unannounced) | **Total** — SYNAPSE won't import at all | `__init__.py:52` `== (3,11)`; `_vendor/{pydantic_core,jiter}-*.dist-info/WHEEL:4` = `Tag: cp311-cp311-win_amd64`; `harness/notes/gate-0.1-sidecar-vs-abi3.md:8` |
| **Symbol table** | Stamp `21.0.671` ≠ running `22.0.x` → gate disarms, all scout verdicts `null` | **Certain** (any build change trips it) | **Wide but graceful** — phantom-API guard inert, agents fall back to hallucinating; no crash | `h21_symbol_table.json` header; `gate_stamp.py:31-33`; `doctor.py:290-296`; `scout._read_symbol_table` stale path |
| **Symbol-table blind spot** *(bug, exists today)* | Regen reproduces empty `dir()` for `hou.qt`/`hou.text`/`hou.secure` → real APIs read as phantom | **Certain** (introspector never force-imports lazy submodules) | **Medium** — false-phantoms on 45+ `hou.secure` sites, panel `hou.qt` | `introspect_runtime.py:81-104` calls `_walk(hou,…)` directly, no submodule import; CLAUDE.md §11 even mislabels `hou.secure` a phantom |
| **USD / pxr** | USD bump changes composition/schema or **punycode parm encoding** | **Medium-High** (encoding already shifted once) | **High, silent** — Solaris light/camera/parm writes miss without error | `lighting.md` `_fya`→`_vya`; `common_errors.md:39`; `boost_python` still used in H21 schema bindings (`usd-schema-registration.md:202`) — USD upstream is migrating off boost, H22 USD bump is the likely trigger |
| **PySide6 / Qt** | Qt API or event-loop change breaks panel boot / signal marshalling | **Low-Medium** | **High** — no UI, no chat panel; daemon can't marshal to main thread | 29 files `from PySide6`; `hou.qt.mainWindow`/`mimeType`/`color` panel-dock + DnD coupling; G:\ docs carry **zero** PySide/Qt version info (gap) |
| **hou / pdg API renames** | Node-type or method removal: legacy `cop2net`/`vopcop2gen`; PDG event-callback API | **Medium-High** for COP2; **Low** for PDG core | **High** for COPs (301 `hou.Cop*` refs); narrow for PDG | `handlers_cops.py` (`cop2net`×6, `vopcop2gen`×11); G:\ `cops_compositing.md` documents only legacy COP2, **not** Copernicus; PDG event API is repo-tribal-knowledge, not RAG-covered |
| **Node-type / parm string drift** | 89 hardcoded `createNode()` strings + 36 `xn__` encoded parms | **Medium** | **Variable** — per-feature break, not systemic | `solaris_compose.py:46` single alias entry; `karma`(196)/`usdrender_rop`(23)/`karmarenderproperties`(22) hardcoded; probe is the intended catch-all but is **unbuilt** (task 0.2 blocked) |

---

## 4. Drop-day runbook

Ordered, leveraging the existing harness. Mode A (now) → Mode B (armed when a human writes `harness/state/drop.json`). Three human gates never auto-crossed (`harness/state/claude-progress.md:16-21`).

**Pre-flight (do before drop — see §5):** resolve gate 0.1, fix the introspector blind spot, build/unblock the probe (task 0.2).

**Day 0 — H22 ships:**

1. **Install H22 clean**, then read the three numbers (the Mode-B trigger inputs):
   ```powershell
   & "C:\...\Houdini 22.0.xxx\bin\hython.exe" -c "import sys,pxr,PySide6.QtCore as q; print(sys.version_info[:2], getattr(pxr,'__version__','?'), q.__version__)"
   ```
2. **Decide the ABI path (HUMAN GATE 0.1)** based on the Python number:
   - **Python == 3.11** → vendor survives unchanged. Proceed.
   - **Python == 3.12+ AND sidecar already staged** → brain immune; just verify the IPC seam (`check_brain_answers`).
   - **Python == 3.12+ AND status-quo** → re-vendor the 2 wheels for the new `cpXX` (`_vendor/README.md:60-82` refresh command), widen `__init__.py:52` to `(3,11),(3,12)`, update `tests/test_vendored_deps.py`. Small, offline.
3. **Write `harness/state/drop.json` (HUMAN GATE — Mode-B trigger):**
   ```json
   { "python": "3.x", "usd": "Y.Z", "pyside": "6.Q.R", "houdini_build": "22.0.xxx" }
   ```
4. **Regenerate the symbol table inside H22** (`docs/studio/UPGRADE.md` Step 1):
   ```powershell
   & "...\hython.exe" host\introspect_runtime.py
   ```
   Overwrites `h21_symbol_table.json` (~1.1 MB diff). Confirm `TABLE: version=22.0.xxx symbols=~33000 truncated=False`. **Commit it.** Bump `ledger.py:63` `CUTOVER_BUILD`.
5. **Re-install the SYNAPSE package** into H22's pref dir (`UPGRADE.md` Step 3): `python scripts/install_synapse_package.py`. Confirm no `houdini21.0` path leaked.
6. **Confirm the gate** (`UPGRADE.md` Step 4): one `synapse_scout` call on `hou.LopNode` → expect `gate_armed: true`, `stale: false`, `exists_in_runtime: true`, panel footer clean.

**Day 0–1 — harness Mode B verification (automated):** tasks 1.3 (`import_panel`+`brain_answers` — brain wakes on H22 Python), 1.4 (fire the probe → `.claude/probe_delta.json`), 1.5 (`doctor` green), 1.6 (`theme_ok` — panel reads H22's theme).

**Day 1–N — patch the deltas (harness loop, max 3 repair rounds/task):** task 2.1 promotes **probe truth over pinned constants** — re-validate `solaris_compose.py:46` alias, the 36 `xn__` encodings, and the `cop2net`/`vopcop2gen` types against the live delta. Tasks 2.2/2.3 (new COPs + Solaris features), 2.5 (provenance ledger on H22's schema).

**Day 7+ — demo (HUMAN GATE):** task 3.1 timed runsheet rehearsal, 3.2 record. **Merge to main is human** (harness commits in worktrees only).

---

## 5. Improvements — do now, before the drop (prioritized, headless-safe)

All verifiable via hython offscreen on H21; none require H22. Ranked by risk-reduction per unit effort.

1. **Fix the introspector submodule blind spot** *(small, high value — this is a live bug)*. Patch `introspect_runtime.py:81-83` to force-import the lazy submodules before `_walk`: `import hou.qt, hou.text, hou.secure` (guarded) so `dir()` captures them. Today scout false-phantoms 45+ real `hou.secure` sites and the panel's `hou.qt.*`; **the H22 regen reproduces the gap unless patched first.** Re-run on H21, confirm the three submodules appear, commit the corrected table. (Side benefit: fixes the CLAUDE.md §11 mislabel of `hou.secure` as phantom.)

2. **Unblock and build task 0.2 — the probe harness** *(medium, critical-path)*. It has been BLOCKED 7 rounds (`claude-progress.md:52-59`). On H21 its delta vs pinned constants should be ~empty — *that empty diff is the proof it works before the drop makes the diff real* (`tasks.json:23`). Without it, drop-day has no automated API-delta detector and §3's node-type/parm drift goes uncaught. Give it the spec it's blocked on, or hand-build it from `scripts/run_apex_verify.py` + `science/apex_probes.py`.

3. **Stage the sidecar skeleton (gate 0.1)** *(larger, converts the #1 blocker from "surgery" to "verification")*. The brief recommends sidecar but says *stage it, don't commit blind* (`gate-0.1-sidecar-vs-abi3.md:38`). The seam is already clean — `cognitive/agent_loop.py` has zero `hou` imports; transports exist (`server/websocket.py`, `server/bridge_endpoint.py`). Build a minimal out-of-process skeleton, re-home the `hou.isUIAvailable()` fork-bomb guard to the host launcher, prove `check_brain_answers` green through IPC on H21, and **measure the unmeasured IPC latency** (`gate-0.1:26` flags ~50-100ms as pure speculation). If it lands, H22's Python version stops mattering entirely.

4. **Pre-stage the re-vendor as a one-command script** *(small insurance)*. Even if sidecar is the target, script the `PYTHONNOUSERSITE=1 hython pip install --target _vendor …` refresh + the `__init__.py:52` gate-widen as a single dry-runnable step, so the status-quo fallback is push-button on drop day.

5. **Audit hardcoded `21.0` / pref-dir assumptions** *(small)*. Grep the install/discovery path for `houdini21.0`, `21.0.512`, literal version strings (303 version-literal hits exist repo-wide). The G:\ docs hardpin these (`pxr-pluginpath.md:97`); make sure none of SYNAPSE's own path derivation inherits the assumption before the pref dir becomes `houdini22.0`.

6. **Single-source the version** *(hygiene, already in flight)*. Task 0.3 PASSed (`claude-progress.md:46`) — `__init__.py:61` now reads `5.15.0`. Keep `VERSION` canonical so the drop-day stamp bumps don't desync.

---

## 6. What the G:\ docs could NOT tell us

The H21 corpus is the wrong instrument for H22 facts, and it is honest about it. Confirmed gaps (whole-tree searches returned zero):

- **Python version: never stated.** The only match is a stale doxygen placeholder `…\Houdini X.Y.ZZZ\houdini\python3.7libs` (`hengine21.0/_h_a_p_i__python.html:104`). The docs don't even document H21's real 3.11 → **zero signal** on a 3.11→3.12/3.13 bump. The ABI hinge is invisible to the corpus.
- **PySide6 / Qt version: never stated** in the H21 reference. The only Qt doc is the *RAG tool's own* `QT_UPGRADE_SUMMARY.md` (root, 2025-12-17), which targets PySide2/PyQt5→Tkinter — stale, unrelated to SYNAPSE's PySide6, not authoritative.
- **USD/pxr version number: never stated.** Inferable only indirectly via the `boost_python` tell (`usd-schema-registration.md:202`) — USD upstream is migrating off boost, so an H22 USD bump is the *likely* trigger, but the corpus gives no version to diff against.
- **No changelog / "what's new" / deprecation index for hou/pdg/Solaris exists** anywhere in the tree. `houdini_docs/` is empty; the topic map `_metadata/semantic_index.json` indexes MPM/VEX/geometry only — no migration topic. The root `CLEANUP_AND_MIGRATION_GUIDE.md` is about the RAG store's own file reorg, not Houdini.
- **Copernicus (`copnet`, GPU COPs) is undocumented** — the COP doc is legacy COP2, the wrong generation for SYNAPSE's 301 `hou.Cop*` refs.
- **The 803 SideFXLabs HDA schemas carry zero version stamp** (`semantic_index/sidefxlabs_entries.json`) → silent drift if Labs reships for H22.
- **The only hard API-version stamp in the entire corpus is HAPI = "Houdini Engine 8.0"** (`hengine21.0/_h_a_p_i__migration.html`, built Fri Sep 19 2025; tiny 3-member deprecated list, none on SYNAPSE's path). Useful precedent only: HAPI versions independently of Houdini's marketing number — H22's ABI bump need not track the "22" label.

**What only a live H22 build resolves** (must be read from the runtime, not the corpus): the Python/USD/PySide triple (write to `drop.json`), the real symbol table (regen via `introspect_runtime.py`), the actual `xn__` parm encodings, whether `cop2net`/`vopcop2gen`/`usdrender` survive, and the probe's API delta. The docs ground *which* surfaces are version-keyed; only H22 grounds *what changed*. **The corpus cannot pre-validate a single H22 API** — it tells you exactly where to point the probe, and nothing more.

---

**Bottom line for the TD:** You have ~3 weeks. The drop-day mechanics are built and the runbook is real. Spend the runway on three headless-safe items — (1) patch the introspector blind spot, (2) unblock task 0.2 so the probe actually exists, (3) stage + latency-test the sidecar skeleton so the Python-bump blocker becomes a non-event. Do those and drop day is genuinely verification, not surgery. Skip them and you're debugging a dead brain and an inert phantom-gate on launch day with the corpus unable to help.

**Key files:** `python/synapse/__init__.py:52` · `python/synapse/cognitive/tools/data/h21_symbol_table.json` · `host/introspect_runtime.py:81-104` · `harness/notes/gate-0.1-sidecar-vs-abi3.md` · `harness/tasks.json` · `harness/state/claude-progress.md:52-59` · `docs/studio/UPGRADE.md` · `python/synapse/server/solaris_compose.py:46` · `python/synapse/server/handlers_cops.py` · `python/synapse/memory/ledger.py:63` · `G:/HOUDINI21_RAG_SYSTEM/documentation/solaris_reference/lighting.md` · `…/troubleshooting/common_errors.md:39` · `…/api_reference/usd-schema-registration.md:278`

---

# Appendix — completeness critique (adversarial)

Verification complete. Every claim below is grounded in files I read this session. Here is the adversarial critique.

---

# Adversarial review: SYNAPSE → H22 Readiness Report

**Bottom line:** the report's architecture is sound and its top-3 blockers are real, but it contains **three ungrounded/inflated numbers**, **one wrong failure-mechanism**, and it **misses four concrete risks** — including the single cheapest high-value prep item (fail-closed drift policy) and a latent punycode bug that already exists in the tree today. Detail with citations:

## A. Claims NOT grounded in the code (accuracy failures)

1. **"301 `hou.Cop*` refs / SYNAPSE's heaviest API usage is `hou.Cop*`" — FABRICATED.** `grep "hou\.Cop"` across the entire repo (worktrees excluded) returns **0**. There is no `hou.Cop*` attribute access anywhere. The actual COP surface is **36 node-type-*string* sites** (`cop2net`×9, `vopcop2gen`×11, `copnet`×6, in `server/handlers_cops.py` + `routing/recipes/pipeline_recipes.py`). The risk is real (legacy COP2 strings are the likeliest removal in the Copernicus migration) but the report **overstates its magnitude ~8× and mislabels the mechanism** — it's `createNode("cop2net")` string drift, not Python-API-attribute removal. The report's "most likely removal" verdict survives; the "301 refs / heaviest API usage" framing does not.

2. **`hou.secure` "45 sites" — inflated.** Actual: **25** in `python/synapse/`, **0** in `host/`. Off by ~80%.

3. **`hou.text` is NOT a symbol-table blind spot.** I queried the live table: `hou.qt`→**False**, `hou.secure`→**False**, but **`hou.text`→True** (it IS present). The report lists all three as blind-spot false-phantoms; only two qualify. The §5 fix is still correct (force-import `hou.qt`, `hou.secure` before `_walk` in `introspect_runtime.py:81-83`), just drop `hou.text` from the list.

4. **"task 0.2 BLOCKED for 7 rounds" — misread.** `claude-progress.md` logs **"BLOCKED after 3 rounds"** (the repair-round cap), emitted ~8 times across 2026-06-25. It's "3 repair rounds, re-logged," not 7. The blocked-ness is real; the number is wrong.

5. **Wrong failure *mechanism* on the #1 blocker.** The report says on Python 3.12+ "the `.pyd` files are unloadable → ImportError." Not what happens. `__init__.py:51-57` gates the vendor dir behind `version_info[:2] == (3, 11) and platform.startswith("win")`. On 3.12+ the gate is **False**, so `_vendor/` is **never prepended** — the `.pyd` is never even *attempted*. The real failure is `ModuleNotFoundError: anthropic` (plus httpx/pydantic/anyio — the *entire* vendored stack vanishes, not just the 2 native wheels), because Houdini ships none of them. Outcome (dead brain) is right; mechanism is wrong, and it matters: the fix is **gate-widen + re-vendor**, not just "re-vendor the 2 wheels" — which the runbook gets right but the blocker narrative contradicts. (The gate also means **Linux/macOS seats never load the vendor at all** — `platform.startswith("win")` — an existing portability cliff the report omits.)

6. Minor breadth drift: "67 files import hou" → actual **78**; "89 createNode strings" → ~**79**. Directionally fine.

## B. Missed risks (real, grounded, H22-relevant)

1. **LATENT BUG TODAY: three punycode maps disagree on the same parm.** This is the strongest finding. SYNAPSE hardcodes `inputs:color` as **two different encodings in three files**:
   - `agent/specialist_modes.py:94` + `mcp/server.py` → `xn__inputscolor_vya`
   - `core/aliases.py:173` → `xn__inputscolor_kya`
   - and `color_control`: `specialist_modes.py:95` `…_control_wcb` vs `aliases.py:175` `…_control_r0b`.
   
   There is **no single source of truth** for the punycode surface — it's copy-pasted across ≥3 maps and **has already drifted**. At least one encoding is wrong on H21 *right now* (or they silently target different light schemas with no comment saying so). The report flags "USD encoding may shift in H22" but misses that the map is **already internally inconsistent** — which means the H22 USD bump won't just shift one table, it'll detonate a surface that has no canonical version to regenerate against. **Prep:** collapse to one generated map (derive from `prim.GetAttributes()` via a probe), don't hand-maintain three.

2. **`asyncio.WindowsSelectorEventLoopPolicy` / `set_event_loop_policy` is itself deprecated in newer CPython.** Grounded at `python/synapse/host/daemon.py:363-366` (the report's `daemon.py:355-367` cite is correct in range but abbreviates the path; it's `python/synapse/host/daemon.py`, and the gate-0.1 brief uses the same short form). The report and the brief both treat this as "a 3.11 workaround to bump." Neither flags that `set_event_loop_policy` and the policy classes are **deprecation-warned in Python 3.12+ and slated for removal** — so if H22 bumps Python, this code doesn't just need a version bump, it may emit DeprecationWarnings or break outright and needs rewriting to `asyncio.Runner`/explicit loop-factory. Concrete, not cosmetic.

3. **PySide6 unscoped-enum exposure — the specific Qt mechanism the report hand-waves.** Report rates PySide6 "Low-Medium" with no mechanism. The concrete one: **29 files** import PySide6, and `panel/` uses **unscoped enum shortcuts** heavily — `Qt.AlignLeft`×8, `Qt.AlignVCenter`×9, `Qt.NoPen`×10, `Qt.AlignCenter`×5, `Qt.AlignRight`×3. PySide6 tightened enum scoping across 6.x; a multi-version PySide6 jump in H22 can turn these into `AttributeError` (requiring `Qt.AlignmentFlag.AlignLeft`). This is a countable, grep-able pre-drop fix, not a vague "Qt API may change." Plus `hou.qt` (the panel↔Houdini bridge) is one of the genuinely-absent symbol-table entries — so the panel's bridge reads as phantom AND its enum usage is fragile.

4. **MaterialX is effectively unaddressed.** The user named it; the report mentions it only in passing. SYNAPSE hardcodes MaterialX node-type strings — `mtlxstandard_surface`, `mtlxgeompropvalue`, `mtlximage`, `mtlxnormalmap`, `mtlxstandard_volume` (in `handlers_material.py`, `solaris_compose_tools.py`, recipes). MaterialX ships **inside USD** and its version moves with the USD bump — exactly the H22 trigger. New required inputs or node renames silently break shader builds. This belongs in the risk matrix as its own row, not folded into "89 createNode strings."

5. **Karma render: the report flags the wrong layer as stable.** It calls Karma "low risk" because the **delegate IDs** (`BRAY_HdKarma`) are stable — true. But SYNAPSE's actual fragility is the **render-settings parm names**, which it guesses by hardcoded list: `handlers_render.py:114` tries `("renderer","karmarenderertype","renderengine")`; `solaris_compose_tools.py:12` depends on `productName`/`picture` fallback; `handlers_render.py:536` has a husk-no-op fallback. Your own memory notes already record that on H21 `productName` doesn't author the prim and husk silently no-ops on Indie. Those parm-name assumptions are the H22-fragile part, and the report's "stable/low" verdict points at the one part that *won't* move.

6. **PDG event bridge has two divergent implementations, one contradicting live recon.** `shared/bridge.py:601` subclasses `pdg.PyEventHandler`; `host/tops_bridge.py:484` calls the **constructor** `pdg.PyEventHandler(on_pdg_event)`. Your own recon memory says "`PyEventHandler(fn)` has no constructor — register a RAW callable." So one of these two is already on thin ice, and the PDG event-callback API (worker-thread firing, `event.node.name`, 2-arg `addEventHandler`) is precisely the undocumented, version-tribal surface H22 can shift. The report rates PDG "Low" and cites it as "repo-tribal-knowledge" — fair — but misses that the repo holds two contradictory call patterns *today*, so an H22 PDG change breaks at least one with no shared abstraction to fix in one place.

## C. The single highest-value prep item the report under-emphasizes

**Flip the scout drift policy to fail-closed (`SYNAPSE_SCOUT_DRIFT_POLICY=refuse`) as a pre-drop decision — the report omits this entirely.** `docs/studio/UPGRADE.md` documents it: under the **default `warn`**, the instant H22's version string differs, **every** scout verdict silently degrades to `null` and agents resume hallucinating phantom APIs — during the exact week API drift peaks — with only a panel-footer warning. The report calls this degradation "graceful." It's the opposite: it's the #1 failure class (phantom APIs) re-arming silently. `refuse` makes scout **raise** instead, forcing the regen before any ungrounded `hou.*` ships. Near-zero effort, directly defends the system's stated top risk, and the report never mentions the knob exists.

Runner-up: the report buries **stage + latency-test the sidecar skeleton** at §5 #3 and calls it "larger," yet §1 admits the whole report "turns on" H22's Python number — and the gate-0.1 brief's own recommendation is "default to sidecar, stage it, don't commit blind." The sidecar is the *only* item that makes the Python number **irrelevant** (the `agent_loop.py` seam is already zero-`hou`, transports already exist). With 3 weeks, that's a #1, not a #3 — *unless* you bet H22 stays on 3.11 (plausible: H20.5/21.0/21.5 all 3.11), in which case the brief is right that sidecar is over-investment and the probe/regen detection items win. The report should surface that bet explicitly rather than ranking by effort.

## D. One structural reassurance the report misses (in its favor)

The symbol-table regen is **decoupled from the ABI cliff** — and the report never says so. `host/introspect_runtime.py` imports only `hou`/`pdg`/`pxr` (lines 81-104); it does **not** import `synapse` or the vendored SDK. So even if the Python bump kills the brain, you can **still arm the phantom-gate**. The two top blockers are independent failure domains — worth stating, because it means drop-day can restore the safety gate before fixing the brain.

**Net:** keep blockers #1–#3, but (a) fix the COP "301 hou.Cop*" fabrication and the ImportError-mechanism error, (b) add punycode-divergence / MaterialX / PySide6-enum / asyncio-policy-deprecation as first-class rows, (c) re-aim the Karma verdict at parm names not delegate IDs, and (d) add "set drift policy to `refuse`" as the cheapest §5 item.

**Files grounding this critique:** `python/synapse/__init__.py:51-57` · `python/synapse/_vendor/{jiter,pydantic_core}-*.dist-info/WHEEL` (Tag: `cp311-cp311-win_amd64`) · `python/synapse/cognitive/tools/data/h21_symbol_table.json` (`21.0.671`, 33255 sym) · `host/introspect_runtime.py:81-104` · `docs/studio/UPGRADE.md` (Step 1 + `SYNAPSE_SCOUT_DRIFT_POLICY=refuse`) · `python/synapse/host/daemon.py:363-366` · `python/synapse/agent/specialist_modes.py:94-95` vs `python/synapse/core/aliases.py:173-175` vs `python/synapse/mcp/server.py` (punycode `vya`/`kya`, `wcb`/`r0b`) · `python/synapse/server/handlers_render.py:110-114,536` · `python/synapse/server/solaris_compose_tools.py:12` · `python/synapse/server/handlers_cops.py` (`cop2net`/`vopcop2gen`/`copnet`) · `shared/bridge.py:601` vs `python/synapse/host/tops_bridge.py:484` · `python/synapse/panel/gate_stamp.py` · `python/synapse/memory/ledger.py:63` · `harness/notes/gate-0.1-sidecar-vs-abi3.md` · `harness/state/claude-progress.md` (0.2 "BLOCKED after 3 rounds") · `harness/tasks.json`.
