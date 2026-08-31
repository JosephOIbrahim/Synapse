# RAILS_SEAM — the swappable execution seam

**Leg:** BP1-RAILS · **Files:** `harness/rails_exec.json`, `harness/rails.py::resolve_model` · **Stamped:** 2026-08-31

---

## What it is

One JSON lookup table that maps a **tier** to a **model string**. Nothing more.

```
harness/rails_exec.json
  tiers.mechanical.model  = "claude-haiku-4-5-20251001"   (cheapest Claude model)
  tiers.reasoning.model   = "claude-opus-4-8"             (the brief's reasoning default)
```

`rails.py::resolve_model("mechanical")` reads `tiers.mechanical.model` and returns the
string. That is the entire mechanism. It is a lookup, **not** a second orchestrator —
it selects *who runs a leg*, it never *runs* one.

---

## Why a lookup and not a branch

The gap the survey found (`harness/rope/runner.py::claude_cmd`, lines 44-49) is that engine
choice today is a **hardcoded env branch**: `SYNAPSE_ROPE_ENGINE in {claude, ollama}`, and
the model is one human-confirmed `--model` string. There is **no tier axis** — no
mechanical/reasoning distinction, no table.

A table moves that decision out of code and into data. The value proposition (demo first
principle #1, *"Synapse runs without eating tokens"*): route mechanical legs to a cheap or
local engine and reserve Opus for reasoning, by editing one JSON file — never a code change.

---

## How a local engine slots in (do NOT build it here)

`harness/rope/exec_ollama.py` already exists and is **contract-complete** (survey anchor
`exec_ollama.py:21-25, 72-75, 83`): it takes `--task <id> --model <model>`, writes only the
files the task declared, and exits `0` (wrote) / `3` (none). `runner.py::claude_cmd` already
branches to it on `SYNAPSE_ROPE_ENGINE=ollama`.

To make the **mechanical** tier local, a future editor changes two values in
`rails_exec.json` and nothing else:

```jsonc
"mechanical": { "engine": "ollama", "model": "qwen2.5-coder:7b" }
```

Then the caller reads `tiers.mechanical.engine` to decide dispatch (set
`SYNAPSE_ROPE_ENGINE` / build the `exec_ollama.py` argv) and `tiers.mechanical.model` for
the model name. `rails.py::resolve_model` is untouched — it only ever *looks the value up*.
The `engines` block in `rails_exec.json` records each engine's dispatch shape so that wiring
is a copy, not an invention. `engines.ollama.built = false` marks it explicitly out of BP1
scope.

---

## The boundary with `rails.py` (the meter)

The seam answers *who runs it*. The meter (`rails.py`) answers *may we afford it*. They meet
at exactly one place: `charge --tier <t>` resolves the model via the seam and records that
model string in the ledger entry, so the receipt shows which engine/model each turn spent on.
The two never entangle: you can change the table without touching the cap logic, and change
the cap logic without touching the table.

---

## What is deliberately NOT here

- **The local engine itself.** It exists (`exec_ollama.py`); BP1-RAILS does not extend it.
- **A dispatcher.** `harness/orchestrate.ps1` is the one dispatcher; the seam feeds it a
  model string, it does not replace it.
- **A tier classifier.** How a leg *acquires* a tier (reuse `effort`, or add `task.tier`) is
  a follow-on — see the receipt `spawn[]`. The table is ready for it; the classifier is not
  in scope.
