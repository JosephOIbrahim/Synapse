"""What happened to a call, and what to do next (Level 1, M1). Pure: no hou, no Qt, no transport.

Every SYNAPSE tool call, on every route, ends in exactly one of seven outcomes
(claude/LEVEL1_BLUEPRINT.md, section 2):

  ok               it ran, and the result is attached
  refused          a rule stopped it before dispatch; the same call gets the same answer
  retryable        nothing ran, and the cause is passing; the client may send it once more
  unrecoverable    nothing can succeed until something outside the call changes
  needs_artist     it would run, but a person must approve it first
  unknown_outcome  it may have run; the reply was lost, invalid or late
  failed           it ran and failed

A stable ``code`` names the case for software (``session.expired``). ``message`` says what
happened in one sentence, ``next`` says what to do in plain words, and ``dispatched`` says whether
the call reached Houdini: "no", "yes" or "maybe". A read changes nothing, so a read that may have
run can still be ``retryable``; everything else that is ``retryable`` did not run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class Outcome(str, Enum):
    OK = "ok"
    REFUSED = "refused"
    RETRYABLE = "retryable"
    UNRECOVERABLE = "unrecoverable"
    NEEDS_ARTIST = "needs_artist"
    UNKNOWN_OUTCOME = "unknown_outcome"
    FAILED = "failed"


DISPATCHED = ("no", "yes", "maybe")

#: code -> (outcome, dispatched, next). The one vocabulary every route maps into.
CODES: Dict[str, Tuple[Outcome, str, str]] = {
    "session.expired": (Outcome.RETRYABLE, "no",
                        "Start a new MCP session and send the call again; the SYNAPSE panel does this by itself."),
    "session.missing": (Outcome.REFUSED, "no",
                        "Send initialize first, then send its Mcp-Session-Id header with every request."),
    "policy.read_only": (Outcome.REFUSED, "no",
                         "Unset SYNAPSE_MCP_READ_ONLY in Houdini's environment to allow changes."),
    "policy.safety_guard": (Outcome.REFUSED, "no",
                            "Change the request; the message names what the safety guard refused."),
    "policy.rbac": (Outcome.REFUSED, "no", "Ask a studio admin for a role that allows this command."),
    "request.invalid": (Outcome.REFUSED, "no", "Fix the request; the message names what is wrong with it."),
    "request.unknown_method": (Outcome.REFUSED, "no", "Use a method the SYNAPSE MCP server supports."),
    "server.busy": (Outcome.RETRYABLE, "no", "Wait a moment, then send it again."),
    "houdini.busy": (Outcome.RETRYABLE, "no",
                     "Wait for Houdini's cook or render to finish, then send it again."),
    "houdini.not_reachable": (Outcome.UNRECOVERABLE, "no",
                              "Start Houdini, open the SYNAPSE panel and click Connect, then try again."),
    "bridge.unreachable": (Outcome.UNRECOVERABLE, "no",
                           "Click Connect in the SYNAPSE panel, then try again."),
    "transport.not_sent": (Outcome.RETRYABLE, "no", "Send it again."),
    "transport.read_retry": (Outcome.RETRYABLE, "maybe", "Send it again; a read changes nothing."),
    "transport.reply_lost": (Outcome.UNKNOWN_OUTCOME, "maybe",
                             "Check the scene before trying again; it may have run."),
    "transport.timeout": (Outcome.UNKNOWN_OUTCOME, "maybe",
                          "Houdini may still be working on it. Check the scene before trying again."),
    "scene.node_not_found": (Outcome.FAILED, "yes", "Check the node path, then try again."),
    "cook.error": (Outcome.FAILED, "yes", "Read the cook error on the node, fix it, then try again."),
    "tool.failed": (Outcome.FAILED, "yes", "Read the error; it names what failed."),
    "tool.internal": (Outcome.UNKNOWN_OUTCOME, "maybe",
                      "Check the scene before trying again; the call may have run in part."),
    "artist.approval_needed": (Outcome.NEEDS_ARTIST, "no",
                               "Approve it in the SYNAPSE panel, then send it again."),
    "cache.over_budget": (Outcome.NEEDS_ARTIST, "no",
                          "Approve it in the SYNAPSE panel, or reduce the frame range."),
    "cache.unknown_size": (Outcome.NEEDS_ARTIST, "no",
                           "Measure a few frames first, or approve it in the SYNAPSE panel."),
    "cache.insufficient_disk": (Outcome.REFUSED, "no",
                                "Choose a volume with room, or reduce the frame range."),
    "preflight.blocked": (Outcome.UNRECOVERABLE, "no",
                          "Fix the failing check named in the message, then try again."),
    "version.mismatch": (Outcome.UNRECOVERABLE, "no",
                         "Restart the MCP client so it loads the same SYNAPSE version as Houdini."),
}

#: The codes whose ``next`` names a wait when the caller knows how long.
_WAITS = frozenset({"server.busy", "houdini.busy"})


@dataclass(frozen=True)
class OutcomeInfo:
    """One call's outcome: what happened and what to do next."""

    outcome: Outcome
    code: str
    message: str
    next: str
    dispatched: str
    retry_after_s: Optional[float] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def may_retry(self) -> bool:
        """Retryable, which means it did not run, or it is a read that changes nothing."""
        return self.outcome is Outcome.RETRYABLE

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "outcome": self.outcome.value,
            "code": self.code,
            "message": self.message,
            "next": self.next,
            "dispatched": self.dispatched,
        }
        if self.retry_after_s is not None:
            out["retry_after_s"] = self.retry_after_s
        if self.evidence:
            out["evidence"] = dict(self.evidence)
        return out


def info(code: str, message: str = "", *, retry_after_s: Optional[float] = None,
         evidence: Optional[Dict[str, Any]] = None, next_step: Optional[str] = None) -> OutcomeInfo:
    """The outcome for *code*. An unknown code is a programming error and raises KeyError."""
    outcome, dispatched, default_next = CODES[code]
    if retry_after_s is not None and code in _WAITS:
        default_next = "Wait %g s, then send it again." % retry_after_s
    return OutcomeInfo(outcome, code, message, next_step or default_next, dispatched,
                       retry_after_s, dict(evidence or {}))


def describe(outcome: Optional[Dict[str, Any]], message: str) -> str:
    """The message a client shows: what happened, the outcome, and the next step."""
    if not isinstance(outcome, dict) or not outcome.get("next"):
        return message
    return "%s [%s: %s] Next: %s" % (message, outcome.get("outcome"), outcome.get("code"), outcome["next"])


def with_failure_outcome(data: Any, error: Optional[str]) -> Any:
    """A failed WebSocket response's data, with the outcome it carries.

    A site that knows its case sets ``data["outcome"]`` itself. Otherwise the data says it: a
    read-only refusal carries ``read_only_mode``, a busy server ``retry_after``. Anything else is a
    handler that ran and failed. Data that is not a dict (or None) is left as it is.
    """
    if data is not None and not isinstance(data, dict):
        return data
    data = dict(data or {})
    if isinstance(data.get("outcome"), dict):
        return data
    message = error or ""
    if data.get("read_only_mode"):
        data["outcome"] = info("policy.read_only", message).to_dict()
    elif "retry_after" in data:
        try:
            wait = float(data["retry_after"])
        except (TypeError, ValueError):
            wait = None
        data["outcome"] = info("server.busy", message, retry_after_s=wait).to_dict()
    else:
        data["outcome"] = info("tool.failed", message).to_dict()
    return data


def for_exception(exc: BaseException) -> Optional[OutcomeInfo]:
    """The outcome an exception class declares through ``outcome_code``, or None."""
    code = getattr(exc, "outcome_code", None)
    if isinstance(code, str) and code in CODES:
        return info(code, str(exc))
    return None
