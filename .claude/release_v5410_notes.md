*2026-07-31: v5.40.1's deferred list closes and the #1 failure class (phantom APIs) gets a standing housecleaning harness.* **5,336 tests passing, 0 failures, 137 skipped** (+6 vs v5.40.1) · local Windows suite · Houdini 22.0.368

- **The lying SessionStart "connected" is gone** (P3.1) — health claims now require a real bridge ping; the false-positive that armed the v5.40.1 chat-freeze class
- **Websocket cancel reaches mid-frame** (P3.3) — closes v5.40.1's open list; cancel-aware recv loop, 0.46s deterministic in tests
- **CI re-greened** (P3.2) — `mcp==1.26.0` pinned against the `list_tools()` drift that reddened every PR since 2026-07-29
- **CLEAR work-clearance harness ships** (`harness/clear/`) — latency-relay files committed, decisions board fresh, CHANGELOG backfilled v5.34.0–v5.40.0. Bar: 5 PASS / 3 FAIL honest (the 3 are human gates by design)
- **PHANTOM SWEEP harness ships** (`harness/phantoms/`) — house-cleaning for phantom APIs across source/docs/corpus: inventory → h22 symbol-table assay → KEEP/FIX classification → ledger + crucible ledger-attack. Read-only by construction; fixes human-gated. First run caught the corpus re-teaching the `usdrender` phantom in 14 files (fix branch in review, thrice-attacked SOUND) and root-caused `hdefereval` as the sixth headless-blind module

**In review, not in this release:** `clear/l5-phantom-scanner` (pdg/pxr scanner extension, 24 tests) and `fix/corpus-usdrender-rop` (14 commits). Quarantine candidates + hdefereval allowlist proposal: `harness/phantoms/QUARANTINE-PACKET-2026-07-31.md`.

---

### Since this tag

*Updated 2026-08-01 (evening). Nine PRs (#51–#59) merged to master since the v5.41.0 artifact; none of it is in this tag. Suite on master: **5,399 passed / 0 failed** at `a66a8cd`.*

**The freeze work** — [#52](https://github.com/JosephOIbrahim/Synapse/pull/52) shipped the h7 inline guard (a pre-flight-heavy payload is refused when dispatched on the Qt main thread — the only mechanism that can work, since a running payload cannot be interrupted) and fixed the thread-attribution defect that had been corrupting freeze forensics. A follow-up recon then **overturned the chunking plan**: the 10,005 ms figure was a timeout constant, the 46.7 s "stall" contained three recoveries, and the real per-op cost is the bridge running `stage.Flatten().ExportToString()` twice per stage-touching op with its size gate defaulted off. Class 1 remains MITIGATED; the ranked next steps live in `docs/reviews/freeze-class1-recon-2026-08-01.md`.

**The RSI closure harness** — [#51](https://github.com/JosephOIbrahim/Synapse/pull/51) built `harness/rsi/` (ladder L0–L5 with the new **L1 HONEST** rung below reachability, 9-predicate self-updating bar, all-harness `progress.py` board). #55–#57 made all three dishonest reward signals honest — every first fix was incomplete and every crucible caught it. [#59](https://github.com/JosephOIbrahim/Synapse/pull/59) executed the first genuine **subtraction**: loops A2 and F retired (mechanisms deleted, tombstoned entries retained), and **S refused** — its dormancy evidence was false at HEAD; the crucible ran the production entrypoint and got `ledger deposits: 16 ok, 0 failed`. Registry: 9 entries, 7 live, 2 retired. Closure scoreboard, stated honestly: **0 of 9 loops beneficial** — L1 is a precondition, not a victory.

**The decisions board can finally go down** — [#58](https://github.com/JosephOIbrahim/Synapse/pull/58) gave the 289-item board its missing closure mechanism (evidence-carrying `resolved.json`, flywheel items structurally refuse the channel). First use: 289 → 286.

**Ops** — [#53](https://github.com/JosephOIbrahim/Synapse/pull/53) detached-HEAD CI tolerance; the phantom-API symbol table regenerated against the live build (`22.0.397`, 35,908 symbols — the gate had been silently down); worktrees pruned 23 → 17.

**Open on the human side:** `workflow` OAuth scope (blocks the `fetch-depth: 0` CI fix + one unbacked branch) · C-substrate ratification (`harness/rsi/briefs/`) · the `repair/fake-hou-residency` divergence.
