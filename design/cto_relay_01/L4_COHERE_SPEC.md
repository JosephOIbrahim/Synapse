# L4 — PANEL SKIN · the Cohere spec

**Consumed by** `panel-design-warden` · **Governs** `python/synapse/panel/tokens.py`,
`panel/styles.py`, `panel/designsystem/tokens.py`
**Amendment A1 applies:** the panel is two surfaces — **Direct** and **Work**. Review is cut.
**Visual reference:** `design/cto_relay_01/panel_L4_v2.html`

---

## 0 · BLOCKER — resolve before any palette work

`panel/tokens.py` and `panel/designsystem/tokens.py` define **the same token names with
different values**. `styles.py` is the only file importing both, and it mixes them:

| Token | `panel/tokens.py` | `designsystem/tokens.py` |
|---|---|---|
| `SIGNAL` | `#00D4FF` cyan | `#8FB3D9` muted blue |
| `VOID` | `#252525` | `#0A0A0A` |
| `NEAR_BLACK` | `#3A3A3A` | `#111111` |
| `CARBON` | `#333333` | `#1A1A1A` |
| `GRAPHITE` | `#222222` | `#2A2A2A` |
| `SLATE` | `#888888` | `#555555` |
| `SILVER` | `#AAAAAA` | `#999999` |

**Measured on master:** `t.SIGNAL` (cyan) at **11 sites**, `_ds.SIGNAL` (blue) at **20 sites**.

The Mile 7 "de-cyan" fix was applied at call sites, not at the token source — its own comment
says *token sources stay untouched (local fix)*. It converted 20 and left 11. **The panel ships
two different accent colours today.**

A palette pass on top of an unresolved collision produces a third state, not a fix.
**Finish the migration first:** convert the remaining 11 `t.SIGNAL` sites, then make
`panel/tokens.py` re-export from `designsystem/tokens.py` rather than redeclare. One authority.

**Second collision, same file:** `tokens.py:59` sets `SIZE_HERO = 44`; `tokens.py:83` sets
`SIZE_BODY, SIZE_TITLE, SIZE_HERO = 12, 15, 19`. Establish which branch is live before touching
the type scale.

---

## 1 · The title — rule 01

**Site:** `synapse_panel.py:400` — `word = c.label("SYNAPSE", role="body")`

The wordmark inherits whatever `role="body"` carries. It needs its own role.

| | Now | After |
|---|---|---|
| weight | inherited from `body` | **400** |
| tracking | 1px (`styles.py:62`) | **4px** |
| family | `FONT_SANS` | unchanged |
| size | `SIZE_HERO` (44 or 19 — see blocker) | unchanged |

Add `role="wordmark"` rather than special-casing at the call site. Cohere's wordmark carries
identity through **form**, never weight. Anything at 500+ reads as an application announcing
itself.

**Oracle:** `grep -n 'font-weight:\s*[5-9]00\|setBold(True)'` on the wordmark path → 0 hits.
`chat_display.py:311` carries `font-weight:700` — confirm whether that is the wordmark or a
sender label before touching it.

---

## 2 · Palette — natural against synthetic

Cohere pairs natural tones (coniferous green, mushroom grey, volcanic black) with synthetic
hues (simulated coral, synthetic quartz, acrylic blue). `SIGNAL` and `WARM` already sit on the
synthetic side. **The natural side is what's missing.**

Add to `designsystem/tokens.py` — new names, no collisions:

```python
MUSHROOM   = "#7C756D"   # inert metadata, node paths, non-semantic labels
CONIFEROUS = "#6E8F72"   # verified / ok  — replaces OK_SOFT #6FBF8E at panel call sites
```

`#6FBF8E` reads synthetic-mint against a warm coral. `#6E8F72` is the natural counterweight
Cohere's structure calls for.

**Unchanged and non-negotiable:** the Houdini `UIDark.hcs` greys are the host constraint.
`SIGNAL #8FB3D9` (acrylic) and `WARM #FF7759` (coral) stay exactly as they are.

**Ceiling: two accents per view.** The render is the only chromatic event.

---

## 3 · Type — rule 04, widest blast radius

Shipping faces are `FONT_SANS = "DM Sans"` and `FONT_MONO = "JetBrains Mono"`. The comp uses
Space Grotesk / Space Mono. **Do not change the shipping faces in this leg** — that is a
separate ruling. The rule is about *distribution*, not family:

> **Mono is for code. Sans is for everything else.**

Mono retreats to exactly four content classes:

- node and prim paths — `/materials/AMD/link_type_1`
- tool and node type names — `materiallinker`, `karma_xpu`
- versions and build strings — `22.0.368`
- counts and costs — `18.0k`, `$0.06`

Every label, every status line, every verdict, every button becomes `FONT_SANS`. Current
`styles.py` spends mono on labels, which flattens hierarchy into one texture — that single
change does more for the panel than the palette does.

**Oracle:** count `FONT_MONO` references in `styles.py` before and after. It must fall.

---

## 4 · Cells, not boxes — rule 02

The Voronoi is not decoration. **A Voronoi cell is a seed's region of influence** — which is
exactly what a render bucket is, and what a node's downstream reach is. The panel draws the
topology it already operates on.

Three sites, in priority order:

1. **The cook grid** (`Work` surface) — a true Voronoi tessellation, seeded on a jittered grid,
   half-plane clipped, filling on a diagonal front the way a bucket renderer advances.
   This is the signature. Reference implementation in the HTML, ~30 lines.
2. **The mark** — three cells at differing expansion, resolving to an abstract form. Cohere's
   symbol logic. Already drawn in the reference as SVG paths.
3. **Node chips** — `clip-path` cells rather than rounded rectangles. Qt equivalent:
   `QPainterPath` with a 4-point polygon, 2–3px asymmetric offsets.

If Qt cannot carry (1) at acceptable cook-time cost, ship (2) and (3) and log (1) as debt.
**Do not fake it with a uniform grid** — a regular grid is the thing being replaced.

---

## 5 · Icons — rule 03

Monolinear, one weight, 24px grid, no fills, no dual-tone. Replaces the dot-and-square status
vocabulary. Stroke width 1.25 at 15px render size. Three needed to start: check (coniferous),
warning triangle (coral), node hexagon (acrylic).

## 6 · Atmosphere — rule 05

Texture enters as a low-contrast radial field behind content, never as borders or fills.
Hairlines hold at 0.5px. Qt: a `QLinearGradient`/`QRadialGradient` on the panel background at
≤6% alpha. If it is visible as a gradient, it is too strong.

---

## 7 · Definition of done

```
[ ] 11 t.SIGNAL sites converted; panel/tokens.py re-exports from designsystem
[ ] SIZE_HERO branch resolved — one value, documented
[ ] role="wordmark" exists; weight 400, tracking 4px
[ ] grep font-weight:[5-9]00 on wordmark path -> 0
[ ] MUSHROOM + CONIFEROUS added; OK_SOFT call sites migrated
[ ] FONT_MONO reference count in styles.py strictly down
[ ] Review tab, Accept, Revert removed — not restyled
[ ] every token name present before is present after (assert, do not eyeball)
[ ] pytest -k panel -> 0 failed
[ ] no import of routing/ or server/ added to panel/
```
