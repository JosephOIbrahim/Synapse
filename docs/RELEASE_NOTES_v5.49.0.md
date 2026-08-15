# v5.49.0 — five tools take the stage, and the probe finally answers

*The Solaris compose trio and TOPS pause/resume graduate from WS-only handlers to first-class MCP tools, and the F5a render-offload probe — blocked twice by its own scene-build — now delivers all-PASS ground truth on 22.0.400/Indie. Two PRs (#77, #78), workflow-recon'd, adversarially verified, ultrareviewed.*

---

## What you get, plainly

Five tools that previously only existed on the live WebSocket path are now callable as MCP tools with full annotations: `synapse_solaris_shotsetup_karma_xpu` (scaffold a render-ready Karma shot), `synapse_matlib_bind` (bind USD materials), `synapse_assess_render_ready` (read-only readiness report), and `tops_pause_cook` / `tops_resume_cook`. Registry: **124 → 129 tools**.

And three questions that gated any future render-offload design now have measured answers instead of contested memory.

## The promotion (PR #77)

The compose trio's panel aliases were forward-staged in #76; this release makes them registry-live with every classification carried over intact: shotsetup keeps its R4 `touches_disk` → APPROVE elevation, `assess_render_ready` is read-only at BOTH the transport and bridge layers, and all five carry group DISPATCH_KEYS. Pinned by `tests/test_parity_promotions.py` so a registry edit cannot silently un-promote them.

## The probe repair (PR #78)

The F5a probe's first run blanked on `light.parm("intensity")` — H22 Solaris lights punycode-encode `inputs:*` parm names (`xn__inputsintensity_i0a`). Fixing that surfaced a second trap: `usdrender_rop` is invalid in `/out` — the ROP-category husk driver on 22.0.400 is **`usdrender`**; `usdrender_rop` is the LOP-context name (identical parm truth). A third run, attacked by an adversarial workflow pass, caught the probe's hand-authored USDA lacking `orderedVars` (husk refused it before any delegate work) plus a phantom-class miss: `hou.licenseCategoryType()` is the enum TYPE and raises — `hou.licenseCategory()` is the query. All repaired; the per-variant USDA is now flatten-exported from the probe's own karmarendersettings-authored stage.

## Ground truth established (F5a, all four items PASS)

| Question | Answer (22.0.400 / Indie, live) | Producer |
|---|---|---|
| Does husk load the Karma delegate headless? | **YES, with AND without `--indie`** — exit 0, pixels on disk, ~1.9s, empty stderr. The 2026-07-17 flag theory does not reproduce; NO SPLIT. | `harness/notes/probe_render_offload.results.20260815T123824Z.json`, item (a) |
| What does `node.render()` do with `soho_foreground=0`? | **BLOCKS_UNTIL_PIXELS** — 1.84s return ≈ husk wall time; background mode is NOT async dispatch on this build. | same, item (b) |
| What signal marks "pixels on disk"? | **`husk_postframe` sentinel, +0.006s after the EXR lands** — pixel-accurate; file-exists poll acceptable only while render() stays synchronous. | same, item (c) |

F5b design and the F1 flag decision remain human-gated — but they now gate on measurement, not contested memory.

## Numbers, with producers

| Figure | Producer |
|---|---|
| 129 MCP tools registered | `len(TOOL_DEFS)`, live-verified this release; banner bound by `tests/test_phase0c_doc1_toolcount.py` |
| 41 transport read-only / 37 bridge read-only | live set counts, pinned by `tests/test_f6_hygiene.py` + `tests/test_parity_promotions.py` |
| 6,305 passed · 1 failed (pre-existing) · 170 skipped | local `python -m pytest tests/ -q` @ `934eaba2`; the `test_backfill` failure is pre-existing (Py 3.14 vendored ABI, disclosed since v5.48.0) |

## Known limitations

- The CHANGELOG deep record still ends at v5.41.0 — v5.42.0 through v5.49.0 live in their release commits and `docs/RELEASE_NOTES_*` files; backfill is queued housekeeping.
- Leg (b)'s synchrony verdict is one trivial frame on one build; a long-render control would make it airtight. The claim is scoped accordingly.

---

## Post-release verification (2026-08-15T12:45Z)

The F5a ground truth was **independently reproduced by hand** minutes after release — Joe's own PowerShell run of the probe, all four items PASS, every delta vs the committed baseline within timing noise (husk 2.09/2.03s exit 0 + pixels both variants, `render()` blocks 2.19s, sentinel +0.005s). Receipt: `harness/notes/probe_render_offload.results.20260815T124545Z.json` (master `9680a69e`).
