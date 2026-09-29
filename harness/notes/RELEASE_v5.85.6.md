# Release preparation: v5.85.6

Publish six commits on top of v5.85.5 (`894ddb41`), plus the release commit.
Joe's word: "Push plus v5.85.6. Six commits are unpushed", and "Yes to ReADMe"
for the README line (2026-09-29).

| Commit | What it does |
|---|---|
| `9d11dd0f` | Tests: pins the battleplan mission_schema so a shared pytest process stays green (BP12 item 11) |
| `9dbdf106` | Tests: the README receipt checks the two-orange page and runs in the suite (item 17) |
| `2951f96e` | Tests: renames the pin helper to `jev_bp_schema_pin.py`; the first name collided with a `tests/` module |
| `c8242139` | Memory: a flusher append can no longer land on a file `save()` replaced (item 21) |
| `5311b2f9` | Memory: untitled-scene notes follow the launch session's folder (item 18) |
| `daf51459` | Memory: `embedder_backend` in the status report, docstring corrected (item 19) |

The release commit also removes the first-save row from the README's stuck
table, since v5.85.4 fixed it.

## Evidence

- **Tests.** Full bare `pytest -m "not needs_houdini"` before the release commit:
  10,278 passed, 457 skipped, 119 deselected, 5 xfailed, 2 xpassed, 0 failed.
- **Ratchet.** Broad 1366, silent 987, unchanged.
- **Advice.** Fable 5.1 reviewed the embedder design before commit and caught a
  model load inside a health read. It was overloaded for the final review.
  Jev was not used.
- **Known, not fixed.** BP12 items 2 to 8 and 12; item 10 is on hold.

This record does not claim that the later CI, push or publication steps have
completed. They are checked after publication.
