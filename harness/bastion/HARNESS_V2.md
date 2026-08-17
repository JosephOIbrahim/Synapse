# BASTION harness v2 — fork manifest

**What this is.** A hardened fork of the AUTOREVISE revision-execution harness
(`harness/autorevise/`) into `harness/bastion/`, built by **W8-SMITH**
(`harness/bastion/PROGRAM.md` :: `HARNESS-V2-SMITH`). v2 serves the BASTION exec
waves (B1..B7); no W8 leg depends on it.

Fork, not rewrite: every module is copied from its AUTOREVISE source (traced
2026-08-17, first-hand — never memory) and changed only where a v2 delta is
named below.

---

## The v2 deltas (what changed, and only that)

**1 · `skills[]` per mission (schema + compile).**
- `mission_schema.py` adds optional `skills` — a list of repo-relative or `/mnt`
  skill paths. Validated for **shape only** (list of non-empty strings). Existence
  is *not* asserted: a `/mnt` skill is not on this checkout, so a green "exists"
  check we cannot run would be a phantom. Shape is the honest bar.
- `compile_wave.py::render_skills()` injects the paths into the `{SKILLS}` slot of
  the brief. No skills → an explicit *"None declared"* line, never a silent empty
  section.

**2 · Typed bus kinds with a validator on write (`bus.py`).**
- Named v2 vocabulary: **CLAIM / FINDING / HANDOFF / BLOCK / RELEASE**. Carried
  autorevise operational kinds: **request / spawn / status**.
- `canonical_kind()` normalises case and **refuses** anything off-vocabulary
  (`BusKindError` in-process; exit 2 on the CLI). That refusal *is* the
  validator-on-write.
- `HANDOFF` is new (cross-agent state transfer; body mirrors `AgentHandoff` in
  `shared/bridge.py`). `RELEASE` is a new first-class kind. Storage stays
  lowercase so the file format is byte-identical to the autorevise bus.
- **Back-compat:** `has_release()` / `open_claims()` honour BOTH the v2 `release`
  kind AND the autorevise idiom (a `status` with `body.release`), so the shipped
  orchestrator close-gate still works (see promotion seam below).

**3 · Arm template v2 (`arm_template.ps1`) + forked steward (`steward.ps1`).**
- Parametrised arm skeleton for any exec wave. Folds the **steward arm/refresh**
  in: it (re)launches the bastion steward with a deadline **past the wave
  horizon** (`-StewardDeadlineHours`, default 12h), so steward liveness is a
  property of arming, not a manual act (PROGRAM.md /rc doctrine).
- **/rc bake-in slot** (`$RcBakeIn`): headless (`-p`) legs have no window and are
  unreachable by the steward's SendKeys, so /rc must be baked into their prompt.
  Its content is the /rc **expansion**, which is **UNKNOWN** (task 1 below). The
  slot ships as a NAMED UNKNOWN sentinel; while it holds that sentinel the arm
  template **warns** that headless legs run without /rc coverage. Never guessed.

---

## Runner survival rules carried (each traced to source — no phantom surface)

| # | Rule | Carried in (bastion) | Source (first-hand) |
|---|---|---|---|
| 1 | hold-turn clause (team lead must not end turn until teammates confirm shutdown; actively wait in one turn) | `prompts/_template.md` "Hold the turn" + receipt "hold there" | `harness/notes/CARD_cache-advisor.md:66-67`; leg form `harness/autorevise/prompts/_template.md:71` |
| 2 | `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` (LANDMINE 2 — 600s ceiling kills teams) | `arm_template.ps1` env block | `harness/autorevise/arm_w8.ps1:21`; `CARD_cache-advisor.md:65` |
| 3 | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (AGENT_TEAMS) | `arm_template.ps1` env block | `harness/autorevise/arm_w8.ps1:20` |
| 4 | detached `Start-Process` + pid capture | `arm_template.ps1` (orchestrator + steward) | `harness/autorevise/arm_w8.ps1:25-26`; runner form `harness/orchestrate.ps1:493,504` |
| 5 | debom discipline (BOM breaks downstream json.load) | `quote_safe.py` (verbatim) + pid files `-Encoding ascii` | `harness/autorevise/quote_safe.py`; PS twin `harness/lib/quote-safe.ps1` used at `harness/orchestrate.ps1:357,366` |

---

## /rc — task 1 verdict: **UNKNOWN, escalated with transcript**

**Delivery (RESOLVED, first-hand):** the steward finds leg windows by title
`SYNAPSE (W…-…)` and sends the literal keystroke `/rc` + Enter, once each —
`harness/notes/h22/steward.ps1:22-31`. The bastion `steward.ps1` preserves this
verbatim.

**Definition (UNKNOWN):** what typing `/rc` *resolves to* inside Claude Code
could not be captured, after a genuine interrogation:
1. No `rc.md` command under `~/.claude` (only `bridge.md`), none in the repo,
   none in any plugin.
2. No built-in `/rc` CLI subcommand (Claude Code **2.1.233**; subcommands:
   agents/auth/auto-mode/doctor/gateway/import/install/mcp/plugin/project/setup-token/ultrareview/update).
3. No settings alias.
4. Print-mode probes (`/rc`, `/bridge`, `/help`) all hang (`EXIT=124`) after the
   connectors warning — no resolution.
5. Interactive TUI is unobservable headless: `--ax-screen-reader` forces
   `--print`; a non-TTY pipe cannot drive the slash autocomplete. A dispatched
   agent has no TTY.

`/rc`'s interactive resolution is a **live-TUI fuzzy autocomplete over the
session's command set** — non-deterministic from disk, unobservable without a
terminal. Per the constitution it is recorded UNKNOWN, never guessed. Escalated
on the wave8 bus as a `block` (W8-SMITH → W8-LIBR + Joe). Resolution path: Joe
states it, or a future interactive-session interrogation runs `/help` and reads
what `/rc` autocompletes to.

---

## Promotion seam (a human word, outside smith's scope)

The shipped orchestrator hardcodes its close-gate to the **autorevise** bus:
`harness/orchestrate.ps1:206` (`$busPy = …\autorevise\bus.py`), called at `:211`
as `bus.py released <wave> <leg>`. The bastion `bus.py` is a strict **superset
drop-in** (identical CLI, file layout, and `released` exit-code contract, plus
typed validation and the release back-compat above). To make the shipped
close-gate read the typed bastion bus, repoint that one line to
`…\bastion\bus.py`. That edit touches `harness/orchestrate.ps1` (not
`harness/bastion/`), so it is a human act, not this leg's.

---

## Self-test (stock pytest, pure Python, no hou)

`tests/test_bastion_v2.py` — **10 passed** (skip is not pass): schema round-trip
incl. `skills[]`, compile of the `fixtures/w99_skills.json` mission carrying
`skills[]` (brief lists both paths), bus kind validation (typed + operational
accepted, unknown refused on write), and the release/close-gate back-compat.
Run: `python -m pytest harness/bastion/tests/test_bastion_v2.py -v`.

The two `.ps1` templates are **not executed** (arming is a Joe word); they were
authored line-faithfully against their traced sources. Live PowerShell AST parse
was permission-blocked this session — verified by inspection instead.
