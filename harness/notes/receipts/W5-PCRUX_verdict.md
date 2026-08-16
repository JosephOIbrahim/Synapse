# W5-PCRUX — parity crucible verdict

**Adversarial gate over the two parity probes (W5-PARITY + W5-SEAT). No verdict inherited.**

- Leg: `W5-PCRUX` · branch `wave5/pcrux` · base `1679a700` (master) · read-only (`touches: []`)
- Deps audited: `W5-PARITY` (branch `wave5/parity` @ `e70022bf`, product `10bd5495`) · `W5-SEAT` (branch `wave5/seat` @ `9bd16c01`, product `5a2f0bd4`)
- Method: both peer probes **re-executed from scratch** in this worktree under the real hython; every number below is first-hand from *this* leg's runs, cross-checked against the peer receipts. Peer receipts were read to know what was claimed, **never trusted as evidence**.

## Re-execution recipe (first-hand)

- hython: `C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe` — hou **22.0.400**, Python **3.13.10**
- prefs dir: `C:/Users/User/OneDrive/Documents/houdini22.0` (the live GUI seat's prefs)
- parity: `HOUDINI_USER_PREF_DIR=… QT_QPA_PLATFORM=offscreen hython probe_parity.py` → **EXIT 0**
- seat: `env -u SYNAPSE_ROOT -u HOUDINI_PACKAGE_DIR HOUDINI_USER_PREF_DIR=… hython probe_seat.py --expect-root C:/Users/User/SYNAPSE --out …` → **EXIT 0**
- probe provenance (my copies are byte-identical to the committed peer scripts):
  - `probe_parity.py` sha256 `11706300656d6728cd875df97c8084c4bb90440738283f80fa950db6ad1d7850` == `git show wave5/parity:…/probe_parity.py`
  - `probe_seat.py`  sha256 `9bca798dc49ff15534482cd209fe85cab5c61502f6a14ff8da1972d7caad2734` == `git show wave5/seat:…/probe_seat.py`
- first-hand outputs committed under `harness/notes/receipts/W5-PCRUX_reexec/` (parity/seat stdout + results, exec-fidelity probe + results, live GUI process capture).

## Target-by-target findings

### Target 1 — both probes re-executed with first-hand evidence; divergences enumerated → **PASS**

**PARITY re-run = green (7/7 acceptance pass).** Byte-exact agreement with the peer run:
- Section 0: hou 22.0.400; `HOUDINI_PATH` contains `C:/Users/User/SYNAPSE/houdini`; main-tree `python/` on `sys.path`.
- Section 2: glob **90** == **90** rows == 90/90 imported, `__file__` in repo, loaded from MAIN tree, `sha_match`, and **worktree bytes == loaded bytes** for all 90. Module-set identical to peer; **0** `loaded_sha256` mismatches across the two independent runs.
- Section 3 (exec/shim): flush evicted `synapse.__parity_sentinel__`=True, popped bare `synapse`=True, non-synapse control survived=True, widget `SynapsePanel` from `…/python/synapse/panel/synapse_panel.py`, `fresh_reimport`=True.
- Section 4 (behavior): R1 double-site at `synapse_panel.py:1950` + `:2091`; `next_font_scale(default,1.3)=1.3`, ladder `[1.3,1.4,1.6]`, never below floor; chat leading 176.0→188.0 = **+12.0px**; live `SynapsePanel._chat` carries the leading token.

**SEAT re-run = green_with_findings (3/3 acceptance pass; T5 gate PASS).** Every T1–T5 value matches the peer:
- T1 `SYNAPSE_ROOT=C:/Users/User/SYNAPSE`, `<repo>/houdini` on `hou.houdiniPath()`, producer `packages/synapse.json` present.
- T2 icon_count **7** (incl. `SYNAPSE_synapse.png`) + shelf all `hou.findFile`-resolve inside the repo.
- T3 shadow_count **0**, `find_spec` → `repo/python/synapse/__init__.py`, repo/python is the lowest-index **importable** provider (idx 7), metadata_shadows 0.
- T4 five 22.x builds → single `houdini22.0` prefs dir; probe ran under 22.0.400 (proven).
- T5 pypanel `hou.findFile`-resolved inside repo; flush block L37–L38; **0** shadow pypanels.

**Divergences enumerated (mine vs peer):** exactly one, cosmetic and expected — SEAT T3 lists a lower-index **non-importable** `synapse/` namespace dir at the worktree root, which is `…/w5-pcrux/synapse` in my run vs `…/w5-seat/synapse` in the peer run (I ran from a different worktree). It is not an importable provider; the winner (repo/python, idx 7) and shadow_count (0) are identical. No parity-affecting divergence.

### Target 2 — exhaustiveness attack → **PASS**

Independent glob = **90** by three engines (`find … -name '*.py'`=90, Python `glob.glob(recursive=True)`=90, bash globstar=90), matching the probe's glob (90) and row count (90). Decomposes exactly as 67 top-level + 8 `designsystem/` + 4 `manifests/` + 11 `providers/` — all three subpackages recurse in, each with a valid `__init__.py`. Module-set of my rows == peer rows (no only-mine / only-peer); no hidden dotfile `.py`, no symlinks, no `.pyc`-only modules. **No missed module.**

Two consumer footnotes (adversarial pass, HOLDS):
- **"exhaustive / 1:1 with repo / no missed module" is scoped to the panel subtree** — the panel's own **90** modules — **not** the panel's wider *execution closure*. `python/synapse/panel/tool_bridge.py:31-32` dynamically imports `mcp_tools_{scene,render,usd,tops,memory,cops}` which live *outside* the subtree, and `synapse.core.*` / `synapse.server.*` / `shared.*` are not byte-checked. The probe discloses this (`probe_parity.py:20-22`, `results.json s2_modules.scope`); restated here so the headline is not over-read.
- **"glob" means Python/find recursive globbing, not git.** `git ls-files 'python/synapse/panel/**/*.py'` returns only 23 (git wildmatch `**/` semantics catch subpackage files only) — a matcher quirk, **not** a real miss; the recursive filesystem glob is the correct 90.

### Target 3 — build question attack → **OBSERVED-LIVE (current seat = 22.0.400, reconfirmed); two residual gaps named below**

The peer seat probe declared the GUI-launch build UNKNOWN because it only inspected prefs/log artifacts (none bind a launch to a build — all 22.0.x share the one `houdini22.0` prefs dir). This crucible took an angle the peer did **not**: the **live process table**.

- **A Houdini GUI is running now:** `houdini.exe` PID **55056**, `ExecutablePath = C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\houdini.exe`, started **2026-08-16 2:25:35 PM**, bare interactive cmdline (no batch/`-foreground`/scriptfile args ⇒ interactive GUI, not a headless run). (Evidence: `W5-PCRUX_reexec/live_gui_process.json`; independently re-confirmed alive by the adversarial pass — same PID, same path.)
- That start time spans the parity/seat probe window (14:23–14:48), so the seat behind the "stale after relaunch" concern and the seat the probes measured are the **same live 22.0.400 session**. The parity hython (`…/Houdini 22.0.400/bin/hython.exe`) shares the install dir — hence the same `libHoudini` — as `houdini.exe`, so "the build the probes ran under == the current seat's build" is sound.
- Six hython builds are installed (`21.0.773` + five 22.0.x: `368/397/400/406/413`); a stray `houdini_launcher.exe` runs from `Launcher\22.0.368` — that is the launcher app version, not the session; the session is 22.0.400.

**Honest limits (why this is "observed-live", not "provably" absolute — adversarial pass, WEAKENED→folded):**
- The build binding is **perishable**: it is a point-in-time process fact, true for as long as PID 55056 lives. It legitimately answers the seat probe's T4 "Joe's GUI launch build" for the *current* seat — but it is not a permanent property.
- The SYNAPSE panel actually being *hosted inside* PID 55056 is **inferred**, not directly observed: it follows from `packages/synapse.json` sitting on the shared `HOUDINI_PATH` that any 22.0.x GUI scans. The parity/exec-fidelity panel proofs were produced in the **hython/offscreen** process, not read out of the GUI process. Build of the current seat = **known**; panel-in-that-seat = **inferred (safe, but unobserved)**.

### Target 4 — exec-fidelity attack → **PASS (independently verified with the crucible's own probe)**

The `.pypanel` loader runs via `exec()` in Houdini's panel context, where `__file__` is undefined (pypanel comment L19) and a `sys.modules` flush (L36–L38) forces a fresh re-import on every panel (re)open. Verified two ways:

1. The parity probe's Section 3 genuinely **execs the real CDATA** in a namespace with no `__file__` (not a plain import), plants sentinels, and confirms eviction + a `fresh_reimport` id change.
2. **This crucible's own instrument** (`W5-PCRUX_reexec/pcrux_execfidelity_probe.py`, run first-hand, EXIT 0) adds the adversarial contrast the peer did not: a plain `import` twice returns the **same object id** (cached — it would mask a reload), whereas the exec+flush path evicts a planted `synapse.*` sentinel, keeps a non-synapse control, and rebuilds `SynapsePanel` from the repo file with the module **id changed across the flush**. `__file__` is absent from the exec namespace before and after. Exec fidelity is real, not import-masked.

### Target 5 — mandate table (binary per leg)

| Check | W5-PARITY | W5-SEAT |
|---|---|---|
| Product HEAD exists **before** receipt write (CRX0) | **PASS** — `10bd5495` is ancestor of `e70022bf`; receipt states `product_head 10bd5495` | **PASS** — `5a2f0bd4` is ancestor of `9bd16c01`; receipt states `product_head 5a2f0bd4` |
| Receipt is the leg's **own closing commit** (named, = branch HEAD) (W5H) | **PASS** — `e70022bf` is `wave5/parity` HEAD, touches only `W5-PARITY.json` | **PASS** — `9bd16c01` is `wave5/seat` HEAD, touches only `W5-SEAT.json` |
| **RELEASE posted on the bus** (wave5l F2/F3) | **FAIL** — no `status`/RELEASE message from W5-PARITY exists in the raw bus store; only a `claim` + one `finding`→SEAT | **PASS** — `status` @ 2026-08-16T14:48:15, `RELEASE=true`, release[], receipt_head, product_head |

**Mandate finding (F-PCRUX-1):** W5-PARITY's receipt (`W5-PARITY.json:72`) asserts *"RELEASE posted on the bus"*, but the raw bus store (`harness/autorevise/bus/wave5/*.jsonl`) contains **no** W5-PARITY `status`/release message. This is a receipt overclaim of exactly the wave5l F2/F3 no-release class the mandate check exists to catch. It does not affect the parity *evidence* (which reproduces green), but the RELEASE mandate is **not** met for W5-PARITY.

## Every UNKNOWN, and exactly what Joe's seat must observe to close it

1. **UNKNOWN — will a *future* Houdini relaunch use 22.0.400?** The live seat is observed 22.0.400 *now* (PID 55056), but this binding is **perishable** (holds only while that process lives) and all five 22.0.x builds share the single `houdini22.0` prefs dir with nothing pinning a default — a later launch could pick 397/406/413/368. **To close:** launch Houdini explicitly from `…\Houdini 22.0.400\bin\houdini.exe` (or add a per-build launch marker in the prefs dir); a snapshot of `houdini.exe`'s `ExecutablePath` at that session confirms it.
   - **Sub-gap (inference, not observation):** that the SYNAPSE panel is *hosted inside* the running 22.0.400 GUI is inferred from the shared-`HOUDINI_PATH` `synapse.json`, not read out of PID 55056 (the panel proofs ran under hython/offscreen). **To close:** from the live GUI, in the panel's own Python, print `hou.applicationVersion()` + the panel module `__file__` — that ties build, panel, and repo path in one observation from inside the seat.
2. **UNKNOWN — live GUI close/reopen serves a fresh disk re-import (Joe's seat).** Headless proved the flush *runs* and forces a fresh re-import; a real long-lived GUI panel close→reopen was not exercised (GUI pixel/interaction is out of scope by mandate). **To close:** from the live seat, edit a `synapse.panel` module, reopen the panel, and confirm the edit appears with no Houdini restart. (Tracked by held spawn `W5-PARITY-LIVEREOPEN`.)
3. **Whole-closure byte parity is not claimed** (only the 90-module panel subtree). Not strictly an UNKNOWN — a deliberate scope boundary — recorded so "1:1 with repo" is not over-read. **To close if desired:** extend the parity glob to the panel's import closure.

## Adversarial pass (four independent skeptics)

Four independent skeptics (read-only, `general-purpose`) each tried to break one load-bearing conclusion. Run `wf_25d5c160-fa8`, 4/4 completed, 0 errors.

| Attack | Verdict | Outcome |
|---|---|---|
| **exhaustiveness** (90 == denominator, no missed module) | **HOLDS** | 90 reproduced by three glob engines; scope-to-panel-subtree footnotes folded into Target 2. |
| **live-seat-build** (current seat = 22.0.400) | **WEAKENED** | Core upheld — do **not** revert to fully UNKNOWN — but "provably" softened to "observed-live/perishable" and the panel-in-PID-55056 inference caveat added (Target 3). Skeptic independently re-confirmed PID 55056 alive. |
| **byte-parity-soundness** (0/90 loaded-sha mismatch is real, not cache/tautology) | **HOLDS** | Hashes read raw source (not `.pyc`); worktree vs loaded are genuinely distinct trees (worktree `python/` is not on `sys.path`, main `python/` is); 0/90 across three distinct trees. |
| **mandate-release** (PARITY missing RELEASE; SEAT has it) | **HOLDS** | SEAT release = bus `bus.jsonl` L77; PARITY = 0 releases across all waves; overclaim verbatim at `W5-PARITY.json:72`; commit ordering clean for both. Corroborating: PARITY's bus **claim is still OPEN** (never released) while SEAT's is closed. |

Net: three of four load-bearing claims survive unchanged; one (live-seat-build) is upheld in substance with its wording tightened, folded above. No claim broke.

## Verdict

- **Parity evidence:** independently reproduced, byte-exact — the design panel **is 1:1 with the repo** at the 90-module panel-subtree layer, and the seat resolves to the repo with zero shadows. The peer probes' technical claims **survive the crucible**.
- **Build question:** the live GUI seat is **22.0.400** (first-hand, not inherited from the peer's UNKNOWN); the probes exercised that exact build. Residual future-relaunch UNKNOWN named above.
- **Mandate:** W5-SEAT clean; **W5-PARITY fails the RELEASE mandate** and its receipt overclaims one (F-PCRUX-1).

**W5-PCRUX status: green_with_findings** — the parity pair's evidence holds under independent re-execution; the one substantive finding is W5-PARITY's missing bus RELEASE vs. its receipt claim. Merge of the parity probe artifacts remains Joe's word.
