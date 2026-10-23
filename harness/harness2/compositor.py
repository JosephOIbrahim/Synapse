# compositor.py - the HARNESS2 compose guard and the graph guard.
#
# Harness2 (google-research/harness2) proposes harness edits, probes them on the same
# task, compares behaviour, and composes a refined harness. It explicitly does NOT
# specify an acceptance threshold, a scoring formula, or a candidate-ranking
# algorithm. This file is that missing specification: the judgment comes from Jev
# (a System One model), the threshold comes from plain code, and the record is
# machine-written.
#
# THE TRUST PATH: Jev -> decision.json -> STATE.json. No language model transcribes a
# verdict into the ledger. A seat may read decision.json; it may not write the
# decision. That is the same lesson AF2 taught: identity carried by an ambient label
# instead of a verified fact is not a fact.
#
# FAIL CLOSED. If Jev cannot answer, the decision is "no adoption" and the candidates
# are reported as needing Joe, with the probe each one still owes. Never a silent
# default dressed as a judgment.
#
# SCRUBBED STATE. Nothing that leaves this machine carries an absolute path, a hash, a
# username or a pid. The scrubber runs on the state BEFORE it is sent.
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parents[0] / "jev"))
import jev_client as jc  # noqa: E402

QUESTIONS = HERE / "questions.json"
RUNS = HERE / "runs"

# ---------------------------------------------------------------- scrubbing

_WIN_ABS = re.compile(r"[A-Za-z]:[\\/][^\s\"'`,;)\]]*")
_POSIX_ABS = re.compile(r"/(?:Users|home|opt|var|tmp|mnt|media|Volumes)/[^\s\"'`,;)\]]*")
_HEX40 = re.compile(r"\b[0-9a-f]{40}\b")
_HEX8 = re.compile(r"\b[0-9a-f]{16,}\b")
_USERDIR = re.compile(r"(?i)\b(?:C:[\\/]Users[\\/]|/Users/|/home/)([A-Za-z0-9_.-]+)")
_PID = re.compile(r"(?i)\b(pid|process id)\s*[:=]?\s*\d+")


def scrub_text(s: str) -> str:
    """Strip machine-specific detail out of a string before it leaves the box."""
    s = _WIN_ABS.sub(lambda m: _relativise(m.group(0)), s)
    s = _POSIX_ABS.sub(lambda m: _relativise(m.group(0)), s)
    s = _USERDIR.sub(lambda m: "<path>/" + m.group(1) + "/", s)
    s = _HEX40.sub("<sha>", s)
    s = _HEX8.sub("<hash>", s)
    s = _PID.sub(lambda m: m.group(1) + " <pid>", s)
    return s


def _relativise(p: str) -> str:
    """A path inside the repo stays readable (repo-relative); anything else becomes <path>.

    BOTH absolute-path branches go through here. The POSIX branch used to
    substitute a bare "<path>", which meant a repo path on a Linux or macOS
    checkout lost every byte of it - while the same path on Windows survived,
    because the Windows branch was the only one that relativised. The scrubber
    has to treat the two platforms the same way, or the evidence it keeps
    depends on which machine produced it.
    """
    try:
        norm = p.replace("\\", "/")
        root = str(REPO).replace("\\", "/")
        if norm.lower().startswith(root.lower()):
            return norm[len(root):].lstrip("/")
    except Exception:  # noqa: BLE001
        pass
    return "<path>"


def scrub(value):
    """Recursively scrub a JSON-able structure."""
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


# ---------------------------------------------------------------- questions

def load_questions() -> dict:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def _fill(template: str, values: dict) -> str:
    """Substitute {key} placeholders without format() - candidate text may contain braces."""
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out


# ---------------------------------------------------------------- binding

def _subject_values(item: dict) -> dict:
    """The substitution values for ONE candidate or node."""
    files = item.get("files") or []
    owner = item.get("owner_files") or files
    return {
        "id": item.get("id", ""),
        "claim": item.get("claim", ""),
        "change": item.get("change", ""),
        "files": ", ".join(str(f) for f in files),
        "probe": item.get("probe", "NOT PROBED"),
        "exclusion": item.get("exclusion", "no exclusion stated"),
        "title": item.get("title", item.get("claim", "")),
        "owner_files": ", ".join(str(f) for f in owner),
        "depends_on": ", ".join(str(d) for d in (item.get("depends_on") or [])) or "none",
        "why": item.get("why", item.get("problem", "")),
    }


def _others_block(items: list[dict], item: dict, sshape: dict, key: str) -> str:
    """The other items in the wave - the composable question is inherently relative."""
    template = (sshape or {}).get(key)
    if not template:
        return ""
    lines = []
    for other in items:
        if other.get("id") == item.get("id"):
            continue
        lines.append(_fill(template, _subject_values(other)))
    return "\n".join(lines)


def _bind(instructions: str, bind: list[str] | None, subject: str, others: str,
          label: str = "ITEM") -> str:
    """Bind a per-item question to ONE item.

    A JEV question id is NOT sent to the model - only the instructions and the criteria
    are. An instruction that says "this candidate" therefore names nothing, while the
    state carries EVERY candidate. The model then averages over the whole set, and the
    per-item questions stop being per-item: a candidate whose probe literally reads
    NOT PROBED scores the same as one with a real before/after probe.

    The fix is the same mechanism the `adopt` choice already uses: substitute the
    item's own text into the instruction at build time, so the question is answerable
    from the instruction alone.
    """
    blocks = []
    for key in (bind or []):
        if key == "subject":
            blocks.append("%s UNDER JUDGMENT:\n%s" % (label, subject))
        elif key == "others":
            if others:
                blocks.append("OTHER ITEMS IN THIS WAVE:\n%s" % others)
            else:
                blocks.append("OTHER ITEMS IN THIS WAVE:\n(none - this is the only item)")
    if not blocks:
        return instructions
    return instructions + "\n\n" + "\n\n".join(blocks)


def check_policy(guard_name: str, guard: dict, spec: dict) -> list[str]:
    """Refuse a DEAD GATE. A Score with N criteria ranges 0..N-1, so a threshold above
    N-1 can never fire; and a Noul threshold outside 0..1 can never fire. Both are
    reported rather than silently ignored."""
    problems = []
    policy = guard.get("policy", {})
    for qid, q in spec.items():
        t = q.get("type")
        if t == "score":
            n = len(q.get("criteria") or [])
            threshold = policy.get("min_strength" if "strength" in qid else "min_value")
            if threshold is None:
                continue
            if n and threshold > n - 1:
                problems.append(f"{guard_name}.{qid}: threshold {threshold} exceeds max score {n - 1} (N={n} criteria) - DEAD GATE")
        if t == "noul":
            for key in ("min_probe_support", "joe_escalate_min"):
                threshold = policy.get(key)
                if threshold is None:
                    continue
                if not (0.0 <= threshold <= 1.0):
                    problems.append(f"{guard_name}.{qid}: {key}={threshold} is outside 0..1 - DEAD GATE")
    return problems


# ---------------------------------------------------------------- compose guard

def compose_spec(candidates: list[dict], guard: dict) -> dict:
    """The compose spec.

    `adopt` gets one criterion per candidate, built at RUNTIME so the model answers with
    a candidate id rather than a free-text label.

    The per-candidate questions (strength/probe/composable) get the CANDIDATE'S OWN TEXT
    substituted into their instructions. Without that binding they are not per-candidate
    questions at all - a JEV question id is never sent to the model, so an instruction
    saying "this candidate" names nothing, and the state carries every candidate.
    """
    shape = guard["criteria_shape"]
    sshape = guard.get("subject_shape") or {}
    label = sshape.get("label", "CANDIDATE")
    criteria = {}
    for c in candidates:
        vals = _subject_values(c)
        criteria[c["id"]] = {
            "what": _fill(shape["what"], vals),
            "not_for": _fill(shape["not_for"], vals),
        }
    q = guard["questions"]
    spec = {
        "adopt": {"type": "choice", "instructions": q["adopt"]["instructions"], "criteria": criteria},
    }
    for c in candidates:
        vals = _subject_values(c)
        subject = _fill(sshape.get("subject", "{claim}"), vals)
        others = _others_block(candidates, c, sshape, "others")
        for qid, kind in (("strength", "score"), ("probe", "noul"), ("composable", "noul")):
            spec[qid + "_" + c["id"]] = {
                "type": kind,
                "instructions": _bind(q[qid]["instructions"], q[qid].get("bind"),
                                      subject, others, label),
                "criteria": q[qid].get("criteria"),
            }
    return spec


def files_disjoint(a: dict, b: dict) -> bool:
    """The single-writer rule, checked in CODE because a file set is mechanically
    checkable. Jev's opinion does not override two seats claiming one file."""
    fa = {str(x) for x in (a.get("files") or a.get("owner_files") or [])}
    fb = {str(x) for x in (b.get("files") or b.get("owner_files") or [])}
    return not (fa & fb)


def decide_compose(answers: dict | None, candidates: list[dict], policy: dict) -> dict:
    """Plain code applies the policy to the judgments. Never a model deciding policy."""
    fallback = {"adopted": [], "reason": policy.get("fallback", "NO ADOPTION"),
                "needs_joe": [c["id"] for c in candidates], "per_candidate": {}}
    if answers is None:
        fallback["reason"] = "fallback: no Jev answer (see the ledger row) - " + fallback["reason"]
        return fallback

    ch = answers["choices"].get("adopt") or {}
    choice = ch.get("choice")
    conf = ch.get("confidence")
    by_id = {c["id"]: c for c in candidates}

    per = {}
    for c in candidates:
        cid = c["id"]
        per[cid] = {
            "strength": (answers["scores"].get("strength_" + cid) or {}).get("score"),
            "probe_support": (answers["nouls"].get("probe_" + cid) or {}).get("noul"),
            "composable": (answers["nouls"].get("composable_" + cid) or {}).get("noul"),
        }

    jev = {"choice": choice, "confidence": conf, "probabilities": ch.get("probabilities")}

    if choice not in by_id:
        return {**fallback, "reason": f"fallback: Jev chose {choice!r}, which is not a candidate id",
                "jev": jev, "per_candidate": per}
    if conf is None or conf < policy["adopt_min_confidence"]:
        return {**fallback, "reason": f"fallback: adopt confidence {conf} < {policy['adopt_min_confidence']}",
                "jev": jev, "per_candidate": per}

    primary = by_id[choice]
    ps = per[choice]
    if ps["strength"] is None or ps["strength"] < policy["min_strength"]:
        return {**fallback, "reason": f"fallback: strength {ps['strength']} < {policy['min_strength']} for {choice}",
                "jev": jev, "per_candidate": per}
    if ps["probe_support"] is not None and ps["probe_support"] < policy["min_probe_support"]:
        return {**fallback, "reason": f"fallback: probe support {ps['probe_support']} < {policy['min_probe_support']} for {choice}",
                "jev": jev, "per_candidate": per}

    adopted = [primary]
    conflicts = []
    for c in candidates:
        if c["id"] == choice:
            continue
        pc = per[c["id"]]
        if pc["strength"] is None or pc["strength"] < policy["min_strength"]:
            continue
        if pc["probe_support"] is not None and pc["probe_support"] < policy["min_probe_support"]:
            continue
        if pc["composable"] is not None and pc["composable"] < policy["min_composable"]:
            continue
        if not files_disjoint(primary, c):
            conflicts.append({"candidate": c["id"], "with": choice, "why": "code check: the two candidates claim the same file"})
            continue
        adopted.append(c)
        if len(adopted) >= policy["max_adoptions"]:
            break

    return {
        "adopted": adopted,
        "reason": f"jev: {choice} @ {conf:.2f} (strength {ps['strength']}, probe {ps['probe_support']}); "
                  f"{len(adopted)} adopted, {len(conflicts)} file conflict(s)",
        "needs_joe": [],
        "primary": choice,
        "conflicts": conflicts,
        "jev": jev,
        "per_candidate": per,
    }


# ---------------------------------------------------------------- graph guard

def graph_spec(nodes: list[dict], guard: dict) -> dict:
    """The graph spec. Same binding rule as the compose guard: a per-node question
    carries that node's own text, because the question id never reaches the model."""
    shape = guard["criteria_shape"]
    sshape = guard.get("subject_shape") or {}
    label = sshape.get("label", "NODE")
    criteria = {}
    for n in nodes:
        vals = _subject_values(n)
        vals["exclusion"] = ("a node whose dependencies are unsatisfied, or whose files "
                             "another node also owns")
        criteria[n["id"]] = {"what": _fill(shape["what"], vals), "not_for": shape["not_for"]}
    q = guard["questions"]
    spec = {
        "first_landing": {"type": "choice", "instructions": q["first_landing"]["instructions"],
                          "criteria": criteria},
    }
    for n in nodes:
        nid = n["id"]
        vals = _subject_values(n)
        subject = _fill(sshape.get("subject", "{title}"), vals)
        others = _others_block(nodes, n, sshape, "others")
        for qid, kind in (("lands", "noul"), ("value", "score"), ("joe_decides", "noul")):
            spec[qid + "_" + nid] = {
                "type": kind,
                "instructions": _bind(q[qid]["instructions"], q[qid].get("bind"),
                                      subject, others, label),
                "criteria": q[qid].get("criteria"),
            }
    return spec


def decide_graph(answers: dict | None, nodes: list[dict], policy: dict) -> dict:
    if answers is None:
        return {"first_landing": None, "land_now": [], "park": [n["id"] for n in nodes],
                "needs_joe": [], "reason": "fallback: no Jev answer (see the ledger row)",
                "per_node": {}, "jev": None}
    ch = answers["choices"].get("first_landing") or {}
    choice = ch.get("choice")
    conf = ch.get("confidence")
    by_id = {n["id"]: n for n in nodes}
    jev = {"choice": choice, "confidence": conf, "probabilities": ch.get("probabilities")}

    per = {}
    for n in nodes:
        nid = n["id"]
        per[nid] = {
            "lands": (answers["nouls"].get("lands_" + nid) or {}).get("noul"),
            "value": (answers["scores"].get("value_" + nid) or {}).get("score"),
            "joe_decides": (answers["nouls"].get("joe_decides_" + nid) or {}).get("noul"),
        }

    def landable(nid: str) -> bool:
        v = per[nid]["lands"]
        return v is not None and v >= policy["blocked_max"]

    def valued(nid: str) -> bool:
        v = per[nid]["value"]
        return v is not None and v >= policy["min_value"]

    def needs_joe(nid: str) -> bool:
        v = per[nid]["joe_decides"]
        return v is not None and v >= policy["joe_escalate_min"]

    first = None
    reason = ""
    # The first landing is a JUDGMENT, so it is only ever set from a judgment that
    # holds up. Four ways the answer can fail to hold up, and none of them is a
    # licence to pick a node by its position in the caller's list.
    #
    #   - no confidence at all: a missing confidence is NOT maximum confidence.
    #     The old code read it as maximum, then formatted it - and crashed on the
    #     None, so the fail-open could never even report itself.
    #   - an id that is not a node
    #   - a confidence below the gate
    #   - a node that is not landable-and-valued
    #
    # In every failing case the first landing is simply not established. The nodes
    # that independently qualify are still listed in land_now, because that list is
    # computed from the per-node judgments, not from the choice. What is removed is
    # the old "fell back to the first landable-and-valued node in the given order":
    # the caller's order is not evidence, and a default dressed as a judgment is
    # the exact failure this file's header forbids.
    if conf is None:
        reason = "fallback: Jev's answer carried no confidence, so no first landing is designated"
    elif choice not in by_id:
        reason = f"fallback: Jev chose {choice!r} @ {conf}, not a confident node id"
    elif conf < policy["first_landing_min_confidence"]:
        reason = (f"fallback: Jev chose {choice} @ {conf}, below the confidence gate "
                  f"{policy['first_landing_min_confidence']}")
    elif not (landable(choice) and valued(choice)):
        reason = (f"fallback: Jev chose {choice} but it is not landable-and-valued "
                  f"(lands {per[choice]['lands']}, value {per[choice]['value']})")
    else:
        first = choice
        reason = f"jev: {choice} @ {conf:.2f} (lands {per[choice]['lands']}, value {per[choice]['value']})"

    land_now = [n["id"] for n in nodes
                if landable(n["id"]) and valued(n["id"]) and not needs_joe(n["id"])]
    joe = [n["id"] for n in nodes if needs_joe(n["id"])]
    park = [n["id"] for n in nodes if n["id"] not in land_now and n["id"] not in joe]
    return {"first_landing": first, "land_now": land_now, "park": park, "needs_joe": joe,
            "reason": reason, "per_node": per, "jev": jev}


# ---------------------------------------------------------------- entry points

def compose(candidates: list[dict], wave: str, harness: dict, standards: list[str],
            evidence: list[str] | None = None, *, source: Path) -> dict:
    q = load_questions()
    guard = q["guards"]["compose"]
    spec = compose_spec(candidates, guard)
    problems = check_policy("compose", guard, spec)
    if problems:
        raise ValueError("dead gate in the compose guard: " + "; ".join(problems))
    state = scrub({
        "harness": harness,
        "candidates": candidates,
        "standards": standards,
        "evidence": evidence or [],
    })
    answers = jc.ask(state, spec, wave=wave, guard="compose", leg="COMPOSE")
    decision = decide_compose(answers, candidates, guard["policy"])
    decision["candidates"] = [c["id"] for c in candidates]
    decision["wave"] = wave
    decision["state_scrubbed"] = True
    # Law 2: a decision names the file it was made from. The CLI used to attach
    # this AFTER the decision came back, so a library caller could produce a
    # decision with no producer path at all. It is attached here, where the
    # decision is made, and `source` is REQUIRED - there is no way to make one
    # without saying what made it.
    decision["provenance"] = provenance(source, "compose", wave)
    return decision


def graph_decision(nodes: list[dict], wave: str, objective: str, standards: list[str],
                   edges: list[dict] | None = None, seams: list[dict] | None = None,
                   *, source: Path) -> dict:
    q = load_questions()
    guard = q["guards"]["graph"]
    spec = graph_spec(nodes, guard)
    problems = check_policy("graph", guard, spec)
    if problems:
        raise ValueError("dead gate in the graph guard: " + "; ".join(problems))
    state = scrub({
        "objective": objective,
        "nodes": nodes,
        "edges": edges or [],
        "seams": seams or [],
        "standards": standards,
    })
    answers = jc.ask(state, spec, wave=wave, guard="graph", leg="GRAPH")
    decision = decide_graph(answers, nodes, guard["policy"])
    decision["wave"] = wave
    decision["objective"] = objective
    decision["state_scrubbed"] = True
    # Attached here, not in the CLI wrapper: see compose().
    decision["provenance"] = provenance(source, "graph", wave)
    return decision


def provenance(input_path: Path, mode: str, wave: str) -> dict:
    """What produced this receipt, recorded in the receipt itself.

    A committed decision that cannot say which input produced it is a claim
    without a producer path. The input bytes are hashed, so a later reader can
    tell whether the graph was edited AFTER the decision was made - which is
    exactly the failure the World Labs receipt had: the decision was still
    filed under the graph's filename, but the graph had been corrected and the
    receipt had not been re-judged. The hash makes that state visible instead
    of invisible.

    The path is relativised, not absolute: a receipt is a committed artifact
    and must not carry a machine's directory layout.
    """
    import hashlib
    import datetime

    raw = input_path.read_bytes()
    return {
        "input": scrub_text(str(input_path)),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "mode": mode,
        "wave": wave,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }


def write_decision(decision: dict, wave: str, name: str = "decision") -> Path:
    RUNS.mkdir(parents=True, exist_ok=True)
    d = RUNS / wave
    d.mkdir(parents=True, exist_ok=True)
    p = d / (name + ".json")
    p.write_text(json.dumps(decision, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="")
    return p


def _main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="HARNESS2 compose guard")
    ap.add_argument("--wave", required=True)
    ap.add_argument("--mode", choices=["compose", "graph"], default="compose")
    ap.add_argument("--input", required=True, help="candidates json (compose) or nodes json (graph)")
    ap.add_argument("--objective", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)

    payload = json.loads(Path(a.input).read_text(encoding="utf-8"))
    source = Path(a.input)
    if a.mode == "compose":
        candidates = payload.get("candidates") or payload
        decision = compose(
            candidates, a.wave,
            payload.get("harness") or {},
            payload.get("standards") or [],
            payload.get("evidence") or [],
            source=source,
        )
        name = "decision"
    else:
        nodes = payload.get("nodes") or payload
        decision = graph_decision(
            nodes, a.wave,
            payload.get("objective") or a.objective,
            payload.get("standards") or [],
            payload.get("edges") or [],
            payload.get("seams") or [],
            source=source,
        )
        name = "graph_decision"
    out = Path(a.out) if a.out else write_decision(decision, a.wave, name)
    print(json.dumps(decision, indent=1, ensure_ascii=False))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
