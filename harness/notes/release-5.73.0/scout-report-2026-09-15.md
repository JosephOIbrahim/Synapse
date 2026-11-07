# SYNAPSE Status Report — 2026-09-15

Read at HEAD `85c8fe29` plus the in-flight v5.73.0 working tree. Two marks are used throughout: **[read]** = I re-read the cited path this pass and it says what the claim says; **[scout]** = the claim and its citation come from a scout finding handed to me and I did not re-read it.

---

## 1. Where this repo stands right now

SYNAPSE is a working Houdini agent panel with a real release train behind it, and it is currently mid-cut. Six branches merged through a CI-gated train; `VERSION`, `pyproject.toml`, `python/synapse/__init__.py`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `docs/getting-started/installation.md` all carry 5.73.0 **only in uncommitted working-tree copies** — HEAD's `README.md` banner still reads `tags: v5.72.0 is Latest` **[scout]**, no `v5.73.0` tag or GitHub release exists, and `docs/releases/v5.73.0.md:47-51` still holds five unfilled fill tokens (`@@STOCK@@ @@SEAT@@ @@INST@@ @@QUAL@@ @@PAYLOAD@@`) **[read]**. The release is not pushed, not tagged, and not published. One product file sits edited but unstaged — `python/synapse/panel/synapse_panel.py` — and the ritual's own staging list does not include it (§3, item 1). The cut has run once tonight (logs 19:04–19:16) and stopped.

---

## 2. What is verified working

These are structural facts a reader can check and rely on.

**The tool registry is real and its headline number is honest.** `python/synapse/mcp/_tool_registry.py:127` opens `TOOL_DEFS: list[tuple] = [` and closes at `:1743`; an AST count gives **137 entries, zero duplicate names** (synapse 56, houdini 41, tops 19, cops 21) **[scout]**. `README.md:159` **[read]** defines the number correctly: *"The count is `len(TOOL_DEFS)` in `python/synapse/mcp/_tool_registry.py`, pinned by `tests/test_phase0c_doc1_toolcount.py`."*

**The panel that ships is the panel that's tested.** `houdini/python_panels/synapse_panel.pypanel:56` does `from synapse.panel.synapse_panel import onCreateInterface as _build`, and `packages/synapse.json` sets `hpath: "$SYNAPSE_ROOT/houdini"` — so `python/synapse/panel/synapse_panel.py` is on the artist-facing path, not dead code **[scout]**.

**The installer is a real, bounded, per-user install.** `installer/windows/Synapse.iss:26` `PrivilegesRequired=lowest`, `:24` `DefaultDirName={localappdata}\Programs\SYNAPSE`, two AppIds selected by `#ifdef TestBuild` at `:19` **[read: :24/:26]**. Every Houdini-facing action is delegated to a bundled `python -I setup_cli.py` engine (`:96-103`), and `:241-244` refuses a silent install without explicit `/HFS` and `/PREFS`. Its unit surface is 37 test functions (26 in `test_adversarial.py` + 11 in `test_lifecycle.py`), matching the recorded `37 passed, 1 warning in 6.38s` **[scout]**.

**The pending-tool mechanism is built and holds nothing.** `_tool_registry.py:1760` `PENDING_TOOL_DEFS: list[tuple] = []` **[scout]** — parsed empty. The exclusion from `TOOL_DISPATCH`/`TOOL_JSON`/`TOOLS_LIST_CACHE`/`TOOL_NAMES` is real; there is simply nothing in it. Dormant infrastructure, not a gate withholding a tool.

**One honesty marker is accurate and has not gone stale.** `rulebook/surfaces/` contains only `.gitkeep` and `scripts/rulebook_harvest.py` does not exist — both **[read]**: a `Glob` of `rulebook/surfaces/**` returns exactly `rulebook\surfaces\.gitkeep`, and a `Glob` for `scripts/rulebook_harvest.py` returns nothing. The fallback authority the same section names is present. Reported because a sweep that only lists stale markers cannot tell "checked and clean" from "not checked."

**Shape, for orientation.** 529 test files and 7800 `def test_` functions; 490 of those files and roughly 96% of the functions sit in the flat root `tests/` tree, against `tests/panel` (31 files / 170 functions), `tests/solaris` (6/128), `tests/rsi` (1/10), `tests/rulebook` (1/7) **[scout]**.

---

## 3. What is at risk or wrong, ranked

### CRITICAL — the cut cannot reach tag, and the reason may have changed under us

**Read this item before acting on any of the ship-path findings below.**

The scout's ship-path verdict was: `step_compose`'s copy-forward is entirely dead — four `str.replace` searches that each match **zero** occurrences in the source they copy — so the composer for v5.73.0 is a byte copy of v5.72.0's, still pointed at `C:/synapse-build/output-5.72.0`, and `compose` therefore cannot complete **[scout]**. I re-read `harness/notes/release-5.73.0/cut.py` this pass and **that is no longer what the file at that path does.**

What I read at `:375-439` **[read]**:

- `src` is derived from `PREV`, never a literal: `os.path.join(REPO, "harness/notes/release-%s/compose_assets.py" % PREV[1:])` (`:380`).
- Two replacements derived from `PREV`, each preceded by a guard that **raises** if the search string is absent — `SystemExit("STOP: the composer copy-forward cannot find %r in %s … Do not tag.")` (`:409-414`).
- A third guarded replacement for the stock-suite scope string (`:429-437`).

The un-guarded, hardcoded four-replace version the scout describes **does** exist — at `harness/notes/release-5.72.1/cut.py:333-336` **[read]**:

```
read(src).replace('VERSION = "5.72.0"', 'VERSION = "%s"' % V)
         .replace("release-5.72.0", "release-" + V)
         .replace("output-5.72.0", "output-" + V)
         .replace('"v5.70.0"', '"%s"' % PREV)
```

Every ship-path citation in the scout's set lands at a *lower* line number than the same content in the tree's file, and the offset grows down the file: hytest call quoted at `:336`, read at `:355` **[read]**; stock-suite stop quoted at `:344`, read at `:362-363` **[read]**; seat equality quoted at `:349-354`, read at `:368-373` **[read]**; `git add` list quoted at `:415-417`, read at `:509-511` **[read]**; the publish title quoted at `:460`, read at `:554` **[read]**. Two more things the scout's missed-items list says are *absent* are now present: the placeholder gate scans **three** files including `CHANGELOG.md` (`:466-479`) **[read]**, and `sub_n(text, old, new, what, expect)` exists with per-call expected counts (`:259`, five call sites) where `release-5.72.1/cut.py` has bare `.replace()` **[read]**.

Conclusion I can stand behind: **the `cut.py` at that path is a repaired re-author, and it gained further repairs after the scouts read it.** I cannot say whether the repair is complete or whether the composer would now run, and I am not going to find out by running it. What survives regardless of the repair:

- `docs/releases/v5.73.0.md:47-51` still carries five unfilled tokens **[read]**, and the file's own last line still reads *"Six panel seat tests remain red; none is new."*
- `CHANGELOG.md:35-36` still carries `@@STOCK@@ @@SEAT@@ @@INST@@ @@QUAL@@` unfilled **[read]**.
- Both would stop the cut by the gate at `cut.py:466-480` **[read]** — the gate raises rather than tags, so this is a stop, not a mispublish.
- **The next round must re-verify finding 17 against the current file before anyone repeats "compose cannot complete" as the blocking fact.** It may still be true; the file no longer argues it.

### CRITICAL — the publish title is the previous release's, and nothing checks it

`harness/notes/release-5.73.0/cut.py:554` **[read]**:

```python
"--title", "v%s — One scale, one family, and fences that hold" % V,
```

That title is v5.72.0's. The release note at `docs/releases/v5.73.0.md:1` **[read]** reads `# v5.73.0 - Readable, and the fences that failed`, and `CHANGELOG.md:25` carries the same wording **[scout]**. The same literal is carried in `release-5.72.0/cut.py:366` and `release-5.72.1/cut.py:420` **[scout]** — a copy-paste constant, not a per-release value.

**Consequence:** the title is the one release field that reaches the public GitHub page unchecked. The placeholder gate refuses on unfilled `@@[A-Z_]{3,}@@` tokens only; the claim gate (`cut.py:493-505`) is docs-only and compares the diff under `python/` and `installer/` **[read]**. Nothing compares the title to the note. Shipping would put v5.73.0's release page under v5.72.0's name.

### CRITICAL — the commit step publishes the whole release-notes directory, including its own tooling

`cut.py:509-511` **[read]** is the file's only `git add`, and it stages an explicit list ending in `"harness/notes/release-%s" % V` — a **directory**, swept wholesale. `.gitignore:75` is `_*.py` and `.gitignore:82` is `_*.txt` **[scout]**; none of `cut.py`, `cut.stdout`, `cut.stderr`, `probe_j5*.py` (six files), `probe-5720.txt`, `j5_diag.txt`, `strip_probe.txt`, `seat-5.73.0.txt`, `suite-5.73.0.txt` begins with an underscore **[scout]**. `git status --porcelain --ignored=matching` marks only `__pycache__/` and `*.log` as ignored in that tree **[scout]**. `cut.py:23` **[read: :22 is `PREV`, the `REPO` literal sits just above]** hardcodes `REPO = r"C:/Users/User/SYNAPSE"` **[scout]**.

The precedent is already public: `git ls-files harness/notes/release-5.71.0/` lists `cut.py`, `cut.stdout`, `cut.stderr`, `cut2..cut7.stdout`, and both suites **[scout]**. `harness/githooks/pre-push` fences only `VERSION`, `harness/state/*` and `harness/verify/*_baseline.json` **[scout]** — nothing under `harness/notes/`.

**Consequence:** a public remote gains a directory of diagnosis scripts and captured stdout with a hardcoded local path in it, every release.

### HIGH — `CLAUDE.md` names a marshal primitive the repo bans and has removed

`CLAUDE.md:45` **[read]** states the Thread Safety mechanism as:

> | **Thread Safety** | All `hou.*` on main thread | `hdefereval.executeInMainThreadWithResult()` in bridge. |

`tests/test_marshal_lint.py:122` **[read]** is `_BLOCKING_ALLOWLIST: dict[tuple[str, str], str] = {}` — empty, with the docstring *"No SYNAPSE source may call Houdini's blocking main-thread marshal directly."* A repo-wide grep for `hdefereval.executeInMainThreadWithResult(` returns **one** hit, `shared/bridge.py:2066` **[read]**, inside a `# Was:` comment. The real marshal is `synapse.server.main_thread.run_on_main`, which `CLAUDE.md` names only for the `/synapse` path.

**Consequence:** any agent or reader who follows the doc builds against a banned symbol. Two of the doc's most load-bearing statements about how Houdini is reached describe a mechanism that is not in the code.

### HIGH — the transport the repo's MCP client config actually points at is bridge-less

`.mcp.json` **[read, whole file]** is 163 bytes and declares `{"mcpServers":{"synapse":{"type":"stdio","command":"python","args":["mcp_server.py"],"env":{}}}}`. `grep -n "bridge" mcp_server.py` returns 2 hits, neither of them the bridge **[scout]**. The bridge-wired `/mcp` endpoint is a **separate**, in-Houdini route registered at `python/synapse/mcp/server.py:1073` **[scout]**. This was reached independently on 2026-08-31 and is still unfixed **[scout]**.

**Consequence:** a Claude Desktop user reading `CLAUDE.md` §1 believes they are on the audited path. They are not. One wording correction: the precise claim is *"the only transport the repo's MCP client config points at"* — the repo does also configure the hwebserver `/mcp` route.

### HIGH — `execute_python` runs with full builtins, no length cap, and its RBAC check is off by default

`python/synapse/server/handlers.py:688` registers it, `:1283` is the handler, `:1316` **[read]** is:

```python
exec_globals = {"hou": hou, "__builtins__": __builtins__}
```

No import allowlist, and a grep for `MAX_CODE`/`MAX_CONTENT`/`len(code)` across `python/synapse/` finds no size guard **[scout]**. The only permission check is gated at `websocket.py:676` `if is_rbac_enabled() and self._session_manager:` **[scout]**, and `python/synapse/server/rbac.py:202-203` **[read]** is:

```python
mode = os.environ.get("SYNAPSE_DEPLOY_MODE", "local").strip().lower()
return mode != "local"
```

So on a default install the denial rows at `rbac.py:120` — which name `execute_python` and `execute_vex` — never fire.

**Read the severity honestly.** This posture is in-tree declared deliberate for single-user localhost. The impact is *conditional*: high if this box ever becomes multi-user or remotely reachable.

### HIGH — `CLAUDE.md`'s PDG failure note cites two line numbers that don't hold the code

`CLAUDE.md:119` **[read]** states the call is at `shared/bridge.py:1718` and the catch at `:1723`. The actual sites are `:2377` and `:2382` **[read]**:

```
2377:                    lambda: top_node.dirtyAllTasks(remove_files=remove_files),
2382:                rollback_note = f" Rollback (dirtyAllTasks) failed: {_rb_exc}."
```

A third number, `:2318`, circulates at `harness/bastion/FINDINGS_INDEX.md:95` **[scout]**. `wc -l shared/bridge.py` = 3012 **[scout]**, so 2318 is a stale middle rather than an out-of-range value — which is why it survived review.

**The substantive claim is correct and worth keeping**: the rollback has never executed, the failure is recorded not rolled back, the live signature is `dirtyAllTasks(self, remove_outputs)` **[scout]**. Only the pointers are wrong — which is exactly the failure mode that makes a correct warning unverifiable by a reader who follows it.

### HIGH — the release "seat" evidence is 207 panel tests, not a suite

`cut.py:355-357` **[read]** runs `.synapse/hytest.py tests/panel -q`. The artifact tail reads `7 failed, 200 passed, 47 warnings in 76.26s` = 207 executed **[scout]**. The only recorded **full-suite** hython measurement in the tree is a different artifact: `harness/verify/suite_baseline.json`'s shipping leg at `6193 passed / 119 failed / 191 skipped / 5 errors`, marked *RECORDED-NOT-RERUN* **[scout]**, measured 2026-08-15.

**Consequence:** the number that appears in the shipped release note as "panel seat suite" describes 207 tests. The 119-failure figure describes the whole `tests/` tree under hython and has not been refreshed in a month.

### HIGH — the green floor's 9584 passes are not evidence about Houdini

`harness/verify/suite_baseline.json` gate interpreter: `system python 3.14.2 (C:/Python314/python.exe) - vendor tree INACTIVE (_VENDOR_ABI_RISK True; no cp314 wheels)` **[scout]**. With no real `hou`, `tests/conftest.py:134-135` plants a canonical fake when `hou` is absent, sentinel-tagged `hou.__synapse_canonical__ = True` at `:66` **[read]**. 75 test modules touch `sys.modules["hou"]` **[scout]**.

**Consequence:** a green floor says the Python logic is coherent against a permissive fake. It says nothing about Houdini behaviour. The seat leg is the only place real `hou` participates, and it covers 207 tests.

### HIGH — 43% of `tests/panel` skips on the floor, and neither artifact records why

`harness/notes/release-5.73.0/suite-5.73.0.txt` per-file progress letters total **202 collected / 87 skipped / 115 passed** on `tests/panel` **[scout]**. `grep -c SKIPPED` = 0 and `grep -c "Skipped:"` = 0 in both that file and `suite-floor-bd65e4b6.txt` **[scout]** — both run `-q` without `-rs`. Mechanism: PySide6 is absent from both site-packages the 3.14 interpreter uses, and 17 of 31 `tests/panel` files carry a `pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")` **[scout]** — confirmed at `tests/panel/test_zzz_j5_diag.py:37` **[read]**.

**Consequence:** the green floor silently declines to test almost half the panel, and no artifact in the release records which half or why. An operator reading "9584 passed" has no way to learn that 87 panel tests did not run.

### HIGH — a seat test can hang instead of failing, bounded only by a subprocess timeout

`tests/panel/conftest.py:47` **[read: quoted text sits at :47]** names four unguarded live `QMenu.exec` call sites — `chat_panel.py:535` and `synapse_panel.py:1749`, `:1787`, `:2690` — and documents at `:38` that the obvious `setattr` patch is inert. The only bound is `cut.py:356` `timeout=2400` **[read]** on the seat subprocess, which records no test failure **[scout]**.

**Consequence:** a wedged seat run burns 40 minutes and reports a timeout, not a named red. The modality guard's own installation proof is the test that skips on the floor **[scout]**.

### MEDIUM — the shipped panel help text advertises 115 tools against a 137 registry

`houdini/python_panels/synapse_panel.pypanel:86` **[read]**, in the live entry point's `<help>` block:

> `/` command palette to browse the 115 built-in tools.

`harness/notes/receipts/W6-FCRX_verdict.md:126` **[scout]** filed it when the registry was 129. The registry is now 137. `harness/probes/flow/probe_flow.py:937` already regex-extracts the string **[scout]**, so it is measurable.

**Consequence:** an artist is told a smaller surface than they have. Honest severity: this is cosmetic; the repo classifies it as a doc-fix flag with no behavioural effect.

### MEDIUM — a complete second panel surface is built, tested and unreachable

`python/synapse/panel/synapse_chat.pypanel:35` **[scout]** imports `SynapseChatPanel` from a path entirely outside the hpath, so Houdini never scans it. `python/synapse/ui/panel.py:47` **[scout]** defines a second `SynapsePanel` the deployed pypanel never imports. The named examples (`chat_panel`, `agent_prompts` with zero repo-wide refs, `bookmarks`, `cross_scene`, `save_shot`, and more) check out **[scout]**. It is tracked, not hidden: `harness/cto/BACKLOG.json:363` and `tests/test_panel_alt_entry_unshipped.py` **[scout]**.

**Do not repeat the aggregate** — the "24 modules / 43,986 lines" figures were the one part the refuter could not reproduce **[scout]**.

### MEDIUM — the PDG regression pin cannot detect the bug it sits next to

`tests/test_pdg_cook_timeout.py:62` declares `def dirtyAllTasks(self, remove_files=False)` — the fake accepts the exact wrong kwarg the production call passes. Nothing in `tests/` mentions `remove_outputs` **[scout]**. So no test can raise the `TypeError` that real hython would.

Correction to the scout's framing: the fake was authored as **cook-timeout coverage** (`6da0ec4d`), not as a signature guard, and the production defect is already on record at `CLAUDE.md:119` and `FINDINGS_INDEX.md:95` **[scout]**. New status fact: none. Still worth fixing, because a fake that mirrors a wrong signature will keep every future probe green.

### MEDIUM — `SEAT_KNOWN_REDS = 6` points at a baseline file that does not exist

`cut.py:34-35` **[read]**:

```python
SEAT_KNOWN_REDS = 6  # v5.72.0 shipped six, named with a measured baseline diff in
                     # harness/notes/release-5.73.0/SEAT_REDS.md. A seventh stops the cut.
```

That path does not exist for this release; the file lives at `harness/notes/release-5.71.0/SEAT_REDS.md` **[scout]**. The scout's stronger framing was **refuted** and must not be repeated here: the six reds *are* documented, and the 6-vs-7 comparison never executed tonight because the stock-suite stop precedes the seat gate **[scout]**.

**Consequence:** a safety constant's provenance points at a file nobody authored. Repairing the pointer is the fix.

### MEDIUM — the release note says "Six", the seat artifact says seven

`docs/releases/v5.73.0.md:77` **[read]** ships the line `- Six panel seat tests remain red; none is new.` The seat log records `7 failed` **[scout]**. The "Six" prose is a machine-written template literal — `cut.py:180` **[read]** carries the identical string.

The tree's `cut.py:368-373` **[read]** now asserts `nfail != SEAT_KNOWN_REDS` and raises, so the repaired gate would stop on that mismatch. But the shipped document still asserts a number that disagrees with the artifact produced beside it. This is the class of defect the same release's prose says it repaired. Flagged for the next round: I read both files this pass and they disagree; I did not run anything.

### LOW / INFO

- **The stdio server advertises 147 tools against the registry's 137.** `mcp_server.py:1067` assembles 137 + 6 group-info + 1 inspector + 1 scout + 2 BLOCKS **[scout]**. Deliberate and documented — `README.md:159` **[read]** pins the number as `len(TOOL_DEFS)`. Not a defect.
- **The 3.43:1 and 6.15:1 figures are arithmetically correct but pinned by no test.** They appear at `README.md:106` **[read]**, `CHANGELOG.md:29`, `docs/releases/v5.73.0.md:8`, and in `tokens.py:289-293` and `components.py:350` **[scout]**. Independent WCAG recomputation reproduces both **[scout]**; `tests/test_panel_readability_defects.py` asserts only inequalities (`:244`, `:256-257`) **[scout]**. A token edit would leave the prose standing.
- **`PENDING_TOOL_DEFS` is empty** — dormant infrastructure, §2.

---

## 4. Documentation claims the tree does not support

Two are live claims with no code behind them (the marshal primitive, §3 HIGH; the PDG line numbers, §3 HIGH). The rest of this section is the **corrections** — claims a scout made that the refuter killed. They are stated here as corrections, not as findings.

**Killed: "artist consent gates never block on either transport."**
The bridge half is right: `shared/bridge.py:2954-2955` constructs the process-wide singleton with `consent_callback=lambda op: True` and `bridge._gate = None`, and `mcp/tools.py:123-128` routes every non-read-only, non-farm-control tool through it **[scout]**. The generalization is false. A **blocking, fail-closed admission gate does exist** on the artist-facing path: `python/synapse/panel/worker_policy.py:138` `is_tool_allowed_for_worker` in its default `'standard'` mode denies every review/approve/critical tool — including `execute_python` and `execute_vex` — plus every unknown tool, and it runs before dispatch at `claude_worker.py:401-406` with the panel switching it on at `synapse_panel.py:3422` **[scout]**. The bridge half is also not new: it is already recorded at `cache_policy/models.py:104-110`.

**Killed: "the live path has no integrity wrap."**
The live path genuinely lacks *enforced* integrity — no composition validation, no rollback, no consent. It does emit an observe-only, path-qualified `IntegrityBlock` per mutating command (`handlers.py:546-571` and `:650-656` → `integrity_envelope.record_live_block`) **[scout]**. That is what `CLAUDE.md` §1's live-path note already says.

**Killed: "README asserts a published v5.73.0 that doesn't exist."**
The banner lives only in **uncommitted** working-tree copies; `git tag --list 'v5.73*'` is empty and `gh release list` still shows v5.72.0 as Latest **[scout]**. That ordering is the designed mid-ritual state — `cut.py:509-511` commits every bumped surface in one commit **[read]**. The material status fact is the unfilled tokens, not a shipped false claim.

**Killed: the SEAT_REDS finding.** See §3 MEDIUM. The threshold is documented; the pointer is broken.

**Killed: "the seat equality gate never executes in any run."** It is **unreachable today**, not dead. Once the stale-README red is repaired the stock check passes and the seat comparison executes and halts on 7 ≠ 6 **[scout]**.

**Killed: "the ratchet baseline CI enforces."** `.github/workflows/ci.yml:109` is the test step and no step invokes `check_suite_baseline` **[scout]**. The baseline is consumed only by the autorevise predicate harness (`harness/verify/checks.py:2539`, registered `:3122`). Not enforced by CI; the staleness and the ~3200-pass delta are real.

**Killed: "CI's `-m "not needs_houdini"` measures a different suite."** `tests/conftest.py:834` heads *"THE HONESTY INVARIANT — why this marker cannot hide a failure"*, `:841` states an AST-deselected test *"cannot deselect a test that would otherwise have run and passed"*, and `docs/CI_TWO_WORLDS.md` records identical pass counts (5682/5682) between the filtered and unfiltered runs **[scout]**. Documented, measured, test-pinned.

**Killed: "the payload can ship stale."** The stated hazard does not materialize. `cut.py:509-511` **[read]** is the only `git add` and it does **not** stage `python/synapse/panel/` — so the uncommitted product edit cannot ship either way, and the tag and payload would agree. The residual, real gap is that nothing binds a payload sha to a source revision (`compose_assets.py:134-137`) **[scout]**. The live defect is the inverse one: **an uncommitted product fix the tag silently drops.**

**Killed: "four surfaces would be swept by `git add -A`."** Three would, not four: `Claude outputs/`, `harness/design_review/2026-09-15/canvas/synapse-panel-crit.html`, and `tests/panel/test_zzz_j5_diag.py`. `design/` is fully tracked (258 files); `docs/releases/v5.73.0.md` is meant to publish. And no step issues `git add -A` **[scout]**.

**Killed: "no credential-looking literal exists."** `.env` (1039 bytes) and `.env.bak-20260625-133203` (847 bytes) exist, protected by `.gitignore:102` (`.env`) and `:103` (`.env.*`) and nothing else **[scout]**. The claim was true only by excluding the files that matter.

**Killed: "the Current Status table's Status column is stale."** Only the `Lines` column is. The real multiplier range is 1.18x–4.30x (`shared/bridge.py` 3012 vs ~700 = 4.30x; `shared/router.py` 320 vs 271 = 1.18x), and the `✅ Verified H21` markers are explicitly build-scoped by `CLAUDE.md:4` and §15 **[scout]**.

**Killed, and it cuts against the scouts' own method: "nearly no test file can fail."** The zero-assert sweep used a case-insensitive `assert` grep, which the docstring sentence "Asserts nothing." defeated — masking `tests/panel/test_zzz_j5_diag.py` **[scout]**. See §6.

---

## 5. What is exposed beyond the public remote

Origin is a **public** GitHub repo, and `orchestrate.ps1` auto-pushes feature branches **[context]**. Three exposure surfaces, all read this pass or handed over from a read.

**1. The release-notes directory is staged wholesale into the push.** §3 CRITICAL. `cut.py:509-511` **[read]** adds `harness/notes/release-5.73.0` as a directory, sweeping `cut.py` (which hardcodes `C:/Users/User/SYNAPSE`), `cut.stdout`, `cut.stderr`, six `probe_j5*.py` scripts, and five captured `.txt` files. `.gitignore`'s `_*.py` and `_*.txt` rules do not match any of them **[scout]**. Already public precedent at `release-5.71.0/` and `release-5.72.0/` **[scout]**.

**2. Three working-tree surfaces sit outside both `.gitignore` and the staging list.** `Claude outputs/`, `harness/design_review/2026-09-15/canvas/synapse-panel-crit.html`, and `tests/panel/test_zzz_j5_diag.py` **[scout]**. None is swept by the ritual — but each is one `git add -A` from a public origin, and nothing fences them.

**3. Real credential-shaped material exists in the working tree.** `.env` and `.env.bak-20260625-133203` **[scout]**, held out of the push by exactly two `.gitignore` lines (`:102`, `:103`). On a public origin, a single `.gitignore` edit or one `git add -f` exposes them.

---

## 6. What this report does NOT know

No test was executed for this report. `pytest` and `hython`/`.synapse/hytest.py` were off-limits by the brief, and two suites in this repo rotate the same production log, so a concurrent run fakes a red. Every claim above is **verified in the tree** or **read from an artifact** — never **verified at runtime**.

**The largest gap is one I created.** I found the `cut.py` at the ship-path's cited location no longer matches the scout's critical finding (§3 CRITICAL). I do not know whether the repair is complete, whether the composer would now run, or whether the tag can now be cut. I did not run the composer, and I have no shell access this pass to read mtimes. **The next round must re-run the copy-forward audit against the current file.**

**Per-dimension blind spots, as each scout reported them:**

- **product-surface.** Handler-level reachability of each of the 137 tool names was not audited — "registered" is proven, "invokable" is not. The hand-lists in `panel/bridge_adapter.py` (`_READ_ONLY_TOOLS`, `_TOOL_TO_OPERATION`, `_DISK_WRITING_TOOLS`) were **not** diffed against the registry, and prior work flags the unmapped-tool default as the most permissive gate. CI/origin state was not queried. The red regression pin `tests/panel/test_j5_rail_air.py` was **not** analysed — whether the uncommitted footer edit clears it is unestablished. Rendered panel appearance was not assessed by any capture.
- **documentation-truth.** No end-to-end confirmation that a stdio client sees 147 tools. `SHA256SUMS.txt`, the Setup payload and the "unsigned installer" claim were not audited on disk or remotely. Only six documents were read; `docs/status.md` and `docs/architecture/overview.md` were not opened. Nothing traces whether other consumers inherit the stale `CLAUDE.md:45` claim.
- **suite-integrity.** Which of the 87 stock-skipped panel tests actually pass under hython is unverified — the claim rests on progress letters plus the seat FAILED list, not a matched run. `test_doctor_button.py`'s skips are not attributable to specific node IDs. ~488 root test files were not read for doc-copied expectations. `tests/solaris`, `tests/rsi` and `tests/rulebook` were counted but not read. Why the panel block collects 202 on stock vs 207 under hython — the 5-test delta — is unexplained.
- **ship-path.** CI job state for HEAD was not queried (no network call). The contents of `Claude outputs/` and `design/` were not inventoried. The public origin's served content was not fetched, so "would publish" is asserted from the staging list. `build_windows.py` and `build_payload.py` internals were not re-read. **The as-run v5.73.0 `cut.py` is unrecoverable** — untracked and overwritten in place — so its text is inferred from the sibling `release-5.72.1` copy. And **nothing on disk logs what wrote `README.md`, `installation.md` and `cut.py` at 19:19:48–19:19:56`; the "post-run hand repair" reading is inferred from mtimes.

**Two claims this report marks as probable rather than verified.** The "stock-suite red no longer reproduces" finding (severity medium, confidence *probable*) and the aggregate module/line counts quoted in the second-panel-surface finding, which the refuter could not reproduce and which are **not** repeated above.

**One artifact that defeats the sweep method.** `tests/panel/test_zzz_j5_diag.py` **[read, whole file]** — untracked (`??`), 3327 bytes, mtime 2026-09-15 20:08:07, written *after* the 19:14 stock run. It contains no executable assertion; the only case-insensitive `assert` match is the docstring at `:6` reading *"Asserts nothing."* It plants `_hou = types.ModuleType("hou")` at `:20-21` rather than importing `hou`, so it earns no `needs_houdini` marker — meaning CI's `-m "not needs_houdini"` will **not** deselect it, and the next stock suite collects a file the recorded baseline never saw. It self-labels `"""TEMPORARY diagnostic (delete after use)"""` at `:1` and writes to `harness/notes/release-5.73.0/j5_diag.txt` at `:94`. Its own docstring says it exists to see the process-global Qt state that `test_j5_rail_air.py` saw a few tests earlier — which is precisely the coupling the parallel panel-footer scout owns.

---

## 7. Sections owned by the parallel scouts

*Not written here. Each line states what the section must answer.*

### RELEASE STATE
Owner: release-state scout. Must answer: what is the exact state of the v5.73.0 cut right now — which steps ran, which stopped, at what wall-clock, and what the run log records as the reason; and does the working tree's `cut.py` still match the file that produced those logs. *(My §3 CRITICAL item is direct input: the tree's copy no longer matches the scout's reading of it.)*

### SUITE & CI HEALTH
Owner: suite/CI scout. Must answer: what does CI currently report on HEAD `85c8fe29` across the required contexts, and how does that compare with the 9584-pass / 433-skip local floor and the 207-test seat leg that this release's evidence actually rests on.

### OPEN WORK & HUMAN GATES
Owner: open-work scout. Must answer: what decisions are waiting on a human right now, which named gates are open, and what each one blocks — in particular the two "still unfinished" items this release note names as awaiting a ruling (`docs/releases/v5.73.0.md:62-69`).

### PANEL FOOTER REGRESSION
Owner: panel-footer scout. Must answer: whether the uncommitted `python/synapse/panel/synapse_panel.py` edit actually clears `tests/panel/test_j5_rail_air.py`, what the edit changes beyond the `SPACE_LG`→`SPACE_12` value, and whether the tag drops a fix the artist can see. *(Relevant to my §6: I did not read that pin, and I cannot run it.)*