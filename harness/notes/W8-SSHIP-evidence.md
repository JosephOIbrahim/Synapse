# W8-SSHIP — ship scout evidence dossier

**Leg:** W8-SSHIP · band TRUTH · readonly · branch `wave8/sship`
**Base:** merge-base(master,HEAD) = `327f52fd` · **Observed HEAD at recon:** `v5.51.0-11-g327f52fd`
**Method:** first-hand read-only recon (Read/Grep/Bash) in this worktree. Every claim
carries a `file:line` anchor or a first-hand command observation. Unobtainable = UNKNOWN.

All findings were posted to the wave8 bus addressed to W8-LIBR as they landed
(9 `finding` messages, 2026-08-17). Ranking: **P0** production-blocking · **P1**
hardening · **P2** polish.

---

## Target 1 — the g1–g9 (actually g1–**g10**) ship-gate automation map

**Two different G-axes exist and collide.** The *ship* gates the mission asks about are the
**release-readiness** axis (the B7-SHIP row names `F-G9-ROLLBACK`; G9=Rollback lives on
this axis), **not** the H22 gap-blueprint G-axis (G1 ports, G5 grounding, G6 benchmark, G9
pre-flight). The collision is documented in-tree: `docs/SCENE_GROUNDING_CONTRACT.md:13`
("two different axes on the same label … human decision: confirm the label, or rename one
axis"). **[P2]**

Release-readiness gate definitions: `docs/reviews/synapse-h22-readiness-2026-07-10.md:486-495`
(G1–G10). Live verdict emitter: `harness/verify/checks.py:2401-2410`.
Ritual receipts (v5.51.0): `harness/state/release_receipts.json`.

| Gate | Definition | Automation **today** | Evidence anchor |
|---|---|---|---|
| **G1** clean install | panel+shelf appear from a ZIP on a fresh Windows account | **pure-human GUI** | `release_receipts.json:2` (Joe "pass", 22.0.400, 2026-08-16) |
| **G2** dependency isolation | brain boots w/ user-site disabled, no global pkgs | **scripted** (`per_check.deps_isolated`) | `checks.py:2402` |
| **G3** host truth | symbol/node/punycode artifacts committed + build-stamped | **scripted** (stamp check; `panel/gate_stamp.py`) | `checks.py:2403` |
| **G4** mutation integrity | bridge-off blocks every mutation | **scripted** (`per_check.mutation_fail_closed`) | `checks.py:2404` |
| **G5** lifecycle | heartbeat survives every panel close | **split**: machine (`runtime_owns_heartbeat`, scripted) **+** human (open/close GUI) | `checks.py:2405-2406` + `release_receipts.json:8` |
| **G6** core smoke | SOP/LOP/COP/TOP ops pass or capability-disabled | **pure-human GUI** | `release_receipts.json:14` |
| **G7** reversibility | one Ctrl+Z reverses the whole build | **pure-human GUI** ("never simulatable") | `release_receipts.json:20` |
| **G8** restart | save/quit/relaunch/reconnect, no dup threads | **pure-human GUI** | `release_receipts.json:26` |
| **G9** rollback | prior release restored with one documented op | **pure-human GUI + CTO chain** (orig uninstall-drill CRASHED → `F-G9-ROLLBACK`: SideFX libUI icon-paint segfault) | `release_receipts.json:32` |
| **G10** documentation truth | README claims a build only after receipts exist | **doc-checkable** (see README self-contradiction, Target 2) | readiness `:495` |

**Headline:** the entire ship-gate set is **ritual-time — zero of it runs in CI.** Within the
ritual, ~4 gates are scripted (the OPERATOR'S CARD "driver greens every automatable gate"),
and 6 are pure-human GUI acts recorded as Joe's spoken "pass". **[P1]**

The mechanical tag ritual (distinct from the acceptance gates) is
`docs/RELEASE_CARD.md:10-20`: edit VERSION → `sync_version.py --write` → commit →
`tag_release.py --check-only` → `tag_release.py` → push → `gh release create` →
reinstall+doctor. `scripts/tag_release.py` is the scripted gate: it **refuses** on a dirty
tree, on `sync_version --check` DRIFT, or on any UNKNOWN (`tag_release.py:7`).

The live-driven ritual card is `harness/notes/h22/OPERATORS-CARD-release-ritual.md` — human
per-act words: `ritual` → `pass`×N → `drop.json` → `bump`/`verify`/`tag`. "If any gate stays
red, the ritual STOPS — no partial releases" (`:37`).

**v5.51.0 correlation (first-hand):** tag `v5.51.0` commit subject is
`release(bump): 5.51.0 across six surfaces via sync_version --write, verdict PASS`
(2026-08-16 23:00), and the six human g-receipts are dated 2026-08-16 at build 22.0.400 —
same ritual. **Caveat [P1]:** the g-receipts pin **pre-tag** master SHAs; HEAD is now **11
commits past** the v5.51.0 tag, so the current tree carries **no fresh g1–g9 receipts** — a
new tag cut from HEAD would ship against stale acceptance evidence.

---

## Target 2 — VERSION-sync: drift-detected, or run on memory?

**The script (`scripts/sync_version.py`).** One observer + propagator over **six** surfaces:
`VERSION`, `pyproject`, `__version__`, docstring, `CLAUDE.md`, README `<sub>` banner
(`sync_version.py:41-53`). UNKNOWN-never-zero house rule; `--check` observes, `--write`
propagates (refuses to write if anything is UNKNOWN, `:100-114`).

**First-hand observation** (`python scripts/sync_version.py --check`): all six surfaces
`CONFORM`, `canonical=5.51.0`, `verdict=PASS`. No live drift on this branch.

**Is it drift-detected anywhere, or "run on memory"?**
- **Wired to nothing automated.** grep of `.github/`, `harness/orchestrate.ps1`,
  `harness/githooks/` for `sync_version`/`checks.py`/`release_readiness` = **empty**. The
  script itself runs only (a) at the release ritual (`RELEASE_CARD.md:13`, `--write`, human
  memory) and (b) inside `scripts/tag_release.py:92` (`--check` gate, refuses tag on drift).
- **BUT drift IS caught in CI — by an independent re-implementation, not the script.**
  `tests/test_phase0c_doc1_version_conformance.py` reads the surfaces by path (no import →
  stock-CI-safe, runs in CI). It pins in-tree agreement **and** the live tree-vs-published-tag
  half (`:184` `test_no_published_tag_outruns_the_canonical_version` — "goes red the moment
  someone tags a release without running the version bump"). **[P1: the guard is duplicated
  logic, not the script — the script's own output is never asserted in CI.]**

**Blind spot [P2].** `sync_version` tracks only the README `<sub>vX.Y.Z · Houdini` banner —
**not** the `tags: v5.50.0 is latest` note on the *same line* (`README.md:11`). That note is
now **stale**: `git tag` lists `v5.51.0`, `git describe` = `v5.51.0-11-g327f52fd`. So the
README self-contradicts (banner says 5.51.0, note says v5.50.0-is-latest) and **no surface
guards the latest-tag claim.** The conformance test only forbids tag > tree, not a stale
"latest" string in prose.

---

## Target 3 — SUPPORT_MATRIX: tested-in-CI / tested-once / asserted

Source: `docs/SUPPORT_MATRIX.md`. Convention (honest): "newest row is the live claim …
Unmeasured renders as *pending*, never a pass" (`:3-5`).

| Row / claim | Provenance | Anchor |
|---|---|---|
| H22.0.400 symbol table (35,908, gate armed) | **tested-once** (hython `host/introspect_runtime.py` stamp) | `SUPPORT_MATRIX.md:9` |
| H22.0.400 E2E | **asserted-pending** (not run) | `SUPPORT_MATRIX.md:9` |
| H22.0.400 node-type assay (2 missing types + 266 parm deltas) | **asserted-pending** — 268 drift items, `check_probe_clean` red until assay lands | `SUPPORT_MATRIX.md:13-16` + `checks.py:102` |
| H22.0.400 punycode (27 match / 99 new) | **tested-once** (probe), adoption pending | `SUPPORT_MATRIX.md:9` |
| H22.0.368 symbol table (superseded) / **E2E verified** | **tested-once** under hython; the live tier `test_live_wiring.py` `PINNED_BUILD=22.0.368` is **deselected in CI** | `SUPPORT_MATRIX.md:10,33` + `tests/solaris/test_live_wiring.py:44,59` |
| H21.0.671 baseline (33,255) | **tested-once** historically (H21 authority) | `SUPPORT_MATRIX.md:11` |
| `lastCookTime()` ms-vs-0.0 contract | **tested-once** both contexts (GUI ms receipt + headless-0.0 receipt) | `SUPPORT_MATRIX.md:43-59` |
| MonetaMemory USD schema registration (headless .400 verified / GUI pending) | **tested-once** (W2 registration probe) | `SUPPORT_MATRIX.md:65-66` |

**Verdict [P1]:** **every build-specific row is tested-once (hython/GUI receipt) or
asserted/pending — ZERO rows are tested-in-CI**, a direct consequence of CI carrying no
Houdini and no `pxr`. What CI *does* exercise is the symbol-table *walker* logic
(`tests/test_scout_introspect.py`, stock-safe) — never the live counts. The matrix is
honest about this (pending ≠ pass); the gap is that **nothing re-checks a build claim
automatically** — each is a one-time human/hython receipt.

---

## Target 4 — what the CI verify does NOT cover · distribution for a non-builder

**The CI (`.github/workflows/ci.yml`).** Matrix = `[ubuntu-latest, macos-latest] ×
["3.11","3.14"]` (`:13-14`). Command = `pytest tests/ -m "not needs_houdini"` (`:109`).

**First-hand counts** (collected in this worktree, Python 3.14.2 / Windows):
- **Full suite: 6763 tests** (brief's "6587-test verify" is **stale [P2]**).
- **CI subset: 6678 run / 85 deselected** across **7 modules**, all `hou`/`pxr` hard-gated:
  `test_live_wiring.py`(27,hou), `test_h22_cops_solver_live.py`(5,hou),
  `test_h22_setdressing_live.py`(4,hou), `test_hwebserver_integration.py`(4,hou),
  `test_scene_hash_gate.py`(22,pxr), `test_stage_exceeds_cache_and_composition_valid.py`(13,pxr),
  `test_stage_hash_honesty.py`(10,pxr).
- `docs/getting-started/installation.md:60` ("~4,700 collected / ~100 skip") is **also stale**.

**What CI structurally does NOT cover:**
1. **The 85 needs_houdini live tiers** — deselected loudly (honesty-invariant AST marker,
   `tests/conftest.py:826-960`; pinned by `test_needs_houdini_marker.py`). Tested-once under
   hython only.
2. **The GUI / panel class — and it SKIPS *silently-as-pass* [P1].** PySide is **not** a
   declared dependency (`pyproject.toml` grep = empty), so `synapse_panel.py`'s top-level
   PySide import makes the whole `tests/panel/*` suite **skip** on stock CI — and
   "**A SKIP exits 0, which the harness reads as PASSING**" (`tests/panel/test_docking.py:21-23`,
   verbatim). `tests/qt_stub_window.py:1-16` documents historical **cross-file-residue
   phantom passes** (`importorskip` modules "reported 3 passed each … partly fiction"). These
   panel modules are **not** in the 85 (the AST marker keys only on `hou`/`pxr`, never on
   PySide), so they are collected-then-skipped, not deselected. Real graphical Houdini 22
   panel behaviour has **NEVER** been run (`docs/reviews/h22-per-context-postmortem-2026-07-17.md:426`
   — "no real on-screen widget geometry … NULL"). The panel is covered by hython-offscreen +
   human hands (g1/g5/g6 receipts) only.
3. **Windows** — CI is ubuntu+macos only; the *production* seat + the whole install story is
   Windows (`README.md` install §, `$JOB` WinError-5, OneDrive pref-dir redirect). No
   Windows leg.
4. **The real runtime** — CI runs against conftest's canonical **fake `hou`** (a MagicMock
   superset reporting `applicationVersion=(21,0,671)`, `conftest.py:96`). CI green is a
   *mock-H21* signal; the phantom-API defense (scout symbol table) exists precisely because
   the fake can't catch a phantom `hou.*`.
5. **The deployment interpreter** — Houdini 22 embeds Python 3.13; **neither** CI leg (3.11,
   3.14) matches it. The `_vendor` wheels are cp311+cp313 only, so the 3.14 CI leg (and any
   mismatched seat) runs with the vendor tree **INACTIVE** (ABI-risk warning observed live at
   collection, `conftest.py:507`).

**Distribution for a non-builder.** SYNAPSE needs **no compile** — pure Python + committed
`python/synapse/_vendor/` wheels + a Houdini package file. Paths (`installation.md`,
`README.md` install §):
- Artist: download + run installer + paste API key (README 5-min).
- Dev: `git clone` → `pip install -e ".[dev]"` → `python scripts/install_synapse_package.py`
  (or the portable `$HOUDINI_PACKAGE_DIR` route, no install).
- `--verify` prints PASS/FAIL/**MANUAL** rows; 3 MANUAL rows can't be seen outside Houdini
  (Pane Tab menu, "make a box", Connect button) and never count as PASS
  (`installation.md:45-47`).

**Distribution gaps [P1]:**
- **(a) Moneta is a SEPARATE PRIVATE repo** (`JosephOIbrahim/Moneta`, deploy-key gated,
  `docs/MONETA_FOLLOWUPS.md:95-106`). SYNAPSE's own repo is public; a public/non-builder user
  **cannot** get Moneta → silent jsonl fallback (doctor reports it honestly, but the advertised
  substrate is undistributable to them).
- **(b) No wheel / no PyPI / no ZIP-builder script** (grep `make_archive`/`ZipFile` = empty).
  The non-builder "ZIP" is only GitHub's auto source-archive from `gh release create`
  (the g1 receipt: "vNEXT ZIP cannot exist pre-tag; ZIP re-run available post-tag").
- **(c) Vendored-wheel ABI fragility** — a seat whose embedded Python ≠ cp311/cp313
  inactivates `_vendor` and the brain later dies with "a cryptic deep ImportError"
  (`conftest.py:507` warning text). Sidecar is the documented mitigation
  (`harness/CLAUDE.md` survival rule).

---

## Honesty ledger

- **No P0 substantiated first-hand.** The release process is heavily human-gated and honest
  about pending items; I found no defect I can prove *blocks a correct release today*. Per
  the crucible criterion, I record this as an observation, not a manufactured pass.
- **UNKNOWN:** whether the scripted gates G2/G3/G4/G5-machine actually green *headless* vs
  needing a live seat was **not** exercised — I read the verdict emitter (`checks.py:2401`),
  not a live `checks.py` run (that is a ritual act, and `release_readiness_verdict.json` is
  gitignored `.gitignore:148`, so no committed sample exists to inspect). Classified
  scripted from the code shape; live headless-greenness = UNKNOWN.
- All test counts are from *this* worktree on Python 3.14.2/Windows; a real CI leg (3.11/3.14
  on Linux) may collect a slightly different number if platform-gated modules differ. The
  6763/6678/85 split is the first-hand figure here.
