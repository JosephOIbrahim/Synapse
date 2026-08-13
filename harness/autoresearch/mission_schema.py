"""AUTORESEARCH mission schema — pure Python, zero hou imports.

A mission is a JSON question-set. The model may author questions;
only probes produce answers. This module validates the questions.

Kinds:
    type_discovery   {"pattern": str}
    type_existence   {"name": str, "note": str?}
    parm_probe       {"type": str, "highlight": [str]?, "skip_if_missing": bool?}
    chain_hash       {"name": str, "chain": [str], "repeat": int?, "candidate": bool?}
    store_census     {"roots": [{"path": str, "max_depth": int?}], "exclude_globs": [str]?}

Validation normalizes defaults into each question dict so the runner
never guesses. All errors carry phase/question coordinates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_KINDS = {"type_discovery", "type_existence", "parm_probe", "chain_hash",
               "fixture_hash", "usd_schema_probe", "store_census"}


class MissionError(ValueError):
    """Mission file failed validation. Message carries coordinates."""


@dataclass
class Phase:
    id: str
    kind: str
    questions: list = field(default_factory=list)


@dataclass
class Mission:
    name: str
    version: str
    target_build: str
    phases: list = field(default_factory=list)

    def total_questions(self) -> int:
        return sum(len(p.questions) for p in self.phases)


def _req(d: dict, key: str, typ, where: str):
    if key not in d:
        raise MissionError(f"{where}: missing required field '{key}'")
    v = d[key]
    if not isinstance(v, typ):
        raise MissionError(
            f"{where}: field '{key}' must be {typ.__name__}, got {type(v).__name__}"
        )
    return v


def _validate_question(kind: str, q: dict, where: str) -> dict:
    """Validate one question in place; return it with defaults normalized."""
    if not isinstance(q, dict):
        raise MissionError(f"{where}: question must be an object")

    if kind == "type_discovery":
        pattern = _req(q, "pattern", str, where)
        if not pattern.strip():
            raise MissionError(f"{where}: 'pattern' must be non-empty")

    elif kind == "type_existence":
        name = _req(q, "name", str, where)
        if not name.strip():
            raise MissionError(f"{where}: 'name' must be non-empty")
        q.setdefault("note", "")

    elif kind == "parm_probe":
        t = _req(q, "type", str, where)
        if not t.strip():
            raise MissionError(f"{where}: 'type' must be non-empty")
        hl = q.setdefault("highlight", [])
        if not isinstance(hl, list) or not all(isinstance(x, str) for x in hl):
            raise MissionError(f"{where}: 'highlight' must be a list of strings")
        sim = q.setdefault("skip_if_missing", True)
        if not isinstance(sim, bool):
            raise MissionError(f"{where}: 'skip_if_missing' must be a bool")

    elif kind == "chain_hash":
        name = _req(q, "name", str, where)
        if not name.strip():
            raise MissionError(f"{where}: 'name' must be non-empty")
        chain = _req(q, "chain", list, where)
        if not chain or not all(isinstance(x, str) and x.strip() for x in chain):
            raise MissionError(f"{where}: 'chain' must be a non-empty list of type names")
        rep = q.setdefault("repeat", 2)
        if not isinstance(rep, int) or rep < 1:
            raise MissionError(f"{where}: 'repeat' must be an int >= 1")
        cand = q.setdefault("candidate", False)
        if not isinstance(cand, bool):
            raise MissionError(f"{where}: 'candidate' must be a bool")

    elif kind == "fixture_hash":
        name = _req(q, "name", str, where)
        if not name.strip():
            raise MissionError(f"{where}: 'name' must be non-empty")
        path = _req(q, "path", str, where)
        if not path.strip():
            raise MissionError(f"{where}: 'path' must be a repo-root-relative fixture path")
        rep = q.setdefault("repeat", 2)
        if not isinstance(rep, int) or rep < 1:
            raise MissionError(f"{where}: 'repeat' must be an int >= 1")

    elif kind == "usd_schema_probe":
        name = _req(q, "name", str, where)
        if not name.strip():
            raise MissionError(f"{where}: 'name' must be non-empty")
        st = _req(q, "schema_type", str, where)
        if not st.strip():
            raise MissionError(f"{where}: 'schema_type' must be non-empty")
        pn = q.setdefault("plugin_name", "")
        if not isinstance(pn, str):
            raise MissionError(f"{where}: 'plugin_name' must be a string")
        rt = q.setdefault("roundtrip", True)
        if not isinstance(rt, bool):
            raise MissionError(f"{where}: 'roundtrip' must be a bool")
    elif kind == "store_census":
        # A filesystem census question. Pure Python, zero hou — enumerates
        # candidate memory-store directories under each root, classifies each,
        # and computes cross-store key overlap. Deterministic: sorted output,
        # no clock in the answer beyond the runner's per-entry timestamp.
        roots = _req(q, "roots", list, where)
        if not roots:
            raise MissionError(f"{where}: 'roots' must be a non-empty list")
        for ri, r in enumerate(roots):
            rw = f"{where} roots[{ri}]"
            if not isinstance(r, dict):
                raise MissionError(f"{rw}: each root must be an object")
            path = _req(r, "path", str, rw)
            if not path.strip():
                raise MissionError(f"{rw}: 'path' must be non-empty")
            md = r.setdefault("max_depth", 6)
            if not isinstance(md, int) or md < 0:
                raise MissionError(f"{rw}: 'max_depth' must be an int >= 0")
            r.setdefault("note", "")
        ex = q.setdefault("exclude_globs", [])
        if not isinstance(ex, list) or not all(isinstance(x, str) for x in ex):
            raise MissionError(f"{where}: 'exclude_globs' must be a list of strings")

    return q


def validate_mission(data: dict, source: str = "<mission>") -> Mission:
    if not isinstance(data, dict):
        raise MissionError(f"{source}: top level must be an object")

    name = _req(data, "mission", str, source)
    version = _req(data, "version", str, source)
    target_build = _req(data, "target_build", str, source)
    raw_phases = _req(data, "phases", list, source)
    if not raw_phases:
        raise MissionError(f"{source}: 'phases' must be non-empty")

    phases: list = []
    seen_ids: set = set()
    for pi, rp in enumerate(raw_phases):
        pwhere = f"{source} phase[{pi}]"
        if not isinstance(rp, dict):
            raise MissionError(f"{pwhere}: phase must be an object")
        pid = _req(rp, "id", str, pwhere)
        if pid in seen_ids:
            raise MissionError(f"{pwhere}: duplicate phase id '{pid}'")
        seen_ids.add(pid)
        kind = _req(rp, "kind", str, pwhere)
        if kind not in VALID_KINDS:
            raise MissionError(
                f"{pwhere}: unknown kind '{kind}' (valid: {sorted(VALID_KINDS)})"
            )
        qs = _req(rp, "questions", list, pwhere)
        if not qs:
            raise MissionError(f"{pwhere}: 'questions' must be non-empty")
        validated = [
            _validate_question(kind, q, f"{pwhere} ({pid}) question[{qi}]")
            for qi, q in enumerate(qs)
        ]
        phases.append(Phase(id=pid, kind=kind, questions=validated))

    return Mission(name=name, version=version, target_build=target_build, phases=phases)


def load_mission(path: Path) -> Mission:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MissionError(f"mission file not found: {path}")
    except json.JSONDecodeError as e:
        raise MissionError(f"{path}: invalid JSON — {e}")
    return validate_mission(data, source=str(path))
