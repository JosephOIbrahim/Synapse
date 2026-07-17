# The Rulebook — constitution

> **This file is the operator's guide to `rulebook/`: how to read it, cite it, and amend it.**
> The **law** lives in [`../SYNAPSE_RULEBOOK.md`](../SYNAPSE_RULEBOOK.md) (the governing blueprint, §§0–8) and in the ratified `contracts/`. This constitution points at the law; it never restates it.

Rulebook version: **0.1.0** (`VERSION`) — independent of the code `VERSION`.

---

## What the Rulebook is

SYNAPSE's Core Specification: the versioned, machine-readable contract agents build against and CI enforces, harvested from the live runtime because SideFX publishes none. Full rationale in blueprint §0.

**The defining property is enforcement coupling.** A rule in `docs/` is prose and drifts; a rule here is law. If a `ratified` rule has no green test binding, **CI fails**. If a quarantined phantom symbol appears in source, **CI fails**. If a harvested surface file is hand-edited, **CI fails**. Everything else serves that property (blueprint §0, §4).

## First principles

Read them in blueprint §1 — do not paraphrase them into code. In brief: **P1** the runtime is the spec · **P2** contracts precede code · **P3** every rule is testable or it isn't a rule · **P4** goldens are evidence, contracts are law · **P5** durable per build, elastic across builds · **P6** human gates stay human.

---

## How to READ

Layout per blueprint §2. Nothing here moves existing evidence — the Rulebook indexes it in place.

| Path | Kind | Rule |
|---|---|---|
| `manifest.json` | index | the machine truth — sections, rules, statuses, bindings, provenance, checksums |
| `VERSION` | semver | Rulebook version, independent of code |
| `surfaces/<build>/` | **harvested** | regenerable only via `scripts/rulebook_harvest.py`; **never hand-edit** (meta-test 3) |
| `phantoms.json` | quarantine | confirmed-absent symbols; referencing one anywhere in `python/synapse/` fails CI (meta-test 5) |
| `failures/` | registry | failure classes; `SF-N` numbering preserved |
| `contracts/` | **normative law** | human-ratified; edits are amendment-locked (meta-test 4) |
| `contracts/tools/_TEMPLATE.md` | template | Appendix A — the per-tool answer-key shape |
| `goldens/` | evidence | captured WS / Dispatcher envelopes (blueprint §6) |
| `fixtures/` | builders | deterministic programmatic scenes; no binary `.hip` |

Before touching any `hou.*` surface: check `surfaces/<build>/` and `phantoms.json` first (also in the CLAUDE.md stanza).

## How to CITE

**IDs are permanent** (blueprint §3). A superseded rule keeps its ID with the status flipped.

- `RB-<DOM>-NNN` — a rule (`RB-THR-001`)
- `PH-NNN` — a quarantined phantom
- `SF-N` — a failure class (numbering preserved from the existing registry)
- `g-<context>-<tool>-NNN` — a golden

**Statuses:** `draft` (advisory — read, don't rely) · `ratified` (binding, CI-enforced) · `rfc-gated` (blocks dependent work until the named RFC lands; no test binding needed to hold the gate) · `superseded` (kept for citation; replacement named).

**Provenance kinds:** `empirical` (live `dir()` / observed, build-stamped) · `audit` (existing spike audit, cited in place) · `repo` (enforced by existing code/test, cited by path) · `golden` (captured envelope).

Every normative claim carries provenance: how verified, which build, which interpreter, when (P1).

## How to AMEND

Per blueprint §4:

- **Surfaces** — regenerate via the harvester only; the PR shows the diff. Hand-edits die in CI (meta-test 3).
- **Contracts** — `draft` → `ratified` is a **Joe action**, recorded in the manifest (`ratified_by`, `ratified_on`). Any contract edit forces a deliberate manifest bump + `contracts_checksum` rehash **in the same commit** (meta-test 4). No silent law changes.
- **Phantoms** — re-litigation is forbidden absent new empirical evidence from a **newer build** (to be encoded as `RB-META-001`). Ratified quarantine stays quarantined.
- **RFC gates** — `rfc-gated` flips only when the RFC reference lands in the contract file. FORGE structurally cannot ratify around a gate (`contracts/usd_customdata.md`, Michael Gold).

---

## The enforcement layer — five meta-tests

Written at Mile 0, green forever after. Implemented in [`../tests/rulebook/test_rulebook_meta.py`](../tests/rulebook/test_rulebook_meta.py). Full text in blueprint §4.

1. **Schema** — `manifest.json` validates; statuses from the enum; every section path exists.
2. **Binding** — every `ratified` rule lists ≥1 collectable test node ID; a ratified rule with a missing binding **fails the suite by rule ID** (proven live by a bad-manifest fixture, even while the real ratified set is empty).
3. **Surface integrity** — every `surfaces/` file carries `generated_by` + checksum in `_meta.json`; the recomputed checksum must match.
4. **Amendment lock** — the recomputed `contracts/` tree hash must equal `manifest.contracts_checksum`.
5. **Phantom lint** — grep of `python/synapse/` (excluding `_vendor/`) for every `phantoms.json` symbol; any reference fails CI. Mirrors `tests/test_cognitive_boundary.py`, pointed at the quarantine.

**Commandment 7 holds:** an awkward meta-test means fix the implementation, never the test.

---

## Where the miles go

Mile 0 (this charter) built the skeleton, the empty-but-valid `manifest.json`, and the meta-tests. Content arrives later, each mile gated (blueprint §5): Mile 1 harvests `surfaces/`, Mile 2 backfills the law (Joe ratifies), Mile 3 captures goldens + the `synapse_inspect_stage` keystone, Mile 4 pilots a port slice, Mile 5 is the H22 diff (horizon). **The discipline exists before any content does — that is Mile 0's whole purpose.**

*The spec is durable. The agents are elastic. The runtime is the truth.*
