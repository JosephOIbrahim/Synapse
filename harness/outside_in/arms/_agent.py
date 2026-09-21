"""Shared provider agent loop + token accounting for both arms.

Both arms call ``run_agent`` with a tool schema list and a ``tool_runner``. The loop
is a standard Anthropic tool-use cycle; the ONLY numbers it reports come from the
provider response (``usage.input_tokens`` / ``usage.output_tokens``), never a proxy
tokenizer -- this is what closes the README's "no live-model arm" caveat (T2). Tokens
are SUMMED across the turns of one prompt. wall-clock, tool-call count and the last
three tool names are recorded for the ledger.

Fail-closed: any provider or tool exception is captured into ``error`` and the loop
returns what it accumulated. It never raises into the runner, and it never fabricates
a token count -- an unavailable client yields error + zero counts flagged UNKNOWN by
the runner, not a made-up number.
"""
from __future__ import annotations

import json
import os
import time

try:
    import anthropic  # type: ignore
    ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore
    ANTHROPIC_AVAILABLE = False


def load_dotenv_key(repo_root) -> str | None:
    """Read ANTHROPIC_API_KEY from the process env, else from the project's gitignored .env
    (memory: each project reads its own .env; no global key). Never logs the value."""
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    try:
        from pathlib import Path
        env = Path(repo_root) / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return v or None
    except Exception:  # noqa: BLE001
        pass
    return None


def anthropic_client(repo_root=None):
    """Construct an Anthropic client, or None if the SDK or a key is unavailable.
    Returns (client_or_None, reason)."""
    if not ANTHROPIC_AVAILABLE:
        return None, "anthropic SDK not importable"
    key = load_dotenv_key(repo_root) if repo_root else os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, "ANTHROPIC_API_KEY absent (env and .env)"
    try:
        return anthropic.Anthropic(api_key=key), "ok"
    except Exception as e:  # noqa: BLE001
        return None, f"client init failed: {type(e).__name__}: {e}"


def new_result() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "tool_calls": 0, "tool_names": [],
            "last_tools": [], "final_text": "", "wall_s": 0.0, "turns": 0,
            "stop": None, "error": None}


def run_agent(*, client, prompt: str, tools: list, tool_runner, model: str,
              system: str | None = None, max_turns: int = 12, max_tokens: int = 4096) -> dict:
    """One prompt, driven to completion (or max_turns). ``tool_runner(name, input) -> str|obj``
    performs a tool call on the arm's transport and returns its result payload."""
    r = new_result()
    if client is None:
        r["error"] = "provider client unavailable"
        return r
    messages = [{"role": "user", "content": prompt}]
    t0 = time.perf_counter()
    try:
        for turn in range(max_turns):
            r["turns"] = turn + 1
            kwargs = dict(model=model, max_tokens=max_tokens, messages=messages, tools=tools)
            if system:
                kwargs["system"] = system
            resp = client.messages.create(**kwargs)
            usage = getattr(resp, "usage", None)
            if usage is not None:
                r["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
                r["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
            assistant_content, text_parts, tool_uses = [], [], []
            for block in resp.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    text_parts.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                elif btype == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append({"type": "tool_use", "id": block.id,
                                              "name": block.name, "input": block.input})
            if text_parts:
                r["final_text"] = "\n".join(text_parts)
            messages.append({"role": "assistant", "content": assistant_content})
            r["stop"] = getattr(resp, "stop_reason", None)
            if r["stop"] != "tool_use" or not tool_uses:
                break
            tool_results = []
            for tu in tool_uses:
                r["tool_calls"] += 1
                r["tool_names"].append(tu.name)
                try:
                    out = tool_runner(tu.name, tu.input)
                    content = out if isinstance(out, str) else json.dumps(out, default=str)[:6000]
                    is_err = False
                except Exception as e:  # noqa: BLE001 - a tool failure is data, not a crash
                    content = f"tool error: {type(e).__name__}: {e}"[:2000]
                    is_err = True
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                     "content": content, "is_error": is_err})
            messages.append({"role": "user", "content": tool_results})
    except Exception as e:  # noqa: BLE001 - fail closed; keep whatever tokens accrued
        r["error"] = f"{type(e).__name__}: {e}"[:500]
    r["wall_s"] = round(time.perf_counter() - t0, 3)
    r["last_tools"] = r["tool_names"][-3:]
    return r
