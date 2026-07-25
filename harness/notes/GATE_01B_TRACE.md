# GATE 0.1b TRACE — hython3.13 access violation

VERDICT: QT

CRASHING FRAME: `tests/panel/test_font_scale.py:65` in `test_host_scale_tracks_large_host_font`
— the statement is `saved = app.font()`, i.e. `PySide6.QtWidgets.QApplication.font()`.
Tier: **VERIFIED-RUNTIME** (reproduced in this worktree, 2026-07-25, hython3.13 / Python 3.13.10).

Zero frames under `python/synapse/_vendor` appear anywhere in the faulthandler traceback.
`synapse._VENDOR_ABI_RISK` is `False` on this interpreter (vendor tree ACTIVE) and `import synapse`
succeeds cleanly — the vendored tree is live and is not implicated in the fault.

## PRODUCER (Law 2)

Isolated — PASSES, no crash:

    hython3.13.exe -X faulthandler -m pytest tests/panel/test_font_scale.py -q -p no:cacheprovider
    -> 8 passed, 1 warning in 1.67s

Whole panel dir — no crash:

    hython3.13.exe -X faulthandler -m pytest tests/panel/ -q -p no:cacheprovider
    -> 2 failed, 27 passed in 1.22s

MINIMAL CRASH REPRO (2 files):

    hython3.13.exe -X faulthandler -m pytest -q -p no:cacheprovider -W ignore::Warning \
      tests/panel tests/test_hda_panel.py
    -> access violation at tests/panel/test_font_scale.py:65

PYTHONPATH for all three: `C:\Users\User\SYNAPSE\python;C:\Users\User\SYNAPSE`
cwd: `C:\Users\User\SYNAPSE\.claude\worktrees\solaris-repair`

**Trigger is fake-Qt residency, not ABI.** `tests/test_hda_panel.py:172-175` plants
`sys.modules["PySide6"]` / `.QtCore` / `.QtWidgets` / `.QtGui` stubs at MODULE level,
unconditionally. pytest imports every test module during collection, so the stub is resident
before the first panel test runs. `tests/panel/*` then executes against a half-stubbed Qt.
This is the known fake-residency trap, now reaching a native fault instead of a plain failure.

## FAULTHANDLER TRACEBACK (trimmed, worktree repro)

    Windows fatal exception: access violation

    Current thread 0x0000b724 (most recent call first):
      File ".../tests/panel/test_font_scale.py", line 65 in test_host_scale_tracks_large_host_font
      File ".../_pytest/python.py", line 167 in pytest_pyfunc_call
      File ".../pluggy/_callers.py", line 121 in _multicall
      File ".../_pytest/python.py", line 1707 in runtest
      File ".../_pytest/runner.py", line 184 in pytest_runtest_call
      File ".../_pytest/runner.py", line 139 in runtestprotocol
      File ".../_pytest/main.py", line 408 in pytest_runtestloop
      File ".../_pytest/main.py", line 330 in wrap_session
      File "<frozen runpy>", line 198 in _run_module_as_main

Every frame is test code, pytest, pluggy, or runpy. The faulting native call is Qt's
`QApplication::font()`. No `_vendor`, no `hou`, no compiled SYNAPSE extension in the stack.

## OTHER FAILURES

`tests/panel/test_docking.py::test_usable_at_min_height` (fails only in the composed run):

    python\synapse\panel\synapse_panel.py:237: in __init__
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    E   AttributeError: 'SynapsePanel' object has no attribute 'setAttribute'

That is the stub base class leaking in — under a clean import the MRO is
`SynapsePanel -> PySide6.QtWidgets.QWidget -> PySide6.QtCore.QObject` (probed, VERIFIED-RUNTIME).

`tests/panel/test_failure_trail.py::test_runtime_paths_log`:

    tests\panel\test_failure_trail.py:123: in test_runtime_paths_log
        assert trailed, (
    E   AssertionError: a swallowed failure on a guarded runtime path (_wire_gate) left no
        logger.debug trail — the bare `except: pass` is still silent (Codebase 1.4).

`tests/panel/test_failure_trail.py::test_dead_verb_hidden`:

    tests\panel\test_failure_trail.py:151: in test_dead_verb_hidden
        assert not shown, (
    E   AssertionError: the 'open in render view' verb is present and shown while the render
        bridge is absent — a visible no-op (Design 2.5).

Both failure_trail failures also occur in the ISOLATED `tests/panel/` run — they are real
red, independent of the residency trap and independent of the crash.

## QAPPLICATION

Exists at import time? No — `QtWidgets.QApplication.instance()` is `None` both before and after
importing `synapse.panel.synapse_panel` under hython3.13 (probed).

Widgets built without one? No — each panel test file carries its own module-global `_APP` and
calls `QApplication.instance() or QApplication([])` before constructing any widget
(`tests/panel/test_docking.py:88-93`, `tests/panel/test_font_scale.py:50-60`). The per-file
`_APP` globals are the hazard: several independent modules each believe they own the
application object.

## STATE

- `git rev-parse --short HEAD` -> `de53153` (branch `feat/solaris-repair-01`)
- receipts present in `harness/notes/receipts/`: `L0.json`, `L1.json`, `L2.json`, `L3.json`, `T0.json`
- `.claude/worktrees/solaris-repair/harness/notes/receipts/SR1.json`: **does not exist**

## GATE BEARING (evidence only — Gate A is human, Article I)

The one crash blocking 0.1b is Qt-side and residency-triggered — not evidence against the
vendored tree, which is ACTIVE and imports clean on hython3.13. No fix attempted (Law 6);
no test skipped or xfailed.
