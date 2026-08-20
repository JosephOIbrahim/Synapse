# mission_schema.py - LOOP mission schema (cloned from harness/autoresearch/mission_schema.py).
#
# The autoresearch clone validates missions of many probe kinds. This LOOP clone
# carries the same MissionError discipline and the same Phase/Mission dataclasses,
# with two additive changes:
#   1. VALID_KINDS extends to the five loop probe kinds
#        port_contract, mapper_green, precommit_order, stageport_cow, closure_rate
#      (the autoresearch kinds are NOT copied - loop missions only probe the loop seam).
#   2. Mission gains `needs_hou: bool = False` - the runner gates probes.require_hou()
#      behind it. V0.0 is pure-python; a later rung (V0.1+, SafetyPort/SALUS) sets true.
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_KINDS = {
    "port_contract",      # ports.py surface matches blueprint §4 (PortResult + method sigs)
    "mapper_green",       # deterministic mapper truth table: all-True -> ALLOW, any False/None -> BLOCK
    "precommit_order",    # precommit authored in ledger BEFORE the mutating act, every turn
    "stageport_cow",      # StagePort UNAVAILABLE with zero side effects (closes without Octavius)
    "closure_rate",       # terminal-honest-verdict rate over N turns; V0.0 requires 1.0, zero HIT/MISS
}


class MissionError(ValueError):
    """Invalid mission definition - schema violation, not a probe failure."""


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
    phases: list
    artifact_prefix: str = "loop_truth"
    needs_hou: bool = False

    def total_questions(self) -> int:
        return sum(len(p.questions) for p in self.phases)


def _req(d: dict, key: str, typ, where: str):
    if key not in d:
        raise MissionError(f"{where}: missing required key '{key}'")
    if not isinstance(d[key], typ):
        raise MissionError(f"{where}: '{key}' must be {typ.__name__}, got {type(d[key]).__name__}")
    return d[key]


def _validate_question(kind: str, q: dict, where: str) -> None:
    """Normalize defaults and type-check one question. Raises MissionError on violation."""
    if not isinstance(q, dict):
        raise MissionError(f"{where}: question must be an object, got {type(q).__name__}")

    if kind == "port_contract":
        port = _req(q, "port", str, where)
        if not port.strip():
            raise MissionError(f"{where}: 'port' must be non-empty")
        methods = _req(q, "methods", list, where)
        if not all(isinstance(m, str) and m.strip() for m in methods):
            raise MissionError(f"{where}: 'methods' must be a list of non-empty strings")

    elif kind == "mapper_green":
        name = _req(q, "name", str, where)
        if not name.strip():
            raise MissionError(f"{where}: 'name' must be non-empty")

    elif kind == "precommit_order":
        turns = q.setdefault("turns", 3)
        if not isinstance(turns, int) or turns < 1:
            raise MissionError(f"{where}: 'turns' must be an int >= 1")

    elif kind == "stageport_cow":
        sid = q.setdefault("stage_identifier", "/stage")
        if not isinstance(sid, str) or not sid.strip():
            raise MissionError(f"{where}: 'stage_identifier' must be a non-empty string")

    elif kind == "closure_rate":
        turns = q.setdefault("turns", 5)
        if not isinstance(turns, int) or turns < 1:
            raise MissionError(f"{where}: 'turns' must be an int >= 1")

    else:  # unreachable: validate_mission checks kind membership first
        raise MissionError(f"{where}: unknown kind '{kind}'")


def validate_mission(data: dict, source: str) -> Mission:
    name = _req(data, "mission", str, source)
    version = _req(data, "version", str, source)
    target_build = _req(data, "target_build", str, source)
    phases_raw = _req(data, "phases", list, source)
    if not phases_raw:
        raise MissionError(f"{source}: at least one phase is required")

    needs_hou = data.get("needs_hou", False)
    if not isinstance(needs_hou, bool):
        raise MissionError(f"{source}: 'needs_hou' must be a boolean")

    artifact_prefix = data.get("artifact_prefix", "loop_truth")
    if not isinstance(artifact_prefix, str) or not artifact_prefix.strip():
        raise MissionError(f"{source}: 'artifact_prefix' must be a non-empty string")

    phases: list = []
    seen_ids: set = set()
    for i, p in enumerate(phases_raw):
        where = f"{source} phase[{i}]"
        pid = _req(p, "id", str, where)
        if pid in seen_ids:
            raise MissionError(f"{where}: duplicate phase id '{pid}'")
        seen_ids.add(pid)
        kind = _req(p, "kind", str, where)
        if kind not in VALID_KINDS:
            raise MissionError(f"{where}: unknown kind '{kind}' (valid: {sorted(VALID_KINDS)})")
        questions = _req(p, "questions", list, where)
        for j, q in enumerate(questions):
            _validate_question(kind, q, f"{where} question[{j}]")
        phases.append(Phase(id=pid, kind=kind, questions=questions))

    return Mission(
        name=name,
        version=version,
        target_build=target_build,
        phases=phases,
        artifact_prefix=artifact_prefix,
        needs_hou=needs_hou,
    )


def load_mission(path: Path) -> Mission:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise MissionError(f"mission file not found: {path}")
    except json.JSONDecodeError as e:
        raise MissionError(f"mission file is not valid JSON: {path}: {e}")
    return validate_mission(data, str(path))
