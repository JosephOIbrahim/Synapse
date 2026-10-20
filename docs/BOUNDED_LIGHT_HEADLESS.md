# Bounded headless LIGHT qualification

This experimental API changes one captured key-light exposure in a closed,
disposable Houdini 22.0.400 headless fixture. It has no registered artist tool
or panel route. The existing Solaris reference capture remains `PENDING_HUMAN`;
this work does not ratify the RC+xi blueprint, qualify a reference render or
activate external substrates.

The supported scene contains the nine standard manager contexts, one captured
`domelight::3.0` and its network box. Other graphs, animation, locked exposure,
unknown ownership, incomplete capture and a Houdini GUI refuse before mutation.
The operation sets only the captured exposure, within [-2, 2]. Generated HOM
authored code is parsed as data; userdata is captured explicitly. This capture
does not promise arbitrary HIP or external-asset fidelity. The USD read is
labelled `source=local_stage`, `sanitization=none`.

`HeadlessLightGate` borrows an existing recipe lifecycle, host backend and
explicit local `LedgerPort`. It uses the existing `BuildTransaction` ownership,
main-thread dispatch and undo mechanism. Its typed provisional decision runs
before lifecycle acceptance while ownership is held. Unexplained changes during
evaluation quarantine the transaction. A rejected candidate can use exactly one
measured recovery undo only when its complete state, tracking and latest undo
label prove ownership. Foreign or unknown edits are preserved for inspection.

The independent observer measures six values: normalized actual USD exposure
error, elapsed transaction-to-observation milliseconds, Windows process-lifetime
peak working set in decimal MB, node-plus-edge delta, Shannon entropy of the
complete captured light-exposure histogram, and invariant violation. Entropy of
the supported single-light set is zero; it is not image quality or artistic
uncertainty. USD exposure uses its measured binary32 storage type; exact IEEE
quantization is checked against the authored HOM value. No guessed tolerance is
used for schema fidelity.

Calibration is a separately approved disposable experiment. Every candidate is
rejected and restored. The first round collects 12 training and six independent
validation measurements. A six-dimensional sample covariance and explicit
measurement/structural resolutions define the profile. Lifetime-peak prediction
uses the measured pre-trial peak plus learned new-high-water growth; observed
peak memory remains the actual absolute process-lifetime value.

The training envelope is fixed before validation. An out-of-population validation
set cannot widen its own limit. The bounded acquisition plan retains all failed
validation samples as training and requires six fresh validation samples for the
next model, with at most three rounds, 30 restored probes and 60 seconds. Source,
invariant, custody or recovery failures stop immediately. Exhausted acquisition
reports `UNAVAILABLE`. These empirical profiles provide no statistical coverage
guarantee for future or artist workloads.

A usable profile binds the process, exact initial authored state and revision,
source identities, selected ledger owner and ledger URI. A successful edit makes
that profile stale. A second action must remeasure its new prestate. All forecasts,
observations, decisions and terminal states use the existing durable local ledger
writer. Run identity replay, corruption, truncation, interrupted claims, policy
changes and owner replacement refuse dispatch. Fuel and restoration history are
checked from persisted records. The fixed pure referee runs off-thread with only
detached numbers and immutable policy; no host or memory handle enters it.

`HEADLESS_ACCEPTED_UNSETTLED` means the measured local edit committed. Local
custody remains `EXPOSED`; Hanish settlement is `UNAVAILABLE` with the unconfigured
port. No SALUS approval, Octavius sanitization, external settlement or hostile-code
sandbox is claimed. Routes requiring unavailable external gates remain unavailable.
Cancellation is cooperative: a completed write must be restored before cancellation
is reported terminal.

Cancellation is forwarded to the active transaction. Its final cancellation
check and commit decision share a lock; a cancellation accepted before that
decision prevents metadata commit. A later request reports that the decision
already happened. Calibration also checks cancellation and its whole-experiment
deadline after the final restored probe and fitting, before publishing a profile.

Local custody keeps an independent acknowledged ledger count and digest. The
existing ledger writer flushes and syncs a row first, then the custody owner
syncs a pending acknowledgement, atomically replaces its anchor and rereads it.
A gap, missing anchor or leftover pending update refuses further dispatch;
interrupted evidence is preserved for inspection. This detects restoration or
truncation of the ledger while its anchor remains current. Restoring both the
ledger and anchor to an older matching backup is outside this local guarantee.

## Repeating the host checks

The opt-in source tests are `tests/host/test_light_gate_matrix.py` and
`tests/host/test_light_gate_cancel_foreign.py`. Run each module in a separate,
fresh, isolated headless H22 process. Ordinary CI skips them explicitly.

The isolation runner must bind this checkout as the imported source, provide its
own pytest dependencies, and isolate Houdini preferences, home, temporary files,
logs and ledgers. Set `SYNAPSE_HEADLESS_LIGHT_QUALIFICATION` to `matrix` or
`cancel_foreign`, and set `SYNAPSE_HEADLESS_LIGHT_SANDBOX` to the newly owned run
directory. Both `SYNAPSE_LOG_DIR` and `SYNAPSE_LOOP_LEDGER_DIR` must be inside it.
The runner writes `LIGHT_QUALIFICATION_SANDBOX.json` before launching:

```json
{
  "schema": "synapse.light.qualification-sandbox.v1",
  "disposable": true,
  "case": "matrix",
  "source_root": "<absolute path to this checkout>"
}
```

The tests check this marker, exact source origin, build, headless state, empty
stage and a new fixture ledger directory before editing. The matrix intentionally
corrupts and restores only its own disposable ledger bytes. It never repairs an
unknown production ledger or automatically removes an interrupted claim.

The pure checks are `tests/test_light_precommit.py`, `tests/test_light_capture.py`,
`tests/test_light_custody.py` and `tests/test_light_profile.py`. The ctypes resource
cache control runs on the qualified CPython 3.13 host; CPython 3.14 skips that
specific control because its cache interface changed.

## Cooperative deadline boundary

The absolute monotonic operation deadline is checked after durable forecast persistence, before each host mutation, and at the final transaction commit decision after callback persistence and ownership checks. An expired candidate is restored before deadline rejection is reported; unknown ownership still quarantines first. Calibration carries its experiment deadline into each provisional transaction too. These checks do not interrupt an in-flight filesystem or HOM call, and final cleanup/terminal receipt I/O may return after the deadline. They bound permission to dispatch or decide commit, not OS scheduling or hard real-time completion.

The headless backend's live dependency mapping includes the same source digest used by the gate. Post-callback dependency checks therefore quarantine source drift even when the callback rejects or raises. The gate also rechecks policy/custody after durable decision persistence and checks committed evidence before reporting acceptance. These are observed cooperative boundaries, not a cross-process checkout lock; coordinate source edits outside running host operations.

Certified dependencies and the original recipe instance/revision are captured before calibration or operation custody I/O and passed unchanged into each transaction. Calibration-plan and forecast persistence are followed by source/context/acknowledgement revalidation before dispatch. Provisional recovery rereads dependency and exact recipe metadata ownership before undo, before metadata synchronization and before releasing a restored scope. It accepts only the original record or this transaction's own saved record at the legitimate undo intermediate boundary. Fail-closed exception boundaries emit bounded operation/exception-class diagnostics; the existing ratchet baseline and panic containment remain unchanged.
