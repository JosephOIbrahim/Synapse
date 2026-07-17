# RETINA Blueprint Reconciliation — 2026-07-16

**Artifact:** `docs/SYNAPSE_RETINA_BLUEPRINT.md` v1.0, received 2026-07-16 evening, committed verbatim per its own F3 rule.
**Protocol:** the v5.24 precedent — a blueprint is reconciled against the repo **before** execution; anything authored above the code is corrected here, not silently in the blueprint. Per the blueprint's own §12 rule, this record and the future perception truth catalog outrank any INFERENCE line in the blueprint.
**Administrator note:** unlike the v5.24 drop-harness blueprint (which re-specified shipped work) and the pasted "SideFX memo" (which was refuted), this document reconciles **clean**: it is internally consistent with the v5.26.0 repo state, self-labels its inferences, and its single stale line is an INFERENCE it explicitly asked to have closed.

---

## 1 · Truth-appendix closures (what today's evidence already settles)

| Blueprint §12 line | Label there | Closure | Evidence |
|---|---|---|---|
| `opencv-python(-headless)` 5.0.0.93 abi3 win_amd64 on PyPI, 2026-07-02 | VERIFIED | **RE-VERIFIED LIVE this administration** — exact filename `opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl` (43.8 MB), released Jul 2 2026, abi3 not per-version tags. | PyPI files page, fetched 2026-07-16 evening |
| SYNAPSE host build = H22 **py3.11** (`_vendor` remains CP311) | INFERENCE — "close in drop record" | **CLOSED — CORRECTED.** The H22 host Python is **3.13.10** (`harness/state/drop.json`, captured live inside 22.0.368 on drop day), and `_vendor` is **dual-ABI cp311 + cp313** since the drop-day re-vendor (commit `38b33b6`; `_VENDOR_PYS = {(3,11),(3,13)}`). **Impact on the blueprint: none-to-positive** — the derived move (P5: worker in its own venv on the abi3 wheel) is unaffected; the abi3 wheel spans both ABIs regardless. The §1 sentence "H22's dual Python builds" remains true (SideFX ships a separate 3.11 build), but SYNAPSE's *installed* host is the 3.13.10 build. | `harness/state/drop.json` · `docs/reviews/h22-abi-verdict.md` |
| `Usd.GetVersion()` python symbol | INFERENCE — "runtime check" | **CLOSED — VERIFIED-LIVE.** Called live during the CTO-01 probe: `Usd.GetVersion()` → `(0, 26, 5)` on the running 22.0.368. | `docs/reviews/h22-live-reconfirm-2026-07-16.md` (CTO-01 section) |
| H22 = 22.0.368; USD 26.05; Python 3.13.10 default; Qt5 dropped | VERIFIED (launch coverage) | **CONFIRMED against the installed build** — with the notation fix: USD is **0.26.5** (`drop.json`), matching the blueprint's "26.05" intent. Qt/PySide 6.8.3 confirmed (qt-smoke artifact). | `harness/state/drop.json` · `docs/reviews/h22-qt-smoke.md` |
| SYNAPSE v5.26.0 live-verified; 4,387/0 | VERIFIED | **CONFIRMED** — and already advanced: master sits at 4,387 passed / 0 failed / 97 skipped post-W.4/U.1-fold merges. | this session's post-merge suite runs |

## 2 · Risk-register corrections (facts that *improve* the register)

- **"H21 uninstalled at v5.25.0" is half-stale:** H21.0.**671** (the catalog-stamped build) is uninstalled, but **H21.0.773 is installed on this machine** and was used *today* as the U.1-fold crucible's second-major live verification. The register's mitigation option ("keep one H21 instance for release gates") is **already satisfied** — with the known caveat, on record from that crucible, that the frozen 21.0.671 catalogs serve same-major-stale truth to a .773 host (accepted; the granularity note lives in `U.1b-H22-resolver-hardening`).
- **Zero-cv2 baseline confirmed pre-existing:** grep across `python/synapse/` finds no `cv2` import anywhere today — the M0 pin starts from a clean floor, not a cleanup.

## 3 · Repo-reality checks on §3/§6 references (all real)

| Blueprint reference | Repo reality |
|---|---|
| "perception channel, Phases A/B" | Real: `python/synapse/host/tops_bridge.py` (Phase A) + `scene_load_bridge.py` (Phase B) |
| "BL-007 class" (T0's target) | Real, documented: `docs/reviews/h22-cto-roadmap-2026-07-16.md` (N-8 pins) + wave-2 doc-intel; the synthesized-default path in `handlers_render.py` |
| zero-`hou` cognitive-boundary lint (the pin's pattern) | Real: `tests/test_cognitive_boundary.py` — the M0 pin mirrors it structurally |
| customData RFC gate (M. Gold) | Real, standing: `docs/RFC_agent_usd_ledger.md` gate registry — verdict-USD writes correctly stay off RETINA's critical path |
| major-aware host-hook pattern (P5) | Real as of today: the U.1-H22 fold shipped exactly this pattern for the connectivity catalog (`wiring.py::_pkg_catalog_path`) |

## 4 · Sequencing findings (the one genuine conflict surface)

1. **The render port wave vs. M1 host hooks.** The manifest writer + `.done` sentinel (M1) touch the render-submit path — the same surface the queued `render` port sub-wave will golden-pin. **Ruling required at M1 dispatch, not now:** either M1's hooks land *before* the render wave captures parity goldens (fix-before-freeze, the roadmap's own rule), or the render wave goes first and M1 rides a ratified post-wave cycle with golden updates in-cycle. Recorded on the RETINA.M1 queue entry; the gatewarden enforces whichever order is ruled.
2. **M4 is explicitly paired with the Copernicus expansion** (C.3/C.4/C.10, ratified + spec'd at `docs/SYNAPSE_COPERNICUS_EXPANSION.md`). The expansion's serialized builds (C.4→C.3→C.10) are queued ahead of M4; the pairing is natural — C.10's terrain COP recipes and M4's agent-authored QC COP nets share the `cops_create_node`/recipe surface, and the neural-preflight honesty rule is shared verbatim.
3. **No file-ownership conflicts with anything in flight** — nothing currently building touches the render-submit path or a `retina/` tree.

## 5 · Cross-reference passes

Two read-only agent passes (HDK × blueprint; HAPI × blueprint) were dispatched at administration time — targets: aiming the M1 probe at any HDK-named Karma object-ID/cryptomatte truth; the husk/ROP hook surface; EXR channel-layout facts for T0/T1; and HAPI's versioned image-extraction API as the existence proof behind §10 asks #2/#3. **Their sections append below when they land.** Per the blueprint's own rule, anything they surface is probe-*aiming* only — nothing is coded against until the M1 catalog verifies it live.

## 6 · Administration verdict

**RECONCILED — CLEAN, with one INFERENCE corrected (host Python / vendor ABI) and two INFERENCE lines closed for free by today's live evidence.** M0 proceeds: this record + the blueprint + the zero-cv2 pin commit together. The six miles enter the flywheel queue as gated cycles (M1 next; M2–M5 sequenced). The blueprint governs; this record and the M1 catalog outrank its INFERENCE column.
