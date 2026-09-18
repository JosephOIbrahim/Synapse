# Current status and limits

[Back to README](../README.md) · [Architecture](architecture/overview.md)

This page separates shipped behavior, optional scaffolds and future work.
It is not a claim that every feature has been exercised in a fresh live session.

**Current as of v5.75.1, 2026-09-17.** Where a limit this page used to name has
since been fixed, it says so and dates it.

## What the latest changes cover

**[v5.75.1](https://github.com/JosephOIbrahim/Synapse/releases/latest) is the
latest release.** It supersedes v5.75.0, which was tagged on a commit whose CI
concluded failure. v5.75.1's tag was gate-checked before publication:
`scripts/release_ci_gate.py` reported `tag v5.75.1 53e4f9cb / ci completed
success / OK` ([release notes](releases/v5.75.1.md)).

**The suite on that tag commit:** `9461 passed, 485 skipped, 44 deselected,
4 xfailed`.

The same four numbers came back from every required context. Producer:
`gh run view 35283424577 --log --job=<id>` for each of `test (ubuntu-latest,
3.11)`, `test (ubuntu-latest, 3.14)`, `test (macos-latest, 3.11)` and
`test (macos-latest, 3.14)` — all `success` on `53e4f9cb`.

**What that number does not cover.** CI runs stock Python 3.11 and 3.14 on Linux
and macOS ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)). Houdini
22.0.400 runs SYNAPSE on its own Python 3.13, and **no Houdini-interpreter run is
published for v5.75.1.** A green badge is not a live render and not a
clean-machine installation.

**The v5.75.1 installer is not install-qualified.** The release carries three
assets — the Setup executable, `SHA256SUMS.txt` and a redacted public build
report. v5.74.0 shipped a fourth, `installer-verification.json`, and this release
does not. Producer: `gh release view v5.75.1 --json assets`. The installer is
built from pinned, hash-verified inputs and its payload digest is recorded; it
has not been probed against a running Houdini.

### Releases since this page was last current

It was last written for v5.67.4 (`d7c90a15`). What landed after it:

| Release | What changed |
|---|---|
| [v5.68.0](releases/v5.68.0.md) | Graph review controls; the Windows installer moves into the source tree |
| [v5.69.0](releases/v5.69.0.md) | The stop controls actually stop |
| [v5.70.0](releases/v5.70.0.md) | Tool names an artist can read |
| [v5.70.1](releases/v5.70.1.md) | Documentation only — no product change |
| [v5.71.0](releases/v5.71.0.md) | The render farm; tool registry 128 → 137 |
| [v5.72.0](releases/v5.72.0.md) | One type scale in the panel |
| [v5.72.1](releases/v5.72.1.md) | Evidence repair — no product change |
| [v5.73.0](releases/v5.73.0.md) | Panel contrast and legibility |
| [v5.74.0](releases/v5.74.0.md) | Documentation and tests only |
| [v5.75.0](releases/v5.75.0.md) | Memory-store fix — superseded by v5.75.1 |
| [v5.75.1](releases/v5.75.1.md) | The tag that was checked |

For commits after the tag, read the
[current CI run](https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml)
and the matching
[release notes](https://github.com/JosephOIbrahim/Synapse/releases).

## Artist control

**The panel worker is restricted by gate level, not by trust.** The default mode
is `standard` (`python/synapse/panel/worker_policy.py`):

- Read-only tools and knowledge-group tools — **permitted.**
- `inform`-level changes — **permitted**, and undo-grouped. Create node, set
  parameter, connect nodes, apply VEX, create material, lock seed, undo, redo.
- `review` / `approve` / `critical` gates — **refused.** Delete node,
  `execute_python`, `execute_vex`, renders, exports, memory prunes, PDG cooks.
  The model receives the refusal and its reason, and re-plans.
- A tool that is not in the registry — **refused**, fail-closed.
- Two composite Solaris builders are allowlisted, because each is one
  undo-wrapped call made entirely of `inform`-level primitives.

The gate levels themselves live in `shared/constants.py`, `OPERATION_GATES`.

An opt-in `proposal` mode narrows this further. `standard` remains the default.

**Consent gates exist in the bridge, and no shipped path arms them.** There is
one `LosslessExecutionBridge` per process, constructed gate-less with an
auto-approve callback (`shared/bridge.py`, `get_process_bridge`), and the panel
re-asserts that posture on first use (`python/synapse/panel/bridge_adapter.py`).

That is deliberate, not an oversight. The blocking approval poll sleeps on the
GUI thread, and the only thread that can draw the approval card is the one it
would be sleeping on. Wiring a real gate there re-arms a confirmed Houdini
deadlock. Pinned by `tests/test_panel_consent_no_freeze.py`.

**The live `/synapse` WebSocket adds no consent of its own.** `execute_python`
and `execute_vex` reach Houdini there with full builtins, no gate and no import
filter. That is the deliberate single-user-localhost posture. Pinned by
`tests/test_phase0b_consent_posture.py`.

So consent today is **structural, not interactive**: the panel worker is refused
the gated tools rather than asked about them. Universal per-operation approval is
not a shipped guarantee, and a handler-layer gate is a prerequisite for any
multi-user or studio deployment.

[Source-backed permission map](architecture/overview.md#permission-and-undo-boundaries)

## Undo, Stop and rendering

- **Undo groups operations.** One Ctrl+Z reverses one recorded operation. It does
  not promise a whole-conversation reversal, and it does not recover files
  already written to disk.
- **Grouping is not rolling back.** A build that fails halfway leaves the part
  already made in your scene until you undo it deliberately. Some bridge failures
  attempt a guarded single-step undo; grouping alone guarantees no recovery.
- **Stop is a request to stop further work.** It is not evidence that an
  in-flight cook or an external renderer has ended.
- **Emergency halt's reach is specific.** It cancels cooking TOP networks under
  `/tasks`, `/obj`, `/stage` and `/out`, writes a session report, and **reports**
  background renders rather than killing them — stop each one explicitly with
  `synapse_render_stop`. See `_handle_emergency_halt` in
  `python/synapse/server/handlers_render.py`.
- **Validate render outputs.** File existence alone does not prove a complete
  frame. Historical render investigations, including interrupted mantra output,
  remain in the [render operator guide](render-freeze-operator-card.md).

**Fixed — the TOPs/render-farm recovery work is merged.** This page used to say
it was held on a separate branch. It landed on master in PR #85 (merge commit
`1d982426`, 2026-09-15) and shipped in [v5.71.0](releases/v5.71.0.md) as durable
TOPs render jobs, an artist render workspace and seven new farm tools.
`fix/cto-render-20260908` is now a historical ref: master contains its farm work
and more.

Producer: `git diff --shortstat origin/fix/cto-render-20260908 HEAD -- python/synapse/farm/`
→ `1 file changed, 33 insertions(+), 3 deletions(-)`, all of it on master's side.
The seven farm tools are `synapse_farm_submit`, `_jobs`, `_job`, `_inspect`,
`_cancel`, `_prepare` and `_capabilities` in `python/synapse/mcp/_tool_registry.py`.

## Memory and suggestions

**Fixed in v5.75.0 and v5.75.1** — a store refused every write for two days while
every health surface read OK:

- One logical memory-add was emitting two records, the second metadata-stripped.
  They collided on one id and degraded the store. The second write is gone at
  source, and a collision guard sits behind it.
- `MemoryStore.health()` now reports whether writes are landing, and counts
  `overwrote_prior` separately from `rejected_writes` so a correct idempotency
  refusal cannot be read as a fault (`python/synapse/memory/store.py`). A store
  that cannot answer reads UNKNOWN, never OK.
- The opportunistic prune in `add()` is opt-in and defaults off
  (`python/synapse/memory/moneta_store.py`, `auto_consolidate`).

**Still open:**

- **Installing v5.75.1 does not repair a store that is already degraded.** It
  stops the cause and ships the recovery tools.
- **The whole-second id collision window is unchanged.** A memory's id hashes
  content, `created_at` and type, and `created_at` is generated at whole-second
  resolution — `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())` in
  `python/synapse/memory/models.py`. Two distinct memories with identical content
  and type, written inside the same second, still collide.
- **A pre-migration plaintext store is not recovered**, and mirror-only records
  are not deposited into the primary.

**The three-substrate LOOP is opt-in.** Moneta owns retained project records,
Octavius composes private context, and Hanish owns forecast/outcome evidence. The
forecast measures a narrow handler outcome; it is not predictive modeling.

**Stage 0** recalls one compatible, checked lookdev procedure on request and
offers editable prompt text. It needs an existing project store and a
developer-imported record. It does not train a model, build a library by itself,
or change the scene when memory is recalled.

**Version upgrades:** exact SYNAPSE version matching can produce `NO_MATCH` for an
older experience. Records are not erased; use a matching rehearsal/import.

[LOOP configuration](MEMORY_LOOP_REPAIR.md) · [Stage 0 guide](development/rsi_stage0.md)

## Knowledge and qualification

Houdini symbol and node references are build-aware. Legacy H21 workflow prose and
newer, explicitly sourced H22 notes coexist; an H22 reference does not certify
every generated workflow. Inspect parameters and resulting scenes on the running
build. Rob Pieke reference intake preserves lecture-source status and does not
turn a transcript into a checked procedure.

**Where "does this symbol exist?" is actually answered.** The rulebook's
`surfaces/` directory is still empty — a `.gitkeep` and nothing else — and
`scripts/rulebook_harvest.py` does not exist yet. Until that harvest lands:

- **Symbol existence** is decided by the introspected runtime table
  `python/synapse/cognitive/tools/data/h22_symbol_table.json`, regenerated with
  `hython host/introspect_runtime.py` on the target build.
- **Node types** are decided by the live catalogue `rag/catalog/h22.0.400/`.
- `rulebook/phantoms.json` remains the quarantine list either way.

A headless regeneration omits the GUI-only modules, which
`harness/verify/checks.py` unions back in. The catalogue's totals describe the
packages installed on the machine that built it, not Houdini 22 in general.

See the [knowledge intake record](MEMORY_LOOP_REPAIR.md#solaris-reference-intake).
Older measurements and open investigations are preserved in the
[v5.67.3 README snapshot](https://github.com/JosephOIbrahim/Synapse/blob/v5.67.3/README.md#known-limitations)
and the [review archive](reviews). That snapshot is history, not current status —
read it for the investigations it names, not for what ships today. This page
closes none of them silently.

## Direction, not shipped capability

General predictive node-network creation, frontier-model Computer Use, and full
recursive self-improvement remain development directions. Their intended controls
are defined in [INTENT.md](../INTENT.md): the artist chooses when assistance engages,
its scope, and when to take over.
