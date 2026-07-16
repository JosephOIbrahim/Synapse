# H22 Qt/PySide Smoke — Drop-Week Runbook Step 6

> **VERDICT: PASS — panel boots on H22.0.368 (Vulkan-era build) under hython offscreen;
> `drop.json` PySide 6.8.3 matches the live runtime exactly; every QFont letter-spacing
> path reads back correct values live.** One harness-stub fidelity gap was found and
> fixed mid-step (`run_panel.py` `_Hou` stub lacked `isUIAvailable` — the G1 boot smoke
> could not run under hython AT ALL without it). The fix is 8 lines in the dev harness
> script, not panel or bridge source. Boot was FAIL-as-found, PASS post-fix; both runs
> recorded verbatim below.

- **Governing gate:** h22-gatewarden `GATE VERDICT: ALLOW` (MODE B), this session, carried
  in the dispatch. This artifact is step 6's required output — blueprint
  `docs/SYNAPSE_H22_GAP_BLUEPRINT.md:242` verbatim: "**Qt/PySide smoke.** Panel boot on
  the Vulkan-era build; `drop.json` PySide field vs panel assumptions; QFont
  letter-spacing path included."
- **Author:** h22-forge, this dispatch (2026-07-16). Every output below was produced by
  the author this dispatch under
  `C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe` with
  `QT_QPA_PLATFORM=offscreen` (house rule: hython offscreen ONLY — no PySide in stock
  python).
- **Phantom-guard:** the only `hou.*` symbol emitted by the probe
  (`hou.applicationVersionString`) was checked against the committed
  `python/synapse/cognitive/tools/data/h22_symbol_table.json` before emission (present).

---

## Definition of Done (this artifact)

1. `drop.json` `pyside` field read verbatim and compared against the panel's actual
   assumptions (import structure + Qt6-only call sites). ✅
2. Live version truth captured inside H22 hython: python / PySide6 / Qt / hou build,
   diffed against all `drop.json` fields. ✅ (3/3 exact match)
3. Panel boot exercised offscreen (`run_panel.py --smoke`, the G1 gate). ✅ (FAIL-as-found
   → root-caused → minimal fix → PASS; both runs recorded)
4. The QFont letter-spacing path exercised at **all three** repo call sites, values read
   back and asserted. ✅ (13/13 probe checks PASS + independent G3 corroboration)
5. G3 strict audit (`audit_panel.py --strict`) run under H22 hython as the
   usability/readability backstop. ✅ (exit 0, pass · 1 pre-existing WARN)
6. Pass/fail recorded with output, per dispatch. ✅

---

## 1. `drop.json` PySide field vs panel assumptions

`harness/state/drop.json` (verbatim): `"pyside": "6.8.3"`, `"python": "3.13.10"`,
`"houdini_build": "22.0.368"`, `"usd": "0.26.5"`.

**Panel assumptions (from code, this dispatch):**

| Assumption | Where | Verdict on 6.8.3 |
|---|---|---|
| PySide6 primary, PySide2 fallback — **no version pin anywhere** | every Qt import in `python/synapse/panel/` (`chat_panel.py:32`, `chat_display.py:11`, `command_palette.py:24`, `context_bar.py:18`, `designsystem/{components,fontload,motion,loader}.py`, `dnd.py:15`, `image_prep.py:18`, `gate_widget.py:15`, …) | ✅ primary branch taken; PySide2 code paths dormant |
| `QFont.setFamilies(list)` (Qt ≥ 5.13) with `setFamily` fallback | `designsystem/fontload.py:146-148` | ✅ Qt6 path taken |
| `QFont.Weight.Medium` (Qt6 enum) with Qt5 fallback | `designsystem/fontload.py:178-181` | ✅ live: `<Weight.Medium: 500>` |
| `QShortcut`/`QKeySequence` imported from **QtGui** (their Qt6 home; QtWidgets in Qt5) | `run_panel.py:104` | ✅ resolves |
| Shortened-enum access `QFont.PercentageSpacing` / `QFont.AbsoluteSpacing` (PySide6 "forgiving" compat spelling, canonical is `QFont.SpacingType.*`) | `fontload.py:187`, `components.py:47`, `health_infographic.py:236` | ✅ resolves on 6.8.3 and `== QFont.SpacingType.*` (probe 3a) — see caution §6.3 |
| Tracking lives on QFont, never QSS (Qt QSS has no `letter-spacing`) | `fontload.py` module contract; pinned by `audit_panel.py` "no bundled font in QSS" | ✅ G3: clean |

**Conclusion:** the panel's assumption set is exactly satisfied by PySide 6.8.3. No
version-conditional branch misfires; the PySide2 fallbacks are unreachable dead weight on
this build (by design — they stay for standalone/CI portability).

## 2. P1 — live version truth (PASS 3/3)

Probe: `h22_qt_smoke_probe.py` (scratchpad; full content reproduced in §8) under H22
hython offscreen. Output verbatim:

```
sys.executable : C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe
sys.version    : 3.13.10 (main, Mar  4 2026, 17:45:46) [MSC v.1942 64 bit (AMD64)]
hou build      : 22.0.368
PySide6        : 6.8.3
Qt runtime     : 6.8.3
Qt compiled    : 6.8.3
[PASS] drop.json houdini_build == live :: drop=22.0.368 live=22.0.368
[PASS] drop.json python == live :: drop=3.13.10 live=3.13.10
[PASS] drop.json pyside == live PySide6.__version__ :: drop=6.8.3 live=6.8.3
```

PySide `__version__`, Qt runtime `qVersion()`, and Qt compile-time version are all
identical (6.8.3) — no binding/runtime skew.

## 3. P2 — panel boot, G1 smoke (FAIL as-found → PASS post-fix)

### 3.1 As-found: FAIL (exit 1)

`hython run_panel.py --smoke` — verbatim traceback tail:

```
  File "C:\Users\User\SYNAPSE\shared\bridge.py", line 56, in <module>
    import hdefereval
  File "C:\PROGRA~1/SIDEEF~1/HOUDIN~1.368/houdini/python3.13libs\hdefereval.py", line 240, in <module>
    if not hou.isUIAvailable():
           ^^^^^^^^^^^^^^^^^
AttributeError: type object '_Hou' has no attribute 'isUIAvailable'
SMOKE FAIL / SMOKE_EXIT=1
```

### 3.2 Root cause (harness-stub fidelity gap — NOT a panel/bridge/H22 defect)

- `run_panel.py` plants a minimal `_Hou` stub into `sys.modules["hou"]` so the panel
  renders "alive" deterministically.
- Panel `__init__` (`synapse_panel.py:345`) imports `synapse.server.telemetry_dump` →
  `server.handlers` → `integrity_envelope` → `shared/bridge.py:56 import hdefereval`.
- Under **stock python** hdefereval doesn't exist → `ImportError` → bridge guard catches.
  Under **hython** it DOES exist, and its **top-level module code** runs
  `if not hou.isUIAvailable(): raise ImportError(...)`
  (`H22.0.368 houdini/python3.13libs/hdefereval.py:240`).
- Real headless hou answers `False` → hdefereval raises **ImportError** → the
  `except ImportError` guard in `shared/bridge.py:58` catches it → graceful standalone
  fallback. The stub lacked the attribute → **AttributeError** → escapes the guard →
  boot dies.
- **Not an H22 delta:** the identical line exists in the sibling H21.0.773 install
  (`houdini/python3.11libs/hdefereval.py:240`, grepped this dispatch). It is a
  stub-vs-hython interaction the G1 gate had simply never hit on this import chain.

### 3.3 Fix (minimal, faithful): `run_panel.py` — stub gains `isUIAvailable() → False`

8 lines added to the `_Hou` stub, returning exactly what real headless hou reports, so
hdefereval raises the same ImportError the production guard is built for. Dev harness
file only; zero panel/bridge/source changes.

### 3.4 Post-fix: PASS (exit 0)

```
SMOKE OK — SynapsePanel instantiated
SMOKE_EXIT=0
```

## 4. P3 — QFont letter-spacing path (PASS 13/13 probe checks)

All three repo call sites exercised live, offscreen, on the Vulkan-era build:

| Call site | Mechanism | Live readback |
|---|---|---|
| `designsystem/fontload.py:187` `tracked_font()` | `setLetterSpacing(PercentageSpacing, 100 + em×100)` | `BRAND` (em 0.16) → type `PercentageSpacing`, value **116.00** ✅; `BODY` (em 0) skips → 0.00 ✅ |
| `designsystem/components.py:47` `apply_font_role()` | `setLetterSpacing(AbsoluteSpacing, tracking)` | `title` role (1.0 px) → type `AbsoluteSpacing`, value **1.00** ✅ |
| `health_infographic.py:236` `_text()` | raw `QFont` + `AbsoluteSpacing` | 0.5 px round-trips exactly ✅ |

Supporting checks, verbatim probe output:

```
QApplication platform: offscreen
[PASS] shortened enum access QFont.{Percentage,Absolute}Spacing :: <SpacingType.PercentageSpacing: 0> / <SpacingType.AbsoluteSpacing: 1>
[PASS] shortened form == QFont.SpacingType.*
fontload status: {'ok': True, 'families': ['Space Grotesk', 'Space Mono'], 'missing': [], 'loaded': ['SpaceGrotesk-Variable.ttf', 'SpaceMono-Regular.ttf', 'SpaceMono-Bold.ttf'], 'build_mismatch': False}
[PASS] bundled fonts registered (no build_mismatch) :: families=['Space Grotesk', 'Space Mono'] missing=[]
[PASS] tracked_font('BRAND') type == PercentageSpacing :: <SpacingType.PercentageSpacing: 0>
[PASS] tracked_font('BRAND') spacing == 116.0 pct :: 116.00
[PASS] tracked_font('BODY') em=0 skips setLetterSpacing :: 0.00
[PASS] weight=500 -> QFont.Weight.Medium (Qt6 path) :: <Weight.Medium: 500>
[PASS] apply_font_role('title') type == AbsoluteSpacing :: <SpacingType.AbsoluteSpacing: 1>
[PASS] apply_font_role('title') spacing == 1.00 px :: 1.00
[PASS] raw QFont AbsoluteSpacing round-trip (health_infographic path) :: 0.50

== PROBE SUMMARY: 13 checks - 0 FAIL ==
```

Bundled Space Grotesk / Space Mono register cleanly into H22's QFontDatabase
(`build_mismatch: False`) — the graceful native-fallback branch is not needed on this
build.

## 5. P4 — G3 strict audit backstop (PASS, exit 0)

`hython audit_panel.py --strict` → `G3 RESULT: pass · 1 WARN`, exit 0. Independent
corroboration of the letter-spacing path from G3's own readback:

```
wordmark is brand    : 14px @ tracking 116.0%  [ ok ]
bundled fonts        : ['Space Grotesk', 'Space Mono']  [ ok ]
no bundled font in QSS: clean  [ ok ]
body matches host    : body 12px vs host 12px  [ ok ]
```

The single WARN is the pre-existing warnable item "interactive targets: 22 found, 13
under 26px" — tagged `warnable=True` in `audit_panel.py` by design; not a step-6
regression and not a FAIL.

## 6. Residuals and cautions (none blocks steps 7–9)

1. **OpenSSL legacy-provider warning** on every H22 hython 3.13 start
   (`Warning: OpenSSL 3's legacy provider failed to load…`). Cosmetic, emitted by the
   interpreter before any SYNAPSE code; recorded so later steps don't mis-attribute it.
2. **hdefereval is ImportError-by-design outside graphical Houdini** (raise at module
   top-level when `not hou.isUIAvailable()`). Anything that plants a fake `hou` and then
   runs under hython must stub `isUIAvailable` or the AttributeError escapes every
   `except ImportError` guard in the repo (`shared/bridge.py`, `shared/evolution.py`,
   §12 guards). The 46 test files that plant `sys.modules` hou fakes are safe **only**
   because the suite runs under stock python where hdefereval doesn't exist — worth
   remembering if any test ever runs under hython.
3. **Shortened enum spelling is compat, not canonical.** `QFont.PercentageSpacing`
   resolves on PySide 6.8.3 and is identical to `QFont.SpacingType.PercentageSpacing`
   (probe-verified), but it's the "forgiving enum" form Qt has been threatening to
   retire since 6.x began. No action owed this drop; if a future PySide drops it, the
   three call sites in §4 plus `motion.py`'s `QEasingCurve.Type` fallback pattern are
   the touch list.
4. **13 interactive targets under 26px** — pre-existing G3 WARN (§5), unchanged by H22.

## 7. What this step does NOT do (non-goals)

- Does not test panel behavior inside **graphical** Houdini (G2) — that is a
  live-session check, out of scope for the offscreen smoke by house rule.
- Does not touch rigging/KineFX/APEX (structurally refused), quarantine members,
  the sweep diff, or anything owned by steps 3–5 and 7–9.
- Does not execute any `flywheel_queue.json` proposal (C.0/S.0/R.0 remain
  `ratified:false`).
- Does not commit, merge, push, ratify, or touch `VERSION`.

## 8. Reproduction

Probe script: scratchpad `h22_qt_smoke_probe.py` (session-local). To reproduce, the
probe is fully specified by §2/§4: set `QT_QPA_PLATFORM=offscreen`, add repo root +
`python/` to `sys.path`, then under
`"C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe"`:
read versions (`sys.version_info`, `PySide6.__version__`, `QtCore.qVersion()`,
`hou.applicationVersionString()`) and diff against `harness/state/drop.json`; build an
offscreen `QApplication`; call `fontload.load_application_fonts()`,
`fontload.tracked_font("BRAND", 14)` / `("BODY", 12)` / `("LABEL", 12, weight=500)`,
`components.apply_font_role(QLabel(), "title")`, and a raw
`QFont().setLetterSpacing(QFont.AbsoluteSpacing, 0.5)`; assert `letterSpacingType()` /
`letterSpacing()` against `tokens.TRACKING_EM` / `tokens.TYPE_ROLES`. The two gate
commands are in-repo: `hython run_panel.py --smoke` and `hython audit_panel.py --strict`.

## 9. Suite gate (full `python -m pytest tests/`, the CI command)

A source file changed this step (`run_panel.py`, dev harness). Full-suite result
(stock python, the CI command, this dispatch):

```
4278 passed, 87 skipped, 553 warnings in 89.57s
```

Exit 0 — at/above the `harness/verify/suite_baseline.json` floor (4275/0/87; the +3 is
pre-existing branch delta, and floor advances are human-promoted only). The expected
cp314 vendor-ABI `RuntimeWarning`s fired in `test_undo_redo`/`test_vendored_deps`
(vendor tree correctly INACTIVE on stock 3.14 — the gate-0.1 posture, not a regression).

## Paths checked / commands run (every one, this dispatch)

| Path / command | How |
|---|---|
| `harness/state/drop.json` | Read (verbatim fields) |
| `docs/SYNAPSE_H22_GAP_BLUEPRINT.md:242` | Grep (step-6 verbatim text) |
| `python/synapse/panel/**` PySide imports | Grep `PySide2|PySide6|qVersion` (assumption table §1) |
| `python/synapse/panel/designsystem/fontload.py` | Read in full (tracked_font contract, lines 146-190) |
| `python/synapse/panel/designsystem/components.py:35-51` | Read (`apply_font_role`) |
| `python/synapse/panel/health_infographic.py:229-239` | Read (`_text` raw path) |
| `python/synapse/panel/designsystem/tokens.py:283-314` | Read (`TYPE_ROLES`, `TRACKING_EM`) |
| `run_panel.py` | Read in full; edited (§3.3); `--smoke` run twice under H22 hython |
| `audit_panel.py` | Read (gate semantics); `--strict` run under H22 hython |
| `shared/bridge.py:49-60` | Read (ImportError-only guard) |
| `H22.0.368 …/python3.13libs/hdefereval.py:225-255` | `sed` (top-level `isUIAvailable` raise) |
| `H21.0.773 …/python3.11libs/hdefereval.py` | Grep `isUIAvailable` (line 240 — same, not an H22 delta) |
| `python/synapse/cognitive/tools/data/h22_symbol_table.json` | Grep `applicationVersionString` (present — phantom-guard) |
| `harness/verify/suite_baseline.json` | Read (floor 4275/0/87) |
| Probe run (`P1`+`P3`), 13 checks | H22 hython offscreen, exit 0 |
