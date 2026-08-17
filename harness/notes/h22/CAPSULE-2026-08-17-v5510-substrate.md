# CAPSULE — 2026-08-17 — v5.51.0 shipped · substrate crucible team live

**For tomorrow-you.** Chunk boundary after the release session (evening 08-16 → morning 08-17).

## Where we are
**v5.51.0 "Close the tab, keep the session" is PUBLISHED** — Latest on GitHub, tag cut, six surfaces
CONFORM, CI green. Ritual g1–g9 walked at Joe's seat, all receipted (`harness/state/release_receipts.json`).
Master = origin = `89c50421`. The ONE open thread: substrate quartet (CATALOG · PARMGATE · MEASURES · WCRUX)
unmerged, gated on the sharded crucible now running.

## Shipped this session
- Waves merged: W5L+parity (yesterday), **W6 hardening** (5 gates WIRED: QUOTE injection-kill,
  PROV fail-closed, BEAT behavioral beat, GATE receipt==HEAD+RELEASE close-gates, FORGE ledger),
  **W6 flow** (journey map, rig, 2 pinned fixes), one R135 close-pass recorded openly.
- **W7-SESSCOPE** (driver-direct, 7 pins): boot-scoped sessions — close/reopen reattaches,
  new Houdini boot parks previous work, `/restore-session` restores. Live-GUI feel = Joe's
  10-second check still open.
- Release chain: bump → verify (R.R honest RC, v5.50.0 precedent shape) → tag → publish.
- Overnight arc (archived `CTO-RULING-measures-divergence-2026-08-16.md` + supersession):
  first MEASURES agent diverged → ruling caught it → resurrected agent DELIVERED the
  cook-verify charter (`520a10d4`, receipt-is-closing-commit, GATE-verified close).
- Parity re-proof TODAY: 7/7 green under hython 22.0.400, local panel byte-identical with
  pushed HEAD incl. SESSCOPE (`harness/probes/parity_modules/results.json`).
- README mermaid updated (SESSCOPE + close-gate edges); prompts regenerated clean.

## Live right now (may be dead by the time you read)
- Shard team on `wave5l.live.json` (25 legs): **W5-WXA** (contracts re-exec) · **W5-WXB**
  (goldens + tier) · **W5-WXC** (history/mandates/F-VER plan) → **W5-WCRUX synthesizer**
  (deps all three, one writer, flag `w5m-landed.flag`).
- Sentries: orchestrator pid file `orchestrator-w5l.pid`, steward `steward.pid` (10h deadline).
- KNOWN SEAM: WCRUX board state is zombie-"running" from the killed solo; if orchestrator
  doesn't clear it when shards land, re-fire `%TEMP%\orch_W5-WCRUX.ps1` (reads the NEW
  synthesizer prompt). Liveness gap (running+dead invisible) = docket, GATE covers closing only.

## The next act (Joe words, in order)
1. WCRUX verdict toast → digest → **merge word** (quartet, cross-merge F-VER reconcile per
   shard-C plan: branch VERSION 5.50.0 vs tag — likely `sync_version --write` post-merge).
2. Post-merge: substrate line appended to published v5.51.0 notes (`gh release edit`).
3. **Teach-down DEBT (owed, twice-queued):** three-wave + release + SESSCOPE teach-down and
   Operator's Card update — deliver before any new wave authoring.

## Docket (cold rulings, fresh session)
~31 ruling items banked in receipts, plus named: F-G9-ROLLBACK (SideFX libUI icon-paint segfault
on uninstall + stale desktop — file SideFX report; ship uninstall hygiene) · F-PCRUX-1 (PARITY
RELEASE overclaim) · 8 historical closing-holds (backfill or waive RELEASEs) · S1 MCP DISCLOSURE
wiring (MEASURES deferred follow-on) · `docs/*.json` Phase-0 debris (delete/file after CATALOG
merges) · steward v2 filter (exclude "HEAD is now at" lines) · flags tracked-vs-ephemeral mixed ·
launcher/installer zombie (kill word never given; re-check liveness) · old worktree+branch
graveyard (w2–w5 era, ~50 worktrees with stray receipts) · rich re-render on /restore-session ·
SESSCOPE live feel check · Wave 6 SQLite+FTS5 authoring · domain waves A–E (gated on substrate).

## Hard-won this chunk
- DC 4-min tool ceiling: long verifies MUST detach (`Start-Process python -Redirect*`), poll the log.
- Windows-MCP vision unusable on this rig (6016×3384 > 1MB tool cap); text Snapshot shows
  4 virtual desktops (Michealangelo/Raphael/Leonardo/Donatello) — agent windows scatter across them.
- Dead-leg resurrection: temp runner `%TEMP%\orch_<LEG>.ps1` re-fire into the same worktree works;
  runner reads the prompt file at launch (new briefs ride).
- Orchestrator state derives receipt-existence; running+dead = invisible zombie (twice now).
- Enumerated-approval jurisprudence: pasted list + "I approve" = valid batch word; blanket
  "preapproved as CTO" ≠ P4 seam coverage; approval-as-closing-word recorded WITH caveat, then
  regrounded via observation×proof chain (g9 receipt pattern).
- `gh release edit --draft=false` publishes; untagged-URL rotates per edit; drafts invisible publicly.
