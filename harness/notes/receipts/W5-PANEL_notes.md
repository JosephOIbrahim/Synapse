# W5-PANEL — panel UX truth (font floor · chat leading · token tab)

Wave 5, branch `wave5/panel`. Fix work for Joe's live-seat observations 2026-08-16
(items 2–5 of `harness/notes/h22/panel-observations-2026-08-16.md`). Three targets;
all built in the small panel modules — **`synapse_panel.py` was never touched**
(it is peer-claimed by W5-ROPE and W5-LIFE; the bus claim is disjoint from theirs).

Every Qt-dependent claim below was proven under **hython Houdini 22.0.400** (real
PySide6, Python 3.13.10, `QT_QPA_PLATFORM=offscreen`), not just headless-skipped.

---

## What shipped

**Target 2 — chat leading (+0.75pt).** `chat_display.py::_apply_leading` merges an
**absolute** `QTextBlockFormat` `LineDistanceHeight` onto every just-inserted block
(user / synapse / system, sync + async paths). Absolute leading is the one
line-spacing mechanism this QTextDocument honours — CSS `line-height` and
`ProportionalHeight` were both measured inert here (`message_formatter.py:43`). The
token is `CHAT_LEADING_PT = 0.75` → `chat_leading_px()` = 0.75·96/72 = **1.0px/line**
at Qt's 96-DPI logical default. Proven effective: a 12-line block grew document
height 176→188 (Δ = 1.0px × 12 lines); stripping the format shrinks it back.

**Target 3 — Token tab per-task spend.** New pure sink `usage_sink.py` folds
`provider.last_usage` (the four real Anthropic usage fields) across the worker's
whole tool loop (`claude_worker._conversation_loop`: `begin_task` at loop top,
`add()` after each `stream()`), defeating the per-`stream()` reset so the total is
**per-task**, not per-call. `face_token.FaceToken._refresh_usage` (called by the
already-wired tab-open `refresh_from_probe`) lands **CACHE prefix ← cache_read**,
**CACHE last-turn ← cache_creation**, **ENGINE model ← the selected model that
spent**. Every number traces to a receipt (`provider.last_usage`, pinned by
`tests/test_provider_cache_and_usage.py`). Unmeasurable → UNKNOWN: a non-Anthropic
engine reports no usage (`base.py:42`) so its spend stays UNKNOWN, `bool` is never a
count, a genuinely API-reported `0` is kept while never-measured stays `None`.

**Target 1 — font floor (MATH only; live wiring handed off).** Pure helpers in
`designsystem/tokens.py`: `host_floored_steps(host_scale)` and
`next_font_scale(current, host_scale)` build/cycle a ladder whose **floor is the
host default** and every step is ≥ it — proven (8 tests) that no scale below the
floor is reachable for any host. The live switcher is **not** rewired because it
lives in the off-limits `synapse_panel.py`. See the handoff below.

---

## FOR RULING — wiring the host-floored ladder into the live switcher

`synapse_panel.py` is peer-claimed; this leg cannot edit it. The math is ready; a
one-line change at **two** call sites closes the live acceptance. The crucible pass
caught that there are TWO below-floor entry points, not one:

1. **`_cycle_font_scale` (synapse_panel.py ~2089-2099)** — replace the raw-ladder
   cycle body with:
   ```python
   cur = getattr(self, "_font_scale", t.FONT_SCALE_DEFAULT)
   self._set_scale(t.next_font_scale(cur, getattr(self, "_chrome_scale", t.FONT_SCALE_DEFAULT)))
   ```
   `_chrome_scale` is the correct floor source — the frozen host baseline seeded at
   `synapse_panel.py:331` (== `_host_font_scale()` at seed), cheaper than a live Qt
   read. Verified this keeps `tests/panel/test_font_scale.py::test_aa_cycle_steps_above_a_host_base_scale`
   green (headless `_chrome_scale`==1.0 → `next_font_scale(1.33, 1.0)`==1.4, >1.33 and
   ∈ FONT_SCALE_STEPS).

2. **"Larger text" menu action (synapse_panel.py:1948)** — currently
   `menu.addAction("Larger text", lambda: self._set_scale(1.15))` sets 1.15
   unconditionally, which is BELOW the floor on any host whose UI font > ~13.8px
   (host_scale > 1.15, e.g. a 15px host = 1.25). Route it through the floor too:
   ```python
   menu.addAction("Larger text",
                  lambda: self._set_scale(t.next_font_scale(self._font_scale, self._chrome_scale)))
   ```
   "Default text" (synapse_panel.py:1949 → `_set_scale(self._chrome_scale)`) is
   already floor-correct — leave it.

Fixing only #1 leaves #2 reachable below the floor. Close both.

---

## Known limitations (bounded, honest)

- **Font-floor LIVE acceptance is not met by this leg** — the running panel's
  switcher still reaches below-floor states until the ruling above lands. Marked
  UNKNOWN in the receipt, not PASS; PASS would launder an unshipped fix.
- **Legacy `chat_panel.py`** (the alternate panel under `synapse_chat.pypanel`,
  NOT on the hpath, not the panel Houdini loads) still cycles the raw ladder and
  hardcodes reading sizes 11/14/18 (`chat_panel.py:474-487`). Pre-existing, out of
  this leg's scope; noted so a future ruling can floor it too if that surface is
  ever revived.
- **Token tab, non-spend rows unchanged** — the THIS-TURN composition still shows
  `system prompt` / `tool surface` as char-derived estimates (~6% low, disclosed in
  the footnote, `measure_static`), and `cost` still comes from the probe (an honest
  measured `0.0` for a free local model, UNKNOWN for a metered one with no price).
  Neither is faked from the usage receipt; both are pre-existing and untouched.
- **ENGINE cross-engine row** — `model` now comes from the last task's real spend
  while `runs`/`cost`/`probed` come from the first available probe. In the common
  single-engine case they agree; only under cross-engine use can they name different
  engines. Cache rows + model row stay mutually consistent (one snapshot).
- **`USAGE_SINK` is a process-wide singleton**, lock-guarded; correct for the panel's
  one-conversation-at-a-time model. A mid-task tab-open reads a partial-but-honest
  running total.
- **Streamed tokens** render un-led during streaming; `end_stream` re-appends the
  finalized reply through the led path, so the persistent message carries the
  leading (the un-led state is a transient preview only).
- **Leading magnitude** is 1px/line at 96-DPI logical; its perceptibility on
  high-DPI seats was not measured (see spawn proposal in the receipt).
