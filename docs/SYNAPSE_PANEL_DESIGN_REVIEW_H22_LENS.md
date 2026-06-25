# SYNAPSE Panel — Design Review (Houdini 22 Panel-Engineering Lens)

> Reviewer stance: a SideFX UI panel engineer working on Houdini 22, reviewing a
> third-party Python Panel's interaction + visual design as if it were an incoming
> PR. First-principles frame — a Python Panel is a **guest on Houdini's main
> thread**, must **read as native**, must **survive the host's lifecycle**, and
> must **defer to the host's own tools**.
>
> Companion document: `SYNAPSE_PANEL_CODEBASE_REVIEW_H22_LENS.md` (codebase
> review). The two cross-reference each other by section number (§).

---

## Verdict

The interaction model is more considered than most first-party Houdini panels and
should be kept. The critiques below are about **fit with the host**, not the
interaction logic: the panel doesn't read as native (and isn't, by
construction), it's hostile to docking, it taxes the idle main thread, and it
ships a dead affordance. None of that is taste — it's the four laws.

---

## 2.1 The "faces" model is genuinely good interaction design

Direct / Work, with the **same-pane law** (agent state never auto-switches the
visible tab; it drives a sub-state + the rail mark instead —
`synapse_panel.py:648-660`, `_set_work_substate`) is a real answer to a hard
problem: *how does an async agent show progress without yanking the artist's
context?* The rail's `MarkDot` collapsing identity + live state into one element
(`components.py:128`) is elegant, and the "ring → sweeping half-disc → full disc"
vocabulary is legible at a glance.

This exists *because* the slow path is off-thread (**→ Codebase §1.1**). Keep it.

## 2.2 It doesn't read as native — and isn't, by construction

SideFX ships `hou.qt.color()` and `hou.qt.styleSheet()` **specifically so panels
track the user's theme**. Houdini ships multiple color schemes; users regrade
them; the point is a panel pulls `PaneBorder`, `DRKBASE`, `BackColor` *at
runtime*.

This panel does the opposite: it **hardcodes the matched hex**
(`designsystem/tokens.py:47-56`, "Verified against `$HFS/.../UIDark.hcs`"). The
comment even says CRUCIBLE cross-checks against `hou.qt.color()` live "but the hex
stays source of truth." That's the inversion. The instant a user switches to a
lighter scheme or bumps UI gamma, the panel is a dark hole again — the exact bug
the redesign tried to kill, deferred to a different trigger. **→ Codebase §1.3:**
you built a beautiful token table; it should be *seeded from `hou.qt.color()` at
construction*, hardcoded values as headless fallback — not the reverse.

On top of that the panel **bundles its own typefaces** (Space Grotesk / Space
Mono, `fontload.py`) with letter-spacing tracking, a wordmark, a dual-accent
system (cool SIGNAL + warm coral), a gradient header, and a bouncing-toy loader.
Each is well-executed. Collectively they say *"web product,"* not *"Houdini
tool."* The concern isn't taste — **a tool panel that announces itself competes
with the work.** Houdini's own panels are deliberately quiet so the viewport is
the loud thing. SYNAPSE is the loudest pane on the desktop. Brand confidence is an
asset for a standalone app and a liability for a docked DCC panel.

## 2.3 Hostile to docking — min-heights stack

`PANEL_MIN_WIDTH = 280` is correctly narrow. But vertical minimums stack hard:
rail + ribbon + mode bar + faces (`setMinimumHeight(380)`, line 401) + the Direct
face's chat (`setMinimumHeight(380)`, line 360) + act bar + a `_user_h = 216`
default input (line 90). The Work face independently wants 380, and `FaceReview`'s
hero is 168 + verdict + credit + flags + gate + actions.

Against **Law 3**, panels live in docked columns sized by *the artist's layout*,
not the panel. A ~900px floor means the panel forces the column open or scrolls
its own chrome. The 216px default composer (3× the previous 72) is comfortable in
isolation, greedy in a stack. Cut the hard minimums ~in half and let faces
collapse gracefully — the panel should be usable at 400px tall, which is its own
declared `PANEL_MIN_HEIGHT`.

## 2.4 Idle main-thread tax

Three timers run forever on the main thread: 2s context poll (`hou` reads), 4s
health poll, 1s freeze beat. Even idle, the panel touches `hou` and repaints on a
fixed cadence. Individually trivial; the principle (**Law 1**) is that a *quiet*
panel should cost *nothing*. The better mechanism is already wired — the
V0-guarded selection callback (`_register_selection_cb`, line 1135). Lean on
event-driven updates; drop the 2s poll to a slow fallback (10–15s) so an idle
SYNAPSE is genuinely idle. **→ Codebase §1.5:** the 1s beat is the worst offender
and shouldn't live here at all.

## 2.5 Deferring to the host: right instinct, half-applied

`_on_open_render` (line 590) correctly refuses to reimplement the Render View and
feature-detects `hou.ui` rather than guessing the `paneTabOfType(IPRViewer)`
chain — exactly **Law 4 (defer to the host)** and phantom-API discipline working.
Good.

But it's a **clean no-op that does nothing visible** — the "⤢ open in render
view" verb (`face_review.py:212`) surfaces nothing live. Honest, but a dead
affordance reads as broken. Either wire the confirmed chain (verifiable the moment
the bridge is up — it's an OPEN ITEM in the ledger) or hide the verb until it's
real. Don't ship a visible control that no-ops.

Conversely, `RenderHero` painting a frame thumbnail in-panel (`face_review.py:97`)
is mild host-duplication — MPlay / the Render View *are* the image viewers. The
"real-frame-only, else hide and show the locator" rule (line 135) is a reasonable
compromise; just ensure the hero never becomes a second-rate image viewer the
artist has to distrust.

---

## Cross-reference map (design → codebase)

| Design finding | Codebase root | Law |
|---|---|---|
| §2.2 reads two-toned + non-native | §1.3 two token systems; hardcoded `.hcs` hex | Native fit |
| §2.4 idle main-thread tax (1s beat) | §1.5 panel is the process heartbeat | Main thread + lifecycle |
| §2.1 faces model works | §1.1 worker correctly off-thread | Main thread |
| §2.5 dead "open in render view" verb | §1.4 `except: pass` makes no-ops invisible | Defer to host |

---

## Prioritized punch list (design)

**Ship-blockers:**
1. **Seed tokens from `hou.qt.color()`** so the panel tracks the user's scheme/gamma. (§2.2 / Codebase §1.3)
2. **Halve the stacked min-heights**; usable at 400px tall. (§2.3)

**Should-fix:**
3. Move the 1s heartbeat off the panel; drop the 2s context poll to event-driven + slow fallback. (§2.4 / Codebase §1.5)
4. Either wire or hide "⤢ open in render view." (§2.5)

**Worth a conversation, not a fix:**
5. The brand intensity (bundled type, dual accent, gradient, toy). Good work; also the loudest pane on the desktop. Decide deliberately whether SYNAPSE is a *Houdini tool* (quiet down) or a *platform that lives in Houdini* (keep it). It's currently defaulting to the latter without having chosen.

The interaction model (§2.1) and the worker isolation (Codebase §1.1) are the
parts to least want touched.
