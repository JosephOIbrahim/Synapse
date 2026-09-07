"""Pure, measured model selection. A route never grants sharing permission.

The caller creates one route per task and retains it for every follow-up. No
provider, model, credential, endpoint, settings or network access occurs here.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import time

from .connections import ConnectionFacts, ConnectionSpec


@dataclass(frozen=True)
class RouteDecision:
    ok: bool
    facts: ConnectionFacts | None
    requirements: frozenset[str]
    automatic: bool
    reason: str


def _has_images(messages):
    pending = [messages]
    visited = set()
    while pending:
        item = pending.pop()
        if not isinstance(item, (Mapping, list, tuple)) or id(item) in visited:
            continue
        visited.add(id(item))
        if isinstance(item, Mapping):
            if item.get("type") in ("image", "image_url", "input_image"):
                return True
            for key in ("inline_data", "inlineData", "file_data", "fileData"):
                data = item.get(key)
                if isinstance(data, Mapping) and str(data.get("mime_type") or data.get("mimeType") or "").startswith("image/"):
                    return True
            if isinstance(item.get("images"), (list, tuple)) and item["images"]:
                return True
            pending.extend(item.values())
        else:
            pending.extend(item)
    return False


def required_capabilities(need="conversation", tools=None, messages=None):
    """Union the artist's selected need with tools and image content in payload."""
    needs = {"conversation": (), "tools": ("tools",), "houdini_tools": ("tools",),
             "vision": ("vision",), "images": ("vision",)}
    if not isinstance(need, str) or need not in needs:
        raise ValueError("Choose conversation, Houdini tools, or images as the task need.")
    requirements = {"completion", *needs[need]}
    if tools:
        requirements.add("tools")
    if _has_images(messages):
        requirements.add("vision")
    return frozenset(requirements)


def _facts(value):
    if isinstance(value, ConnectionFacts):
        return value
    if isinstance(value, ConnectionSpec):
        return ConnectionFacts(value)
    return None


def _explanation(facts, detail, now):
    return "%s · %s · %s. %s" % (facts.spec.identity, facts.spec.endpoint, facts.location_at(now), detail)


def _capability_problem(facts, requirements, automatic, now):
    if automatic and not facts.fresh(now):
        return "The connection check expired. Check this model before starting a new task."
    caps = facts.capabilities if facts.fresh(now) else None
    if caps is None:
        if automatic:
            return "Required capabilities are unknown. Check this model before starting a new task."
        return None
    missing = requirements - caps
    if missing:
        return "The model has not reported %s support. Check a suitable model and start a new task." % ", ".join(sorted(missing))
    return None


def validate_route(decision, *, tools=None, messages=None, need=None, now=None):
    """Validate the same route with follow-up needs; refusal cannot revive it."""
    if not decision.ok:
        return decision
    now = time.time() if now is None else now
    try:
        requirements = decision.requirements | required_capabilities(need or "conversation", tools, messages)
    except ValueError as exc:
        return RouteDecision(False, decision.facts, decision.requirements, decision.automatic, str(exc))
    problem = _capability_problem(decision.facts, requirements, decision.automatic, now)
    if problem:
        return RouteDecision(False, decision.facts, requirements, decision.automatic,
                             _explanation(decision.facts, problem, now))
    return RouteDecision(True, decision.facts, requirements, decision.automatic, decision.reason)


def choose_route(chosen, candidates=(), *, mode="chosen_model", need="conversation",
                 tools=None, messages=None, now=None, pinned=None):
    """Select once, or validate a pinned task route without replacing it.

    Automatic choice considers fresh checked facts only. Local candidates precede
    remote ones; the chosen exact identity wins within a location class, followed
    by stable provider/endpoint/model ordering. Metadata never claims model quality.
    """
    if pinned is not None:
        return validate_route(pinned, tools=tools, messages=messages, need=need, now=now)
    now = time.time() if now is None else now
    try:
        requirements = required_capabilities(need, tools, messages)
    except ValueError as exc:
        return RouteDecision(False, None, frozenset(), False, str(exc))
    if mode not in ("chosen_model", "prefer_checked_local"):
        return RouteDecision(False, None, requirements, False, "Choose Chosen model or Prefer a checked local model.")
    chosen = _facts(chosen)
    if chosen is None:
        return RouteDecision(False, None, requirements, False, "Connect and check a model before starting a task.")
    automatic = mode == "prefer_checked_local"
    if not automatic:
        problem = _capability_problem(chosen, requirements, False, now)
        detail = problem or "Using your chosen model."
        if chosen.capabilities is None or not chosen.fresh(now):
            detail += " Capabilities unknown; generation untested."
        return RouteDecision(problem is None, chosen, requirements, False, _explanation(chosen, detail, now))

    # A newer check for the same exact service/model invalidates the older one.
    # Conflicting simultaneous checks stay unknown instead of depending on order.
    latest = {}
    for candidate in (chosen, *candidates):
        candidate = _facts(candidate)
        if candidate is None or not candidate.fresh(candidate.checked_at):
            continue
        old = latest.get(candidate.spec)
        if old is None or candidate.checked_at > old.checked_at:
            latest[candidate.spec] = candidate
        elif candidate.checked_at == old.checked_at and candidate.metadata != old.metadata:
            latest[candidate.spec] = ConnectionFacts(candidate.spec, {}, candidate.checked_at)
    eligible = [candidate for candidate in latest.values()
                if _capability_problem(candidate, requirements, True, now) is None]
    if not eligible:
        return RouteDecision(False, None, requirements, True,
                             "No checked model reports the required capabilities (%s). Open Connect a model and check a suitable model." % ", ".join(sorted(requirements)))
    eligible.sort(key=lambda item: (item.location_at(now) != "Local", item.spec != chosen.spec,
                                   item.spec.provider, item.spec.endpoint, item.spec.model))
    selected = eligible[0]
    detail = "Selected a checked local model with the required reported capabilities."
    if selected.location_at(now) != "Local":
        detail = "No suitable checked local model was found. This checked model still requires sharing permission."
    return RouteDecision(True, selected, requirements, True, _explanation(selected, detail, now))
