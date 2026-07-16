# H22 ABI Verdict — Drop-Week Runbook Step 2

> **VERDICT: `python 3.13.10` (cp313) ≠ cp311 ⇒ gate-0.1 is RE-OPENED — and its armed
> drop-day contingency (re-vendor) is ALREADY EXECUTED, committed, and pinned.**
> The vendored tree is now dual-ABI (cp311 + cp313) at identical package versions.
> The sidecar remains the human-ruled durable architecture for the first post-release
> cycle; nothing in this verdict closes or reschedules it.

- **Governing gate:** h22-gatewarden ALLOW on runbook step 1 (both `harness/state/drop.json`
  and `harness/state/leg0_baselines.json` exist and parse). This artifact is step 2's
  required output — per blueprint `docs/SYNAPSE_H22_GAP_BLUEPRINT.md:235`, "no output is
  trusted without one."
- **Relay leg:** Leg 2 (drop week), MODE B. Blueprint §9 step 2 verbatim
  (`docs/SYNAPSE_H22_GAP_BLUEPRINT.md:238`): "**ABI verdict.** `drop.json` Python version.
  cp311 → vendored tree holds. Else → gate-0.1 sidecar path; re-vendor from
  `pydantic_core`, `jiter` [INFERENCE]." The `[INFERENCE]` on that dependency list is
  **resolved to VERIFIED below** by local enumeration.
- **Author:** h22-scribe, this dispatch (2026-07-16). Every path, count, hash, and symbol
  below was read/grepped/hashed by the author in this dispatch. Bash was read-only
  (`ls`, `find`, `sha256sum`, `git show/log/ls-files/status`, binary `grep -a`).

---

## Definition of Done (this artifact)

1. `drop.json` Python field read verbatim and compared against cp311. ✅
2. The complete vendored compiled-extension list DERIVED locally (repo-wide binary
   enumeration, not copied from the blueprint or the gate-0.1 brief). ✅
3. Re-vendor status adjudicated: executed / partial / pending — with commit evidence. ✅
4. Enforcement chain verified in code and tests (gate, risk flag, lockstep pins). ✅
5. Residuals and cautions recorded (metadata skew, stale wheel cache). ✅
6. Every path checked is cited. ✅ (§ "Paths checked")

---

## 1. The trigger value

`harness/state/drop.json` (read this dispatch; file untracked in git at dispatch time —
noted for the record; blueprint ruling is existence-at-path, not commit status):

```json
"houdini_build": "22.0.368",
"python": "3.13.10",
"usd": "0.26.5",
"pyside": "6.8.3"
```

`3.13.10` → ABI tag **cp313** → not cp311 → the blueprint's "else" branch fires:
**gate-0.1 re-opens.** Per the human ruling recorded in
`harness/notes/gate-0.1-sidecar-vs-abi3.md:83-91` (DECISION — 2026-07-10): sidecar is the
durable architecture, built in the first post-release cycle; the drop-day contingency is
the in-process re-vendor per `docs/studio/UPGRADE.md` Step 2a (heading verified at
`docs/studio/UPGRADE.md:66`).

## 2. The vendored compiled-extension list (derived, not trusted)

Repo-wide enumeration this dispatch — glob `**/*.pyd` over the whole repo, plus
`find python/synapse/_vendor -type f \( -name "*.pyd" -o -name "*.dll" -o -name "*.so"
-o -name "*.dylib" -o -name "*.lib" \)`. Result: **exactly 4 compiled binaries in the
entire repo, all under `python/synapse/_vendor/`, belonging to exactly 2 packages.**
No `.dll`/`.so`/`.dylib`/`.lib` anywhere in the vendor tree. The blueprint's
"pydantic_core, jiter [INFERENCE]" is hereby **VERIFIED — the list starts and ENDS there.**

| Binary (path relative to repo root) | sha256 (this dispatch) |
|---|---|
| `python/synapse/_vendor/jiter/jiter.cp311-win_amd64.pyd` | `bfb8ccc4bf107b47fc8e68599e31e0b0a9920bfbf0bd0cb2b3441800cb4a9ae0` |
| `python/synapse/_vendor/jiter/jiter.cp313-win_amd64.pyd` | `99d8a53728c34be186a0f0c9449ed5d9fabe32ef04f99d5a90694a21888eb304` |
| `python/synapse/_vendor/pydantic_core/_pydantic_core.cp311-win_amd64.pyd` | `f7ae8ed6e07152a268cd306906c5c50598cf0d1bcd111950deb80fb1dc258c3b` |
| `python/synapse/_vendor/pydantic_core/_pydantic_core.cp313-win_amd64.pyd` | `354e74095baa60fcbfdc32ac151ec8ad88288ac58936bcbf355ef762a848f906` |

The remaining vendored distributions are pure Python and ABI-agnostic: 16 `dist-info`
directories total under `_vendor/` (counted from `ls` this dispatch), 2 native
(`jiter-0.14.0`, `pydantic_core-2.46.3`) + 14 pure (`annotated_types-0.7.0`,
`anthropic-0.96.0`, `anyio-4.13.0`, `certifi-2026.2.25`, `distro-1.9.0`,
`docstring_parser-0.18.0`, `h11-0.16.0`, `httpcore-1.0.9`, `httpx-0.28.1`, `idna-3.11`,
`pydantic-2.13.3`, `sniffio-1.3.1`, `typing_extensions-4.15.0`, `typing_inspection-0.4.2`).

**Version-match probe on the cp313 binaries** (embedded version strings, binary
`grep -a` this dispatch): `_pydantic_core.cp313-win_amd64.pyd` contains `2.46.3` (1
occurrence) and NO `2.47.0`; `jiter.cp313-win_amd64.pyd` contains `0.14.0` (1 occurrence)
and NO `0.16.0`. The cp313 binaries are the version-matched builds, not the stale cached
ones (§5, caution 2).

## 3. Re-vendor status: EXECUTED at commit `38b33b6` (2026-07-15)

`git show --stat 38b33b6a63bc25853a399ce31b4b316a7aee6e9b` — "feat(h22): cp313 re-vendor —
gate-0.1 drop-day contingency for Houdini 22" (authored 2026-07-15, drop day). Touched:
`python/synapse/__init__.py`, `_vendor/README.md`, both cp313 `.pyd`s (new, 449,024 B +
5,256,192 B), `tests/conftest.py`, `tests/test_vendored_deps.py`.

The commit message records live verification: stock-3.14 `test_vendored_deps` 17 passed /
2 skipped (vendor passive), and under H22 hython 3.13 `import synapse` with vendor active,
no ABI warning, anthropic resolving to `_vendor`, pydantic 2.13.3 / pydantic_core 2.46.3.
`docs/reviews/h22-drop-execution-2026-07-15.md:25-37` records the same.
**[RECORDED at 38b33b6 + drop-execution review — not re-run this dispatch.** Runtime
re-confirmation belongs to the brain-wake check under H22 hython (`check_brain_answers`),
which is downstream runbook work, not step 2's.]

## 4. Enforcement chain (verified in code and tests this dispatch)

| Pin | Location | Verified content |
|---|---|---|
| Activation gate | `python/synapse/__init__.py:60-68` | `_VENDOR_PYS = frozenset({(3, 11), (3, 13)})`; prepend only when `sys.version_info[:2] in _VENDOR_PYS` AND Windows AND `_vendor` exists |
| ABI-risk flag | `python/synapse/__init__.py:90-118` | `_VENDOR_ABI_RISK` fires one actionable `RuntimeWarning` on Windows interpreters OUTSIDE the set; warning names both remediations (re-vendor per `_vendor/README.md`, or the sidecar per `gate-0.1-sidecar-vs-abi3.md`) |
| Lockstep test constants | `tests/conftest.py:36-37` | `VENDOR_PYS = frozenset({(3, 11), (3, 13)})`, `VENDOR_ABI_TAGS = ("cp311-win_amd64", "cp313-win_amd64")` |
| Dual-ABI presence test | `tests/test_vendored_deps.py:75` | `test_native_package_has_all_vendored_abis` asserts a `.pyd` per tag in `VENDOR_ABI_TAGS` for BOTH native packages |
| Procedure doc | `python/synapse/_vendor/README.md:23-74` | Dual-ABI documented, drop-day note (2026-07-15) with the 2.47.0 gotcha, exact re-vendor recipe pinned to versions 2.46.3 / 0.14.0 |
| Studio runbook | `docs/studio/UPGRADE.md:66` | "Step 2a — Re-vendor runbook (gate-0.1, in-process path)" exists as cited by the gate-0.1 decision |

## 5. Residuals and cautions (for the record — none blocks steps 3–9)

1. **dist-info metadata skew.** Both `pydantic_core-2.46.3.dist-info/WHEEL` and
   `jiter-0.14.0.dist-info/WHEEL` still read `Tag: cp311-cp311-win_amd64`, and neither
   package's `RECORD` mentions any cp313 file (0 matches, grepped this dispatch). This is
   the documented procedure ("copy only the `.pyd`s", `_vendor/README.md:60`) and is
   harmless at runtime — but any tooling that trusts dist-info (pip-audit-style scanners,
   wheel provenance checks) will see a cp311-only install. Known, accepted, recorded.
2. **`harness/state/wheel_cache/` is stale for BOTH native deps.** `cp313/` holds
   `pydantic_core-2.47.0` (rejected by pydantic 2.13.3 — the drop-day gotcha) AND
   `jiter-0.16.0` (vendored pin is 0.14.0; the README warns a version bump breaks the
   pure-Python layer). `cp312/` mirrors the same stale versions. **Do not re-vendor from
   this cache without version-matching first** — the drop-day fix pulled fresh
   version-matched wheels instead. Cache refresh to 2.46.3/0.14.0 is an optional cleanup,
   not owed for this drop.
3. **`drop.json` is untracked** at dispatch time (`git status --porcelain` → `??`).
   Existence-gate is satisfied by blueprint ruling; commit is the human's call.
4. `_vendor/__pycache__` `.pyc` files exist on disk (cpython-311 + cpython-313) but are
   NOT git-tracked (`git ls-files` → 0 matches) — local artifacts of live runs, not a
   repo residual.

## 6. What this verdict does NOT do (non-goals)

- Does not build, schedule, or re-litigate the **sidecar** — that ruling stands as made
  (human sanction 2026-07-10, first post-release cycle, `gate-0.1-sidecar-vs-abi3.md:83-91`).
- Does not re-run the pytest suite or the H22 hython import check — step 2 adjudicates the
  ABI branch; runtime brain-wake proof lives downstream (and was recorded at `38b33b6`).
- Does not touch quarantine re-litigation (step 3), the sweep diff (step 4), or anything
  after — and executes nothing from `flywheel_queue.json` proposals (C.0/S.0/R.0 remain
  `ratified:false`).
- Does not modify `_vendor/`, `wheel_cache/`, or any code/test — paper only.

## Paths checked (every one, this dispatch)

| Path | How checked |
|---|---|
| `harness/state/drop.json` | Read (verbatim fields; `git status` → untracked) |
| `harness/state/leg0_baselines.json` | Read (step-1 left side present; not load-bearing for step 2 beyond gate context) |
| `harness/notes/gate-0.1-sidecar-vs-abi3.md` | Read in full (options, IPC evidence, 2026-07-10 DECISION) |
| `docs/SYNAPSE_H22_GAP_BLUEPRINT.md:210,235,238-242` | Grep (step-2 verbatim text + artifact requirement) |
| `python/synapse/_vendor/` (whole tree) | `ls -R` (16 dist-infos; package dirs enumerated) |
| Repo-wide `**/*.pyd` + `_vendor` find for `.pyd/.dll/.so/.dylib/.lib` | Glob + `find` (exactly 4 binaries, 2 packages, nothing else) |
| 4 vendored `.pyd`s | `sha256sum` (table in §2) + binary `grep -a` version strings on both cp313 binaries |
| `python/synapse/_vendor/README.md` | Read in full (dual-ABI doc, drop-day note, refresh recipe) |
| `python/synapse/_vendor/{jiter-0.14.0,pydantic_core-2.46.3}.dist-info/WHEEL` | Read (both `Tag: cp311-cp311-win_amd64`) |
| `python/synapse/_vendor/{jiter-0.14.0,pydantic_core-2.46.3}.dist-info/RECORD` | Grep `cp313` (0 matches each) |
| `python/synapse/__init__.py:40-124` | Read (`_VENDOR_PYS`, gate, `_VENDOR_ABI_RISK`, warning text) |
| `tests/conftest.py:32-37` | Grep (lockstep constants) |
| `tests/test_vendored_deps.py:35,75,90,167,238,248` | Grep (dual-ABI test + skip-gating) |
| `docs/studio/UPGRADE.md:66` | Grep (Step 2a heading exists) |
| Commit `38b33b6a63bc25853a399ce31b4b316a7aee6e9b` | `git show --stat` (message + file list + byte sizes) |
| `harness/state/wheel_cache/{cp312,cp313}/` | `ls -la` (stale 2.47.0 / 0.16.0 wheels confirmed) |
| `docs/reviews/h22-drop-execution-2026-07-15.md:25-37,82` | Grep (drop-day record aligns) |
| `git ls-files python/synapse/_vendor` | pycache tracking check (0) |
