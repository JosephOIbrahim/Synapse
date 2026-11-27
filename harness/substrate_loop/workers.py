"""Workers - the part that spends local GPU, not Claude tokens.

Two backends, picked by the tier in tiers.json. Code references tiers, never
model strings, so swapping a model is a one-line edit there.

    lean         The loop drives the model over Ollama's /api/chat. It hands
                 over the objective, the failure from last time and up to
                 `max_files` files; the model answers with SEARCH/REPLACE edit
                 blocks that the loop applies. Small context, fast, predictable.

    claude-code  `claude -p` runs inside the worktree with Read/Edit tools and
                 edits files itself. With provider "ollama" it talks to the
                 local server through Ollama's Anthropic-compatible endpoint, so
                 it spends no Anthropic tokens. With provider "anthropic" the
                 same worker runs on a real Claude model (Haiku, Opus): that is
                 the swap for when a local model stalls.

Neither worker runs a gate or a commit. The loop owns verification; a worker
only ever proposes.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")


class WorkerError(RuntimeError):
    """The worker could not produce a proposal (server down, bad reply, timeout)."""


@dataclass
class Proposal:
    edits: list[tuple[str, str, str]] = field(default_factory=list)  # (path, search, replace)
    why: str = ""
    edited_in_place: bool = False   # claude-code worker already changed the files
    cost_usd: float = 0.0
    seconds: float = 0.0
    raw: str = ""


# ---------------------------------------------------------------- ollama plumbing

def _post(path: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        OLLAMA + path, method="POST", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WorkerError(f"ollama {path}: {exc}") from exc


def ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as r:
            return [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except Exception as exc:
        raise WorkerError(f"ollama is not answering at {OLLAMA} ({exc}) - start it with `ollama serve`") from exc


def unload(model: str) -> None:
    """Free the GPU (used when Houdini opens mid-run). Best effort."""
    try:
        _post("/api/generate", {"model": model, "keep_alive": 0}, timeout=30)
    except WorkerError:
        pass


# ---------------------------------------------------------------- edit blocks

BLOCK = re.compile(
    r"FILE:\s*(?P<path>[^\n]+?)\s*\n"
    r"<<<<<<< SEARCH\n(?P<search>.*?)\n?=======\n(?P<replace>.*?)\n?>>>>>>> REPLACE",
    re.DOTALL,
)


def parse_edits(text: str) -> tuple[list[tuple[str, str, str]], str]:
    edits = [(m["path"].strip().strip("`"), m["search"], m["replace"]) for m in BLOCK.finditer(text)]
    why = ""
    m = re.search(r"^WHY:\s*(.+)$", text, re.MULTILINE)
    if m:
        why = m.group(1).strip()[:300]
    return edits, why


LEAN_RULES = """\
You improve one Python repository toward one objective, one small change at a time.
A harness applies your edits, runs the repository's own tests and measures one number.
Your change is kept only if every test still passes and the number gets better.

Reply with one or more edit blocks in exactly this form, and nothing else before them:

FILE: path/relative/to/repo.py
<<<<<<< SEARCH
lines copied exactly from the file shown
=======
the new lines
>>>>>>> REPLACE

SEARCH must match the current file exactly, once. Keep each change small.
You may only edit the files shown. Never weaken, skip or delete a test.
End with one line: WHY: <one sentence on what you changed and why it moves the number>
"""


def _lean_prompt(ctx: dict) -> str:
    parts = [ctx["program"].strip(), "", f"OBJECTIVE: {ctx['objective']}",
             f"METRIC: {ctx['metric_name']} is {ctx['metric_value']} ({ctx['direction']} is better)."]
    if ctx.get("metric_detail"):
        parts += ["", "METRIC OUTPUT (tail):", ctx["metric_detail"]]
    if ctx.get("last_failure"):
        parts += ["", "YOUR LAST ATTEMPT WAS DISCARDED BECAUSE:", ctx["last_failure"]]
    if ctx.get("deadends"):
        parts += ["", "ALREADY TRIED AND DISCARDED (do not repeat):"]
        parts += [f"- {d}" for d in ctx["deadends"]]
    for path, body in ctx["files"]:
        parts += ["", f"=== {path} ===", body]
    return "\n".join(parts)


def _lean(tier: dict, ctx: dict) -> Proposal:
    t0 = time.time()
    reply = _post("/api/chat", {
        "model": tier["model"],
        "stream": False,
        "keep_alive": tier.get("keep_alive", "30m"),
        "options": {"num_ctx": int(tier.get("num_ctx", 32768)),
                    "temperature": float(tier.get("temperature", 0.3))},
        "messages": [{"role": "system", "content": LEAN_RULES},
                     {"role": "user", "content": _lean_prompt(ctx)}],
    }, timeout=int(tier.get("timeout_s", 900)))
    text = (reply.get("message") or {}).get("content", "")
    if not text.strip():
        raise WorkerError("model returned an empty reply")
    edits, why = parse_edits(text)
    return Proposal(edits=edits, why=why, seconds=time.time() - t0, raw=text)


# ---------------------------------------------------------------- claude -p

def claude_env(tier: dict) -> dict:
    env = dict(os.environ)
    if tier.get("provider", "ollama") == "ollama":
        env.update({"ANTHROPIC_BASE_URL": OLLAMA, "ANTHROPIC_AUTH_TOKEN": "ollama",
                    "ANTHROPIC_API_KEY": ""})
    return env


def claude_base_cmd(tier: dict) -> list[str]:
    cmd = [tier.get("claude_bin", "claude")]
    # --bare skips hooks, CLAUDE.md, MCP and plugins: same behaviour on every
    # run, smaller prompt for a local model. It never reads the subscription
    # login, so a provider-"anthropic" tier drops it and uses your login.
    if tier.get("provider", "ollama") == "ollama":
        cmd.append("--bare")
    return cmd


def _claude_code(tier: dict, ctx: dict) -> Proposal:
    prompt = "\n".join([
        ctx["program"].strip(), "",
        f"OBJECTIVE: {ctx['objective']}",
        f"METRIC: {ctx['metric_name']} is {ctx['metric_value']} ({ctx['direction']} is better).",
        "You may edit only these files: " + ", ".join(ctx["allowed"]),
        "Never edit tests. Make one small change, then stop and reply with one line: WHY: <reason>.",
        *(["", "Last attempt was discarded because:", ctx["last_failure"]] if ctx.get("last_failure") else []),
        *(["", "Already tried and discarded:", *[f"- {d}" for d in ctx.get("deadends", [])]] if ctx.get("deadends") else []),
        *(["", "Metric output (tail):", ctx["metric_detail"]] if ctx.get("metric_detail") else []),
    ])
    cmd = claude_base_cmd(tier) + [
        "-p", prompt, "--model", tier["model"], "--output-format", "json",
        "--max-turns", str(tier.get("max_turns", 25)),
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Edit,Write,Glob,Grep",
        *tier.get("extra_args", []),
    ]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ctx["worktree"], env=claude_env(tier), capture_output=True,
                           text=True, timeout=int(tier.get("timeout_s", 1800)), check=False)
    except FileNotFoundError as exc:
        raise WorkerError("`claude` is not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise WorkerError("claude worker timed out") from exc
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise WorkerError(f"claude worker gave no JSON (exit {p.returncode}): {p.stderr[-400:]}") from exc
    if out.get("is_error"):
        raise WorkerError(f"claude worker failed: {str(out.get('result'))[:400]}")
    _, why = parse_edits(str(out.get("result", "")))
    return Proposal(edited_in_place=True, why=why or str(out.get("result", ""))[:200],
                    cost_usd=float(out.get("total_cost_usd") or 0.0),
                    seconds=time.time() - t0, raw=str(out.get("result", "")))


BACKENDS = {"lean": _lean, "claude-code": _claude_code}


def propose(tier: dict, ctx: dict) -> Proposal:
    backend = tier.get("backend", "lean")
    if backend not in BACKENDS:
        raise WorkerError(f"unknown worker backend {backend!r}")
    return BACKENDS[backend](tier, ctx)


# ---------------------------------------------------------------- reviewer (optional)

VERDICT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {"keep": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["keep", "reason"],
})


def review(tier: dict, objective: str, diff: str) -> tuple[bool, str, float]:
    """Ask a real Claude model whether a gate-passing diff is a genuine improvement.

    Only runs when a mission sets review_each_keep. Returns (keep, reason, cost_usd).
    """
    prompt = (
        "A local model proposed the diff on stdin. Every test passed and the metric improved. "
        "Decide if it is a genuine improvement toward the objective, or gaming the metric "
        "(silencing warnings, deleting behaviour, special-casing a test). "
        f"Objective: {objective}"
    )
    cmd = claude_base_cmd(tier) + [
        "-p", prompt, "--model", tier["model"], "--output-format", "json",
        "--max-turns", "1", "--permission-mode", "dontAsk",
        "--json-schema", VERDICT_SCHEMA,
        "--max-budget-usd", str(tier.get("max_budget_usd", 0.25)),
    ]
    try:
        p = subprocess.run(cmd, input=diff[:200_000], env=claude_env(tier), capture_output=True,
                           text=True, timeout=600, check=False)
        out = json.loads(p.stdout)
    except Exception as exc:
        raise WorkerError(f"reviewer failed: {exc}") from exc
    verdict = out.get("structured_output") or {}
    if "keep" not in verdict:
        raise WorkerError("reviewer returned no verdict")
    return bool(verdict["keep"]), str(verdict.get("reason", ""))[:300], float(out.get("total_cost_usd") or 0.0)
