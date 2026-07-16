"""H22 doc-scout Phase 3 — candidate probe-runner.

Reads ``harness/notes/h22_doc_candidates.json`` (the doc-scout output) and
EXECUTES each candidate's ``probe`` under H22 hython, recording the raw
execution facts (value / stdout / exception) plus a heuristic hint. This is a
deterministic drop-day instrument in the h22_api_delta.py mold — introspection
+ throwaway scratch nodes only; a denylist SKIPS any probe that would touch
disk or spawn a process (the probe strings are machine-authored from SideFX
docs, but exec-ing arbitrary strings still gets a safety gate).

It assigns only a *hint*; the h22-probe-adjudicate workflow turns these facts
into final VERIFIED / REFUTED / INCONCLUSIVE verdicts (judgment lives there,
because many probes need a live node or print node-type strings that require a
human/agent read).

USAGE:  hython scripts/h22_probe_candidates.py
OUT:    harness/notes/h22_probe_results.json

This lives in scripts/ (operator entrypoint — print() is fine here).
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "harness" / "notes" / "h22_doc_candidates.json"
OUT = ROOT / "harness" / "notes" / "h22_probe_results.json"

# Refuse to auto-exec anything with a disk/process side effect.
DENY = re.compile(
    r"hipFile\.save|os\.remove|os\.unlink|shutil\.|subprocess|Popen|rmtree|"
    r"\.write\(|writeText|saveToFile|open\([^)]*['\"][wa]",
    re.I,
)
# Browser/Qt-side probes cannot run in hython at all.
JS = re.compile(r"window\.Python|QWebChannel|qwebchannel|typeof\s", re.I)
# Must reference a real runtime surface to be worth executing.
CODEY = re.compile(
    r"\bhou\.|\bpxr\.|\bpdg\.|\bdir\(|\bhasattr\(|\bassert\b|nodeType|"
    r"editableStage|\.stage\(|import\s",
    re.I,
)


def build_ns() -> dict:
    import hou

    ns = {"hou": hou, "os": __import__("os"), "sys": sys, "re": re}
    try:
        import pxr  # noqa: F401
        ns["pxr"] = pxr
        for m in ("Usd", "Sdf", "UsdGeom", "UsdShade", "Vt", "Tf", "Gf"):
            try:
                ns[m] = getattr(__import__("pxr", fromlist=[m]), m)
            except Exception:
                pass
    except Exception:
        pass
    return ns


def _short(s, n: int = 700) -> str:
    s = s if isinstance(s, str) else str(s)
    return s if len(s) <= n else s[:n] + " ...(truncated)"


def normalize(probe: str) -> str:
    p = (probe or "").strip()
    # strip a `hython -c "..."` / `python -c "..."` shell wrapper — non-greedy so
    # trailing prose after the closing quote (e.g. `))" -> both True`) is ignored.
    m = re.search(r"""-c\s*(['"])(.*?)\1""", p, re.S)
    if m:
        p = m.group(2)
    # strip a leading `python:` / `hython:` annotation prefix
    p = re.sub(r"^\s*(?:py|hy)thon\s*:\s*", "", p)
    # unwrap a single backtick-quoted code span if it is the code
    m = re.search(r"`([^`]+)`", p)
    if m and any(t in m.group(1) for t in ("hou", "hasattr", "dir(", "assert")):
        p = m.group(1)
    return p.strip()


def _hint_from_value(val, out: str) -> str:
    if isinstance(val, bool):
        return "VERIFIED" if val else "REFUTED"
    if val is None:
        return "VERIFIED" if out.strip() else "INCONCLUSIVE"
    if isinstance(val, (list, tuple, set, dict)):
        return "VERIFIED" if len(val) else "REFUTED"
    if isinstance(val, str):
        return "VERIFIED" if val else "REFUTED"
    return "RAN"


def run_probe(probe: str, ns: dict) -> dict:
    raw = probe or ""
    if not raw.strip():
        return {"runnable": False, "reason": "empty"}
    if DENY.search(raw):
        return {"runnable": False, "reason": "denylist: disk/process side effect"}
    if JS.search(raw):
        return {"runnable": False, "reason": "js/qt surface (not a hython probe)"}
    code = normalize(raw)
    if not CODEY.search(code):
        return {"runnable": False, "reason": "prose (no runtime symbol)"}

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            try:
                val = eval(code, ns)  # expression / list-comp
            except SyntaxError:
                exec(code, ns)  # statements / asserts
                out = buf.getvalue()
                return {
                    "runnable": True, "mode": "exec",
                    "hint": "VERIFIED" if "assert" in code else "RAN",
                    "stdout": _short(out),
                }
            out = buf.getvalue()
            return {
                "runnable": True, "mode": "eval",
                "value": _short(repr(val)), "stdout": _short(out),
                "hint": _hint_from_value(val, out),
            }
    except AssertionError as e:
        return {"runnable": True, "mode": "assert", "hint": "REFUTED",
                "error": "AssertionError: " + _short(str(e)), "stdout": _short(buf.getvalue())}
    except Exception as e:  # noqa: BLE001 — every failure is a datum, never fatal
        return {"runnable": True, "mode": "error", "hint": "PROBE_ERROR",
                "error": type(e).__name__ + ": " + _short(str(e)), "stdout": _short(buf.getvalue())}


def main() -> int:
    data = json.loads(CAND.read_text(encoding="utf-8"))
    ns = build_ns()
    results = []
    counts: dict = {}
    for c in data.get("candidates", []):
        r = run_probe(c.get("probe", ""), ns)
        hint = r.get("hint") or ("NOT_RUNNABLE" if not r.get("runnable") else "RAN")
        counts[hint] = counts.get(hint, 0) + 1
        results.append({
            "id": c.get("id"), "domain": c.get("domain"), "bucket": c.get("bucket"),
            "tier": c.get("tier"), "gap": c.get("gap"), "escalate": c.get("escalate"),
            "doc_url": c.get("doc_url"), "relevance": c.get("relevance"),
            "probe": c.get("probe", ""), "hint": hint, "probe_run": r,
        })
    OUT.write_text(json.dumps({
        "generated_by": "scripts/h22_probe_candidates.py",
        "against_build": data.get("against_build", "22.0.368"),
        "source_report": "docs/reviews/h22-doc-intel-2026-07-15.md",
        "counts": counts,
        "results": results,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    import hou
    print(f"PROBED {len(results)} candidates on {hou.applicationVersionString()} -> {OUT.name}")
    print("HINTS:", json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
