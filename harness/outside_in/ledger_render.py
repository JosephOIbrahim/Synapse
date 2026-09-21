"""Render harness/notes/outside_in/LEDGER.md from results.jsonl.

The curated header (intent, fairness rules, UNKNOWN policy, pinned model) is a constant
here so regeneration never loses it; the table below it is generated, with the PRODUCER
COMMAND printed directly above it (house rule: no number without a producer path). Median
and range are shown, never the best. UNKNOWN is shown as UNKNOWN, never as 0.
"""
from __future__ import annotations

import json
from pathlib import Path

PRODUCER = "python harness/outside_in/run.py --scene empty --runs 1 --limit 1"

HEADER = """# Outside-in benchmark ledger

SYNAPSE (panel path, ws://localhost:9999/synapse) vs fxhoudinimcp (MCP over stdio, hwebserver :8100),
isolated hython per arm, isolated scene copy per arm. This ledger holds the measured numbers behind
SYNAPSE's founding claim: cost scales with what you ask about, not with the scene.

**Pinned model (both arms):** `{model}` -- recorded in every row; the arms differ only in tool
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
"""


def _fmt(v):
    return "UNKNOWN" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def _mr(median, rng):
    if median is None:
        return "UNKNOWN"
    lo, hi = (rng or [None, None])[:2]
    if lo is None or lo == hi:
        return _fmt(median)
    return f"{_fmt(median)} [{_fmt(lo)}-{_fmt(hi)}]"


def render(repo: Path, outdir: Path, results: Path, ledger: Path, model: str):
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    if results.exists():
        for line in results.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    lines = [HEADER.format(model=model), "", "## Results", "",
             f"_Producer:_ `{PRODUCER}`", ""]
    cols = ["arm", "prompt", "domain", "runs", "in_tok (med [range])", "out_tok (med [range])",
            "tools", "wall_s (med [range])", "verdicts", "UNKNOWN", "jev_kind", "ledger_rows"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join("---" for _ in cols) + "|")
    if not rows:
        lines.append("| _(no benchmark rows yet -- run the producer above)_ |" + " |" * (len(cols) - 1))
    for r in rows:
        lines.append("| " + " | ".join([
            str(r.get("arm", "?")), str(r.get("prompt", "?")), str(r.get("domain", "?")),
            str(r.get("runs", "?")),
            _mr(r.get("input_tokens_median"), r.get("input_tokens_range")),
            _mr(r.get("output_tokens_median"), r.get("output_tokens_range")),
            _fmt(r.get("tool_calls_median")),
            _mr(r.get("wall_s_median"), r.get("wall_s_range")),
            ",".join(r.get("verdicts", [])) or "UNKNOWN",
            str(r.get("unknown_count", 0)),
            ",".join(r.get("jev_kinds", [])) or "-",
            _fmt(r.get("ledger_rows")),
        ]) + " |")
    lines += ["", "### Reading the rows", "",
              "- `verdicts` come from `verify.py` in a third hython; `jev_kind` is the JEV-BENCH label",
              "  for a not-pass (`refused_unsupported` -> UNKNOWN; else FAIL with a kind).",
              "- `ledger_rows` (SYNAPSE only) is wired at live-run time from `synapse_metrics`; UNKNOWN until then.",
              "- A row that is all UNKNOWN means the arm was unreachable this run -- the reason is in "
              "`results.jsonl`'s `per_run[].reason`, not hidden.", ""]
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ledger
