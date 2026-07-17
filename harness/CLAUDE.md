# CLAUDE.md — SYNAPSE conventions

Keep this short. Short = cached = cheap. Conventions only, no history.

## What this is
SYNAPSE is an agentic Houdini plugin: plain-English prompts → real Houdini work (COPs
networks, Solaris/USD set-dressing, Karma renders), every action **reversible and recorded**.
The differentiator vs. Houdini's native MCP is the receipts. Protect that.

## Survival rule (the one that fails silently)
The brain must wake up regardless of Houdini's Python version. **Default architecture:
sidecar** — brain in its own pinned interpreter, panel/host on Houdini's. Never assume
cp311; the embedded version is whatever the live interpreter reports.

## Hard conventions
- **Provenance or it didn't happen.** Any scene/stage mutation is undo-wrapped AND written
  to `agent.usd` with `decision` + `reasoning` + `revert` path. No ledger entry ⇒ incomplete.
- **Probe truth > pinned constants.** Where the probe reports API drift, use the
  live-introspected op. Never hardcode an H21-era constant the probe flagged.
- **One source of UI truth:** `panel/`. The legacy `ui/` tree is dead — never add to it.
- **One source of version.** `VERSION` is canonical; `pyproject.toml` and the demo script
  follow it. Don't edit `VERSION` from an agent.
- **Reach tools by verb × context** (texture, scatter) × (COP, LOP) — palette, not buried menus.
- **No hardcoded user paths.** Install must work via the package on a clean machine. The
  `C:\Users\User\SYNAPSE` fallback is a bug, not a convenience.

## HDK / C++ grounding

HDK answers and compiled-code work are grounded in the **installed toolkit
for this repo's pinned Houdini version** — never in training memory or
generic documentation. This is the C++ face of the repo's phantom-API rule:
runtime truth beats priors. Headers are the C++ runtime.

**Pinned version:** `harness/state/drop.json` (`houdini_build`) — the drop
record the harness keys MODE on; referenced here, never restated as a number.
Absent that file (pre-drop / clean clone), the live interpreter is
authoritative (step 3 below).

### Resolve the toolkit (in order, stop at first hit)

1. `$HFS` — if set, the toolkit is `$HFS/toolkit`
2. Platform defaults, filtered to the pinned version:
   - Windows: `C:\Program Files\Side Effects Software\Houdini <version>`
   - Linux: `/opt/hfs<version>`
   - macOS: `/Applications/Houdini/Houdini<version>/Frameworks/Houdini.framework/Versions/Current/Resources`
3. Live session connected → `hou.getenv("HFS")` over the wire is
   authoritative
4. Nothing found → **say so and stop.** Do not answer HDK questions from
   memory.

Toolkit layout: `include/` (the actual API) · `samples/` (working code) ·
`cmake/` (build config — `find_package(Houdini)` via
`$ENV{HFS}/toolkit/cmake`)

### Rules

1. **Version match is a gate.** Toolkit version must equal the pinned
   runtime version. Another installed version is not a substitute — a
   symbol present in one version's headers is a phantom in another. Flag
   mismatches; never silently substitute.
2. **Grep before you cite.** Confirm any class, function, or enum exists
   in `toolkit/include` before using it — the C++ analog of `dir()`
   introspection for `hou.*`.
3. **Pattern-match to samples.** Find the closest example under
   `toolkit/samples` and follow its structure. Real, compiling code beats
   plausible invention.
4. **Build config comes from `toolkit/cmake`**, not generic CMake recipes.
5. **Compiled artifacts are per-version.** A plugin built against one
   version's headers is not assumed loadable in another — same failure
   class as the vendored ABI pins.
6. **Toolkit absent** → label all HDK claims as unverified inference per
   the truth contract, or request the install path. Never fabricate an
   API surface.

Nonstandard install? Set `HFS` in your environment — step 1 picks it up.
Nothing machine-specific belongs in this file.

## Commits
One atomic commit per sprint. `feat(area): <id> <what>` / `fix(area): <id> <what>`. Never
squash unrelated work. Never `git push` or `git merge` — promotion to main is human.

## When stuck
Write the blocker to `.claude/remediation_ticket.md` and stop. A clean stop beats a broken
guess; the Evaluator and the human gates exist for exactly this.
