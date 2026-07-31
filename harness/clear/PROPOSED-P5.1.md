# PROPOSED CLEAR Predicate P5.1 — no table-proven phantom hou/pdg/pxr in cleared work

Status: **proposal only.** SPEC.md and verify.py are untouched. Nothing here is ratified.

## Predicate text

Every python line shipped as part of the cleared work contains no `hou.<attr>`, `pdg.<attr>`,
or `pxr.N.<attr>` attribute access that the live introspected symbol table proves absent on
the target Houdini build.

## Proposed PASS / FAIL rule

**FAIL** if the scanner produces any table-proven absent symbol inside the predicate's scope
(scope defined by the CLEAR line itself — see limitation v).

**FAIL if the gate is down.** Table missing, blake2b integrity mismatch, stale build stamp,
or scout loader returning `table_syms = None` → **FAIL**, not WARN. "Couldn't verify no
phantoms" is not "no phantoms." A clearance that can't run its own membership check never
happened.

**PASS** otherwise.

## Ratification precondition — expected-build injection is mandatory

The "stale build stamp → FAIL" rule above **does not bite** when CLEAR's verify.py loads
the scout table **outside a host-injected process** — and that is exactly the CLEAR
scenario (a harness-side gate, not the MCP server). Crucible-verified on
`python/synapse/cognitive/tools/scout.py`:

- `_PKG_SYMBOL_TABLE` defaults to `data/h21_symbol_table.json` (scout.py:138).
- `_running_major()` returns `""` outside Houdini (no `hou`, no injection), so
  `_symbol_table_path()` falls back to `_PKG_SYMBOL_TABLE` — the **H21** surface.
- The stamp check (scout.py:519) falls back to `_pkg_table_version()` when
  `EXPECTED_HOUDINI_VERSION` is unset — that is **the loaded table's own stamp**, so the
  check self-satisfies: the gate reports UP, verified against H21, with no FAIL trigger.

Measured consequence at the scanner's judged depth: **152 pxr depth-2 symbols are
h22-only** (e.g. `pxr.Sdf.AssetPathArrayEdit`) → 152 false-FAIL vectors on legal H22 work;
**24 pxr symbols are h21-only** (e.g. `pxr.Ndr.DiscoveryUri`) → 24 false-PASS vectors
against an H22 target.

Therefore, ratification carries a real implementation requirement, not just the predicate
text: **P5.1's implementation in CLEAR's verify.py MUST set
`scout.EXPECTED_HOUDINI_VERSION = <the SPEC's target build (currently 22.0.368)>` before
calling `_load_symbol_table()`** — or equivalently assert
`status['houdini_version'] == <target>` after load and FAIL on mismatch. Without that
injection the "stale build stamp → FAIL" line above is decorative in the no-injection case:
the loader self-satisfies and the gate verifies against the H21 surface while believing it
judges H22. Say so explicitly because the current text reads otherwise.

## Rationale — why CLEAR holds a harder bar than the per-sprint WARN gate

The per-sprint guardrail (`check_phantom_clean`) WARNs on gate-down because a broken
membership authority should never *stall* in-flight work — it would weaponize a harvester
hiccup into a work stoppage, and the sprint continues with human oversight anyway.

CLEARance is the opposite posture. It's the last gate before work is declared shipped and
forgettable. Whatever a CLEAR says PASS on stops being watched. A phantom API is SYNAPSE's
#1 historical failure class — `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`,
`hou.updateGraphTick()` — and the whole point of the introspected table was proving it
belongs to runtime membership, not training memory. If the authority that makes the verdict
*meaningful* is absent, the honest verdict is refusal, not benefit-of-the-doubt. WARN at
this bar would launder "unchecked" into "cleared."

## Why the authority is trustworthy enough to gate on

Verified live by the L5 scout legs against `python/synapse/cognitive/tools/data/h22_symbol_table.json`:

- Stamp **22.0.368**, **35,903 symbols**, schema `scout_symbol_table/v1`, per-major file
  (`h<major>_symbol_table.json` per running Houdini major).
- **blake2b integrity digest** — verified FRESH on this repo; a mangled or stale file is
  refused by the loader, not silently trusted.
- Membership by introspected `dir()`, never a denylist (the Spike 2.5 demotion that took
  false-phantom rate 0.667 → 0).
- `pdg` covered to depth 2 (`pdg.EventType.CookComplete`, `pdg.GraphContext.addEventHandler`).
- `pxr` covered one level under every lazy namespace (`pxr.Usd.Stage`, `pxr.UsdLux.*`,
  `pxr.Gf.*`) — the harvester force-imports via `pkgutil.iter_modules`
  (`host/introspect_runtime.py:~105`), so lazy namespaces are structurally present, not
  luck.
- Smoke run over **39 production import sites** (all `import pdg` / `from pxr import …`
  files) against the real table: **zero false positives.**

## Known limitations (stated, never hidden)

1. **Membership ≠ constructability.** `pdg.PyEventHandler` is in the table (dir-true) but
   has no constructor on 22.0.368 ("TypeError: No constructor defined" — §1.7). The scanner
   cannot catch it and never will with a membership oracle. The doc rule remains the
   binding defense. *Follow-up proposal (not this leg): a constructability quarantine table —
   symbols proven non-instantiable, probed per build.*
2. **String-indirected access is invisible.** `getattr(Usd, "Prim", None)`
   (`shared/bridge.py:1995,2037`) hides the attribute name in a Constant. AST membership
   scanning never sees it — by design, deliberately not a getattr rule this leg (bounded scope).
3. **Depth-1 / namespace-depth-2 judging only.** `hou.Class.method`,
   `pdg.EventType.CookComplete` (the member under `EventType`), and anything deeper is
   unknown-to-the-table, and unknown is not phantom. The outer known prefix is what's judged.
4. **pxr completeness depends on the harvester's pkgutil force-import.** Structural today:
   re-harvest happens inside the live build's python. A mangled harvest environment could
   degrade the pxr surface. The tripwire is exactly the gate-down-FAIL rule above: blake2b
   + stale-stamp refuse, so the table can only be trusted or refused, never degraded quietly.
5. **Scanner scope at CLEAR needs its own definition.** The per-sprint gate judges only
   *added lines* since the fork point (so pre-existing debt never blocks the sprint). CLEAR
   should define its own scope explicitly — e.g. "all .py in the cleared changeset" vs.
   "added lines only" — and that choice belongs to the SPEC side when this is ratified.
   This proposal takes no position; it only insists the scope be *named* in the predicate,
   not left implicit.
6. ~~Relative pxr imports falsely bind the namespace~~ — **fixed after the crucible review.**
   `from .pxr import Usd` (a package-local relative import, `ast.ImportFrom.level > 0`)
   used to register `Usd` as a pxr namespace, so `Usd.<anything>` was judged against the
   USD surface. The binding branch in `harness/verify/checks.py:_phantoms_in_source` now
   requires `level == 0`, pinned by
   `test_pxr_relative_import_does_not_bind_pxrsurface` (`from .pxr import Usd` +
   `Usd.MadeUp` produces no flag). Zero production exposure: no repo file uses a relative
   `from .pxr import …`.
