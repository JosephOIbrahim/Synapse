# ATTEST — the attestation-hardening refinement loop

**Status:** DRAFT (Joe's word ratifies; no gate is open on this board yet)
**Seeded:** 2026-10-22 from the version-match verification run (`wf_54c4c93b-4f3`)
**Blueprint:** this file. **Board ledger:** `harness/attest/STATE.json`.
**Workflow:** `.claude/workflows/attest-harden.js` (dynamic; one wave per run)

---

## 0. Why this board exists

On 2026-10-22 a Jev-routed, 9-leg adversarial verification run was executed against
SYNAPSE's `version.match` health check. The claim under test:

> a fresh stdio MCP client against the working tree returns `version.match = pass`
> (bridge 5.97.6 == houdini 5.97.6) with `readiness.result = ready`

The run's outcome:

| Phase | Seats | Verdict |
|---|---|---|
| Observe | 4 | `GREEN_CONFIRMED` × 4 |
| Refute | 4 | `SURVIVED` × 4 — no refutation held |
| Adjudicate | 1 | `CONFIRMED` |

**The claim is true.** The judge proved it with a stale-relay control: patching only the
relay's in-memory `synapse.__version__` to `5.97.4` flipped the live answer to
`fail` / `version.mismatch` / `degraded`. The check is live and it discriminates.

**But the judge's `unproven` list is the seed.** A green `version.match` is a much
narrower fact than "the system is healthy", and the review proved exactly how narrow.
This loop hardens the substrate underneath that green.

---

## 1. The graph model

This loop is a **graph**, not a queue.

- **Node** — a work item with exactly one owner and a disjoint file set.
- **Edge** — a typed relation between nodes:
  | type | meaning | must be satisfied by |
  |---|---|---|
  | `dep` | B cannot land before A | topological order |
  | `contract` | A and B must agree on one interface | one shared signature |
  | `invariant` | a property that must hold across A and B | a shared test |
  | `seam` | one truth carried by two divergent carriers | one canonical carrier |
- **Spanning order** — the topological order over `dep` edges. It is the implementation
  order. It is also the *only* legal order: a node with an unsatisfied `dep` does not land.
- **Single-writer** — every file has exactly one node owner. Two nodes may not write
  the same file. Overlap is a `BLOCKED` finding, not a race.

**Graph engineering is the discipline, not the decoration.** The defects below are not
six unrelated bugs: they are one class of defect — *identity and attestation derived from
ambient labels rather than from verified facts* — expressed at six seams. A graph is
the right shape because the fixes are not independent: fixing the carrier split without
the identity primitive produces a second truth; fixing identity without the carrier
consolidation produces two truths that disagree.

---

## 2. The seed defects (all re-verified in the live tree before seeding)

Every line below was confirmed by reading the current source on 2026-10-22. The
analysts in the MAP phase **re-derive** these from the tree; they are claims to attack,
not facts to copy.

### H1 — the label is not the identity
`version_check` (`python/synapse/core/preflight.py:202`) compares two version **strings**.
The working tree and Houdini's installed package are **different code sets** that both
declare `5.97.6`. The judge's own `doctor` probe confirmed the answering Houdini resolves
`moneta_file` and `PXR_PLUGINPATH_NAME` under the *installed* tree. A behavioural
divergence between the two trees would still report green, and nothing in the evidence
set would catch it.

*Question for MAP:* what identity primitive (content-addressed build id, source
revision, tree hash) already exists in the codebase, on which surfaces, and can it be
compared cheaply on both sides of a live call?

### H2 — one truth, three carriers, no cross-check
| carrier | written at | read at |
|---|---|---|
| `payload["client_version"]` | `mcp_server.py:504-511` (get_health only) | `server/handlers.py:994` → `readiness()` → `version_check` |
| top-level `synapse_version` | `core/protocol.py:235-236` (every command) | `server/websocket.py:126`, `server/hwebserver_adapter.py:109` → `admit()` |
| (absent) | — | `mcp/server.py:244` → `preflight_gate.admit(..., tool_name)` — **no version argument at all** |

The health path and the change-gate path read **different fields** and never cross-check
them. On the stdio path both are stamped from the same `_SYNAPSE_VERSION`, so they agree.
Over the raw WebSocket a caller controls them independently — the refuter demonstrated
top-level `5.97.4` + payload `5.97.6` yields health `pass` while the gate would block.

### H3 — the HTTP `/mcp` path has no version carrier
`mcp/server.py:244` calls `preflight_gate.admit(_preflight_holder(...), tool_name)` with
no `client_version`. `version_check` with a falsy client version returns
`NOT_APPLICABLE` (`preflight.py:208`), and `NOT_APPLICABLE` does not block. So a bridge
running a mismatched version is **not refused** on the in-Houdini HTTP endpoint.

### H4 — peer provenance is a stamp echo
`server/doctor.py:732-747` (`_check_bridge_endpoint`) reads `~/.synapse/bridge.json` and
**echoes** it back as `status: ok` — host, port, pid, timestamp. It never verifies the
peer. Measured on 2026-10-22: two `houdini.exe` processes both LISTEN on `0.0.0.0:9999`
(32832, the artist session, and 52896); `bridge.json` names **52896**; the connection
was served by **32832**. The recorded peer was a false provenance record.

### H5 — the installed tree can drift after install
The installed tree is written by the installer and then **nothing checks it again**.
Measured: `.../5.97.6-5536b2e21d03e14b/houdini/python_panels/synapse_panel.pypanel` has
mtime `2026-10-22 11:59`, ~21 hours after the install (`2026-10-20 14:44`).
`installation.json` records `checks.files_checked: 1972, status: PASS` at install time and
`registrations` holds a sha for `packages/synapse.json` only — no per-file manifest for
the tree body, and no runtime check.

> **Corrected by the MAP phase, 2026-10-22 — this seed was wrong in two places.**
> A per-file manifest for the tree body **does** exist, in two places: the installed
> `payload-manifest.json` (1972 `{path: sha256}` entries, `source_revision`, `payload_id`)
> and `installation.json` → `runtimes[active].files` (the same 1972-entry map). The
> manifest is present but **unread by `python/synapse/`** — that, not its absence, is the
> defect. And a runtime check **does** exist and **fails today**: the shipped
> `setup_cli.py verify` re-hashes the tree and reports the one drifted file. What is
> missing is any *automatic* invocation of it. The drift interval is 46.1 h, not ~21 h.
> The MAP phase re-derives the seed from the tree; where the tree disagrees with the
> seed, the tree wins and the seed is corrected here.

### H6 — tier collapse is invisible in the harness
On this host only the session model is reachable. Alias `haiku` and alias `opus` both
resolve to the session model; alias `fable` and every explicit Anthropic model id fail
with *"There's an issue with the selected model (claude-fable-5-1)"*. A workflow that
requests a tier therefore gets a **lens**, not a model — and a receipt that says
`"model": "fable"` is a claim, not a fact. Nothing shipped reads the *effective* model
out of a transcript and fails a tier claim that did not execute.

---

## 3. The loop

One wave per run. Phases in order; each phase's output is the next phase's input.

```
MAP (5, parallel, read-only)      -> per-cluster node/edge candidates, file:line
  |
SEAM (1)                          -> the unified graph; seams ranked by blast radius
  |
DESIGN (parallel, <=4)            -> one proposal per top seam: single-writer map,
  |                                  invariant, proof, back-compat, needs_joe
CRUCIBLE (parallel, one each)     -> SOUND | SOUND-WITH-NITS | BROKEN | COULD-NOT-ASSESS
  |
SYNTH (1)                         -> final graph: nodes, owners, typed edges,
  |                                  spanning order, forge_now vs park
FORGE (parallel, forge_now only)  -> one atomic commit per node, own branch/worktree
  |
VERIFY (parallel, one per forged) -> the node's proof, re-run against the branch
```

**Caps.** 30 spawned agents per board, 2 held in reserve — the same contract as
`harness/loop`. A phase that would breach the cap is refused, not shrunk silently.
The board ledger is `harness/attest/STATE.json`.

**Model policy — the tier comes from Jev, the lens comes from code.** Seats are routed by
the shipped **JEV-ROUTE** guard (`harness/jev/jev_route.py`): a BATTLEPLAN-style mission
per seat, `route_state` → `jc.ask` → `decide`. The tier it returns buys a **lens**
(injected into the seat's prompt) and a **dispatch alias**; the lens text is code's half
of the split and lives in the workflow script, not in the routing payload.

Measured on this host (2026-10-22): the `mechanical` and `reasoning` aliases resolve to
the session model and work; the `referee` alias resolves to a model this host cannot
reach. A referee seat therefore runs the **referee lens on the reachable alias**, and the
substitution is recorded in `routing.*.model_served_by` — never presented as a Fable run.
A seat whose routed alias dies on a terminal API error is re-dispatched once with no
override, and **both** attempts are recorded in the wave's `faults` list.

**The model claim is resolved by the recorder, not by the seat.** The seat schema has
no model field and the seat prompt never asks for one — a seat cannot report the model
it ran on, because it does not know it. The wave recorder reads `requestedModel` and
`message.model` out of each seat's own transcript after the seat returns, and writes
the result into `harness/attest/STATE.json` → `model_attribution`. `meta.json`'s
`model` field records the alias that was **asked for**, never the model that ran, and
is never used as evidence. (Corrected 2026-10-22 after the C5 seat measured the drift
in this paragraph against the script's own schemas.)

The routing table for the first wave lives in `harness/attest/STATE.json` → `routing`.
Its Jev ledger is `attest-20261022.route.jsonl` (14 rows, 0 fallbacks).

**Human gates — halt here, every time.**
- blueprint ratification (this file) — Joe's word
- contract ratification — Joe's word
- **all merges, pushes, tags, VERSION edits** — Joe's word, per act
- any design whose `needs_joe` is non-empty is presented verbatim, then parked

**Forgery discipline.** FORGE legs work in their own worktree, on their own branch, one
atomic commit each, via `git commit -F <file>`. They never push, never merge, never
stash, never export `GIT_*`. A leg that discovers its file set intersects another
forge node's files reports `BLOCKED` and changes nothing.

**Evidence law.** Every claim carries a `file:line`, a command plus its real output, or
a live tool response. `UNKNOWN` is an acceptable answer. An estimate is not.
Unmeasured is reported as `UNKNOWN`, never as zero.

---

## 4. What this board is NOT

- Not a re-run of the verification. The claim is proven; re-proving it burns budget.
- Not the LOOP v5.1 ladder. That ladder is ratified, blocked at v01 on a SALUS scope
  mismatch, and re-sorting it is forbidden. This board is separate, and its spawn
  ledger is separate.
- Not a place to widen scope. A node that grows past its seam stops and reports drift.
