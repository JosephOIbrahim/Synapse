# SYNAPSE Post-Mortem — First Principles, Demo-Ready Hardening Path

**Date:** 2026-08-18 · **Base:** v5.53.0 (459f2181) · **CTO:** Joe + Claude-as-CTO
**Method:** House-cleaning pass on the last wave → swarm (1/8 scouts landed; 9/10 agents died on provider 429) → remaining domains swept directly by CTO. Every finding below carries evidence or is marked UNKNOWN.

---

## Executive Summary

SYNAPSE's **spine is healthy**: the version chain is green on all six surfaces, the public-face gate does its job, 6,932 tests collect clean, the panel is a real product surface, and the memory substrate (Moneta) is genuinely wired. The release train has **good instruments** — the very problems it was built to catch (a stale public-face claim, version drift) are now caught automatically.

The damage is on the **edges**: the runtime that runs the harness is not the runtime the code pins (Python 3.14.2 vs the vendored 3.11/3.13 wheels), the **changelog** is 13 releases behind and outside the release ritual, **~28 stale worktrees** clutter the repo, and **evidence artifacts** (probe outputs, receipts) live untracked where a crash loses them.

**The one true demo-killer is not in the code — it's the environment.** A live demo that boots Houdini 22.0.400 with a mismatched Python host, or a bridge that goes quiet mid-chat, is what breaks. The rest is production hardening.

---

## What's working (evidence-backed)

| Area | State | Evidence |
|---|---|---|
| Version chain | **Green** — all 6 surfaces agree at 5.53.0 | Verifier exit 0; VERSION / `__version__` / pyproject / docstring / CLAUDE.md / README all read 5.53.0 |
| Public-face gate | **Green** — newest tag == banner == VERSION | `.synapse/contracts/reach-public-agreement.yaml` all `passing: true`; `git describe --tags` = v5.53.0 @ 459f2181 |
| Test suite | **Collects clean** | 6,932 tests in 10.1s, no collection errors |
| Panel | **Real product** | 15+ modules (`panel/`), single source of UI truth; legacy `ui/` tree gone |
| Memory | **Moneta is live** | `moneta_runtime.py`, `moneta_store.py`, `consolidation.py`, `embedding.py`, `sqlite_store.py` all present |
| Phantom-API guard | **Fresh table exists** | `h22_symbol_table.json` regenerated Aug 9 (1.3 MB) — my earlier "stale 21 table" claim was **wrong**; the survivor-table finding needs re-examination, not acceptance |

---

## The demo-killers

### D1 — The runtime is not pinned (environment drift, unguarded)
**Finding:** `python` on this seat resolves to **3.14.2**. The pinned Houdini runtime (22.0.400) embeds **3.13**. `pyproject.toml` says `requires-python = ">=3.9"` — a floor, not a pin. The vendored SDK ships cp311+cp313 wheels, which are **INACTIVE** on 3.14.2. A verify/probe run logged "this interpreter is Python 3.14.2" with a RuntimeWarning about the ABI mismatch — and still "succeeded".
**Why it's a demo-killer:** a clean machine, or a colleague's machine, or a CI leg, boots a different Python than the one the artifacts were built against. Silent ABI mismatch = phantom behavior on the demo floor.
**Fix (P1):** pin the harness runtime (`.python-version` + a hard version gate in the verify harness + a CI leg on the pinned version). Everything else is downstream of "which Python am I actually on?"

### D2. Undo guarantees are grouping-only, and two paths have two safety surfaces
**Finding:** `hou.undos.group()` groups, it does **not** auto-rollback on exception — a partial network survives and the artist must Ctrl+Z deliberately (verified live in prior legs; the bridge wraps every op, the live `/synapse` path wraps only a tracked subset). `execute_python`/`execute_vex` run **ungated** on the live path (full `__builtins__`). The `/mcp` bridge path has consent gates; the live path does not. This is **documented honestly** — that's the good part. But for a demo, an operator pressing Enter on the panel has no consent wall.
**Fix (P2):** ship the already-built worker-policy allowlist with the panel live (it's currently OFF by default), and make the undo-group entry point guarantee a *single* Ctrl+Z reverses a full panel op, everywhere.

### D3 — Changelog is 13 releases behind and outside the ritual
**Finding:** `CHANGELOG.md` has v5.53.0 then jumps to v5.41.0. **13 tags** missing (v5.42.0–v5.52.0, incl. patches v5.44.1/v5.45.1) plus 14 pre-v5.16.0 tags. The v5.53.0 entry discloses the gap honestly — the ritual touches the 5 version-chain files, not the changelog.
**Fix (P2):** make the changelog a 7th surface in `scripts/sync_version.py`, backfill once from the tag commits.

---

## The hardening path (by leverage)

| # | Priority | Item | Area | Who |
|---|---|---|---|---|
| 1 | **P1** | Pin the harness runtime (`.python-version`, version gate in `harness/verify/`, CI leg) | Harness | CTO+agents |
| 2 | **P1** | Land the worker-policy allowlist as default-ON (consent posture DECIDE) | Execution safety | Human gate (GATE-OFF is gated on Joe's consent posture) |
| 3 | **P2** | Extend `sync_version.py` surfaces to include `CHANGELOG` + README "New in"; backfill 13 entries | Release | agents |
| 4 | **P2** | Clear the stale worktree fleet (~28 merged; 3 carry uncommitted work — `w5-undob`, `wa1-xref`, and one more — inspect before remove) | Repo hygiene | CTO command, Joe's word to remove |
| 5 | **P2** | Resolve the 13 orphaned probe files in `docs/` (gitignore + relocate to `harness/notes/h22/probes/`, or delete) | Evidence | CTO |
| 6 | **P3** | Delete `harness/finalize.ps1` (stale, hardcoded v5.35.0 — 11 refs; a trap for anyone following the old ritual) | Release | CTO |
| 7 | **P3** | Unify release-notes location (2 dirs, 6/13 missing); enforce naming | Release | agents |
| 8 | **P3** | Verify current CI status (matrix = ubuntu/macos × 3.11/3.14; the "mcp list_tools CI red" claim needs re-check — code now uses the `@server.list_tools()` decorator at `mcp_server.py:1067`, not a call) | CI | agents |

---

## UNKNOWN / needs verification

- **Current CI green/red state** — local suite is green; the historical mcp-server red claim (since 2026-07-29) could not be confirmed without running the action. `git log` shows releases passing, but CI and release are independent surfaces.
- **The scout symbol-table "staleness"** — I over-stated this during house-cleaning. The 22.0.400 table exists and is fresh (Aug 9). What is stale is *any code still loading the 21 table* — needs a grep before claiming.
- **Moneta vector recall** — write-only index known; recall→RAG seam exists (`handlers_memory.py::_augment_with_knowledge`) but end-to-end recall behavior unverified this session.

---

## Swarm honesty

The post-mortem swarm (8 domain scouts + synthesis + crucible) hit the **same provider 429 wall that killed REACH P1**: 9 of 10 agents died on "extra usage auto reload monthly max reached." The structured-refusal layer worked — no fabricated green, no invented findings. One scout (release/versioning) ran to completion with 7 evidence-backed findings — all absorbed above. I then swept the other 7 domains directly (read-only). The 429 wall is itself a **post-mortem finding for the harness** — subagent-heavy runs need a smaller fanout at the margin.

---

## House-cleaning disposition (executed)

| Action | Files | Verdict |
|---|---|---|
| Deleted (transient) | 28: empty `.err`, dead `.pid`, `*.landed.flag`, watcher `.ps1`, `steward.pid`, `rr2.err`, 4× merge-proof, wa1 preview diff | gone, safe (all orchestrators confirmed dead first) |
| Deleted (duplicate) | `harness/notes/h22/union/` — byte-identical copy of committed `harness/autoresearch/` | gone, nothing lost |
| Kept | `harness/notes/h22/v5520-notes.md` | intentional wave retrospective |
| Flagged (not deleted) | 13 orphaned probe files in `docs/` | decision in path #5 above |
