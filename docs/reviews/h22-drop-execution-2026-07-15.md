# H22 Drop-Day Execution — 2026-07-15

> Manual drop-day run (bridge was down, so the DROP_DAY.md headless-hython
> instruments were driven directly rather than through the h22-drop-week
> workflow). Branch: `feat/h22-drop-execution`. All commits are worktree-only —
> **merge to main is the human gate.**

## Host

Houdini **22.0.368** · Python **3.13.10** · USD **0.26.5** · PySide/Qt **6.8.3**
· pref dir `C:/Users/User/OneDrive/Documents/houdini22.0` (OneDrive-redirected).
H21.0.671 is **uninstalled** — its hython is gone; MODE A's "0.x on H21 hython"
is no longer physically runnable, and the Mile-5 H21 live-perception window is
permanently closed (P0.6 shipped only the writer; no baseline was ever captured).

## What ran (all verified)

| Step | Result |
|---|---|
| `drop.json` written | MODE B armed; `mode_gate.py` confirms all 4 required fields real |
| Symbol table regen | `h22_symbol_table.json` — 35903 symbols, dual-build alongside h21; scout phantom-gate restored for H22 |
| `h22_api_delta.py` | symbols +3055/-407, **0 removed symbols referenced in SYNAPSE call-sites**; punycode **0 changed / 0 vanished** (+97 new); 2 node renames |
| Panel install | deployed into the OneDrive pref dir; `hconfig -xa` confirms load + `load_package_once` honored |
| Panel G3 audit | PASS under Qt 6.8.3 (all WCAG green; live-widget build skipped headless) |
| cp313 re-vendor | brain deps import in-process under H22 hython (see below) |

## Committed on this branch

1. `e433a41` — H22 probe artifacts (symbol table + usdlux encodings).
2. `38b33b6` — **cp313 re-vendor** (gate-0.1 drop-day contingency). pydantic_core
   2.46.3 + jiter 0.14.0 `.cp313-win_amd64.pyd` added alongside cp311 (same
   versions → pure-Python layer serves either ABI). Gate widened to
   `_VENDOR_PYS = {(3,11),(3,13)}`. **Gotcha fixed:** the pre-staged
   `wheel_cache/cp313` held pydantic_core 2.47.0, which pydantic 2.13.3 rejects
   (`SystemError`, requires 2.46.3) — pulled the version-matched wheels.
   Verified: stock-3.14 `test_vendored_deps` 17 pass / 2 skip; H22 hython
   `import synapse` clean, vendor active, no ABI warning, anthropic → `_vendor`.
3. `8ff27c9` — r_track `deps_isolated` now GREEN (R.4/P0.1 resolved by the
   re-vendor; snapshot truth-up).
4. `30c5bb7` — package hygiene: `hpath` (path deprecated per H22 docs),
   `load_package_once`, OneDrive pref-dir detection.
5. (this doc + relay floor drift 4118→4275.)

## OPEN — needs your ruling

### 1. Set-dressing recipe: 2 Solaris LOP changes (Solaris domain)
The only in-scope API breakage. Multi-site — do NOT half-fix:
- **`instancer` → `pointinstancer`** — confirmed rename (label "PointInstancer",
  same Lop category). High confidence.
- **`layout` — absent** from H22's default Solaris LOP surface (no name/label
  match in any category; not a loose stock HDA; siblings all loaded). Genuine
  removal/rename with no obvious successor — **needs your Solaris knowledge of
  what the H22 Layout LOP became.**
- Affected: `server/solaris_graph_templates.py:393` (emits `layout`/scatter),
  `server/handlers_solaris_assemble.py:54,69` (order map), `routing/recipes/
  scene_recipes.py`, `tests/test_setdressing_recipe.py` (verified-type set),
  palette filters. Wants a live-H22 functional test (create + cook), not just a
  string swap. Best handled as a ratified flywheel candidate.

### 2. Pre-existing suite failures (NOT introduced by this branch)
Confirmed by running against a clean `master` (4081f97) worktree — both fail there too:
- `test_phase0c_doc1_version_conformance` — `python/synapse/__init__.py`
  `__version__` is **5.23.0** but `VERSION`/pyproject are **5.24.0** (v5.24.0
  release left `__version__` unbumped). One-line follower fix, but it's
  release-version territory — flagged, not auto-changed.
- `test_m3_logs_doctor::test_symbol_table_check_h22_without_table_fails_loud` —
  environment/stamp-sensitive; fails on clean master in this stock-3.14 env.
- **Consequence:** the committed `suite_baseline.json` (4275 / **0 failed**)
  does not hold in this environment — master already has ≥2 hard failures. This
  branch adds **zero** new failures (it fixes deps_isolated). The baseline needs
  an honest human re-measure or these two tests fixed before `check_suite_baseline`
  can pass.

### 3. Minor H21 pins (low priority)
- `scripts/rewire_assess.py:40` `DEFAULT_VCC` hard-points at H21's `vcc.exe`
  (H21 removed → dev tool would fail). Derive from `--houdini-exe`/`HYTHON`.
- `python/synapse/panel/chat_panel.py:499` unguarded `menu.exec_()` (deprecated
  PySide6 alias) — guard like the `hasattr(menu, "exec")` sites elsewhere.

## Not done by design (human/durable-arch gates)
- **Sidecar** (gate-0.1 durable architecture) — ruled for the first post-release
  cycle, not the drop window. The re-vendor is the bridge.
- Formal drop-week `docs/reviews/*` artifacts + flywheel ratification (step 10).
- `git merge` / promotion to main.
