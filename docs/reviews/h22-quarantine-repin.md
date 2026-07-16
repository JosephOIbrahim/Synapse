# H22 Quarantine Re-Litigation — Runbook Step 3 (P6: the one legitimate re-probe event)

**Artifact:** `docs/reviews/h22-quarantine-repin.md` (persisted by the drop-week orchestrator from the ASSAYER dispatch report, 2026-07-16)
**Role:** ASSAYER (V1 hard gate)
**Date:** 2026-07-16
**Membership source:** `harness/state/leg0_baselines.json` → `baselines.quarantine_snapshot.members[]` (read verbatim this dispatch — 4 members; never from memory)
**Baseline (left side):** H21.0.671 symbol table, `symbol_count` 33255 (frozen 2026-07-11 @ `314acd6`)

## Probe path

- **Live bridge:** DOWN. `socket.connect(('127.0.0.1', 9999))` → `timed out`. Charter priority 1 unavailable.
- **Hython fallback (used):** `HYTHON` env var → `C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe`
- **Probed build (derived from the probe itself, verbatim):** `hou.applicationVersionString()` → `22.0.368`
- **Mismatch flag:** No live bridge build exists to compare — no site-packages mismatch observable. Per charter, any PASS below would be PROVISIONAL-headless; all verdicts are headless-derived and should be spot-reconfirmed when the bridge next comes up on 22.0.368.
- **Calibration control (same interpreter):** `hou.text` (non-GUI lazy) → `<module 'hou.text'>` — lazy loading works headless; `hou.qt` (GUI-lazy) → `AttributeError` — the GUI blind spot is real.

## Verdicts

### Member 1 — `hou.pdg` (namespace, quarantine form `hou.pdg.*`)

```
PROBE getattr(hou, 'pdg') -> AttributeError: module 'hou' has no attribute 'pdg'
PROBE importlib.import_module('hou.pdg') -> ModuleNotFoundError: No module named 'hou.pdg'; 'hou' is not a package
```

**QUARANTINE (re-pinned H22.0.368).** Absent by attribute access AND import. Cross-check: the top-level `pdg` module is alive — `importlib.import_module('pdg')` → `<module 'pdg' from 'C:\\PROGRA~1/SIDEEF~1/HOUDIN~1.368/houdini/python3.13libs\\pdg\\__init__.py'>`. The H21 rule carries forward unchanged: the live PDG API is top-level `pdg`; any `hou.pdg.<x>` is phantom on H22.

### Member 2 — `hou.secure` (lazy namespace, re-litigate priority HIGH)

Probed by lazy-namespace TOUCH + import per the baseline's own instruction ("probe by importing the namespace, not by plain dir()"):

```
PROBE getattr(hou, 'secure') -> AttributeError: module 'hou' has no attribute 'secure'
PROBE importlib.import_module('hou.secure') -> ModuleNotFoundError: No module named 'hou.secure'; 'hou' is not a package
```

**QUARANTINE (re-pinned H22.0.368), with one honest caveat.** Calibration control run in the same interpreter: `hou.text` (non-GUI lazy) resolves (lazy loading DOES work headless), while `hou.qt` (GUI-lazy) does not (GUI blind spot confirmed live). So `hou.secure` is either genuinely absent from 22.0.368 or GUI-session-only — headless cannot distinguish those two. **Consequence: `hou.secure` did NOT PASS → the auth resolver does NOT auto-adopt.** One reconfirmation touch on the live GUI bridge (22.0.368) is warranted before the auth-resolver question is closed permanently; until then the quarantine holds.

### Member 3 — `hou.lopNetworks` (callable)

```
PROBE getattr(hou, 'lopNetworks') -> AttributeError: module 'hou' has no attribute 'lopNetworks'
```

**QUARANTINE (re-pinned H22.0.368).** Still phantom. The R10 walk-from-root `hou.LopNetwork` idiom remains the replacement.

### Member 4 — `hou.updateGraphTick` (callable)

```
PROBE getattr(hou, 'updateGraphTick') -> AttributeError: module 'hou' has no attribute 'updateGraphTick'
```

**QUARANTINE (re-pinned H22.0.368).** Still phantom.

## Re-pin table

| Symbol | H21.0.671 status | H22.0.368 verdict | Tag |
|---|---|---|---|
| `hou.pdg.*` | QUARANTINE | ABSENT (attr + import) | `quarantine/h22.0.368` |
| `hou.secure` | QUARANTINE | ABSENT (lazy-touch + import; GUI-session caveat) | `quarantine/h22.0.368 (reconfirm-on-live-bridge)` |
| `hou.lopNetworks` | QUARANTINE | ABSENT (attr) | `quarantine/h22.0.368` |
| `hou.updateGraphTick` | QUARANTINE | ABSENT (attr) | `quarantine/h22.0.368` |

**Probe discipline:** each member probed ONCE (single hython dispatch, one probe block per member); one non-member calibration control (`hou.qt`/`hou.text`) run to weight the `hou.secure` verdict; no probe weakened, no result inferred from docs.

---

```
QUARANTINE hou.pdg             — absent on 22.0.368 (getattr AttributeError + ModuleNotFoundError); top-level pdg module remains the live API
QUARANTINE hou.secure          — absent on 22.0.368 headless (lazy-touch + import both fail; hou.text control proves lazy-load works headless); NO auth-resolver auto-adoption; reconfirm once on live GUI bridge
QUARANTINE hou.lopNetworks     — absent on 22.0.368 (getattr AttributeError)
QUARANTINE hou.updateGraphTick — absent on 22.0.368 (getattr AttributeError)
```

**COMPRESSED SUMMARY:** Probed build 22.0.368 (hython fallback; bridge ws://localhost:9999 DOWN/timed out — no build mismatch observable). 4/4 quarantine members re-pinned QUARANTINE on H22.0.368; 0 PASS. `hou.secure` did NOT pass → auth resolver does NOT auto-adopt; its ABSENT carries a GUI-session caveat (headless can't rule out GUI-only lazy load — one live-bridge reconfirmation owed). Cross-check: top-level `pdg` module present on H22 (`python3.13libs\pdg\__init__.py`).
