# SYNAPSE v5.43.0 — BLOCKS: deterministic scene setups

## Ask twice, get the same scene

Asking a model to author a Solaris network is sampling, and a sampler is not a
function — the same request produced a different graph every time. **BLOCKS** moves
canonical setups out of generation entirely. A **fixture** is a scene setup stored
as data — node types, exact names, wires, positions, parm values. The operation is
*reconcile to the definition*, not *create*. Ask twice and the second call is a no-op;
delete it and ask again and you get the same scene, byte-for-byte.

## What's proven

Fifteen checks green, headless on Houdini 22.0.368 — seven negative controls that
show each instrument *can* disagree, run before any invariant, then eight invariants:

| | claim |
|---|---|
| **F-1** | apply on a clean stage reproduces the committed baseline `762e3a85`, byte-exact |
| **F-2** | apply → remove → apply gives the same hash |
| **F-3** | apply on an applied stage does nothing — 0 ops, hash unchanged |
| **F-4 / F-4b** | an artist node outside the box keeps every authored property; a display transfer is reported by name, never silent |
| **F-5** | a name clash refuses with zero mutations, stage signature identical across the call |
| **F-6** | **cross-machine portable** — the same fixture hashes identically from two different `$HIP` values |
| **F-7** | a stray node dragged into the box is ejected and left alive, never deleted |

Reproduce: `hython harness/blocks/invariants_m5.py`

Suite: **5765 passed, 9 failed, 147 skipped** — the 9 failures pre-exist BLOCKS and
are unchanged in identity and count. **+20 tests** net from M5 to M5b, all new and passing.

## The baseline is machine-portable

The composed USD stage carries **expanded** environment paths — `$HIP` arrives as an
absolute path on 242 of 643 lines, one of them buried mid-string in a query parameter.
The `c3` canonicalizer rewrites absolute-path-valued environment variables back to their
token, so the same fixture produces the same hash on any machine. It rewrites *only*
absolute paths — `$HIPNAME` expands to the bare word `untitled` and `$OS` to the node
name, and substituting those by value would corrupt real scene content. Proven in both
directions: identical under `c3` across two working directories, different under the old
`c2`. The prior `c2` baseline (`8bb05761`) is recorded in the fixture with the reason it moved.

## Four silent failures the harness caught

- **Node types are versioned.** `createNode('domelight')` yields `domelight::3.0` —
  comparing against the plain literal never converges, so every apply planned a
  delete-and-recreate. The stable identity is `nameComponents()[2]`.
- **Create auto-renames silently.** `createNode`, `createNetworkBox` and `setName` all
  rename on a clash and raise nothing — which is why the collision gate must run *before*
  creation, since afterwards the scene is already mutated.
- **`NetworkBox.destroy()` keeps its members** by default. Removal would have orphaned every node.
- **A parm's authored value is `unexpandedString()`, not `eval()`.** The camera's default
  primpath `/cameras/$OS` evaluates to exactly what the fixture declares — comparing on
  `eval()` reports "already correct" and never writes the literal.

## Phantom-API gate, closed wider than expected

The committed Houdini symbol table was regenerated on 22.0.368 (**35903 symbols**; five
symbols stamped for 22.0.397 that do not exist on this build were removed) with a
load-time build check. Regenerating it surfaced a larger hole: an uninjected in-Houdini
process was silently serving **H21** symbols as authority on an H22 host, with no
staleness signal. Closed by making the Houdini environment a host-agnostic source of the
running build.

## The evidence harness underneath (AUTORESEARCH)

Three tiers: Claude orchestrates, a local model authors and triages questions through
ollama at zero API cost, hython executes probes deterministically. The model may author
**questions**; only probes produce **answers**, and proposed missions pass a literal
fence plus schema validation before they can run. First campaign: 55 answers, 0 failures.
It confirmed four dead H22 literals with live successors mapped, caught
`karmarenderproperties` deprecated one step before it entered the fixture, and found
Houdini stamping session node IDs into composed USD — the canonicalizer rule without
which cross-session determinism was impossible.

## Not done

No phrase routing (M6) — both tools take a fixture name; typing "basic Solaris setup"
resolves to nothing yet. No panel surface for the verdict line. No USD `customData`
(RFC-gated). `solaris.basic` remains the only fixture.

---

**Full changelog:** https://github.com/JosephOIbrahim/Synapse/blob/master/CHANGELOG.md
