# jev_bench.py - JEV-BENCH guard: verify.py not-pass -> a named failure_kind in the LEDGER.
# verify.py (harness/outside_in/) tells PASS from not-pass with plain `hou`; it cannot tell
# WHY a not-pass happened. This guard reads the arm's final text tail and last tool names and
# classifies the failure (refused / attempted-and-failed / claimed-success / asked-clarification).
# CODE OWNS THE DECISION: Jev supplies calibrated probabilities; the policy that turns them into
# an outcome is decide() below, a plain function you can read. Every call is ledgered; a fallback
# (no key / timeout / SDK error) never carries a fabricated probability.
#
# Policy (mission BP10-BENCH T3; questions.json guards.bench; ADR-0001 Site 3):
#   no Jev answer (no key / timeout / disabled)  -> FAIL / unjudged   (distinct from UNKNOWN)
#   failure_kind confidence < confidence_floor    -> FAIL / cannot_tell (NEVER UNKNOWN)
#   P(refused_unsupported) >= refused_min         -> UNKNOWN            (an unsupported context, not a fail)
#   otherwise                                     -> FAIL / <top failure_kind>
#
# --leak-check runs the leak Noul (hints_a_tool_or_arm) over every prompt so no prompt hands an
# arm a tool or arm name. Its ledger is committed. A prompt scoring >= 0.50 is rewritten before
# any benchmark run.
#
# Invariant 5 (JEV_BLUEPRINT sec.4): this module lives in harness/jev and is imported only by the
# build-time harness (harness/outside_in/verify.py). No product code reaches here
# (pinned by tests/test_jev_product_boundary.py). A Jev answer never promotes a chunk, never names
# a model, never grants consent, never writes a scene.
# Source: harness/battleplan/notes/JEV_BLUEPRINT.md sec.4; ADR-0001 sec 'Site 3'.
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
PROMPTS_DEFAULT = REPO / "harness" / "outside_in" / "prompts.jsonl"

# The leak question. questions.json (guards.bench) is owned by the scaffold leg and is NOT in this
# leg's touched surface, and this wave forbids an intra-wave shared seam; so the leak question lives
# here as diffable data. It is still a text edit with a diff, honouring invariant 6 in spirit. It
# SHOULD be promoted into questions.json guards.bench by a leg that owns that file (see receipt
# for_ruling). If a future questions.json adds it, _leak_question() prefers that copy.
LEAK_QUESTION_DEFAULT = {
    "type": "noul",
    "instructions": (
        "Does `prompt_text` reveal or steer toward a SPECIFIC software tool, function, MCP tool "
        "name, server, plugin, application panel, product, or one of the two benchmark ARMS being "
        "compared -- for example a product or bridge name, a function/tool identifier, or an "
        "instruction to call one named tool? Answer YES only for such a tool-surface or arm-specific "
        "hint that could advantage one agent over the other. Answer NO for ordinary Houdini creative "
        "vocabulary that BOTH arms share equally -- node types, VEX or wrangles, USD or Solaris "
        "stages, Copernicus or COPs, Karma, Pyro, Vellum, render settings: naming a Houdini technique "
        "or context is the artist's normal language, not a tool or arm hint."
    ),
}


def _bench_guard() -> dict:
    return jc.load_questions()["guards"]["bench"]


def _leak_question() -> dict:
    """Prefer a hints_a_tool_or_arm question in questions.json if one is ever added; else the
    module default. Never edits questions.json."""
    qs = _bench_guard().get("questions", {})
    return qs.get("hints_a_tool_or_arm", LEAK_QUESTION_DEFAULT)


def bench_spec() -> dict:
    """failure_kind (Choice) + named_a_limitation (Noul), read from questions.json guards.bench."""
    g = _bench_guard()["questions"]
    fk = g["failure_kind"]
    nl = g["named_a_limitation"]
    return {
        "failure_kind": {"type": "choice", "instructions": fk["instructions"], "criteria": fk["criteria"]},
        "named_a_limitation": {"type": "noul", "instructions": nl["instructions"]},
    }


def _tail(s: str, n: int = 1500) -> str:
    s = s or ""
    return s[-n:]


def _last(seq, n: int = 3) -> list:
    seq = list(seq or [])
    return seq[-n:]


def bench_state(prompt_text: str, final_text: str, tools, check_summary: str) -> dict:
    """State per questions.json guards.bench.state_fields. Tail = last 1,500 chars; last 3 tools."""
    return {
        "prompt_text": prompt_text,
        "final_text_tail": _tail(final_text, 1500),
        "last_tools": _last(tools, 3),
        "check_summary": check_summary,
    }


def decide(answers: dict | None, policy: dict) -> dict:
    """The whole policy, in code. Called ONLY on a not-pass. Returns a LEDGER outcome dict."""
    refused_min = float(policy.get("refused_unsupported_min", 0.7))
    conf_floor = float(policy.get("confidence_floor", 0.6))
    unknown_v = policy.get("unknown_verdict", "UNKNOWN")
    fail_v = policy.get("other_verdict", "FAIL")

    if answers is None:  # fail closed: no key / timeout / disabled / malformed -> unjudged, NOT unknown
        return {"verdict": fail_v, "kind": "unjudged",
                "reason": "fallback: no Jev answer (see ledger); UNKNOWN is never fabricated from absence",
                "confidence": None, "p_refused": None, "named_limitation": None, "jev": None}

    fk = answers.get("choices", {}).get("failure_kind") or {}
    choice = fk.get("choice")
    probs = fk.get("probabilities") or {}
    conf = fk.get("confidence")
    if conf is None and probs:
        conf = max(probs.values())
    p_refused = float(probs.get("refused_unsupported", 0.0) or 0.0)
    named = (answers.get("nouls", {}).get("named_a_limitation") or {}).get("noul")
    jev = {"choice": choice, "confidence": conf, "probabilities": probs, "named_a_limitation": named}

    if conf is None or conf < conf_floor:
        return {"verdict": fail_v, "kind": "cannot_tell",
                "reason": f"failure_kind confidence {conf if conf is None else round(conf, 3)} < floor {conf_floor}; never UNKNOWN on low confidence",
                "confidence": conf, "p_refused": p_refused, "named_limitation": named, "jev": jev}

    if p_refused >= refused_min:
        return {"verdict": unknown_v, "kind": "refused_unsupported",
                "reason": f"P(refused_unsupported)={round(p_refused, 3)} >= {refused_min}: unsupported context, not a fail"
                          + (f"; named a limitation ({round(named, 3)})" if isinstance(named, (int, float)) else ""),
                "confidence": conf, "p_refused": p_refused, "named_limitation": named, "jev": jev}

    return {"verdict": fail_v, "kind": choice or "cannot_tell",
            "reason": f"failure_kind={choice} at confidence {round(conf, 3)}",
            "confidence": conf, "p_refused": p_refused, "named_limitation": named, "jev": jev}


def classify_leg(prompt_text: str, final_text: str, tools, check_summary: str,
                 *, wave: str = "bp10", leg: str) -> dict:
    """Classify ONE not-pass. Asks Jev (guard 'bench' -> bp10.bench.jsonl), applies decide(),
    ledgers the decision. Never raises: a fallback is a valid, honest outcome."""
    g = _bench_guard()
    state = bench_state(prompt_text, final_text, tools, check_summary)
    answers = jc.ask(state, bench_spec(), wave=wave, guard="bench", leg=leg)
    d = decide(answers, g["policy"])
    jc.ledger(wave, "bench", {"leg": leg, "result": "decision", "decision": d,
                              "state_hash": jc.state_hash(state)})
    return d


# --------------------------------------------------------------------------- #
# --leak-check: no prompt may hand an arm a tool or arm name.
# --------------------------------------------------------------------------- #
def leak_check(prompts_path: Path, *, wave: str = "bp10", threshold: float = 0.5) -> dict:
    rows = [json.loads(l) for l in Path(prompts_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    spec = {"hints_a_tool_or_arm": _leak_question()}
    out = []
    fallbacks = 0
    for r in rows:
        pid = r.get("id", "?")
        answers = jc.ask({"prompt_text": r["prompt"]}, spec, wave=wave, guard="leak", leg=pid)
        if answers is None:
            fallbacks += 1
            out.append({"id": pid, "noul": None, "leak": False, "status": "fallback"})
            continue
        noul = (answers.get("nouls", {}).get("hints_a_tool_or_arm") or {}).get("noul")
        leak = isinstance(noul, (int, float)) and noul >= threshold
        out.append({"id": pid, "noul": noul, "leak": bool(leak), "status": "measured"})
    leaked = [r for r in out if r["leak"]]
    summary = {"prompts": len(rows), "measured": len(rows) - fallbacks, "fallbacks": fallbacks,
               "threshold": threshold, "leaked": [r["id"] for r in leaked], "rows": out}
    jc.ledger(wave, "leak", {"result": "summary", "summary": {k: v for k, v in summary.items() if k != "rows"}})
    return summary


def _print_leak(summary: dict) -> int:
    print(f"leak-check over {summary['prompts']} prompts  "
          f"(measured {summary['measured']}, fallback {summary['fallbacks']}, threshold {summary['threshold']})")
    for r in summary["rows"]:
        noul = "  --  " if r["noul"] is None else f"{r['noul']:.3f}"
        mark = "LEAK" if r["leak"] else ("fallback" if r["status"] == "fallback" else "ok")
        print(f"  {r['id']:10} noul={noul}  {mark}")
    print(f"-- ledger: harness/jev/ledger/{ 'bp10'}.leak.jsonl")
    if summary["fallbacks"] == summary["prompts"] and summary["prompts"] > 0:
        print("-- ALL fallback: no TYPESAFE_API_KEY resolved; leak scores UNKNOWN, not 0. "
              "The prompts were authored leak-free by construction; re-run with a key to measure.")
    if summary["leaked"]:
        print(f"-- ACTION: rewrite leaking prompt(s) {summary['leaked']} before any benchmark run.")
        return 1
    return 0


# --------------------------------------------------------------------------- #
# --grade: replay ledgered bench decisions against bench_key.json hand labels. ZERO new Jev calls.
# --------------------------------------------------------------------------- #
def grade(key_path: Path, *, wave: str = "bp10") -> int:
    key = json.loads(Path(key_path).read_text(encoding="utf-8")) if Path(key_path).exists() else {}
    labels = {k: v for k, v in key.items() if not k.startswith("_")}
    led = jc.LEDGER_DIR / f"{wave}.bench.jsonl"
    decided = {}
    if led.exists():
        for line in led.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("result") == "decision":
                decided[row["leg"]] = row["decision"]
    if not labels:
        print("no hand labels in bench_key.json yet; nothing to grade (template is empty by design)")
        return 0
    print(f"{'prompt':12} {'expected_kind':22} {'jev_kind':22} {'verdict':8} agree")
    hit = 0
    for pid, lab in sorted(labels.items()):
        d = decided.get(pid)
        jk = d["kind"] if d else "-"
        agree = (jk == lab.get("expected_kind")) if d else False
        hit += agree
        print(f"{pid:12} {str(lab.get('expected_kind')):22} {jk:22} {str(d['verdict']) if d else '-':8} {'yes' if agree else 'no'}")
    print(f"-- {hit}/{len(labels)} agree; evidence for a ruling, not a ruling. Re-run after a labelled bench run.")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="JEV-BENCH guard: failure classification + prompt leak check.")
    ap.add_argument("--leak-check", action="store_true", help="run the leak Noul over every prompt")
    ap.add_argument("--prompts", default=str(PROMPTS_DEFAULT), help="prompts.jsonl (default: harness/outside_in/prompts.jsonl)")
    ap.add_argument("--wave", default="bp10")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--grade", metavar="BENCH_KEY", help="grade ledgered decisions against a bench_key.json")
    ap.add_argument("--classify", metavar="@FILE_OR_JSON",
                    help="classify one not-pass from a JSON state {prompt_text,final_text,last_tools,check_summary,leg}")
    a = ap.parse_args()

    if a.leak_check:
        sys.exit(_print_leak(leak_check(Path(a.prompts), wave=a.wave, threshold=a.threshold)))
    if a.grade:
        sys.exit(grade(Path(a.grade), wave=a.wave))
    if a.classify:
        raw = a.classify
        st = json.loads(Path(raw[1:]).read_text(encoding="utf-8")) if raw.startswith("@") else json.loads(raw)
        d = classify_leg(st.get("prompt_text", ""), st.get("final_text", ""), st.get("last_tools", []),
                         st.get("check_summary", ""), wave=a.wave, leg=st.get("leg", "AD-HOC"))
        print(json.dumps(d, indent=1))
        sys.exit(0)
    ap.print_help()
    sys.exit(2)
