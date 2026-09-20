# jev_client.py - the one place the harness talks to Jev (TypeSafe System One).
# Loads questions.json, builds SDK question objects, makes the call, and writes an
# append-only ledger row for every judgment. FAIL CLOSED: any error returns None and
# the caller applies its pre-Jev behaviour. Jev never names a model, never writes a
# file outside harness/jev/ledger/, and is never imported from the product tree.
# Source: harness/battleplan/notes/JEV_BLUEPRINT.md sec.4 invariants.
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
QUESTIONS = HERE / "questions.json"
LEDGER_DIR = HERE / "ledger"
RAILS_EXEC = REPO / "harness" / "rails_exec.json"


class JevUnavailable(Exception):
    """Raised (and caught) when Jev cannot answer: no key, SDK missing, API error."""


def enabled() -> bool:
    return os.environ.get("SYNAPSE_JEV", "on").lower() not in {"off", "0", "false"}


def api_key() -> str | None:
    k = os.environ.get("TYPESAFE_API_KEY")
    if k:
        return k
    # Windows: a shell spawned from Claude Desktop does not see a User-scope variable
    # set after the app launched. Read the registry scope directly so no restart is needed.
    if sys.platform == "win32":
        try:
            import winreg  # type: ignore
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as hk:
                v, _ = winreg.QueryValueEx(hk, "TYPESAFE_API_KEY")
                if v:
                    return str(v)
        except OSError:
            pass
    return None


def load_questions() -> dict:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def rails_tiers() -> dict:
    """Tier names -> entry, from rails_exec.json. The ONLY source of tier names."""
    table = json.loads(RAILS_EXEC.read_text(encoding="utf-8"))
    return table.get("tiers", table)


def _sdk():
    try:
        from typesafe_sdk import Choice, Noul, Score, TypeSafeClient  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise JevUnavailable(f"typesafe_sdk not importable: {e}")
    return TypeSafeClient, Choice, Score, Noul


def build_questions(spec: dict):
    """spec: {qid: {"type": choice|score|noul, "instructions": ..., "criteria": ...}} -> SDK objects."""
    _, Choice, Score, Noul = _sdk()
    out = {}
    for qid, q in spec.items():
        t = q["type"]
        if t == "choice":
            out[qid] = Choice(instructions=q["instructions"], criteria=q["criteria"])
        elif t == "score":
            out[qid] = Score(instructions=q["instructions"], criteria=q["criteria"])
        elif t == "noul":
            out[qid] = Noul(instructions=q["instructions"])
        else:
            raise ValueError(f"unknown question type {t!r} for {qid}")
    return out


def _get(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _answers_to_dict(resp) -> dict:
    """Flatten an SDK response into plain JSON for the ledger and for policy code."""
    out = {"choices": {}, "scores": {}, "nouls": {}}
    for qid, a in (_get(resp, "choices") or {}).items():
        probs = _get(a, "probabilities") or {}
        if not isinstance(probs, dict):
            probs = dict(probs) if probs else {}
        conf = _get(a, "confidence")
        if conf is None and probs:
            conf = max(probs.values())  # docs: confidence collapses the distribution; max is a fair stand-in
        out["choices"][qid] = {"choice": _get(a, "choice"), "probabilities": probs, "confidence": conf}
    for qid, a in (_get(resp, "scores") or {}).items():
        out["scores"][qid] = {"score": _get(a, "score"), "confidence": _get(a, "confidence"),
                              "probabilities": _get(a, "probabilities")}
    for qid, a in (_get(resp, "nouls") or {}).items():
        out["nouls"][qid] = {"noul": _get(a, "noul")}
    out["request_id"] = _get(resp, "request_id")
    return out


def state_hash(state) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def ledger(wave: str, guard: str, row: dict) -> Path:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    p = LEDGER_DIR / f"{wave}.{guard}.jsonl"
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "guard": guard, **row}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def ask(state, spec: dict, *, wave: str, guard: str, leg: str, model: str | None = None) -> dict | None:
    """One System One request. Returns flattened answers, or None (fail closed) after ledgering why.
    Never raises: the caller's fallback is the contract."""
    base = {"leg": leg, "state_hash": state_hash(state), "questions": sorted(spec)}
    if not enabled():
        ledger(wave, guard, {**base, "result": "disabled", "reason": "SYNAPSE_JEV=off"})
        return None
    key = api_key()
    if not key:
        ledger(wave, guard, {**base, "result": "fallback", "reason": "TYPESAFE_API_KEY absent"})
        return None
    try:
        TypeSafeClient, *_ = _sdk()
        qs = build_questions(spec)
        model = model or load_questions().get("model", "jev-latest")
        t0 = time.perf_counter()
        with TypeSafeClient(api_key=key, timeout=30.0) as client:
            try:
                resp = client.system_one(state=state, questions=qs, model=model)
            except TypeError:  # older SDK: model set on the client, not the call
                resp = client.system_one(state=state, questions=qs)
        ms = int((time.perf_counter() - t0) * 1000)
        answers = _answers_to_dict(resp)
        ledger(wave, guard, {**base, "result": "ok", "model": model, "latency_ms": ms, "answers": answers})
        return answers
    except Exception as e:  # noqa: BLE001 - fail closed on anything
        ledger(wave, guard, {**base, "result": "fallback", "reason": f"{type(e).__name__}: {e}"[:400]})
        return None


if __name__ == "__main__":
    # smoke: `python harness/jev/jev_client.py` -> proves key + SDK + one trivial call
    st = {"doc": "The count line reads 21 rows; the brief expected 22."}
    sp = {"mismatch": {"type": "noul", "instructions": "Does `doc` report a count different from the expected count?"}}
    a = ask(st, sp, wave="smoke", guard="smoke", leg="SMOKE")
    print(json.dumps(a, indent=1) if a else "fallback - see harness/jev/ledger/smoke.smoke.jsonl")
    sys.exit(0 if a else 1)
