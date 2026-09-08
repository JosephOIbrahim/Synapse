"""Opt-in checked experience for one development workflow.

The developer imports a retained native rehearsal result through a trusted
local boundary. A digest detects changed data; it does not authenticate an
arbitrary JSON file as a Houdini execution. This module is not a public tool,
never constructs a memory owner, and cannot execute a recalled procedure.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .models import Memory, MemoryTier, MemoryType

TASK = "copernicus_lookdev"
NAMESPACE = "synapse:rsi_stage0:v1"
PRODUCER = "synapse.server.solaris_lookdev.build_lookdev"
CHECKER = "synapse.server.solaris_lookdev._verify_stage"
MAX_BYTES = 16 * 1024
MAX_CANDIDATES = 20
_AGENT = "rsi_stage0_native_import"
_ENV_FIELDS = {"houdini_build", "synapse_version", "implementation_sha256",
               "dependency_sha256", "producer", "checker"}
_RECORD_FIELDS = {"schema_version", "task_key", "record_id", "source_id",
                  "checked_at", "environment", "procedure", "evidence",
                  "evidence_sha256", "record_sha256", "role"}
_VERIFICATION_FIELDS = {"configuration", "usd", "geometry", "material", "binding",
                        "uv", "texture_sources", "camera", "render_settings",
                        "texture_pixels", "rendered_appearance"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _timestamp(value):
    _require(isinstance(value, str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value),
        "Use a canonical UTC timestamp: YYYY-MM-DDTHH:MM:SSZ")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return value


def validate_environment(environment):
    _require(type(environment) is dict and set(environment) == _ENV_FIELDS,
             "Missing or unsupported environment facts")
    _require(environment["houdini_build"] == "22.0.400", "Unsupported Houdini build")
    version = environment["synapse_version"]
    _require(isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version),
             "Missing SYNAPSE version")
    for key in ("implementation_sha256", "dependency_sha256"):
        value = environment[key]
        _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
                 "Missing " + key)
    _require(environment["producer"] == PRODUCER and environment["checker"] == CHECKER,
             "Unsupported evidence producer or checker")
    return dict(environment)


def capture_environment(houdini_build, dependency_path):
    """Called by the trusted native producer with observed build/dependency.

    Hash only the implementation and fixed dependency relevant to this task;
    documentation-only commits do not invalidate the procedure.
    """
    from synapse import __version__

    package = Path(__file__).resolve().parents[1]
    sources = {}
    for name in ("solaris_lookdev.py", "copernicus_texture.py"):
        sources[name] = hashlib.sha256((package / "server" / name).read_bytes()).hexdigest()
    return validate_environment({
        "houdini_build": houdini_build, "synapse_version": __version__,
        "implementation_sha256": _digest(sources),
        "dependency_sha256": hashlib.sha256(Path(dependency_path).read_bytes()).hexdigest(),
        "producer": PRODUCER, "checker": CHECKER,
    })


def _evidence(result):
    _require(type(result) is dict, "Native result must be an object")
    _require(result.get("status") == "created" and result.get("dry_run") is False
             and result.get("template") == TASK, "No successful native lookdev outcome")
    verification = result.get("verification")
    _require(type(verification) is dict and _VERIFICATION_FIELDS <= set(verification),
             "Incomplete native verification")
    verification = {key: verification[key] for key in sorted(_VERIFICATION_FIELDS)}
    _require(verification["configuration"] == "verified" and verification["usd"] == "verified",
             "Configuration and USD must both be verified")
    _require(verification["uv"] == "faceVarying st", "Missing verified UV association")
    for key in ("geometry", "material", "camera", "render_settings"):
        value = verification[key]
        _require(isinstance(value, str) and value.startswith("/") and len(value) > 1,
                 "Missing verified " + key)
    _require(verification["binding"] == [verification["material"]], "Binding evidence differs")
    sources = verification["texture_sources"]
    _require(type(sources) is dict and set(sources) == {"base_color_file", "specular_roughness_file"},
             "Missing verified texture sources")
    _require(all(isinstance(v, str) and v.startswith("op:/") and "{" in v and v.endswith("}")
                 for v in sources.values()), "Unsupported texture source evidence")
    _require(verification["texture_pixels"] == "not measured"
             and verification["rendered_appearance"] == "not checked",
             "Preserve the native pixel and appearance limits")
    _require(result.get("resolution") == [256, 256], "Unsupported preview resolution")
    _require(result.get("layout") in ("vertical", "horizontal"), "Unsupported layout")
    return {"status": "created", "dry_run": False, "template": TASK,
            "verification": verification, "resolution": [256, 256], "layout": result["layout"]}


def _procedure(request, summary):
    # This existing validator is pure data logic; it performs no host access.
    from ..server.solaris_lookdev import validate_request

    settings = validate_request(request)
    _require(settings["dry_run"] is False, "A dry-run request is not checked experience")
    _require(isinstance(summary, str) and 0 < len(summary.strip()) <= 500,
             "Provide a procedure summary of at most 500 characters")
    return {"ref": TASK, "summary": summary.strip(), "layout": settings["layout"],
            "parameters": {key: settings[key] for key in
                           ("base_color", "noise_type", "frequency", "octaves")}}


def make_experience(native_report, summary):
    """Normalize a developer-controlled native report, not a chat assertion.

    The caller is responsible for the report's provenance. The standalone
    command requires an explicit native-report import; no agent tool exposes it.
    """
    _require(type(native_report) is dict and native_report.get("origin") == "native_hython_rehearsal",
             "Expected a developer-controlled native rehearsal report")
    _require(native_report.get("main_thread") is True and native_report.get("ui_available") is False,
             "Expected a disposable main-thread native rehearsal")
    environment = validate_environment(native_report.get("environment"))
    source_id = native_report.get("source_id")
    _require(isinstance(source_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", source_id),
             "Retain a stable source outcome identity")
    checked_at = _timestamp(native_report.get("checked_at"))
    evidence = _evidence(native_report.get("result"))
    procedure = _procedure(native_report.get("request"), summary)
    _require(procedure["layout"] == evidence["layout"], "Request and result layout differ")
    record = {
        "schema_version": 1, "task_key": TASK,
        "record_id": "exp_" + _digest([NAMESPACE, source_id]),
        "source_id": source_id, "checked_at": checked_at,
        "environment": environment, "procedure": procedure,
        "evidence": evidence, "evidence_sha256": _digest(evidence),
        "role": "working_procedure",
    }
    record["record_sha256"] = _digest(record)
    return validate_experience(record)


def validate_experience(record):
    """Return a detached validated record, retaining facts and their limits."""
    encoded = _json(record)
    _require(len(encoded.encode("utf-8")) <= MAX_BYTES, "Experience exceeds 16 KiB")
    _require(type(record) is dict and set(record) == _RECORD_FIELDS, "Unsupported experience schema")
    _require(type(record["schema_version"]) is int and record["schema_version"] == 1
             and record["task_key"] == TASK and record["role"] == "working_procedure",
             "Unsupported schema, task, or learning role")
    validate_environment(record["environment"])
    source_id = record["source_id"]
    _require(isinstance(source_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", source_id),
             "Invalid source identity")
    _require(record["record_id"] == "exp_" + _digest([NAMESPACE, source_id]), "Record identity differs")
    _timestamp(record["checked_at"])
    evidence = _evidence(record["evidence"])
    _require(record["evidence_sha256"] == _digest(evidence), "Evidence digest differs")
    procedure = record["procedure"]
    _require(type(procedure) is dict and set(procedure) == {"ref", "summary", "layout", "parameters"}
             and procedure["ref"] == TASK, "Unsupported procedure reference")
    expected = _procedure({"template": TASK, "template_params": procedure["parameters"],
                           "layout": procedure["layout"]}, procedure["summary"])
    _require(procedure == expected and procedure["layout"] == evidence["layout"],
             "Procedure contains unsupported or destination-specific instructions")
    unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
    _require(record["record_sha256"] == _digest(unsigned), "Experience digest differs")
    return json.loads(encoded)


class ExperienceMemory:
    """Use an injected existing owner. Disabled and unrequested paths do no work."""

    def __init__(self, owner=None, *, enabled=False):
        self.owner = owner
        self.enabled = enabled is True

    def _store(self):
        from .embedding import HashEmbedder, SemanticEmbedder
        from .moneta_store import MonetaBackedStore

        store = self.owner if isinstance(self.owner, MonetaBackedStore) else getattr(self.owner, "store", None)
        if not isinstance(store, MonetaBackedStore):
            raise RuntimeError("Stage 0 is qualified only for an existing persistent Moneta owner")
        if type(store._embedder) not in (HashEmbedder, SemanticEmbedder):
            raise RuntimeError("Stage 0 requires the existing local Moneta embedder")
        return store

    def record(self, experience):
        if not self.enabled:
            return {"status": "UNAVAILABLE", "reason": "Checked experience is disabled"}
        try:
            record = validate_experience(experience)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return {"status": "INELIGIBLE", "reason": str(exc)}
        memory = Memory(
            id=record["record_id"], created_at=record["checked_at"], updated_at=record["checked_at"],
            content=_json(record), summary=record["procedure"]["summary"],
            memory_type=MemoryType.FEEDBACK, tier=MemoryTier.SHOW,
            tags=[NAMESPACE], source="auto", agent_id=_AGENT,
        )
        try:
            inserted = self._store().add_durable_if_absent(memory)
        except ValueError as exc:
            return {"status": "INELIGIBLE", "reason": str(exc), "record_id": memory.id}
        except Exception as exc:
            return {"status": "UNAVAILABLE", "reason": str(exc), "record_id": memory.id}
        return {"status": "STORED" if inserted else "DUPLICATE", "record_id": memory.id}

    def recall(self, task_key, environment, *, requested=False):
        if not self.enabled or requested is not True:
            return {"status": "UNAVAILABLE", "reason": "Checked recall requires enabled, explicit assistance"}
        if task_key != TASK:
            return {"status": "UNAVAILABLE", "reason": "Unsupported task"}
        try:
            environment = validate_environment(environment)
            candidates = self._store().get_by_tag_strict(NAMESPACE, limit=MAX_CANDIDATES)
            matches = []
            for memory in candidates:
                # Generic memory_add writes source=ai and has no adapter identity.
                if (memory.memory_type != MemoryType.FEEDBACK or memory.source != "auto"
                        or memory.agent_id != _AGENT):
                    continue
                record = validate_experience(json.loads(memory.content))
                _require(memory.id == record["record_id"], "Stored identity differs from experience")
                if record["environment"] == environment:
                    matches.append(record)
        except Exception as exc:
            return {"status": "UNAVAILABLE", "reason": str(exc)}
        if not matches:
            return {"status": "NO_MATCH", "reason": "No compatible checked experience", "complete": True}
        matches.sort(key=lambda record: record["record_id"])
        matches.sort(key=lambda record: record["checked_at"], reverse=True)
        record = matches[0]
        explanation = (
            "This lookdev procedure previously passed the scene-configuration checks on Houdini "
            + environment["houdini_build"] + ". Texture pixels were not measured; rendered appearance "
            "was not checked. Choose a fresh ordinary build request if you want to use it."
        )
        return {"status": "HIT", "record_id": record["record_id"], "complete": True,
                "explanation": explanation, "experience": record}
