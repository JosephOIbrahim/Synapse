# OPERATOR'S CARD — cache advisor (Phase 0+1)

*One card, one system. Updated 2026-08-09, wave R-CACHE-1. Read-only by design — the
advisor observes and recommends; it never cooks a dirty node, never writes disk, never
inserts a node. Phase 2 (insert/bake) does not exist and is REJECTed pending SideFX.*

---

## Turn it on

```powershell
$env:SYNAPSE_CACHE_ADVISOR_ENABLED = '1'     # session-scoped; OFF by default
```

Flag logic: `advisor_enabled()` in `python/synapse/server/handlers_cache.py`.

## Run it

Inside a live Houdini 22.0.400 session, through the panel bridge:
call the tool **`synapse_assess_cache`** on a selected node (read-only class,
registered in `python/synapse/panel/bridge_adapter.py`).

## What you'll see

One advice card on the existing panel result surface:
one verdict headline (`cache_now` / `insert_boundary_only` / `measure_first` /
`optimize_first` / `not_worth_it` / `insufficient_disk` / `unsupported` / `unknown`),
up to three reasons, ranges not point estimates, blockers separated from uncertainty,
confidence + missing evidence always listed.

## When it breaks

1. **Cook time shows UNKNOWN with `lastCookTime_unreported`** — expected in any
   headless/farm/hbatch context: `lastCookTime()` returns 0.0 there on 22.0.400
   (observed contract, SUPPORT_MATRIX). In-GUI it reports real milliseconds.
2. **Verdict `unsupported`** — the node's context has no validated strategy
   (only SOP geometry / VDB-only / SOP-level sim results resolve in Phase 1).
   Not a bug; the registry refuses to guess.
3. **Tool absent from the panel** — flag is off. Set it, restart the bridge.

## Where it lives

```text
python/synapse/cache_policy/        pure decisions (no hou, no Qt) — safe to unit-test anywhere
host/cache_host_probe.py            the ONLY ms->s conversion + UNKNOWN producer
python/synapse/server/handlers_cache.py   tool + flag
python/synapse/panel/bridge_adapter.py    read-only registration
tests/assay_h22_cache_contract.py   live contract, rerun per build:
```

```powershell
& 'C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe' tests\assay_h22_cache_contract.py
```

Expect **7/7**. Item 3 is a declared delta: headless 0.0 is the pass condition and
fails loudly only if SideFX changes the behavior.

---

# APPENDIX — dispatching an agent-team wave (`claude -p`)

The runner shape that survives everything (pattern of record, five waves proven):

```powershell
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = '0'    # LANDMINE 2: 600s ceiling kills teams
# mission MUST contain: "do NOT end your turn until teammates confirm shutdown;
# actively wait inside this single turn"                LANDMINE 1: hold-turn clause
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$runner -WindowStyle Hidden -PassThru
```

Ticks: mission appends `HH:mm TASK <desc> DONE|FAIL` to a progress log — watch with
`Get-Content <log> -Wait`. Resume after any drop: **read the log first**, never append
blind. Verdict lines print only at the end; silence is normal, file mtimes are the pulse.
