"""AUTORESEARCH mission schema — pure Python, zero hou imports.

A mission is a JSON question-set. The model may author questions;
only probes produce answers. This module validates the questions.

Kinds:
    type_discovery   {"pattern": str}
    type_existence   {"name": str, "note": str?}
    parm_probe       {"type": str, "highlight": [str]?, "skip_if_missing": bool?}
    chain_hash       {"name": str, "chain": [str], "repeat": int?, "candidate": bool?}
    store_census     {"roots": [{"path": str, "max_depth": int?}], "exclude_globs": [str]?}
    apex_wire_matrix     {"type_set": [str], "repeat": int?, "sample": [[str,str]]?}  # WA1-WIRE (C2)
    apex_token_resolution {"tokens": [str], "contexts": [str]?}                        # WA1-WIRE (C2)

The mission may carry an OPTIONAL top-level "artifact_prefix" (default
"lop_truth"); the runner names its evidence file "<artifact_prefix>_<build>.json".
apex_wire sets "apex_wire_matrix" so its artifact is self-describing.

Validation normalizes defaults into each question dict so the runner
never guesses. All errors carry phase/question coordinates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_KINDS = {"type_discovery", "type_existence", "parm_probe", "chain_hash",
               "fixture_hash", "usd_schema_probe", "store_census",
               # WA1-WIRE (C2): APEX wire-typing matrix + @/$ resolution table.
               # probes.py resolves these against the live apex runtime.
               "apex_wire_matrix", "apex_token_resolution"}


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
    # WA1-TRUTH: the runner names its evidence file "<artifact_prefix>_<build>.json".
    # Default preserves every existing mission's "lop_truth_<build>.json" artifact.
    artifact_prefix: str = "lop_truth"

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

    elif kind == "apex_wire_matrix":
        # WA1-WIRE (C2): the ordered-pair wire-typing matrix over a DECLARED type
        # set. The type set is the matrix axis; being declared (not runtime-derived)
        # keeps the product deterministic -> the repeat-2 idempotence hash is stable.
        ts = _req(q, "type_set", list, where)
        if not ts or not all(isinstance(x, str) and x.strip() for x in ts):
            raise MissionError(f"{where}: 'type_set' must be a non-empty list of type-name strings")
        rep = q.setdefault("repeat", 2)
        if not isinstance(rep, int) or rep < 1:
            raise MissionError(f"{where}: 'repeat' must be an int >= 1")
        # Optional explicit idempotence sample; None -> probe picks a fixed subset.
        sample = q.setdefault("sample", None)
        if sample is not None:
            ok = isinstance(sample, list) and all(
                isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p)
                for p in sample)
            if not ok:
                raise MissionError(f"{where}: 'sample' must be a list of [out,in] string pairs or omitted")

    elif kind == "apex_token_resolution":
        # WA1-WIRE (C2 step 3): @/$ resolution table, one row per (token, context).
        toks = _req(q, "tokens", list, where)
        if not toks or not all(isinstance(x, str) and x.strip() for x in toks):
            raise MissionError(f"{where}: 'tokens' must be a non-empty list of token strings")
        ctxs = q.setdefault("contexts", None)
        if ctxs is not None and (not isinstance(ctxs, list)
                                 or not all(isinstance(x, str) and x.strip() for x in ctxs)):
            raise MissionError(f"{where}: 'contexts' must be a list of non-empty strings or omitted")

    return q


def validate_mission(data: dict, source: str = "<mission>") -> Mission:
    if not isinstance(data, dict):
        raise MissionError(f"{source}: top level must be an object")

    name = _req(data, "mission", str, source)
    version = _req(data, "version", str, source)
    target_build = _req(data, "target_build", str, source)
    # Optional (WA1-TRUTH); defaults to "lop_truth" so existing missions are unchanged.
    artifact_prefix = data.get("artifact_prefix", "lop_truth")
    if not isinstance(artifact_prefix, str) or not artifact_prefix.strip():
        raise MissionError(f"{source}: 'artifact_prefix' must be a non-empty string")
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

    return Mission(name=name, version=version, target_build=target_build,
                   phases=phases, artifact_prefix=artifact_prefix)


def load_mission(path: Path) -> Mission:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MissionError(f"mission file not found: {path}")
    except json.JSONDecodeError as e:
        raise MissionError(f"{path}: invalid JSON — {e}")
    return validate_mission(data, source=str(path))
