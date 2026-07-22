<!-- Implementation contract for M10 Solaris section boxes, produced 2026-07-21
by the netbox-design workflow (10 agents: 1 live-API ground, 3 design lenses +
1 judge, 4 adversarial attacks, 1 synthesis; 0 errors, 940K subagent tokens).

WHAT SHIPPED vs THIS CONTRACT: the shipped feature (handler_helpers.py
_compute_section_bands / _bands_are_rank_monotonic / _apply_section_boxes) took
the design JUDGE's 3-band scheme (SCENE/LIGHTING/RENDER) rather than this
synthesis agent's 6-tier variant -- the judge's minimalist reasoning ("a box the
eye does not need is noise") is the better default for scannability. But it
ADOPTED this contract's load-bearing safety insight verbatim: the layout is
DEPTH-keyed not RANK-keyed, so rank bands are only safe on a rank-monotonic
layout. Hence the unconditional-sweep-first + monotonicity gate + suppress. That
insight came from the adversarial phase (2 blockers) and is the reason the
feature is correct on arbitrary DAGs, not just rank-ordered chains. -->

Contract grounded in the live code. Verified anchors: `handler_helpers.py` holds the pure/`hou`-wrapper layout pair (`_compute_dag_positions` L517 pure, `_layout_dag_vertical` L649 wrapper); rank SSOT is `handlers_solaris_assemble._get_sort_key` L185 / `_SOLARIS_NODE_ORDER` L24 / `_UNRANKED_RANK=690` L134 / `_is_unranked` L194; wire target is `handlers_solaris_graph._handle_solaris_build_graph._on_main`, step 6 display-flag block at L644–649 inside `with hou.undos.group("SYNAPSE: build_graph")` (L563). The layout engine keys Y off longest-path **DAG depth** (`_compute_dag_positions` L554–558), NOT rank — this is why both blocker attacks land and why the monotonicity gate below is mandatory, not optional.

---

# IMPLEMENTATION CONTRACT — Tier-Faithful Network-Box Sectioning

**File:** `python/synapse/server/handler_helpers.py` (pure core + `hou` wrapper) · wired into `python/synapse/server/handlers_solaris_graph.py`
**Target:** H22.0.368 · every `hou` call below is copied from the VERIFIED API — no phantom emitted.
**Non-negotiable:** the layout engine positions by DAG depth, not rank. Rank-band boxes are only safe on a rank-monotonic layout. Every draw is gated by a monotonicity precondition AND a post-fit measured overlap self-destruct. There is NO "structural non-overlap" assumption anywhere in the code.

---

## 1. Signatures to add to `handler_helpers.py`

Add near the layout helpers (after `_layout_dag_vertical`, ~L682). Module constants first:

```python
# ── Tier-box sectioning ────────────────────────────────────────────────
_TIER_BOX_PREFIX   = "SYNAPSE_TIER_"      # reserved namespace; artist boxes never use it
_TIER_LEGEND_NAME  = "synapse_tier__legend"
_TIER_UNRANKED_RANK = 690                 # MUST equal handlers_solaris_assemble._UNRANKED_RANK (pinned by test)
MIN_TOTAL_NODES = 12                      # grafted floor: 6-tier scheme needs mass before boxes earn chrome
MIN_TIER_NODES  = 2                       # a box around a lone node is noise
_OVERLAP_EPS    = 1e-4                    # positive-area threshold for the live self-destruct gate

# (id, lo, hi, rgb, label_template)  — bands are HALF-OPEN [lo, hi); None = unbounded end.
_TIER_SPECS = (
    ("SCENE",     None, 200,  (0.30, 0.43, 0.31), "SCENE · geometry & imports · %d nodes"),
    ("MATERIALS", 200,  270,  (0.24, 0.41, 0.45), "MATERIALS · shading · %d nodes"),
    ("LAYOUT",    270,  400,  (0.37, 0.31, 0.47), "LAYOUT · collections · xforms · instancing · %d nodes"),
    ("LIGHTS",    400,  690,  (0.50, 0.43, 0.22), "LIGHTS · camera + lights · %d nodes"),
    ("RENDER",    700,  900,  (0.25, 0.35, 0.51), "RENDER · settings + ROP · %d nodes"),
    ("OUTPUT",    900,  None, (0.45, 0.31, 0.29), "OUTPUT · USD export · %d nodes"),
)
_TIER_INDEX = {spec[0]: i for i, spec in enumerate(_TIER_SPECS)}  # SCENE=0 … OUTPUT=5


def _compute_tier_boxes(
    ranked: "Dict[str, Tuple[int, float, float]]",
    *,
    min_total: int = MIN_TOTAL_NODES,
    min_tier: int = MIN_TIER_NODES,
    output_singleton: bool = False,
    unranked_rank: int = _TIER_UNRANKED_RANK,
) -> "Dict[str, Any]":
    """PURE. No hou. ranked = {node_id: (rank, x, y)}. Returns a plan dict:
       {"draw": bool, "skip_reason": str|None, "boxes": [ {id,name,label,rgb,members:[ids]} ],
        "unranked": [ids], "warnings": [str]}.
       A node whose rank == unranked_rank (or lands in no band) is NEVER boxed."""


def _draw_tier_boxes(
    parent_node,
    id_to_hou: "Dict[str, Any]",
    *,
    draw_legend: bool = False,
    output_singleton: bool = False,
) -> "Dict[str, Any]":
    """hou-facing wrapper. Assumes the CALLER already holds an open
       hou.undos.group (build_graph does). Reads live rank+position, calls the
       pure core, then reconciles boxes (unconditional sweep FIRST, gated create,
       measured self-destruct). Best-effort: never raises on a box failure.
       Returns the plan dict, possibly downgraded to draw=False by the live gate."""
```

Mirrors the existing `_compute_dag_positions` (pure) / `_layout_dag_vertical` (wrapper) split exactly.

---

## 2. Grouping algorithm — `_compute_tier_boxes` (precise steps)

Input `ranked = {node_id: (rank, x, y)}`. Output: plan dict.

```
1. BUCKET
   unranked = []
   members  = {tier_id: []}   # empty lists for all 6 tiers
   for nid, (rank, x, y) in ranked.items():
       if rank == unranked_rank:            # sentinel -> never boxed
           unranked.append(nid); continue
       tier = first spec in _TIER_SPECS where (lo is None or rank >= lo)
                                          and (hi is None or rank <  hi)
       if tier is None:                     # gap band [690,700) / no real type -> float, never box
           unranked.append(nid); continue
       members[tier.id].append(nid)

2. TOTALS
   total_ranked = sum(len(m) for m in members.values())   # excludes unranked
   drawn_tiers  = [t for t in _TIER_SPECS
                     if len(members[t.id]) >= min_tier
                     or (output_singleton and t.id == "OUTPUT" and len(members[t.id]) == 1)]

3. FLOOR GATES  (skip = return {draw:False, skip_reason, boxes:[], unranked, warnings:[...]})
   if total_ranked < min_total:      skip_reason = "below_min_total"   -> return
   if len(drawn_tiers) < 2:          skip_reason = "single_tier"       -> return

4. MONOTONICITY / DISJOINT-SLAB GATE  (the mandatory precondition — layout is depth-keyed, not rank-keyed)
   For each t in drawn_tiers: slab[t] = (min(y of members[t.id]), max(y of members[t.id]))
   Order drawn_tiers by _TIER_INDEX ascending (SCENE top … OUTPUT bottom; higher screen-Y = lower tier index).
   (a) Adjacent-tier disjointness: for consecutive (upper=a, lower=b) in that order,
       FAIL if slab[a].min <= slab[b].max      # upper tier's lowest node not strictly above lower tier's highest
   (b) Foreign-node-in-slab: for every participating node p (ranked, not unranked),
       let tp = p's tier index; FAIL if for any drawn tier t with _TIER_INDEX[t] != tp:
                 slab[t].min <= p.y <= slab[t].max
   if any FAIL:  skip_reason = "not_monotonic";  warnings += ["layout not rank-monotonic (depth-keyed layout) — boxes suppressed"]  -> return
   # WHY tier-INDEX not raw rank in (a)/(b): equal-Y within-tier siblings (camera 400 + domelight 600 both at
   # depth 0, same Y) would trip a raw-rank "non-decreasing" test into a false skip. Tier-index tolerates
   # within-tier/within-row ordering while still catching the merge case (SCENE merge rank145 sitting below
   # MATERIALS rank220 -> slab[SCENE].min <= slab[MATERIALS].max -> FAIL, correct).

5. EMIT
   boxes = []
   for t in drawn_tiers:
       m = members[t.id]
       boxes.append({ "id": t.id,
                      "name": _TIER_BOX_PREFIX + t.id,
                      "label": t.label_template % len(m),   # live count = the TD tripwire
                      "rgb": t.rgb,
                      "members": m })
   return {"draw": True, "skip_reason": None, "boxes": boxes, "unranked": unranked, "warnings": warnings}
```

Determinism: a node's tier is a pure function of its immutable per-type rank, so members are a contiguous rank slab and identical across rebuilds. `ranked={}` → total 0 → `below_min_total` → clean skip, no crash.

---

## 3. Exact `hou` calls in order — `_draw_tier_boxes` (idempotency guard FIRST)

Caller already holds `hou.undos.group`. All calls copied from VERIFIED API.

```python
def _draw_tier_boxes(parent_node, id_to_hou, *, draw_legend=False, output_singleton=False):
    if not _HOU_AVAILABLE or parent_node is None:
        return {"draw": False, "skip_reason": "no_hou", "boxes": [], "unranked": [], "warnings": []}

    # A. LIVE RANK+POSITION  — lazy import breaks the assemble<->helpers cycle.
    #    Rank SSOT = handlers_solaris_assemble; DO NOT re-derive. NO isinstance(hou.LopNode) filter:
    #    usdrender_rop is a hou.RopNode and must participate (RENDER band), so iterate id_to_hou verbatim.
    from .handlers_solaris_assemble import _get_sort_key, _is_unranked, _UNRANKED_RANK
    ranked = {}
    for nid, node in id_to_hou.items():
        try:
            r = _UNRANKED_RANK if _is_unranked(node) else _get_sort_key(node)
            p = node.position()                       # hou.Vector2 — works on LopNode AND RopNode
            ranked[nid] = (r, float(p[0]), float(p[1]))
        except Exception:
            continue                                  # best-effort; a bad node never kills the pass

    plan = _compute_tier_boxes(ranked, output_singleton=output_singleton,
                               unranked_rank=_UNRANKED_RANK)

    # B. UNCONDITIONAL SWEEP OF OUR NAMESPACE — runs BEFORE the skip gate so a shot that
    #    shrank to empty/single-node/branched leaves NO stranded SYNAPSE_TIER_* frames.
    #    destroy() removes ONLY the box/sticky, never member nodes (verified).
    for b in tuple(parent_node.networkBoxes()):       # tuple() -> safe destroy mid-iteration
        if b.name().startswith(_TIER_BOX_PREFIX):
            b.destroy()
    for s in tuple(parent_node.stickyNotes()):
        if s.name().startswith("synapse_tier__"):
            s.destroy()

    # C. GATE ONLY THE CREATE HALF.
    if not plan["draw"]:
        return plan                                   # stale already cleared -> clean editor

    # D. CREATE populated tiers (belt-and-suspenders findNetworkBox guard blocks auto-suffixing).
    created = []
    for bd in plan["boxes"]:
        existing = parent_node.findNetworkBox(bd["name"])
        if existing is not None:
            existing.destroy()
        box = parent_node.createNetworkBox(bd["name"])
        for nid in bd["members"]:
            box.addItem(id_to_hou[nid])               # addItem accepts LopNode AND RopNode (verified)
        box.fitAroundContents()                       # AFTER membership; encloses members only
        box.setColor(hou.Color(bd["rgb"]))            # single 3-float seq, 0..1 (verified ctor)
        box.setComment(bd["label"])                   # the visible section title (verified round-trip)
        created.append(box)

    # E. MEASURED SELF-DESTRUCT GATE — authoritative. fitAroundContents padding + node extents +
    #    X-spread from merge branches can overlap even when the pure Y-gate passed. Read BACK the
    #    fitted rects (position()+size() — sticky/box geometry getters; box.bounds() does not exist).
    rects = []
    for box in created:
        p, s = box.position(), box.size()
        x0, y0 = float(p[0]), float(p[1])
        rects.append((x0, y0, x0 + float(s[0]), y0 + float(s[1])))
    member_ids = {nid for bd in plan["boxes"] for nid in bd["members"]}
    bad = _any_rect_overlap(rects)
    if not bad:                                       # foreign-node containment (a non-member inside a tier rect)
        for nid, (_r, x, y) in ranked.items():
            if nid in member_ids:
                continue
            if any(rx0 <= x <= rx1 and ry0 <= y <= ry1 for (rx0, ry0, rx1, ry1) in rects):
                bad = True; break
    if bad:
        for b in tuple(parent_node.networkBoxes()):
            if b.name().startswith(_TIER_BOX_PREFIX):
                b.destroy()
        plan["draw"] = False
        plan["skip_reason"] = "overlap_detected"
        plan["warnings"].append("post-fit rect overlap / foreign-node enclosure — boxes self-destructed")
        return plan

    # F. OPTIONAL LEGEND — OFF by default; guarded against empty member set (no min()/max() on []).
    if draw_legend:
        pts = [(x, y) for (_r, x, y) in ranked.values()]
        if pts:                                       # explicit guard: min/max never over an empty seq
            min_x = min(px for px, _py in pts)
            max_y = max(py for _px, py in pts)
            sticky = parent_node.createStickyNote(_TIER_LEGEND_NAME)   # stale one already swept in B
            sticky.setText("SYNAPSE tiers · scene -> materials -> layout -> lights -> render -> output")
            sticky.setTextSize(0.4)
            sticky.setColor(hou.Color((0.15, 0.15, 0.17)))
            sticky.setTextColor(hou.Color((0.83, 0.85, 0.88)))
            sticky.setPosition(hou.Vector2(min_x - 4.0, max_y + 1.0))
            sticky.setSize(hou.Vector2(4.0, 1.4))
            # NEVER call sticky.bounds() — phantom getter (AttributeError). Read via position()+size().

    return plan
```

Helper (module-level, pure):

```python
def _any_rect_overlap(rects):
    """True if any two axis-aligned rects share positive area (> _OVERLAP_EPS on both axes)."""
    for i in range(len(rects)):
        ax0, ay0, ax1, ay1 = rects[i]
        for j in range(i + 1, len(rects)):
            bx0, by0, bx1, by1 = rects[j]
            if (min(ax1, bx1) - max(ax0, bx0) > _OVERLAP_EPS and
                min(ay1, by1) - max(ay0, by0) > _OVERLAP_EPS):
                return True
    return False
```

**Idempotency contract (proven on 22.0.368, minor attack):** sweep-by-prefix before create is the correct answer to the verified no-`removeItem`/auto-suffix reality. Re-run yields a flat box set (never `SYNAPSE_TIER_SCENE1`), clears tiers that emptied since last run, and never touches artist boxes (they lack the prefix). Documented ownership caveat: any artist box named `SYNAPSE_TIER_*` is reserved and will be destroyed on rebuild.

---

## 4. Colors (r,g,b floats) + labels (verbatim)

| Tier id | Box name | `setColor(hou.Color(rgb))` | `setComment(label)` |
|---|---|---|---|
| SCENE | `SYNAPSE_TIER_SCENE` | `(0.30, 0.43, 0.31)` | `SCENE · geometry & imports · {n} nodes` |
| MATERIALS | `SYNAPSE_TIER_MATERIALS` | `(0.24, 0.41, 0.45)` | `MATERIALS · shading · {n} nodes` |
| LAYOUT | `SYNAPSE_TIER_LAYOUT` | `(0.37, 0.31, 0.47)` | `LAYOUT · collections · xforms · instancing · {n} nodes` |
| LIGHTS | `SYNAPSE_TIER_LIGHTS` | `(0.50, 0.43, 0.22)` | `LIGHTS · camera + lights · {n} nodes` |
| RENDER | `SYNAPSE_TIER_RENDER` | `(0.25, 0.35, 0.51)` | `RENDER · settings + ROP · {n} nodes` |
| OUTPUT | `SYNAPSE_TIER_OUTPUT` | `(0.45, 0.31, 0.29)` | `OUTPUT · USD export · {n} nodes` |

Legend sticky (opt-in): fill `hou.Color((0.15, 0.15, 0.17))`, text `hou.Color((0.83, 0.85, 0.88))`, text size `0.4`. All fills ≤ 0.51 max channel so grey LOP node graphics stay legible on top.

---

## 5. Skip conditions (draw NOTHING; stale boxes already swept in step B)

| Condition (checked in this order) | `skip_reason` | Where |
|---|---|---|
| No `hou` / null parent | `no_hou` | wrapper guard |
| `total_ranked < 12` | `below_min_total` | pure §3 |
| `< 2` tiers with ≥ `MIN_TIER_NODES` members | `single_tier` | pure §3 |
| Layout not rank-monotonic (slab overlap OR foreign node in a slab) | `not_monotonic` + warn | pure §4 |
| Post-fit rects overlap OR foreign node enclosed | `overlap_detected` + warn | live §E |

Per-tier degrade (no skip, just fewer boxes): tier with 0 members → no box (6→5 on a typical shot when LAYOUT is empty); tier with exactly 1 member → no box (unless `output_singleton=True` marks OUTPUT at n=1); unranked/gap-band nodes → never boxed, returned in `plan["unranked"]`, left floating.

**Consequence of the depth-keyed layout (stated honestly):** on a branched merge shot the `not_monotonic` gate is the COMMON path, so the pass correctly no-ops there. The headline "5–6 slabs on the 40-node branched target" holds only if/when `_compute_dag_positions` is made rank-monotonic; with today's depth-keyed layout, boxes fire on rank-monotonic single-column chains and the branched shot degrades to nothing rather than shipping overlap. Do not re-add any "structural non-overlap" claim.

---

## 6. Tests

### 6a. Pure unit tests — `tests/test_tier_boxes.py` (fake `ranked` dicts, no `hou`)

Build helper `mk(rank, x, y)`. Y increases upward (matches `_compute_dag_positions`: deeper = lower Y).

1. `test_empty_input` — `{}` → `draw=False`, `skip_reason="below_min_total"`, `boxes==[]`, no exception.
2. `test_below_min_total_skips` — 8 nodes across 3 monotonic tiers → `draw=False`, `"below_min_total"`.
3. `test_single_tier_skips` — 14 nodes all `rank<200`, monotonic → `draw=False`, `"single_tier"`.
4. `test_happy_linear_monotonic` — 15 nodes spanning SCENE/MATERIALS/LIGHTS/RENDER/OUTPUT, Y strictly decreasing with rank → `draw=True`; assert box ids, names, `rgb` tuples exact, labels contain exact member counts, `unranked==[]`.
5. `test_merge_branch_not_monotonic_skips` — reproduce the blocker graph: SCENE `merge` rank145 at low Y BELOW MATERIALS rank220 at higher Y → `draw=False`, `"not_monotonic"`.
6. `test_foreign_node_in_slab_skips` — a LIGHTS node whose Y falls inside SCENE's slab → `"not_monotonic"`.
7. `test_unranked_never_boxed` — include 2 nodes `rank==690` + enough ranked mass → they appear in `plan["unranked"]`, never in any box's members.
8. `test_gap_band_floats` — a node `rank==695` (no band, not sentinel) → `unranked`, never boxed.
9. `test_singleton_tier_dropped` — a tier with exactly 1 member is not drawn; with `output_singleton=True` an OUTPUT n=1 IS drawn.
10. `test_label_count_matches_members` — label `%d` equals `len(members)`.
11. `test_rgb_frozen` — each drawn box `rgb` equals the frozen `_TIER_SPECS` tuple.
12. `test_equal_y_within_tier_no_false_skip` — camera(400) + domelight(600) at equal Y (same LIGHTS tier), plus another monotonic tier → `draw=True` (guards the tier-index-not-raw-rank refinement).
13. `test_unranked_rank_constants_agree` — assert `handler_helpers._TIER_UNRANKED_RANK == handlers_solaris_assemble._UNRANKED_RANK` (drift pin).

### 6b. Live-probe assertions — `scripts/live_probes/probe_tier_boxes.py` (hython 22.0.368, `_netbox_probe` style)

Drive the REAL `_get_sort_key` + real `_compute_dag_positions`. Assert:

- **A (happy):** build a rank-monotonic linear lopnet ≥12 nodes across ≥2 tiers laid out top-to-bottom by rank; call `_draw_tier_boxes` → `parent.networkBoxes()` names == expected `SYNAPSE_TIER_*` set; each `box.comment()` == label; `box.color().rgb()` ≈ rgb (tol 1e-3); `box.nodes()` membership == expected ids.
- **B (idempotent):** call twice → box count flat, no `SYNAPSE_TIER_SCENE1`; run1 name-set == run2 name-set; every member node survives (child count unchanged).
- **C (shrink transition):** after A, delete nodes down to 1 → re-call → `[n for n in parent.networkBoxes() if n.name().startswith("SYNAPSE_TIER_")] == []` (unconditional sweep cleared stale) and the surviving node is untouched.
- **D (branched merge):** build the blocker graph via real `_compute_dag_positions` → call → no `SYNAPSE_TIER_*` boxes remain AND `plan["skip_reason"] in {"not_monotonic","overlap_detected"}` AND a warning recorded; assert zero stale frames.
- **E (overlap self-destruct):** hand-position two tiers' members so fitted rects overlap while faking a monotonic-passing `ranked` → after call all `SYNAPSE_TIER_*` destroyed, `skip_reason=="overlap_detected"`.
- **F (ROP participation):** include a `usdrender_rop` (assert `isinstance(rop, hou.RopNode)` and `not isinstance(rop, hou.LopNode)`); after call the RENDER box exists and `rop in box.items()` — proves NO `isinstance(hou.LopNode)` filter dropped it.
- **G (legend guard):** `draw_legend=True` on a valid shot → sticky `synapse_tier__legend` exists; read geometry via `position()`+`size()`; assert `hasattr(sticky,"bounds") is False` OR calling it raises (never used). On `id_to_hou={}` → no crash, no sticky.

---

## 7. Wire point into `build_graph`

**Location:** `handlers_solaris_graph.py`, `_handle_solaris_build_graph._on_main`, inside `with hou.undos.group("SYNAPSE: build_graph")` (opened L563), as **step 7 immediately after the step-6 display-flag block (after L649), before the `except` at L651.**

```python
                    # 6. Display flag AFTER layout … (existing, L641-649)
                    display_hou = id_to_hou[display_node_id]
                    if hasattr(display_hou, "setDisplayFlag"):
                        try:
                            display_hou.setDisplayFlag(True)
                        except AttributeError:
                            pass

                    # 7. Tier sectioning — cosmetic editor chrome, best-effort.
                    #    A box failure must NOT discard a correct network, so its own try/except
                    #    swallows and logs (mirrors _free_origin / R10 viewport-sync idiom).
                    tier_result = {"draw": False, "skip_reason": "not_attempted"}
                    try:
                        from .handler_helpers import _draw_tier_boxes
                        tier_result = _draw_tier_boxes(parent_node, id_to_hou)
                    except Exception as box_exc:            # noqa: BLE001
                        logger.warning("build_graph: tier sectioning skipped: %s", box_exc)
```

Then add to the return dict (~L685): `"tier_boxes": tier_result,`.

**Justification:**
1. **After layout (step 5):** boxes must enclose FINAL positions; `_draw_tier_boxes` reads `node.position()`, which is only correct once `_layout_dag_vertical`/`_layout_vertical_chain` have run.
2. **After the display flag (step 6):** the display flag triggers a cook; boxes are inert editor overlays. Drawing them last keeps the cook path pristine — box calls never perturb the cook and vice versa.
3. **Inside the existing undo group:** one artist Undo removes the boxes and the build together (atomic), which is exactly the single-undo-group the idempotency reconcile requires. `_draw_tier_boxes` therefore must NOT open its own group.
4. **Own try/except, not the build's:** a box failure logs and continues; it does not fall through to the L651 `except` that calls `hou.undos.performUndo()` and discards the whole network. Boxes are the last, purely-cosmetic step and fail independently.

`id_to_hou` (built at step 1, L571) is exactly the `{id: hou.Node}` the wrapper needs, and it already contains the `usdrender_rop` `RopNode` — no `isinstance` filtering anywhere in the path.