# W8-SSURF — Surface Scout Evidence (B5-SURFACE)

Branch `wave8/ssurf`. Read-only recon. Every finding below is first-hand: the
cited `file:line` was read directly by this scout. Findings streamed to the
wave8 bus addressed to `W8-LIBR` as they landed (not batched). Severity per the
brief: **P0** = production-blocking, **P1** = hardening, **P2** = polish.

No **P0** was found: the current package installer works end-to-end, so no
single defect blocks all fresh users. The install.py defects below are P1
because the primary path still delivers a working panel.

---

## Install path

- **P1 — install.py is H22-blind.** `_detect_houdini_prefs()` searches only
  Houdini majors `[21, 20, 19]` — never 22. On an H22-only machine (project
  target is **H22.0.400**) it returns None and exits 1 with "Couldn't find
  Houdini preferences directory." `install.py:87` (fail path `install.py:309-314`).
- **P1 — install.py is OneDrive-blind.** Windows prefs search uses
  `os.path.join(home, "Documents")` with no OneDrive-redirect branch. The
  current package installer explicitly handles the OneDrive Documents redirect
  (`scripts/install_synapse_package.py:96-108`). The two installers disagree on
  prefs resolution and the OneDrive-blind one is the documented final step.
  `install.py:77-78`.
- **P1 — README manual-install doc path is OneDrive-blind.** `README.md:245`
  and `:264` tell the user the package lives at
  `Documents/houdini22.0/packages/synapse.json`; on an OneDrive-redirected seat
  the real dir is `OneDrive/Documents/houdini22.0/...`, so a hand-install writes
  where H22 never scans and the panel silently never appears. `README.md:245`.
- **P2 — install.py multi-build ambiguity.** Returns `candidates[0]` ("newest
  version found") by a fixed 21→20→19 order across five builds, with no warning
  that multiple prefs dirs exist and no way to know which was chosen.
  `install.py:98-99`.
- **P2 — installer version drift.** `install.py` prints "Installing Synapse
  v1.0.0" (`_VERSION="1.0.0"` at `install.py:31`, used at `:141`) while the
  product is v5.51.0 (`VERSION`). `install.py:31`.

*Positive:* `scripts/install_synapse_package.py` is the robust installer —
OneDrive-aware, globs `houdini2*` (finds H22), installs into all builds, and
`check_package_file` flags the "installed build not wired" drop-day trap
(`install_synapse_package.py:299-348`).

## First run + error language

- **P1 — first-run failure is silent-absence.** Per the README's own
  Troubleshooting, a mis-encoded/mis-keyworded package makes `import synapse`
  succeed, the version print, and the panel simply never appear — "No error.
  Just absence." Only out-of-band CLI diagnostics (`synapse_doctor`,
  `--verify`) exist; nothing in Houdini distinguishes still-loading from
  silently-failed. `README.md:298` (also `:328`).
- **P1 — install step-count inconsistency.** Install is titled "Four steps"
  (Clone/Package/Verify/Doctor) but a parenthetical at `README.md:247` also
  tells the user to run `install.py` for shelf/panel/icons — never a numbered
  step. Four-steps followers skip it; prose followers run the H22/OneDrive-blind
  installer. `README.md:231` vs `:247`.
- **P1 — ANTHROPIC_API_KEY is a hard requirement but not a numbered install
  step.** README Install lists Clone/Package/Verify/Doctor with no add-your-key
  step (`README.md:229-259`); the requirement surfaces only as a `--verify` FAIL
  row (`install_synapse_package.py:201`) and at first prompt. Every fresh artist
  hits the missing-key error on their first prompt. `README.md:229`.
- **P2 — key-location guidance conflict.** Installer verify
  (`install_synapse_package.py:407`) and quickstart (`quickstart.md ~:43`) say
  the key goes in `<repo>/.env`; the panel runtime error
  (`anthropic_provider.py:160`) says set it SYSTEM-level via `setx` and never
  mentions `.env`. The runtime error is the lone outlier. `anthropic_provider.py:160`.
- **P2 — BOM trap is manual-path only.** `README.md:284` warns PowerShell
  `Set-Content -Encoding utf8` writes a BOM Houdini rejects silently; the
  automated installer is BOM-safe (`install_synapse_package.py:129`). Bites only
  hand-installers. `README.md:284`.
- **P2 — shelf error dialogs show raw exceptions.** Every `synapse.shelf` tool
  does `except Exception as e: hou.ui.displayMessage("Synapse ... error:
  {}".format(e), severity=Error)` — a raw exception repr in an artist dialog,
  bypassing `error_translator.py`. `houdini/toolbar/synapse.shelf:18`.

*Positives:* the panel missing-key error (`anthropic_provider.py:158-166`) is
exemplary — exact `setx` command, warns the Windows terminal-scoped `set` won't
inherit into Houdini, offers the `hou.secure` alternative. `error_translator.py`
is a strong plain-English error layer (VEX/cook/render → explanation + fix).
`run_doctor(payload, handler=None, home=None)` (`doctor.py:981`) is
standalone-capable, so the recovery tool is not hard-blocked by a down bridge.

## Panel / shelf / ROP UX debt (enumerated, not fixed)

- **P1 — HALT can give a false confirmation.** `_on_emergency_halt`
  (`chat_panel.py:1022-1028`) posts "Emergency halt triggered." unconditionally
  (`:1024`) but only sends the command if `self._bridge.connected` (`:1025`).
  When the bridge is not connected the artist sees success while no halt is
  sent. A safety control must never report an action it did not perform.
  `chat_panel.py:1024`.
- **P1 — no in-panel render-progress or render-Stop affordance.** The
  connection bar exposes only HALT (`chat_panel.py:646-651`) and Connect; no
  render Stop, no progress. Renders run via chat → MCP tools, and per
  `README.md:148` emergency halt walks `/obj` only and does NOT kill background
  renders. Compounds the documented render-freeze risk (`README.md:124-138`).
  `chat_panel.py:646`.
- **P2 — connection feedback: feedback-less auto-connect + misleading red
  resting state.** The bar is built with a red `_ERROR_COLOR` "● Disconnected"
  default (`chat_panel.py:632-641`). On open, `onActivateInterface`
  (`:262-267`) auto-starts the bridge but posts no "Connecting..." label/message
  — unlike the manual Connect button (`:683-691`). Since normal chat runs
  in-process (quickstart), the red resting state misreads as a fault. Hard
  errors ARE surfaced to chat via `_on_connection_error` (`:946-948`), so it is
  not fully silent. `chat_panel.py:638`.

*Shelf inventory:* 7 shelf tools (`houdini/toolbar/synapse.shelf`): open panel,
project setup, inspect selection, inspect scene, last result, health check,
generate docs. `inspect_selection`/`inspect_scene` are clipboard-for-Claude
helpers, distinct from the MCP `synapse_inspect_scene` that hangs over external
MCP (`README.md:127`).

## Operator docs

- **P1 — no artist-facing Operator's Card.** All six "Operator's Card"/"CARD"
  docs are developer/harness-facing: `blackbox-operator-card.md` (Claude Code
  crash recovery), `latency-relay-operator-card.md`, `render-freeze-operator-card.md`
  (agent-team harness), `rsi-closure-operator-card.md`, `sprint_freeze/OPERATOR_CARD.md`
  (marshal boundary), `RELEASE_CARD.md` (v-bump→tag→push). The artist has
  `quickstart.md` but no consolidated card (install / first render /
  recover-when-broken / where-things-live on one page).
  `docs/blackbox-operator-card.md:1` (+ five siblings).
- **P2 — quickstart README-link anchor is stale.** `quickstart.md:5` links to
  the README install via `#-install--5-minutes`, but the README heading is
  `## Install` (anchor `#install`; jump-nav uses `#install` at `README.md:49`).
  The link will not resolve. `docs/getting-started/quickstart.md:5`.

*Positive:* `docs/getting-started/quickstart.md` IS strong artist operator doc —
explicit success signatures ("✅ You should see..."), failure branches, and the
crucial clarification that the agent runs in-process (no bridge to start for
normal chat). The docs gap is a consolidated/discoverable card, not absence.

### Operator-need gap analysis (6 needs)

| Operator need | Answered? | Where / GAP |
|---|---|---|
| Install into Houdini (which build, where) | Partial | quickstart + README Install; but install.py step is H22/OneDrive-blind |
| Start bridge / connect first time | Yes | quickstart: in-process, no bridge for normal chat |
| First successful op + what success looks like | Yes | README "First prompt" (mountain_displace) + quickstart |
| When it breaks (bridge/render/key) | Partial | Troubleshooting exists; no single recover card; HALT false-confirm |
| Where things live (logs, prefs, .env) | Partial | scattered across README/quickstart; no one-page map |
| Update / uninstall | GAP | uninstall only via `install.py --uninstall` (H22-blind); no update runbook |

---

## Method note (crucible criterion)

This scout dispatched four read-only recon agents to widen coverage; the
usage-limit checkpoint arrived before their results were consolidated. **This
receipt rests entirely on this scout's own first-hand reads** — every anchor
above was opened directly. Any additional anchors the scouts surface are
supplementary and route to W8-LIBR separately.
