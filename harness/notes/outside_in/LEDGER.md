# Outside-in benchmark ledger

SYNAPSE (panel path, ws://localhost:9999/synapse) vs fxhoudinimcp (MCP over stdio, hwebserver :8100),
isolated hython per arm, isolated scene copy per arm. This ledger holds the measured numbers behind
SYNAPSE's founding claim: cost scales with what you ask about, not with the scene.

**Pinned model (both arms):** `claude-sonnet-5` -- recorded in every row; the arms differ only in tool
surface and transport, never in the harness or the model.

**Fairness rules (written before the first run, HARVEST_SPEC sec 'Target 3'):**

- Both arms get the same prompt text; no arm-specific hints (enforced by the JEV leak-check).
- fxhoudinimcp runs with its own server instructions intact.
- SYNAPSE runs the panel path, not the external MCP surface.
- A prompt an arm cannot attempt scores **UNKNOWN**, not fail; the UNKNOWN count is a reported number.
- Three runs per cell in the full run; the ledger shows **median and range, never the best**.

**Numbers policy:** every token count comes from the provider response (`usage.input_tokens` /
`usage.output_tokens`), never a proxy tokenizer. An unreachable arm is **UNKNOWN with a reason**,
never a fabricated count. `verify.py` decides PASS/FAIL in a third hython that reads no arm text.

**Scope of THIS leg (BP10-BENCH):** plumbing proven on one prompt on the empty scene; the full G5
run (24 prompts x 2 arms x 3 runs) is SPEND held for Joe. See the receipt for the live-run blocker.


## Results

_Producer:_ `python harness/outside_in/run.py --scene empty --runs 1 --limit 1`

| arm | prompt | domain | runs | in_tok (med [range]) | out_tok (med [range]) | tools | wall_s (med [range]) | verdicts | UNKNOWN | jev_kind | ledger_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| synapse | sop-01 | SOP | 1 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | 1 | - | UNKNOWN |
| fxhoudinimcp | sop-01 | SOP | 1 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | 1 | - | UNKNOWN |

### Reading the rows

- `verdicts` come from `verify.py` in a third hython; `jev_kind` is the JEV-BENCH label
  for a not-pass (`refused_unsupported` -> UNKNOWN; else FAIL with a kind).
- `ledger_rows` (SYNAPSE only) is wired at live-run time from `synapse_metrics`; UNKNOWN until then.
- A row that is all UNKNOWN means the arm was unreachable this run -- the reason is in `results.jsonl`'s `per_run[].reason`, not hidden.

