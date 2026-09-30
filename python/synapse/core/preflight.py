"""Level 1 preflight (claude/LEVEL1_BLUEPRINT.md section 3, ruling R-5): is Houdini ready for a change?

A preflight is a cheap, read-only check that runs before work that changes the scene. It is the
readiness section of ``synapse_health``, and the transports run it for every caller: before a
session's first change, and again after any retryable or unrecoverable outcome. A check that fails,
or that cannot be observed, refuses the change before it is sent, and names the fix.

This module is pure. Houdini sits behind one seam, the hop: a callable that runs one short function
on Houdini's main thread and returns what it saw, or raises ``TimeoutError`` when the main thread
did not answer in time. ``server/preflight_gate.py`` makes the real one. A process without Houdini
has no hop and no scene to change, so the gate does not apply there.

The checks (the scene check, 8, is its own milestone, R-7):

1. ``bridge.alive``: the server answered. Always PASS when the server itself runs the check.
2. ``session.valid``: the call arrived on a live session. The session gate runs before any tool.
3. ``houdini.responsive``: the main thread answers within 250 ms. A probe cannot tell an open
   dialog from a long cook, so the first FAIL is retryable and a second in a row needs the artist.
4. ``scene.writable``: no scene is loading, and undo is on.
5. ``version.match``: the stdio bridge runs the same SYNAPSE release as Houdini. Only the stdio
   bridge carries a version; the panel runs in Houdini and an HTTP client has no SYNAPSE version.
6. ``mode``: read-only mode, reported.
7. ``resources``: free disk and available RAM, reported. A figure that could not be measured
   stays null; it is never assumed.

UNKNOWN blocks a change, like FAIL. Only a ready result is remembered, for 10 s, and any retryable
or unrecoverable outcome forgets it, so a failing check is always probed again.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .outcomes import OutcomeInfo, info

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"
INFO = "info"
NOT_APPLICABLE = "not_applicable"

#: What a failing check stops: every call (the main thread or the scene is not there to answer),
#: or changes only (reads still work).
ALL = "all"
CHANGES = "changes"

#: The main thread's answer budget. The stall gate's own probe allows 2 s; this one is cheap.
PROBE_TIMEOUT_S = 0.25
#: How long a ready result is remembered.
CACHE_S = 10.0
#: The wait a first "Houdini did not answer" names.
BUSY_RETRY_S = 5.0

#: hop(timeout_s) -> {"loading": bool, "undo_enabled": bool, "hip_path": str}. It raises
#: TimeoutError when the main thread did not answer in time, and ProbeError when it answered but
#: the facts could not be read.
Hop = Callable[[float], Dict[str, Any]]


class ProbeError(RuntimeError):
    """The hop reached Houdini but could not read what the checks need."""


@dataclass(frozen=True)
class Check:
    """One check's result. ``code`` names the outcome when the check blocks a change."""

    name: str
    status: str
    message: str
    code: Optional[str] = None
    scope: str = CHANGES
    retry_after_s: Optional[float] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    next_step: Optional[str] = None

    @property
    def blocks(self) -> bool:
        """FAIL and UNKNOWN both stop a change."""
        return self.status in (FAIL, UNKNOWN)

    def outcome(self, message: Optional[str] = None) -> OutcomeInfo:
        """The outcome that refuses a change because of this check."""
        return info(self.code or "preflight.blocked", message or self.message,
                    retry_after_s=self.retry_after_s, evidence=self.evidence or None,
                    next_step=self.next_step)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"name": self.name, "status": self.status, "message": self.message}
        if self.blocks:
            out["code"] = self.code or "preflight.blocked"
        if self.evidence:
            out["evidence"] = dict(self.evidence)
        return out


_lock = threading.Lock()
_clock = time.monotonic
_ready_facts: Optional[Dict[str, Any]] = None
_ready_at: Optional[float] = None
_unanswered = 0


def invalidate() -> None:
    """Forget the last ready result. Any retryable or unrecoverable outcome calls this."""
    global _ready_facts, _ready_at
    with _lock:
        _ready_facts = None
        _ready_at = None


def reset() -> None:
    """Forget everything, the count of unanswered probes included (tests use this)."""
    global _unanswered
    invalidate()
    with _lock:
        _unanswered = 0


def is_trouble(outcome: Any) -> bool:
    """True for an outcome after which the next change is checked again."""
    return isinstance(outcome, dict) and outcome.get("outcome") in ("retryable", "unrecoverable")


def _scene_checks(facts: Dict[str, Any], cached: bool) -> List[Check]:
    responsive = Check("houdini.responsive", PASS,
                       "Houdini's main thread answered within 250 ms.",
                       evidence={"cached": True} if cached else {})
    loading, undo = facts.get("loading"), facts.get("undo_enabled")
    hip = {"hip_path": facts["hip_path"]} if facts.get("hip_path") else {}
    if not isinstance(loading, bool) or not isinstance(undo, bool):
        scene = Check("scene.writable", UNKNOWN,
                      "SYNAPSE could not read whether a scene is loading or undo is on.", scope=ALL)
    elif loading:
        scene = Check("scene.writable", FAIL, "Houdini is loading a scene.", code="scene.loading",
                      scope=ALL, evidence=hip)
    elif not undo:
        scene = Check("scene.writable", FAIL, "Undo is off in Houdini, so a change could not be undone.",
                      code="scene.undo_off", evidence=hip)
    else:
        scene = Check("scene.writable", PASS, "No scene is loading, and undo is on.", evidence=hip)
    return [responsive, scene]


def probe(hop: Hop) -> List[Check]:
    """Checks 3 and 4 through one hop, or from a ready result of the last 10 s."""
    global _ready_facts, _ready_at, _unanswered
    with _lock:
        if _ready_facts is not None and _ready_at is not None \
                and _clock() - _ready_at < CACHE_S:
            return _scene_checks(dict(_ready_facts), cached=True)
    try:
        facts = hop(PROBE_TIMEOUT_S)
    except TimeoutError:
        with _lock:
            _unanswered += 1
            count = _unanswered
        not_checked = Check("scene.writable", UNKNOWN, "Not checked: Houdini did not answer.",
                            scope=ALL)
        if count == 1:
            return [Check("houdini.responsive", FAIL,
                          "Houdini's main thread did not answer within 250 ms; a cook, a render or "
                          "an open dialog may be holding it.",
                          code="houdini.busy", scope=ALL, retry_after_s=BUSY_RETRY_S), not_checked]
        return [Check("houdini.responsive", FAIL,
                      "Houdini is not answering: its main thread missed %d checks in a row." % count,
                      code="houdini.not_answering", scope=ALL, evidence={"missed": count}),
                not_checked]
    except (ProbeError, RuntimeError, AttributeError, ImportError, LookupError, OSError,
            TypeError, ValueError) as exc:
        reason = str(exc) or type(exc).__name__
        return [Check("houdini.responsive", UNKNOWN,
                      "SYNAPSE could not check Houdini's main thread (%s)." % reason, scope=ALL),
                Check("scene.writable", UNKNOWN, "Not checked: the main-thread check could not run.",
                      scope=ALL)]
    if not isinstance(facts, dict):
        facts = {}
    with _lock:
        _unanswered = 0
    checks = _scene_checks(facts, cached=False)
    if all(check.status == PASS for check in checks):
        with _lock:
            _ready_facts, _ready_at = dict(facts), _clock()
    return checks


def _release(version: Optional[str]) -> Optional[tuple]:
    """"5.87.0" as (5, 87, 0), or None when it does not read as a release."""
    try:
        return tuple(int(part) for part in str(version).split("."))
    except ValueError:
        return None


def version_check(client_version: Optional[str], server_version: Optional[str]) -> Check:
    """Check 5: the stdio bridge and Houdini run the same SYNAPSE release.

    The fix names the side that runs the older release: a bridge left running across an update
    restarts with its MCP client, and a Houdini left running across one restarts itself.
    """
    if not client_version:
        return Check("version.match", NOT_APPLICABLE,
                     "Only the stdio bridge carries a SYNAPSE version, and this caller does not.",
                     evidence={"houdini": server_version} if server_version else {})
    evidence = {"bridge": client_version, "houdini": server_version}
    if not server_version:
        return Check("version.match", UNKNOWN, "SYNAPSE could not read Houdini's SYNAPSE version.",
                     evidence=evidence)
    if client_version != server_version:
        bridge, houdini = _release(client_version), _release(server_version)
        if bridge is not None and houdini is not None and bridge > houdini:
            fix = "Restart Houdini so it loads SYNAPSE %s, as the bridge does." % client_version
        else:
            fix = "Restart the MCP client so its bridge loads SYNAPSE %s, as Houdini does." % server_version
        return Check("version.match", FAIL,
                     "The MCP bridge runs SYNAPSE %s and Houdini runs SYNAPSE %s."
                     % (client_version, server_version),
                     code="version.mismatch", evidence=evidence, next_step=fix)
    return Check("version.match", PASS, "The MCP bridge and Houdini both run SYNAPSE %s."
                 % server_version, evidence=evidence)


def gate(hop: Hop, *, client_version: Optional[str] = None,
         server_version: Optional[str] = None) -> Optional[OutcomeInfo]:
    """The refusal for a change before it is sent, or None when it may be sent.

    The version is compared first, since it needs no hop; then one hop answers checks 3 and 4.
    """
    version = version_check(client_version, server_version)
    if version.blocks:
        return version.outcome(version.message + " The change was not sent.")
    for check in probe(hop):
        if check.blocks:
            return check.outcome(check.message + " The change was not sent.")
    return None


def readiness(hop: Optional[Hop], *, client_version: Optional[str] = None,
              server_version: Optional[str] = None, read_only: bool = False,
              resources: Optional[Callable[[Optional[str]], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """The readiness section of synapse_health: ``ready``, ``degraded`` (reads only) or ``blocked``.

    *resources* measures free disk and RAM for the open scene's folder; it gets the scene's path,
    or None when it is not known.
    """
    started = time.perf_counter()
    checks: List[Check] = [
        Check("bridge.alive", PASS, "SYNAPSE answered this call."),
        Check("session.valid", PASS, "This call arrived on a live session."),
    ]
    if hop is None:
        checks += [Check("houdini.responsive", NOT_APPLICABLE, "There is no Houdini in this process."),
                   Check("scene.writable", NOT_APPLICABLE, "There is no Houdini in this process.")]
    else:
        checks += probe(hop)
    checks.append(version_check(client_version, server_version))
    if read_only:
        checks.append(Check("mode", INFO, "Read-only mode is on: SYNAPSE_MCP_READ_ONLY is set, so "
                            "only read-only tools run.", evidence={"read_only": True}))
    else:
        checks.append(Check("mode", INFO, "Read-only mode is off.", evidence={"read_only": False}))
    hip_path = next((c.evidence.get("hip_path") for c in checks if c.name == "scene.writable"), None)
    measured = resources(hip_path) if resources is not None else {}
    checks.append(Check("resources", INFO,
                        "Free disk and available RAM; a figure that could not be measured is null.",
                        evidence=dict(measured)))
    blocking = [check for check in checks if check.blocks]
    if any(check.scope == ALL for check in blocking):
        result = "blocked"
    elif blocking or read_only:
        result = "degraded"
    else:
        result = "ready"
    first = next((check for check in blocking if check.scope == ALL), blocking[0] if blocking else None)
    return {
        "result": result,
        "outcome": first.outcome().to_dict() if first is not None else None,
        "checks": [check.to_dict() for check in checks],
        "took_ms": round((time.perf_counter() - started) * 1000.0, 2),
    }
