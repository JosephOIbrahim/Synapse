# Moneta Backend — Deferred Follow-ups

Three items were designed by the Mile-7/gap-closing ARCHITECT pass but kept out
of the shipped PRs (#14, #15) on purpose — each needs either a shared-code
change that deserves its own review, or external provisioning. They are not
blockers for the (default-off) Moneta backend; capture is here so they aren't
lost. Each is independently shippable.

---

## FU-1 — `Memory.id` collision fix (data integrity)

**Problem.** `Memory.__post_init__` generates the id *before* it defaults
`created_at`, so on the normal constructor path `created_at == ""` and the id is
a pure function of `content + memory_type` — time-independent. Two memories with
identical content+type collide. The JSONL store dedups by id (dict overwrite);
`MonetaBackedStore` appends both, so `count()`/`get()` diverge once the live
write path is Moneta-backed (i.e. at cutover). Backfill is unaffected (existing
ids are already unique).

**Files**
- `C:\Users\User\SYNAPSE\python\synapse\memory\models.py` — `Memory.__post_init__` / `_generate_id`
- `C:\Users\User\SYNAPSE\tests\test_moneta_crucible.py` — `test_duplicate_content_id_collision_is_documented` (the tripwire to invert)

**Fix (minimal, low-risk).** Reorder `__post_init__` to default `created_at`
before generating the id:

```python
def __post_init__(self):
    if not self.created_at:
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not self.id:
        self.id = self._generate_id()           # now created_at participates
    if not self.updated_at:
        self.updated_at = self.created_at
```

Residual: two same-content+type memories created in the *same second* still
collide. Optional hardening — mix `time.time_ns()` or `uuid4().hex` into
`_generate_id` (makes ids non-deterministic; ship as its own PR since it changes
id semantics).

**Blast radius.** Only the tripwire test depends on the current collision
(invert it → `test_duplicate_content_gets_distinct_ids`). No persisted data
keyed on the formula; existing ids are read from the payload, untouched. Safe to
change unconditionally.

**Risk.** Low. Touches shared `models.py`; warrants a focused PR + the test
inversion. Land **before/with** the production cutover.

---

## FU-2 — AP6: gate the one destructive memory op (`run_sleep_pass`)

**Problem.** Memory `add` is correctly INFORM (unchanged from JSONL). But
`run_sleep_pass` permanently prunes unprotected memories (data loss) and is
currently ungated. It has no production caller yet, so this is not urgent — but
when it is wired to a tool it should route through `HumanGate` at APPROVE
(matching `prune_memory`).

**Files**
- `C:\Users\User\SYNAPSE\shared\constants.py` — `OPERATION_GATES`
- `C:\Users\User\SYNAPSE\python\synapse\panel\bridge_adapter.py` — `_TOOL_TO_OPERATION` map
- `C:\Users\User\SYNAPSE\python\synapse\server\handlers_memory.py` — new `_handle_sleep_pass`
- `C:\Users\User\SYNAPSE\python\synapse\memory\moneta_store.py` — `run_sleep_pass` (unchanged; reached via the handler)

**Design (additive, non-invasive — gate at the tool layer, not in the store).**
1. `OPERATION_GATES["sleep_pass"] = "approve"`.
2. `bridge_adapter` map: `"synapse_sleep_pass": "sleep_pass"`.
3. A thin `_handle_sleep_pass` that calls `store.run_sleep_pass()` and is
   dispatched **through `execute_through_bridge`** (NOT in `_READ_ONLY_TOOLS`) so
   the APPROVE gate fires before the prune. Standalone/CI stays green via the
   bridge's auto-approve fallback.

**Honest scope.** `add` stays INFORM; AP6 covers only the destructive prune.
Do NOT claim "every mutation is gated."

**Risk.** Low–moderate. The single failure mode is wiring the handler without
routing it through the bridge — verify in review. Test: gate consulted on
`sleep_pass`, auto-approves standalone, rejection blocks the prune.

---

## FU-3 — Make CI actually exercise the Moneta backend

**Problem.** ~66 Moneta tests are `skipif not moneta_available` and SKIP on
GitHub CI (the `moneta` package isn't there). AP9 ("CI runs the memory path with
no pxr") is only truly exercised locally.

**Files**
- `C:\Users\User\SYNAPSE\.github\workflows\ci.yml` — the test workflow
- `C:\Users\User\SYNAPSE\python\synapse\memory\moneta_runtime.py` — existing `$MONETA_SRC` seam

**Recommended (Option B1 — deploy key).** Moneta is zero-dep, pxr-free, and
same-owner (`JosephOIbrahim/Moneta`).
1. **Joe provisions:** generate an SSH keypair; add the public key as a
   read-only **Deploy Key** on `JosephOIbrahim/Moneta`; add the private key as
   secret **`MONETA_DEPLOY_KEY`** on `JosephOIbrahim/Synapse`.
2. Workflow diff:
   ```yaml
   - name: Check out private Moneta backend
     uses: actions/checkout@v5
     with:
       repository: JosephOIbrahim/Moneta
       ref: main
       ssh-key: ${{ secrets.MONETA_DEPLOY_KEY }}
       path: _moneta
   # ... after `pip install -e ".[dev,...]"`:
   - name: Install Moneta (zero-dep, pxr-free path)
     run: pip install -e ./_moneta
   ```
3. No-silent-skip tripwire (keep even after B1):
   ```yaml
   - name: Assert Moneta backend active in CI
     run: python -c "import sys; from synapse.memory import moneta_runtime as m; sys.exit(0 if m.moneta_available() else 1)"
   ```

**Status: IMPLEMENTED (conditional).** `ci.yml` now wires the Moneta checkout +
`pip install -e ./_moneta` + the no-silent-skip tripwire, each **gated on the
secret being present** (`if: ${{ env.MONETA_DEPLOY_KEY != '' }}`, the secret
mapped to a job env var since `secrets` isn't usable in `if:`). With no secret,
those steps skip and CI stays green (Moneta tests skip as before). **The only
remaining step is Joe creating the secret**, which activates everything:
1. `ssh-keygen -t ed25519 -f moneta_ci -N ""` (no passphrase).
2. Add `moneta_ci.pub` as a **read-only Deploy Key** on `JosephOIbrahim/Moneta`
   (Settings → Deploy keys).
3. Add the private key `moneta_ci` as secret **`MONETA_DEPLOY_KEY`** on
   `JosephOIbrahim/Synapse` (Settings → Secrets → Actions). `gh secret set
   MONETA_DEPLOY_KEY -R JosephOIbrahim/Synapse < moneta_ci`.
4. Delete the local keypair. Next CI run installs Moneta and runs the ~70 tests;
   the tripwire fails loudly if the checkout/install ever breaks.

---

### Status
| Follow-up | Risk | Blocked on | Ship as |
|---|---|---|---|
| FU-1 Memory.id | Low | — | focused PR (invert tripwire) |
| FU-2 AP6 gating | Low–mod | — (wire when a tool calls it) | PR when sleep_pass is exposed |
| FU-3 CI Moneta | Low | `MONETA_DEPLOY_KEY` secret (workflow already wired conditionally) | DONE — activates on the secret |
