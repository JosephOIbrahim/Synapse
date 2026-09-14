# The panel seat suite is not merely unrun — it is unrunnable past test 11

**Date:** 2026-09-14 · **Found while** closing F4's owed seat verification
**Build:** hython 22.0.400 (the symbol-table-stamped build), `QT_QPA_PLATFORM=offscreen`
**Status:** PRE-EXISTING. Measured identical on `19981ddb` (pre-F4) and on master.

---

## What happens

`python .synapse/hytest.py tests/panel/test_bc_wave.py` reaches 76% and then
**hangs forever**. Killed at 300s on both trees, same point, same two failures
before it:

```
FAILED  test_chat_face_monochrome_one_accent_plus_state_marks   [30%]
FAILED  test_profile_row_retired                                [69%]
PASSED  test_consent_card_vocabulary                            [76%]
        test_turn_receipt_offers_revert_on_chat        <- hangs, never returns
```

## Why

The timeout's own stack dump names it exactly:

```
File "tests/panel/test_bc_wave.py", line 741  in test_turn_receipt_offers_revert_on_chat
File "python/synapse/panel/synapse_panel.py", line 3132 in _send
File "python/synapse/panel/synapse_panel.py", line 2090 in _allow_connection
```

`synapse_panel.py:2090` is `box.exec()` — the connection-consent
**`QMessageBox`**. Under `offscreen` there is nobody to click it, so a modal
dialog blocks the test process indefinitely.

## What it costs

Three of the file's thirteen tests can never run, on any machine, today:

```
test_turn_receipt_offers_revert_on_chat
test_wordmark_lockup_measured
test_consent_inline_on_chat
```

`test_consent_inline_on_chat` is a **consent** test that a **consent dialog**
prevents from ever executing.

Anything queued behind `test_bc_wave.py` in a multi-file run never starts
either — that is how this was found: a combined run with
`tests/test_panel_sweep_a.py` (9 tests) produced zero output from the second
file in twenty minutes.

## Why nobody knew

The file is PySide-gated. Under stock CPython it **skips**, and a skip exits 0.
The harness reads that as passing. This is
`[[synapse-suite-floor-and-phantom-reds]]`'s "412 skipped is 412 proving
nothing" with teeth: the seat suite is not a set of tests waiting for a seat, it
is a set of tests that stop dead a third of the way through even when given one.

## What this is NOT

**Not F4's.** Measured on `19981ddb`, which predates the F4 merge: byte-identical
outcome. `test_consent_card_vocabulary` — the F4-adjacent test — **passes on
both**.

**Not diagnosed further.** The two named failures
(`test_chat_face_monochrome_one_accent_plus_state_marks`,
`test_profile_row_retired`) were not investigated; `--tb=line` output was lost to
the timeout kill. They are recorded here as *named and open*, not as understood.

## The shape of the fix, not built

A test that reaches `_send` must not reach a modal. Either the seat fixture
issues a session grant up front so `_allow_connection` returns without a dialog,
or `_allow_connection` gains a non-interactive path for offscreen runs. The
first is a test-side change and the safer one — the second alters a consent
surface, which is gate joe.

Whatever is chosen, the file needs a hard per-test timeout so a future modal
fails loudly instead of hanging silently.
