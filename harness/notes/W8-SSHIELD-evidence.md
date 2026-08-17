# W8-SSHIELD — Shield Scout Evidence

**Leg:** W8-SSHIELD (BASTION Wave 0, band TRUTH, read-only) · **Branch:** `wave8/sshield`
**Source:** `harness/bastion/PROGRAM.md` anchor B6-SHIELD (SHIELD, marked UNAUDITED — no prior wave touched this)
**Method:** read-only recon of the live worktree + full shared git object store. Four dimensions
(secrets / deps / telemetry / patent-hygiene), each fanned to a `cartographer` discovery scout and
independently re-attacked by a `crucible` adversarial verifier, plus a completeness critic. Load-bearing
new claims additionally spot-confirmed by first-hand reads at the leg operator level.

**Repo posture (load-bearing):** `origin = https://github.com/JosephOIbrahim/Synapse.git` is a **PUBLIC**
repo and an orchestrator auto-pushes every feature branch. Therefore any real secret in tree or history
would be *already published* → P0-rotate-now. That case did **not** occur (see Secrets).

---

## HEADLINE — NO P0

The single most-dreaded shield outcome — a live secret in a public, auto-pushed repo — is **CLEAN**,
confirmed first-hand by the secrets scout **and** independently reproduced by its adversarial verifier:
whole-object-store scan (`git cat-file --batch-all-objects`), full history across all refs, and
`git log --all --full-history --diff-filter=A` over `*.env`/`*.pem`/`*.p12`/`*id_rsa*`/`credentials.json`/
`secrets.json`. No live key, no `PRIVATE KEY` header, no secret file ever added on any ref **except** the
vendored public CA bundle (`_vendor/certifi/cacert.pem`, CERTIFICATE blocks only). All grep hits were
fake test fixtures, redacted doc references, or SHA256 topology signatures — none real.

Everything below is **P1 hardening** or **P2 polish**. Total: 8×P1, 9×P2, plus clean-posture positives
and named UNKNOWNs.

---

## P1 — Hardening (8)

### Dependencies
- **P1 `agent/requirements.txt:1-3`** — pins nothing: `anthropic>=0.75.0`, `websockets>=12.0`,
  `anyio>=4.0` all float (0/3 pinned, no `--hash`). The anthropic SDK mediates the API key + paid egress.
  *Mitigant:* the in-Houdini runtime loads the frozen `_vendor/anthropic` tree per `_vendor/README.md`
  ("No runtime pip"), so the float bites the standalone agent / `pip install` path, not the DCC daemon.
- **P1 `pyproject.toml:29`** — core + security deps float lower-bound-only: `pydantic>=2.0` (sole core dep),
  `cryptography>=41.0.0` (encryption extra), `anthropic>=0.40.0` (dev + routing extras),
  `sentence-transformers>=2.2`. Only `mcp==1.26.0` (`:58`) is exact-pinned (deliberate, documented CI-red
  rationale). No `--hash` anywhere.

### Telemetry / Privacy
- **P1 `python/synapse/panel/system_prompt.py:257-275`** — the panel folds scene topology (network path +
  selected node paths + hip filename), the **full serialization of every tool result** (scene inspection,
  parameter values, and **plaintext memory recall/search/context content**), and 121 tool schemas into the
  cloud-bound request on every turn. Consent is only the act of sending (`bridge_adapter.py:193`
  "request IS the consent"; `EGRESS.md:88,116-119,145`). Broader data class than the typed prompt, implicit
  opt-in. *Not P0:* user initiates the send to a provider they chose; no secret leaks in the payload
  (keys leave only as auth headers, `EGRESS.md:97-101`).
- **P1 `docs/studio/EGRESS.md:160-164`** — the C19 redaction/opt-out hook (a `build_system_prompt` hook +
  per-tool-result filter before serialization) is documented as **NOT implemented**. No code path can
  withhold scene/memory content from egress — the missing mitigation for the panel-egress finding above.

### Patent-hygiene (public repo vs 3 pending patents — flag-for-counsel, mechanism text NOT reproduced)
- **P1 `python/synapse/memory/agent_state.py:574-581`** — production code authors the **patent-1**
  cognitive-state schema: `synapse:decision` / `synapse:reasoning` / `synapse:revert` USD attributes under
  `/SYNAPSE/memory/decisions/`. Claim-bearing schema shipped in public, auto-pushed code (verified verbatim).
- **P1 `docs/RFC_agent_usd_ledger.md:39-60`** — public design doc fully specifies the agent.usd
  cognitive-state ledger prim tree (**patent 1**) at architecture level, citing the built v2.0.0 schema.
- **P1 `docs/SYNAPSE_RETINA_BLUEPRINT.md:24,114`** — states the agent.usd decision/reasoning/revert receipt
  triple (**patent 1**) and the Cosmos predict-renders-without-ray-tracing claim (**patent 3**), while its
  own header asserts mechanism language is NDA-only. Public repo contradicts the stated NDA posture.
- **P1 `docs/H22_PHASE0_RECONCILIATION.md:75`** — plainly characterizes the Cosmos predictive-lighting
  mechanism (**patent 3**: world-foundation model, no ray tracing) inside a section that says the patent
  evidentiary chain is kept outside the repo. (Scout cited `:76`; verified `:75`, same P0.7 paragraph.)

---

## P2 — Polish / defense-in-depth (9)

- **P2 `.gitignore:90-93`** — covers `.env`/`.env.*`/`*.key` but **not** `*.pem`/`*.p12`/`*.pfx`/`id_rsa*`/
  `credentials*.json`/`secrets*.json`. No such files tracked today, but the gap invites a future accidental
  commit on a public repo. *(first-hand, operator)*
- **P2 `pyproject.toml:58`** — no pip manifest uses hash pinning; even exact pins (`mcp==1.26.0`,
  `opencv-python-headless==5.0.0.93` retina:28, `OpenImageIO==3.1.15.0` retina:40) trust the version string
  only → registry-side artifact substitution risk.
- **P2 `python/synapse/_vendor/pydantic_core/_pydantic_core.cp313-win_amd64.pyd`** — dual-ABI native
  extensions (`_pydantic_core` + `jiter`, cp311/cp313) committed into `_vendor` of a public auto-pushed repo;
  integrity anchor is the wheel self-attested RECORD sha256 (self-consistent, not external attestation).
  *Mitigant:* `_vendor/README.md` records exact versions + a pinned re-pull recipe.
- **P2 `python/synapse/_vendor/certifi-2026.2.25.dist-info/METADATA`** — frozen certifi 2026.2.25 is the
  vendored root-of-trust for the vendored httpx/anthropic/httpcore/h11 stack; never updates until manual
  re-vendor, so CA revocations/additions drift silently.
- **P2 `python/synapse/_vendor/README.md:94`** *(new, from verify)* — the documented `_vendor` refresh
  procedure re-introduces the float it was meant to remove: `pip install --upgrade` with a bare unversioned
  un-hashed `anthropic`, so each refresh bakes whatever is latest at that moment into the public repo. The
  "bundle and pin all deps" guarantee holds only *between* refreshes; the refresh itself is unpinned.
  (Contrast the Future-cliff recipe at `:56-61` which *does* pin.)
- **P2 `python/synapse/panel/providers/registry.py:106`** — panel defaults to Anthropic cloud
  (`DEFAULT_PROVIDER="claude"`). Adjusted P1→P2 by verify: no send occurs until the operator supplies a
  cloud API key (itself the opt-in act); the real gap is only the absent first-run egress notice.
- **P2 `docs/studio/EGRESS.md:127-128`** *(new, from verify)* — the Ollama "local" engine can be silently
  redirected off-box via `OLLAMA_HOST`; the Custom engine preserves a plaintext `http://` scheme. An operator
  choosing local for privacy could leak the same scene+memory payload off-box via an inherited env var.
  Documented caveat, defense-in-depth.
- **P2 `.github/workflows/ci.yml:23`** *(critic — outside every dimension scout's file-type net)* — CI
  GitHub Actions pinned to **mutable major tags**, not commit SHAs: `actions/checkout@v5` (`:23,65`),
  `actions/setup-python@v6` (`:77`). A retagged/compromised action would run in CI with repo +
  `MONETA_DEPLOY_KEY` context. *(first-hand, operator)*
- **P2 `harness/githooks/pre-push`** *(critic)* — `git config core.hooksPath` points into the repo tree
  (`harness/githooks`) and `pre-push` is **tracked**, so a committed script auto-executes on every push.
  Grepped clean of secrets/egress today, but a code-exec-on-git-op surface no dimension scout modeled.
  *(first-hand, operator)*

---

## Clean-posture positives (recorded for completeness, not defects)

- **No telemetry / analytics / crash-reporting / update-check egress anywhere** — `docs/studio/EGRESS.md:81-82`,
  verified by independent grep (all 62 keyword hits benign substrings).
- **Logs local-only** — `python/synapse/core/logfile.py:47-57`: `~/.synapse/logs`, opt-out `SYNAPSE_FILE_LOG=0`,
  no prompt text logged, hip basename only; `doctor.py:823` bundles logs into a *local* archive only.
- **Anti-surprise-billing guard** — `.synapse/harness.py:384-392`: the harness REFUSES to run if
  `ANTHROPIC_API_KEY` is set (it would override the subscription and bill API).
- **CI secret hygiene** — `MONETA_DEPLOY_KEY` consumed only via `${{ secrets.MONETA_DEPLOY_KEY }}`
  (`.github/workflows/ci.yml:21,74`), presence-gated (`:64,85,89`); no key material in the tree.
- **Scripts clean** — ~60 tracked `.ps1/.sh/.bat/.cmd` grepped: `set_anthropic_key.bat:14` prompts the key
  interactively (writes to a local `.env`); `synapse.ps1:21` nulls `ANTHROPIC_API_KEY`. No hardcoded secret.
- **No git submodules** (`.gitmodules` absent); external URLs limited to mkdocs GitHub Pages + the CI Moneta pull.

---

## UNKNOWNs — named, never zeroed, never estimated

1. **Secrets in remote-only refs** not fetched into the shared object store — resolving needs `git fetch --all`
   (network; not run to preserve read-only/non-mutating discipline).
2. **Binary blob interiors** (`.hip` / `.png`: `demo/synapse_demo.hip`, `tests/fixtures/*.hip`, `assets/*.png`) —
   `strings` best-effort; cannot parse compressed/binary sections; a key hidden there would evade the scan.
3. **Panel GUI first-run consent dialog** — a Qt surface; presence can only be confirmed by launching the
   panel in Houdini (headless found egress modeled only as "sending is the consent").
4. **hwebserver bind interface** (port 9999, localhost vs all-interfaces) — `run()` invoked without a bind arg;
   needs a running Houdini host + `netstat` per build to observe.
5. **Patent filing-dates vs commit-dates** — filing dates are deliberately kept out of the repo; pre-filing vs
   defensive-publication risk is a counsel judgment, not resolvable from the tree.
6. **Patent-2 (digital injection)** mechanism — first-hand grep found the injection identifiers in **no**
   tracked file except the README name-drop; the `/inject` / `cb_tune_parameters` mechanism lives in the
   user's private global CLAUDE.md (outside the repo). Recorded UNKNOWN (not zero) because a semantic
   paraphrase could evade keyword grep.
7. **retina worker venv** transitive/pinned versions (`.venv` gitignored, network pip install, no lockfile) and
   the **moneta** extra (`pyproject.toml:88`, private proprietary repo) — resolution + provenance not visible
   from this public tree.

---

## Acceptance self-check

- *findings ranked P0/P1/P2 with file:line anchors, receipt committed on own branch* → **pass** (this file +
  receipt; every finding anchored).
- *every claim traced to first-hand observation or named UNKNOWN* → **pass** (agent recon is first-hand at the
  leg; load-bearing new claims independently re-read by the operator; unobtainables recorded UNKNOWN above).
