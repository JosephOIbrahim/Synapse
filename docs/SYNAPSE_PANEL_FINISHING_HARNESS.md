# SYNAPSE · PANEL FINISHING HARNESS — v1

> **ARCHITECT dispatch. Design only — no mutation in this document.**
> Commit this file *first* (F3 / provenance-first), then run FORGE → CRUCIBLE.
> **This SUPERSEDES `SYNAPSE_PANEL_HARNESS_v9.md`** (the 7-spike harness), which is **dead** — a diff against live source proved it would rebuild already-shipped code.

---

## GROUNDING

Written against the actual panel source, read **2026-06-14**, runtime **H21.0.671 / Python 3.11**, HEAD **`86ef9bc`** (1 commit past the `v5.14.0` tag). Branch from HEAD.

Seven files diffed against the v9 comp. **The panel is ~95% the v9 design already** — two faces with Review folded into Work's `done` sub-state, same-pane law enforced in code, the full type pass (`TRACKING_EM` scale applied via `setLetterSpacing(AbsoluteSpacing, em×px)`), `UIDark.hcs`-tuned tokens (`SIGNAL #8FB3D9`, `WARM #FF7759`), rail with `MarkDot` + BRAND-tracked wordmark + display-only author token + activity meter + state-gated Stop, the signed-decision Review (display-only `SIGNED`, DECISION-leads credit, BL-007/008, embedded gate, accept/revert/commit-raises-a-gate), reduced-motion, graceful degradation.

This is the **anchor leg of the panel track**: the panel is already running. Three short hurdles, then the baton goes to the gates. No re-layout.

---

## RESOLVED GATE (do not re-litigate)

**`RenderHero` fate — RATIFIED by owner.**
Real frame on disk → keep the thumbnail (an honest walk-away payoff). **No real frame → drop the decorative gradient+shards placeholder**; show a compact `⤢ open in render view` locator + frame/AOV/path metadata instead. This honors the v9 thesis — *the render is Houdini's job* — without going hollow when a real frame exists.

---

## INVARIANTS (CRUCIBLE guards — never violated, fix-forward only)

1. **Same-pane law.** No new top-level tab switch. `open_render_requested` must **not** switch faces and must **not** spawn a pane — zero `createFloatingPanel` / `createTab` stays zero (snapshot item 24). It surfaces Houdini's *existing* render view only.
2. **SIGNED / commit stay display-only.** No `customData:synapse:signed_by`, no USD authoring — **Michael Gold RFC zone**. `set_signed` and COMMIT-raises-a-gate semantics unchanged.
3. **Zero new hard `hou` deps.** `_on_open_render` is feature-detected and **phantom-API-gated** (see D1); it no-ops headless and on any unconfirmed API. `cognitive.tools.*` untouched.
4. **Graceful degradation preserved.** Every widget still instantiates when a dependency is absent (the `if X is not None` contract).
5. **Reduced-motion preserved.** No new always-on animation.
6. **No token-value changes.** Only a stale *comment* is corrected. `SIGNAL` stays `#8FB3D9`, the 9–20 scale and `TRACKING_EM` unchanged.

**Recorded, no code (decisions ratified):**
- Native-font inheritance (`apply_font_role` inherits Houdini's UI font; `tracked_font` forces the bundled families) is **intentional — kept**. It reads native.
- The rail meter is an **activity** meter, not cost — **kept**. Token/$ accounting is a future wire-up to the worker's usage, **out of scope** here.
- The author token renders the live worker model (`_author_token` [synapse_panel.py:474]) — correct as-is.

---

## D-GATE (FORGE must halt-and-surface, never default)

**D1 — render-view API on H21.0.671.** Surfacing Houdini's render view requires a `hou.*` call. **Phantom-API discipline applies:** confirm the exact API against the live symbol table (`dir()` introspection / the committed `h21_symbol_table.json`) **before** writing it. If the render-view/mplay API cannot be confirmed on H21.0.671, **halt and surface** — ship `_on_open_render` as a clean no-op and flag the open item. Do **not** guess a phantom (`hou.ui` pane plumbing is exactly where phantoms hide).

---

## THE WORK — three hurdles

### Hurdle 1 — `RenderHero`: real-frame-only, drop the placeholder
**File:** `python/synapse/panel/face_review.py`

1. **Strip the decorative placeholder.** Remove `_paint_placeholder` and `_shard` [face_review.py:155–183] and the `_HERO_BG0/1/2` constants [:43]. In `paintEvent` [:138–153] keep **only** the real-pixmap branch [:142–147] + the vignette/meta; when `self._pix is None`, paint nothing (the widget hides — see step 3).
2. **Add the signal.** `open_render_requested = Signal()` alongside `accepted/reverted/committed` [face_review.py:205–207].
3. **No-frame → locator, not 168px of decoration.** When no real frame is in hand, **hide** `RenderHero` (height→0 / `setVisible(False)`) and show a compact locator row beneath the verdict: the frame/AOV/path metadata (the `meta` string already fed via `set_render(path, meta)` → `_hero.set_meta` [:289–292, :134]) **plus** a `⤢ open in render view` verb (reuse `_verb(...)` [:88–98], emits `open_render_requested`). When a real on-disk frame *is* present → show the thumbnail, hide the locator.
4. **Route `set_render`** [:289–292] to the visible/hidden swap: real file at `path` → hero visible, locator hidden; else → hero hidden, locator visible with `meta`.

**Wire it** in `python/synapse/panel/synapse_panel.py` `_build_done_substate`, alongside the existing three connections [synapse_panel.py:447–449]:
```
self._review_face.open_render_requested.connect(self._on_open_render)
```
Add `_on_open_render(self)` — **feature-detected + D1-gated**: best-effort surface of Houdini's existing render view; **no-op** headless or on unconfirmed API. Never switches a face, never spawns a pane.

### Hurdle 2 — rail ⌘K affordance
**File:** `python/synapse/panel/synapse_panel.py` `_build_rail` [:256–320]

The palette is already wired (`QShortcut` + `command_palette`); only the visible hint is missing. Add a quiet mono hint label on **line 1**, right of `self._header_status`, before the `⋯` overflow [:287–288]. Style: `tracked_font("LABEL_SM", t.SIZE_MICRO)`, `TEXT_TERTIARY`. **Render the platform-correct modifier from the actual bound `QKeySequence`** (`⌘K` on `darwin`, `Ctrl K` elsewhere) — the hint must never lie about the key. Must not crowd the meter (`self._observe` keeps its stretch); CRUCIBLE/G3 checks spacing.

### Hurdle 3 — `tokens.py` stale comment
**File:** `python/synapse/panel/designsystem/tokens.py` [:78–80]

The WCAG note reads `SIGNAL (#00D4FF)` — a stale paste from the retired cyan token. `SIGNAL` is `#8FB3D9`. Correct the hex in the comment and let **G3's** contrast matrix be the source of truth on the AA claim. Comment only — no behavior change.

---

## VERIFICATION — all three gates required (per-spike discipline)

**G1 — smoke (headless / standalone interpreter, vendored deps).**
Imports clean; `FaceReview` + `SynapsePanel` instantiate with no QApplication crash; `RenderHero` with no frame paints **no shards**; `open_render_requested` exists and emits; `_on_open_render` no-ops safely with no `hou`; `bl007_flag` / `detect_render_flags` unchanged; graceful-degradation paths hold when optional deps are absent.

**G2 — live H21.0.671 (graphical).**
Panel loads via `synapse_panel.pypanel`; **tab switch is pill-only** (agent state never switches the tab); **Stop** shows only while working; **Review done-state** — real frame → thumbnail; no frame → locator + `⤢`, **no gradient/shards**; `⤢ open in render view` surfaces the render view *or* no-ops cleanly (D1); **⌘K/Ctrl-K hint visible** and the palette opens; reduced-motion honored.

**G3 — `audit_panel.py --strict`.**
WCAG contrast matrix (now honest about `#8FB3D9`), type-scale floor (9–20 + tracking roles), widget-tree walk. All three sub-gates green.

---

## COMMIT / PUSH DISCIPLINE (F3 · atomic · race-safe)

1. **Commit this harness first** — `docs(harness): panel finishing pass v1 — ARCHITECT dispatch`.
2. Per-hurdle atomic commits:
   - `fix(panel): RenderHero — real-frame thumbnail only, drop decorative placeholder (v9)`
   - `feat(panel): rail ⌘K affordance, platform-correct`
   - `docs(tokens): correct stale SIGNAL hex in WCAG note`
3. Race-safe push: **fetch + rebase, max 3 attempts, halt on merge conflict.**

---

## MILE MARKER

- **WHERE WE ARE:** Panel diffed 7/7 against the v9 comp — already ~95% built. `RenderHero` decision **ratified**. Finishing pass = 3 small changes + 3 gates.
- **MILE MARKER:** Anchor leg of the panel track. Baton hand-off from build → verification.
- **BLOCKERS:** **D1** — render-view `hou` API must be confirmed on H21.0.671 before writing; halt-and-surface if not (no-op + flag).
- **NEXT ACTION:** ARCHITECT dispatch committed → FORGE Hurdle 1 → 2 → 3 (atomic) → CRUCIBLE G1/G2/G3. Then the real remaining engineering is the **hardening track** (`SYNAPSE_3xs_HARDENING_HARNESS.md`), not the panel.
