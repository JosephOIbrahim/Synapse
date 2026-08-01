# RSI CLOSURE RELAY — Operator's Card

**The bar** · run anytime, 9 PASS = registry honest (≠ loops closed)

    python harness/rsi/verify.py
    python harness/progress.py

---

## Dispatch — one phase per run, gates between

**1 · SIGNAL** — fix the three lying reward signals (A1 / F / E)

    Workflow rsi-closure  {"phase":"signal","date":"YYYY-MM-DD"}

then → merge each SOUND branch the bar report lists

**2 · DECIDE** — briefs for A2 · S · C (C is the keystone)

    Workflow rsi-closure  {"phase":"decide","date":"YYYY-MM-DD"}

then → read `harness/rsi/briefs/` → flip/defer the three flywheel entries yourself

**3 · CLOSE** — R's L2 evidence + A3 disposition

    Workflow rsi-closure  {"phase":"close","date":"YYYY-MM-DD"}

live render probe only if *you* add `"liveRender":true` · O-audit with `"includeO":true`

---

## Reading the result

- **P4 reason line** — *"still constant"* = signal fix not landed here · *"now carries
  an outcome … registry agrees"* = SIGNAL landed
- worktree claims are **PENDING-MERGE** until you merge them
- R's eval runs with `python tests/rsi/eval_line_r_closure.py` — **never pytest**

## Yours alone

merges · flywheel `ratified` flips · `liveRender` · `dry_run` flips · rungs past L3

## Stop rule

Two consecutive phases of bookkeeping without rung movement → stop the relay.
