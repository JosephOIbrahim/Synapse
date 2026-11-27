"""Metrics - the one number each mission may move.

Every metric returns (value, detail). `detail` is the raw tool output the
worker sees next iteration, so it knows *where* the number comes from.
Lower is better unless the mission says `"direction": "max"`.

Kinds:
    ruff           count of `ruff check` findings over `args` paths
    mypy           count of `error:` lines from mypy over `args` paths
    pytest_failed  failed + errored tests from a pytest run (`cmd`) - the target of a fix mission
    command        any command; `regex` captures one float from its output

Unmeasured is not zero. A metric that cannot be read raises MetricUnreadable,
and the loop treats that candidate as discarded, never as an improvement.
"""
from __future__ import annotations

import re
import subprocess
import sys


class MetricUnreadable(RuntimeError):
    pass


def _run(cmd: list[str], cwd: str, env: dict | None, timeout: int) -> str:
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False,
                           timeout=timeout)
    except FileNotFoundError as exc:
        raise MetricUnreadable(f"tool not found: {cmd[0]} ({exc})") from exc
    except subprocess.TimeoutExpired as exc:
        raise MetricUnreadable(f"metric timed out after {timeout}s") from exc
    return (p.stdout or "") + (p.stderr or "")


def _ruff(spec, cwd, env, timeout):
    out = _run([sys.executable, "-m", "ruff", "check", "--output-format", "concise",
                *spec.get("args", ["."])], cwd, env, timeout)
    if "No module named ruff" in out:
        raise MetricUnreadable("ruff is not installed in this interpreter")
    if "All checks passed" in out:
        return 0.0, out
    m = re.search(r"Found (\d+) error", out)
    if not m:
        raise MetricUnreadable("could not find ruff's summary line")
    return float(m.group(1)), out


def _mypy(spec, cwd, env, timeout):
    out = _run([sys.executable, "-m", "mypy", *spec.get("args", ["."])], cwd, env, timeout)
    if "No module named mypy" in out:
        raise MetricUnreadable("mypy is not installed in this interpreter")
    if not re.search(r"^(Success|Found \d+ error)", out, re.MULTILINE):
        raise MetricUnreadable("could not find mypy's summary line")
    return float(len(re.findall(r": error:", out))), out


def _pytest_failed(spec, cwd, env, timeout):
    out = _run(spec["cmd"], cwd, env, timeout)
    tail = out.strip().splitlines()[-1:] or [""]
    summary = tail[0]
    if not re.search(r"\b(passed|failed|error|errors|no tests ran)\b", summary):
        raise MetricUnreadable("could not find pytest's summary line")
    failed = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b", summary))
    return float(failed), out


def _command(spec, cwd, env, timeout):
    out = _run(spec["cmd"], cwd, env, timeout)
    m = None
    for m in re.finditer(spec["regex"], out):
        pass  # last match wins: the final summary line, not an early echo
    if m is None:
        raise MetricUnreadable(f"regex {spec['regex']!r} matched nothing")
    return float(m.group(1)), out


KINDS = {"ruff": _ruff, "mypy": _mypy, "pytest_failed": _pytest_failed, "command": _command}


def measure(spec: dict, cwd: str, env: dict | None = None) -> tuple[float, str]:
    kind = spec.get("kind")
    if kind not in KINDS:
        raise MetricUnreadable(f"unknown metric kind {kind!r}")
    return KINDS[kind](spec, cwd, env, int(spec.get("timeout_s", 900)))


def improved(before: float, after: float, direction: str, min_delta: float) -> bool:
    """Strictly better by at least min_delta. A tie is not progress."""
    gain = (before - after) if direction == "min" else (after - before)
    return gain >= min_delta and gain > 0
