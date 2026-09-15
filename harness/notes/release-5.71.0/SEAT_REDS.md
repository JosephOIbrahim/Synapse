# Seat-suite reds — measured, named, and diffed (2026-09-15)

Until now the release record carried only a **count** ("5 failed, 201 passed"), never the test
names. That made the recurring claim *"none is new"* unverifiable: two releases could each have
five completely different reds and both print it truthfully. These are the names.

Method: the v5.70.1 baseline was re-measured by checking that tag out in a detached worktree and
running the same command the release runs, with the same pinned hython
(`C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe`). It reproduced
`5 failed, 201 passed` exactly — matching what v5.70.1 recorded, which validates the method.

## v5.70.1 — the five known reds

    tests/panel/test_bc_wave.py::test_chat_face_monochrome_one_accent_plus_state_marks
    tests/panel/test_bc_wave.py::test_profile_row_retired
    tests/panel/test_failure_trail.py::test_dead_verb_hidden
    tests/panel/test_j1_token_liveness.py::test_connected_keyed_engine_is_live_then_working_then_live
    tests/panel/test_j2_token_face.py::test_face_counts_an_ollama_task

## v5.71.0 — six. One new, none fixed.

    ** NEW ** tests/panel/test_doctor_button.py::test_transport_discovers_only_the_running_owner_and_tracks_reconnection

## Diagnosis of the new red

Introduced by `1d982426` (#85, the farm PR) — the only commit since v5.70.1 that touches
`python/synapse/panel/tool_executor.py`. The test file itself was never modified, so the test did
not move; the behaviour did.

`_MCPLocalClient.available` changed contract:

    before:  port = self._detect_port()
             if port != self._port: self._session_id = None; self._port = port
             return port is not None            # losing discovery clears the port

    after:   if port is not None and port != self._port: ...
             return self._port is not None      # losing discovery KEEPS the cached port

The change is deliberate and documented in its own docstring: *"Losing discovery alone keeps the
cached port: only a failed request on it (see `_post`) invalidates it, so no HOM probe is ever
needed."* Avoiding an off-thread HOM probe is a real concern here — see the marshal-deadlock class.

The test pins the older, stricter contract: after a successful detection, an owner that stops
reporting a valid port must make `available` go False.

## Blast radius — measured, not assumed

`available` is read in exactly one place: `tool_executor.py:772`, a pre-check before `call_tool`.
Nothing renders it; there is no connection indicator behind it.

- old: endpoint disappears -> `available` False -> immediate fallback, no request sent
- new: endpoint disappears -> cached port kept -> one request attempted -> fails ->
  `MCPUnavailable` -> same fallback, and `_post` invalidates the port so later calls fall back at once

Net artist-visible cost: one wasted round-trip on an error path, self-healing. No wrong result,
no false "connected" state.

## Open ruling — this is a design call, not a defect

Either the new resilience contract is right and the test must be superseded, or the strict
contract is right and #85's change must be narrowed. Both readings are defensible. Not decided here.
