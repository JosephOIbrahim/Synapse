"""Provider capability probe — routing is probe-derived, never config-declared.

A model list typed into a config file is documentation. A capability probe
against the provider is a probe. This module is the second thing.

Why the distinction is load-bearing here
----------------------------------------
This repository has the receipts. ``hou.ActiveRender`` is documented as working
and is absent at runtime. ``EXPECTED_HOUDINI_VERSION`` was declared and never
assigned, so every session silently loaded a five-year-old corpus. Five Solaris
tools were registered, tested, and completely unreachable. ``registry.py``
carried a comment reading *"no glm-5.2 tag exists, verified 2026-07-01"* while
Ollama's live ``/api/tags`` was returning ``glm-5.2:cloud`` — the comment was
true when written and aged into a false claim about the present (R74).

A model row in ``registry.py`` is exactly the same shape of claim, and it fails
the same way: quietly, while looking healthy. So this module emits a row for
**every registry-declared model as well as every live-discovered one**, and a
declared model that the provider does not actually offer comes back
``available=False, reason="declared_but_absent"`` — the ``ActiveRender`` pattern
caught by construction rather than by luck.

Contract
--------
* **No Qt, no hou.** Pure stdlib HTTP, matching ``base.StreamProvider``.
* **Zero completion spend, structurally.** Every endpoint this module can reach
  is in :data:`FREE_ENDPOINTS`. No code path here builds a completions request;
  ``/v1/messages`` (completions) and ``/v1/chat/completions`` appear nowhere.
  ``/v1/messages/count_tokens`` is free and unmetered and is the *only* member
  of the messages family that is reachable from here.
* **Colour is COMPUTED at read time**, from ``probed_at`` age and quota, by
  :func:`colour_for`. It is never a field, never persisted, never typed. Adding
  a colour field to :class:`ProbeResult` fails ``test_colour_is_not_a_field``.
* **Staleness degrades to GREY, never to green.** :func:`colour_for` checks age
  *before* it looks at ``available`` — a probe that has not run recently reports
  UNKNOWN, not the last thing it happened to see. There is no state meaning
  "we think so"; that is why GREY exists as its own state rather than
  degrading to green.
* **The probe must never be the thing that trips a rate limit.** Probing is
  demand-driven, not timer-driven: :func:`should_refresh` gates on
  :data:`REFRESH_INTERVAL_S`, so an idle panel issues zero probes. See
  `Polling`_ below.

Polling
-------
``REFRESH_INTERVAL_S = 60`` and ``PROBE_TTL_S = 180``.

At most one probe per provider per minute, and only when something actually
reads the state — so an idle panel costs nothing at all, and a busy one costs
60 requests/hour/provider against endpoints that are free and are not the
completions bucket. The lowest published Anthropic request-rate tier is well
above 1 rpm, so the liveness check cannot plausibly consume the quota it
reports on.

TTL is 3x the interval, so two consecutive probe failures are tolerated and the
third greys the rail. Maximum displayed staleness is therefore 3 minutes, not
the hour that the failure mode in the brief describes.

What this module cannot measure, and says so
--------------------------------------------
* **Quota headroom.** MEASURED 2026-07-28 against the live API: neither
  ``GET /v1/models`` nor ``POST /v1/messages/count_tokens`` returns any
  ``anthropic-ratelimit-*`` header, and NVIDIA's ``GET /v1/models`` returns
  none either. Headroom is only published by the completions endpoint, which
  costs money. So ``quota_remaining``/``quota_total`` are ``None`` for metered
  providers with ``quota_source="unavailable_at_zero_cost"``. A 429 *is* still
  detected — rate-limiting is caught reactively, headroom is not reported
  predictively. ``None`` never computes to RED and never computes to GREEN;
  it simply carries no quota signal.
* **Price.** No provider exposes per-token pricing over its API (verified: the
  Anthropic model object carries ``id``/``display_name``/``created_at``/
  ``type``; NVIDIA's carries ``id``/``created``/``object``/``owned_by``;
  Ollama's carries no billing field). Price is therefore ``None`` for metered
  models rather than a table typed into code — a declared price table would be
  the very claim-shape this module exists to refuse, and keying one by model id
  would also put model names in code. Where the probe *can* establish cost it
  does: an Ollama tag with no ``remote_host`` runs on this machine, so there is
  no per-token vendor charge and the cost is a probed ``0.0``. An Ollama
  ``:cloud`` tag has a ``remote_host`` and is metered by that host, so it gets
  ``None`` like any other metered model.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import re
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, fields
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier constants — dispatch asks for a TIER, never for a model name.
# ---------------------------------------------------------------------------

TIER_FRONTIER = "frontier"
TIER_BALANCED = "balanced"
TIER_FAST = "fast"
TIERS = (TIER_FRONTIER, TIER_BALANCED, TIER_FAST)

# ---------------------------------------------------------------------------
# Colour alphabet. These are the only three states. Colour is COMPUTED from a
# ProbeResult by colour_for(); it is never stored on one.
# ---------------------------------------------------------------------------

COLOUR_GREEN = "green"   # probed, fresh, available
COLOUR_RED = "red"       # probed, fresh, and not dispatchable right now
COLOUR_GREY = "grey"     # never probed, or the probe is stale — UNKNOWN

COLOURS = (COLOUR_GREEN, COLOUR_RED, COLOUR_GREY)

# ---------------------------------------------------------------------------
# Polling. See the module docstring's "Polling" section for the reasoning.
# ---------------------------------------------------------------------------

REFRESH_INTERVAL_S = 60.0
"""Minimum seconds between probes of one provider. Doubles as the rate-limit
floor: ``should_refresh`` returns False inside this window, so a caller in a
hot loop still cannot hammer a provider."""

PROBE_TTL_S = 180.0
"""Seconds after which a probe result is STALE and reads GREY. 3x the refresh
interval, so two consecutive probe failures are survivable and the third
surfaces as UNKNOWN."""

# ---------------------------------------------------------------------------
# Endpoint allowlist. Every reachable endpoint is free. This is the structural
# half of the zero-spend guarantee — the other half is that no code below
# builds a completions body.
# ---------------------------------------------------------------------------

FREE_ENDPOINTS = frozenset({
    "ollama:GET /api/tags",
    "anthropic:GET /v1/models",
    "anthropic:POST /v1/messages/count_tokens",
    "nvidia:GET /v1/models",
    "gemini:GET /v1beta/models",
    "custom:GET /models",
    "local:config",
})
"""Every network call this module is permitted to make, plus the one purely
local observation. ``local:config`` is key resolution — a real, zero-cost,
timestamped observation of whether this install can dispatch at all."""

_HTTP_TIMEOUT_LOCAL = 2.0
_HTTP_TIMEOUT_REMOTE = 8.0

_ANTHROPIC_HOST = "api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"
_NVIDIA_HOST = "integrate.api.nvidia.com"
_GEMINI_HOST = "generativelanguage.googleapis.com"
_OLLAMA_DEFAULT_BASE = "http://localhost:11434"


# ---------------------------------------------------------------------------
# The probe result — §3.3's structure, plus the provenance Law 2 requires.
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProbeResult:
    """One model's probed state at one instant.

    The first nine fields are the blueprint §3.3 structure verbatim. The rest
    is provenance: every number carries the call that produced it, because a
    number travelling without a producer is the defect this harness was built
    to stop repeating (Law 2).

    There is deliberately **no colour field.** Colour is a function of this
    structure and the current time — see :func:`colour_for`.
    """

    # -- §3.3 --------------------------------------------------------------
    model: str
    tier_candidates: tuple[str, ...]
    available: bool
    quota_remaining: Optional[int]
    quota_total: Optional[int]
    cost_per_1k_in: Optional[float]
    cost_per_1k_out: Optional[float]
    latency_ms: Optional[float]
    probed_at: Optional[float]          # epoch seconds, UTC; None ⇒ never probed

    # -- provenance --------------------------------------------------------
    provider: str = ""
    method: str = "local:config"        # a member of FREE_ENDPOINTS
    reason: Optional[str] = None        # why available is False, or None
    evidence_tier: str = "UNVERIFIED"
    quota_source: str = "unknown"
    cost_source: str = "unknown"
    tier_basis: str = "unclassified"
    declared: bool = False              # present in registry.py
    live: bool = False                  # returned by the provider
    capabilities: Optional[tuple[str, ...]] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Plain-JSON view. Carries no colour — a serialized result cannot
        smuggle a stored colour past :func:`colour_for`."""
        return {
            "model": self.model,
            "tier_candidates": list(self.tier_candidates),
            "available": self.available,
            "quota_remaining": self.quota_remaining,
            "quota_total": self.quota_total,
            "cost_per_1k_in": self.cost_per_1k_in,
            "cost_per_1k_out": self.cost_per_1k_out,
            "latency_ms": self.latency_ms,
            "probed_at": self.probed_at,
            "provider": self.provider,
            "method": self.method,
            "reason": self.reason,
            "evidence_tier": self.evidence_tier,
            "quota_source": self.quota_source,
            "cost_source": self.cost_source,
            "tier_basis": self.tier_basis,
            "declared": self.declared,
            "live": self.live,
            "capabilities": list(self.capabilities) if self.capabilities is not None else None,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Colour — COMPUTED, never stored. This is the whole design.
# ---------------------------------------------------------------------------

def age_s(result: ProbeResult, *, now: Optional[float] = None) -> Optional[float]:
    """Seconds since the probe ran, or ``None`` if it never ran."""
    if result.probed_at is None:
        return None
    return (time.time() if now is None else now) - result.probed_at


def is_stale(result: ProbeResult, *, now: Optional[float] = None,
             ttl_s: float = PROBE_TTL_S) -> bool:
    """True when the result carries no usable freshness.

    Stale means: never probed, older than ``ttl_s``, or stamped in the future.
    A future timestamp is clock skew, and skew is not freshness — treating it
    as fresh would let a wrong clock hold a rail green indefinitely.
    """
    age = age_s(result, now=now)
    if age is None:
        return True
    return age > ttl_s or age < 0.0


def colour_for(result: ProbeResult, *, now: Optional[float] = None,
               ttl_s: float = PROBE_TTL_S) -> str:
    """The display colour for ``result`` **at this instant**.

    Order matters and is the point:

    1. stale or never probed  → GREY. Checked FIRST, before ``available`` is
       even consulted. The failure mode being designed against is a rail that
       shows a model as available because the last probe said so an hour ago —
       that is the phantom-API pattern with a timestamp on it.
    2. not available          → RED (``reason`` says which kind of no).
    3. quota exhausted        → RED. Only an explicit ``0`` counts; ``None``
       means no quota signal was obtainable and must not manufacture one.
    4. otherwise              → GREEN.

    Cost never appears here. A price cannot make anything green.
    """
    if is_stale(result, now=now, ttl_s=ttl_s):
        return COLOUR_GREY
    if not result.available:
        return COLOUR_RED
    if result.quota_remaining is not None and result.quota_remaining <= 0:
        return COLOUR_RED
    return COLOUR_GREEN


def should_refresh(result: Optional[ProbeResult], *, now: Optional[float] = None,
                   interval_s: float = REFRESH_INTERVAL_S) -> bool:
    """True when ``result`` is old enough to be re-probed.

    Demand-driven: the caller asks before reading. Nothing here runs on a
    timer, so an idle panel issues zero probes and the liveness check cannot
    consume the quota it reports on. A missing result always refreshes; a
    future-stamped one refreshes too (skew must not pin a stale row).
    """
    if result is None:
        return True
    age = age_s(result, now=now)
    if age is None:
        return True
    return age >= interval_s or age < 0.0


# ---------------------------------------------------------------------------
# Tiering — rules applied to LIVE probe output, never to a typed model list.
# ---------------------------------------------------------------------------

_PARAM_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([kmbt])\b", re.IGNORECASE)
_PARAM_SCALE = {"k": 1e-6, "m": 1e-3, "b": 1.0, "t": 1e3}

# Capability thresholds in billions of parameters. These are numbers about
# model SIZE, not model identity — they classify whatever the probe returns,
# including models that did not exist when this was written.
FRONTIER_MIN_B = 200.0
BALANCED_MIN_B = 25.0

# Family tokens as they appear in LIVE provider output. This is the weaker
# signal and is labelled as such in tier_basis: it is matched against the id
# and display name the PROVIDER returned this second, so a newly-released
# model is classified the moment the provider serves it. That is the property
# a config-declared list cannot have.
_TIER_TOKENS = (
    (TIER_FRONTIER, ("opus", "ultra", "-pro", "pro-", "max", "large")),
    (TIER_BALANCED, ("sonnet", "super", "medium", "-49b", "instruct")),
    (TIER_FAST, ("haiku", "mini", "nano", "flash", "small", "lite", "tiny", "-oss")),
)


def parse_parameter_size(text: Optional[str]) -> Optional[float]:
    """``"123.6B"`` → ``123.6`` (billions). ``None`` when unparseable.

    Returns None rather than guessing — an unparseable size must reach
    :func:`tier_candidates_for` as absent evidence, not as zero.
    """
    if not text:
        return None
    m = _PARAM_RE.match(str(text))
    if not m:
        return None
    try:
        return float(m.group(1)) * _PARAM_SCALE[m.group(2).lower()]
    except (ValueError, KeyError):
        return None


def tier_candidates_for(
    model_id: str,
    *,
    display_name: str = "",
    parameter_size: Optional[str] = None,
    capabilities: Optional[Sequence[str]] = None,
) -> tuple[tuple[str, ...], str]:
    """``(tiers, basis)`` for a model, derived from what the probe returned.

    Evidence is used strongest-first:

    * ``parameter_size`` (numeric, only Ollama publishes it) → ``"parameter_size"``
    * a family token in the id/display name the provider just returned →
      ``"live_id_token"``
    * nothing matched → ``()`` and ``"unclassified"``

    An unclassified model gets an EMPTY tier tuple, never a default tier. A
    default would be a guess wearing a tier constant, and it would route work
    to a model nothing established was suitable.

    Tool use is a hard gate where it is known: a model the provider says has no
    ``tools`` capability cannot serve the dispatch spine, so it is
    ``()``/``"no_tool_capability"`` regardless of size. Where capabilities are
    unknown (``None``) no gate is applied — absence of evidence is not
    evidence of absence.
    """
    if capabilities is not None and "tools" not in {str(c).lower() for c in capabilities}:
        return (), "no_tool_capability"

    billions = parse_parameter_size(parameter_size)
    if billions is not None:
        if billions >= FRONTIER_MIN_B:
            return (TIER_FRONTIER,), "parameter_size"
        if billions >= BALANCED_MIN_B:
            return (TIER_BALANCED,), "parameter_size"
        return (TIER_FAST,), "parameter_size"

    haystack = "%s %s" % (model_id or "", display_name or "")
    haystack = haystack.lower()
    for tier, tokens in _TIER_TOKENS:
        if any(tok in haystack for tok in tokens):
            return (tier,), "live_id_token"

    return (), "unclassified"


# ---------------------------------------------------------------------------
# HTTP plumbing — GET/list endpoints only.
# ---------------------------------------------------------------------------

def _request(scheme: str, host: str, path: str, *, method: str = "GET",
             headers: Optional[dict] = None, body: Optional[str] = None,
             timeout: float = _HTTP_TIMEOUT_REMOTE):
    """One bounded HTTP round trip → ``(status, headers_dict, text, latency_ms)``.

    Raises on transport failure; callers convert that into an unreachable
    result rather than letting it escape. Never follows a redirect and never
    retries — a probe that retries is a probe that can amplify a rate limit.
    """
    if scheme == "http":
        conn = http.client.HTTPConnection(host, timeout=timeout)
    else:
        conn = http.client.HTTPSConnection(
            host, timeout=timeout, context=ssl.create_default_context())
    t0 = time.perf_counter()
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        text = resp.read().decode("utf-8", errors="replace")
        latency_ms = (time.perf_counter() - t0) * 1000.0
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        return resp.status, hdrs, text, latency_ms
    finally:
        conn.close()


def _quota_from_headers(hdrs: Mapping[str, str]) -> tuple[Optional[int], Optional[int], str]:
    """``(remaining, total, source)`` from whatever rate-limit headers exist.

    MEASURED 2026-07-28: none of the free endpoints this module calls emit
    ``anthropic-ratelimit-*`` or ``x-ratelimit-*``. This parser therefore
    normally returns ``(None, None, "unavailable_at_zero_cost")`` — which is
    the honest answer, not a bug. It is kept live because a 429 response *does*
    carry them, and because a provider adding them later should be picked up
    without a code change.
    """
    remaining = total = None
    for rk, tk in (
        ("anthropic-ratelimit-requests-remaining", "anthropic-ratelimit-requests-limit"),
        ("x-ratelimit-remaining-requests", "x-ratelimit-limit-requests"),
        ("x-ratelimit-remaining", "x-ratelimit-limit"),
        ("ratelimit-remaining", "ratelimit-limit"),
    ):
        if rk in hdrs:
            try:
                remaining = int(str(hdrs[rk]).strip())
            except ValueError:
                remaining = None
            try:
                total = int(str(hdrs[tk]).strip()) if tk in hdrs else None
            except ValueError:
                total = None
            if remaining is not None:
                return remaining, total, "header:%s" % rk
    return None, None, "unavailable_at_zero_cost"


def _rows(provider: str, live: Mapping[str, dict], declared: Sequence[str],
          *, probed_at: float, latency_ms: Optional[float],
          quota: tuple[Optional[int], Optional[int], str], method: str,
          evidence_tier: str = "VERIFIED-RUNTIME") -> list[ProbeResult]:
    """Union of live-discovered and registry-declared models, as rows.

    A declared model missing from ``live`` is emitted ``available=False``,
    ``reason="declared_but_absent"``. That row is the entire reason this
    function takes both arguments: it is how a ``registry.py`` entry that the
    provider does not actually serve shows up RED instead of looking healthy.
    """
    q_rem, q_tot, q_src = quota
    out: list[ProbeResult] = []
    seen = set()

    for model_id, meta in live.items():
        seen.add(model_id)
        caps = meta.get("capabilities")
        caps_t = tuple(caps) if caps is not None else None
        tiers, basis = tier_candidates_for(
            model_id,
            display_name=meta.get("display_name", "") or "",
            parameter_size=meta.get("parameter_size"),
            capabilities=caps,
        )
        cost_in, cost_out, cost_src = meta.get(
            "cost", (None, None, "unprobeable:no_pricing_endpoint"))
        out.append(ProbeResult(
            model=model_id,
            tier_candidates=tiers,
            available=True,
            quota_remaining=q_rem,
            quota_total=q_tot,
            cost_per_1k_in=cost_in,
            cost_per_1k_out=cost_out,
            latency_ms=latency_ms,
            probed_at=probed_at,
            provider=provider,
            method=method,
            reason=None,
            evidence_tier=evidence_tier,
            quota_source=q_src,
            cost_source=cost_src,
            tier_basis=basis,
            declared=model_id in set(declared),
            live=True,
            capabilities=caps_t,
            detail=meta.get("detail", {}),
        ))

    for model_id in declared:
        if model_id in seen or not model_id:
            continue
        tiers, basis = tier_candidates_for(model_id)
        out.append(ProbeResult(
            model=model_id,
            tier_candidates=tiers,
            available=False,
            quota_remaining=q_rem,
            quota_total=q_tot,
            cost_per_1k_in=None,
            cost_per_1k_out=None,
            latency_ms=latency_ms,
            probed_at=probed_at,
            provider=provider,
            method=method,
            reason="declared_but_absent",
            evidence_tier=evidence_tier,
            quota_source=q_src,
            cost_source="unprobeable:no_pricing_endpoint",
            tier_basis=basis,
            declared=True,
            live=False,
            capabilities=None,
            detail={},
        ))
    return out


def _unreachable(provider: str, declared: Sequence[str], *, probed_at: float,
                 method: str, reason: str,
                 latency_ms: Optional[float] = None,
                 quota: tuple[Optional[int], Optional[int], str] =
                 (None, None, "not_applicable")) -> list[ProbeResult]:
    """Rows for a provider that could not be reached or is not configured.

    ``available=False`` on a FRESH timestamp, so these read RED, not GREY. The
    distinction is deliberate: the probe *did* run and it established that this
    install cannot dispatch to this provider right now. GREY is reserved for
    "we do not know", and here we do know. ``reason`` carries which kind of no.

    ``quota`` is threaded through because a 429 response is the one case where
    rate-limit headers ARE published — the free endpoints publish none while
    they are succeeding.
    """
    q_rem, q_tot, q_src = quota
    rows = []
    for model_id in declared or ("",):
        if not model_id:
            continue
        tiers, basis = tier_candidates_for(model_id)
        rows.append(ProbeResult(
            model=model_id,
            tier_candidates=tiers,
            available=False,
            quota_remaining=q_rem,
            quota_total=q_tot,
            cost_per_1k_in=None,
            cost_per_1k_out=None,
            latency_ms=latency_ms,
            probed_at=probed_at,
            provider=provider,
            method=method,
            reason=reason,
            evidence_tier="VERIFIED-RUNTIME",
            quota_source=q_src,
            cost_source="not_applicable",
            tier_basis=basis,
            declared=True,
            live=False,
            capabilities=None,
            detail={},
        ))
    return rows


# ---------------------------------------------------------------------------
# Per-provider probes. Each returns a list of ProbeResult.
# ---------------------------------------------------------------------------

def _declared_models(provider_id: str) -> tuple[str, ...]:
    """The model ids ``registry.py`` declares for a provider — the claim under
    test, never the answer."""
    try:
        from . import registry
        return tuple(mid for mid, _label in registry.models_for(provider_id) if mid)
    except Exception as exc:            # pragma: no cover - registry import guard
        logger.debug("registry rows unavailable for %r: %s", provider_id, exc)
        return ()


def _ollama_base() -> tuple[str, str, str]:
    base = os.environ.get("OLLAMA_HOST", "").strip() or _OLLAMA_DEFAULT_BASE
    parts = urlsplit(base if "//" in base else "http://" + base)
    return (parts.scheme or "http", parts.netloc or "localhost:11434",
            parts.path.rstrip("/"))


def probe_ollama(*, now: Optional[float] = None,
                 timeout: float = _HTTP_TIMEOUT_LOCAL) -> list[ProbeResult]:
    """``GET {OLLAMA_HOST}/api/tags`` — free, local, no quota to consume.

    Cost is genuinely probe-derived here and nowhere else: a tag with no
    ``remote_host`` runs on this machine, so there is no per-token vendor
    charge and cost is ``0.0``. A ``:cloud`` tag reports a ``remote_host`` and
    is metered by that host — it gets ``None``, the same as any other metered
    model. The registry's default (``glm-5:cloud``) is one of those, so
    "Ollama is local and free" is not true of the row the panel ships with.
    """
    probed_at = time.time() if now is None else now
    declared = _declared_models("ollama")
    method = "ollama:GET /api/tags"
    scheme, host, path = _ollama_base()
    try:
        status, hdrs, text, latency = _request(
            scheme, host, path + "/api/tags", timeout=timeout)
    except Exception as exc:
        logger.debug("Ollama unreachable: %s", exc)
        return _unreachable("ollama", declared, probed_at=probed_at,
                            method=method, reason="unreachable")
    if status == 429:
        return _unreachable("ollama", declared, probed_at=probed_at,
                            method=method, reason="rate_limited", latency_ms=latency,
                            quota=_quota_from_headers(hdrs))
    if status != 200:
        return _unreachable("ollama", declared, probed_at=probed_at, method=method,
                            reason="http_%d" % status, latency_ms=latency)

    live: dict[str, dict] = {}
    try:
        payload = json.loads(text)
        for m in payload.get("models", []) or []:
            name = m.get("name") or m.get("model")
            if not name:
                continue
            det = m.get("details") or {}
            remote = m.get("remote_host") or ""
            cost = ((None, None, "metered:remote_host=%s" % remote) if remote
                    else (0.0, 0.0, "probed:local_weights_no_remote_host"))
            live[name] = {
                "display_name": name,
                "parameter_size": det.get("parameter_size"),
                "capabilities": m.get("capabilities"),
                "cost": cost,
                "detail": {
                    "remote_host": remote or None,
                    "context_length": det.get("context_length"),
                    "family": det.get("family") or None,
                },
            }
    except Exception as exc:
        logger.debug("Ollama /api/tags unparseable: %s", exc)
        return _unreachable("ollama", declared, probed_at=probed_at, method=method,
                            reason="unparseable_response", latency_ms=latency)

    return _rows("ollama", live, declared, probed_at=probed_at, latency_ms=latency,
                 quota=_quota_from_headers(hdrs), method=method)


def probe_anthropic(*, now: Optional[float] = None,
                    timeout: float = _HTTP_TIMEOUT_REMOTE) -> list[ProbeResult]:
    """``GET /v1/models`` — free and unmetered. No completion is issued.

    The models endpoint answers availability. It does NOT answer quota:
    measured 2026-07-28, it returns no rate-limit header of any kind, and
    neither does the free ``count_tokens`` endpoint. Headroom is published
    only by the completions endpoint, which costs money, so it is not read
    here and ``quota_source`` says exactly that.
    """
    probed_at = time.time() if now is None else now
    declared = _declared_models("claude")
    method = "anthropic:GET /v1/models"
    try:
        from synapse.host.auth import get_anthropic_api_key
        key = get_anthropic_api_key()
    except Exception as exc:            # pragma: no cover - import guard
        logger.debug("anthropic key resolution failed: %s", exc)
        key = None
    if not key:
        return _unreachable("claude", declared, probed_at=probed_at,
                            method="local:config", reason="unconfigured")
    try:
        status, hdrs, text, latency = _request(
            "https", _ANTHROPIC_HOST, "/v1/models?limit=100",
            headers={"x-api-key": key, "anthropic-version": _ANTHROPIC_VERSION},
            timeout=timeout)
    except Exception as exc:
        logger.debug("Anthropic unreachable: %s", exc)
        return _unreachable("claude", declared, probed_at=probed_at,
                            method=method, reason="unreachable")
    if status == 429:
        return _unreachable("claude", declared, probed_at=probed_at, method=method,
                            reason="rate_limited", latency_ms=latency,
                            quota=_quota_from_headers(hdrs))
    if status in (401, 403):
        return _unreachable("claude", declared, probed_at=probed_at, method=method,
                            reason="unauthorized", latency_ms=latency)
    if status != 200:
        return _unreachable("claude", declared, probed_at=probed_at, method=method,
                            reason="http_%d" % status, latency_ms=latency)

    live: dict[str, dict] = {}
    try:
        for m in (json.loads(text).get("data") or []):
            mid = m.get("id")
            if not mid:
                continue
            live[mid] = {
                "display_name": m.get("display_name") or "",
                "parameter_size": None,      # not published by this API
                "capabilities": None,        # unknown ⇒ no tool gate applied
                "cost": (None, None, "unprobeable:no_pricing_endpoint"),
                "detail": {"created_at": m.get("created_at")},
            }
    except Exception as exc:
        logger.debug("Anthropic /v1/models unparseable: %s", exc)
        return _unreachable("claude", declared, probed_at=probed_at, method=method,
                            reason="unparseable_response", latency_ms=latency)

    return _rows("claude", live, declared, probed_at=probed_at, latency_ms=latency,
                 quota=_quota_from_headers(hdrs), method=method)


def probe_nvidia(*, now: Optional[float] = None,
                 timeout: float = _HTTP_TIMEOUT_REMOTE) -> list[ProbeResult]:
    """``GET /v1/models`` on the NIM cloud (or ``NVIDIA_BASE_URL``) — free."""
    probed_at = time.time() if now is None else now
    declared = _declared_models("nemotron")
    method = "nvidia:GET /v1/models"
    try:
        import synapse.host.auth  # noqa: F401 — side effect: loads <repo>/.env
    except Exception:
        pass
    base = os.environ.get("NVIDIA_BASE_URL", "").strip()
    if base:
        parts = urlsplit(base if "//" in base else "https://" + base)
        scheme = parts.scheme or "https"
        host = parts.netloc or _NVIDIA_HOST
        path = (parts.path.rstrip("/") or "/v1") + "/models"
    else:
        scheme, host, path = "https", _NVIDIA_HOST, "/v1/models"

    key = (os.environ.get("NVIDIA_API_KEY") or "").strip()
    if not key and host == _NVIDIA_HOST:
        return _unreachable("nemotron", declared, probed_at=probed_at,
                            method="local:config", reason="unconfigured")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        status, hdrs, text, latency = _request(scheme, host, path,
                                               headers=headers, timeout=timeout)
    except Exception as exc:
        logger.debug("NVIDIA unreachable: %s", exc)
        return _unreachable("nemotron", declared, probed_at=probed_at,
                            method=method, reason="unreachable")
    if status == 429:
        return _unreachable("nemotron", declared, probed_at=probed_at, method=method,
                            reason="rate_limited", latency_ms=latency,
                            quota=_quota_from_headers(hdrs))
    if status in (401, 403):
        return _unreachable("nemotron", declared, probed_at=probed_at, method=method,
                            reason="unauthorized", latency_ms=latency)
    if status != 200:
        return _unreachable("nemotron", declared, probed_at=probed_at, method=method,
                            reason="http_%d" % status, latency_ms=latency)

    live: dict[str, dict] = {}
    try:
        for m in (json.loads(text).get("data") or []):
            mid = m.get("id")
            if not mid:
                continue
            live[mid] = {
                "display_name": mid,
                "parameter_size": None,
                "capabilities": None,
                "cost": (None, None, "unprobeable:no_pricing_endpoint"),
                "detail": {"owned_by": m.get("owned_by")},
            }
    except Exception as exc:
        logger.debug("NVIDIA /v1/models unparseable: %s", exc)
        return _unreachable("nemotron", declared, probed_at=probed_at, method=method,
                            reason="unparseable_response", latency_ms=latency)

    return _rows("nemotron", live, declared, probed_at=probed_at, latency_ms=latency,
                 quota=_quota_from_headers(hdrs), method=method)


def probe_gemini(*, now: Optional[float] = None,
                 timeout: float = _HTTP_TIMEOUT_REMOTE) -> list[ProbeResult]:
    """``GET /v1beta/models`` — free listing. Skipped entirely without a key."""
    probed_at = time.time() if now is None else now
    declared = _declared_models("gemini")
    method = "gemini:GET /v1beta/models"
    try:
        import synapse.host.auth  # noqa: F401 — side effect: loads <repo>/.env
    except Exception:
        pass
    key = ""
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        key = (os.environ.get(var) or "").strip()
        if key:
            break
    if not key:
        return _unreachable("gemini", declared, probed_at=probed_at,
                            method="local:config", reason="unconfigured")
    try:
        status, hdrs, text, latency = _request(
            "https", _GEMINI_HOST, "/v1beta/models?pageSize=200",
            headers={"x-goog-api-key": key}, timeout=timeout)
    except Exception as exc:
        logger.debug("Gemini unreachable: %s", exc)
        return _unreachable("gemini", declared, probed_at=probed_at,
                            method=method, reason="unreachable")
    if status == 429:
        return _unreachable("gemini", declared, probed_at=probed_at, method=method,
                            reason="rate_limited", latency_ms=latency,
                            quota=_quota_from_headers(hdrs))
    if status in (401, 403):
        return _unreachable("gemini", declared, probed_at=probed_at, method=method,
                            reason="unauthorized", latency_ms=latency)
    if status != 200:
        return _unreachable("gemini", declared, probed_at=probed_at, method=method,
                            reason="http_%d" % status, latency_ms=latency)

    live: dict[str, dict] = {}
    try:
        for m in (json.loads(text).get("models") or []):
            raw = m.get("name") or ""
            mid = raw.split("/", 1)[1] if raw.startswith("models/") else raw
            if not mid:
                continue
            methods = m.get("supportedGenerationMethods")
            live[mid] = {
                "display_name": m.get("displayName") or "",
                "parameter_size": None,
                "capabilities": None,
                "cost": (None, None, "unprobeable:no_pricing_endpoint"),
                "detail": {"supported_methods": methods},
            }
    except Exception as exc:
        logger.debug("Gemini /v1beta/models unparseable: %s", exc)
        return _unreachable("gemini", declared, probed_at=probed_at, method=method,
                            reason="unparseable_response", latency_ms=latency)

    return _rows("gemini", live, declared, probed_at=probed_at, latency_ms=latency,
                 quota=_quota_from_headers(hdrs), method=method)


def probe_custom(*, now: Optional[float] = None,
                 timeout: float = _HTTP_TIMEOUT_REMOTE) -> list[ProbeResult]:
    """``GET {base_url}/models`` on a user-configured OpenAI-compatible endpoint.

    An unconfigured Custom engine is a determinate local observation, not a
    network call.
    """
    probed_at = time.time() if now is None else now
    declared = _declared_models("custom")
    method = "custom:GET /models"
    try:
        from . import registry
        cfg = registry._custom_config()
    except Exception:
        cfg = {}
    base = (cfg.get("base_url") or "").strip()
    if not base or not (cfg.get("model") or "").strip():
        return _unreachable("custom", declared or (cfg.get("model") or "",),
                            probed_at=probed_at, method="local:config",
                            reason="unconfigured")
    parts = urlsplit(base if "//" in base else "https://" + base)
    scheme = parts.scheme or "https"
    host = parts.netloc
    path = (parts.path.rstrip("/") or "/v1") + "/models"
    headers = {"Accept": "application/json"}
    key_env = (cfg.get("key_env") or "").strip()
    if key_env:
        key = (os.environ.get(key_env) or "").strip()
        if not key:
            return _unreachable("custom", declared, probed_at=probed_at,
                                method="local:config", reason="unconfigured")
        headers["Authorization"] = "Bearer " + key
    try:
        status, hdrs, text, latency = _request(scheme, host, path,
                                               headers=headers, timeout=timeout)
    except Exception as exc:
        logger.debug("Custom endpoint unreachable: %s", exc)
        return _unreachable("custom", declared, probed_at=probed_at,
                            method=method, reason="unreachable")
    if status != 200:
        reason = ("rate_limited" if status == 429
                  else "unauthorized" if status in (401, 403)
                  else "http_%d" % status)
        return _unreachable("custom", declared, probed_at=probed_at, method=method,
                            reason=reason, latency_ms=latency,
                            quota=_quota_from_headers(hdrs))
    live: dict[str, dict] = {}
    try:
        for m in (json.loads(text).get("data") or []):
            mid = m.get("id")
            if mid:
                live[mid] = {
                    "display_name": mid,
                    "parameter_size": None,
                    "capabilities": None,
                    "cost": (None, None, "unprobeable:no_pricing_endpoint"),
                    "detail": {},
                }
    except Exception as exc:
        logger.debug("Custom /models unparseable: %s", exc)
        return _unreachable("custom", declared, probed_at=probed_at, method=method,
                            reason="unparseable_response", latency_ms=latency)
    return _rows("custom", live, declared, probed_at=probed_at, latency_ms=latency,
                 quota=_quota_from_headers(hdrs), method=method)


_PROBES = {
    "ollama": probe_ollama,
    "claude": probe_anthropic,
    "nemotron": probe_nvidia,
    "gemini": probe_gemini,
    "custom": probe_custom,
}


def configured_providers() -> dict[str, bool]:
    """Which providers this install can dispatch to, with **no network call**.

    Key resolution is itself an observation — cheap, local, and determinate.
    Running it first means an unconfigured provider never causes a request.
    """
    out: dict[str, bool] = {}
    for pid in _PROBES:
        try:
            from . import registry
            prov = registry.build_provider(pid)
            out[pid] = bool(prov.resolve_key())
        except Exception as exc:
            logger.debug("configured check failed for %r: %s", pid, exc)
            out[pid] = False
    return out


def probe_all(provider_ids: Optional[Sequence[str]] = None, *,
              now: Optional[float] = None,
              max_workers: int = 4) -> list[ProbeResult]:
    """Probe each provider once and return every row, sorted.

    Providers are probed concurrently because they are independent and a slow
    one must not gate a fast one. Each row still carries its own measured
    ``latency_ms``. Ordering of the returned list is deterministic
    (provider, then model) so two runs are diffable.
    """
    ids = tuple(provider_ids) if provider_ids is not None else tuple(_PROBES)
    ids = tuple(p for p in ids if p in _PROBES)
    if not ids:
        return []
    rows: list[ProbeResult] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(ids)))) as pool:
        for result in pool.map(lambda pid: _safe_probe(pid, now=now), ids):
            rows.extend(result)
    rows.sort(key=lambda r: (r.provider, r.model))
    return rows


def _safe_probe(provider_id: str, *, now: Optional[float] = None) -> list[ProbeResult]:
    """Run one provider's probe; an unexpected raise becomes a RED row, never a
    lost provider. Law 3: the status describes what happened."""
    try:
        return _PROBES[provider_id](now=now)
    except Exception as exc:            # pragma: no cover - defensive
        logger.warning("probe for %r raised: %s", provider_id, exc)
        return _unreachable(provider_id, _declared_models(provider_id),
                            probed_at=time.time() if now is None else now,
                            method="local:config", reason="probe_error")


def summarize(rows: Sequence[ProbeResult], *, now: Optional[float] = None,
              ttl_s: float = PROBE_TTL_S) -> dict:
    """Counts by computed colour plus tier coverage — a read-time view.

    Colour is computed here exactly as the panel would compute it, from the
    same function, so the summary can never disagree with the rail.
    """
    by_colour = {c: 0 for c in COLOURS}
    by_tier = {t: 0 for t in TIERS}
    unclassified = 0
    for r in rows:
        by_colour[colour_for(r, now=now, ttl_s=ttl_s)] += 1
        if r.tier_candidates:
            for t in r.tier_candidates:
                by_tier[t] = by_tier.get(t, 0) + 1
        else:
            unclassified += 1
    return {
        "rows": len(rows),
        "by_colour": by_colour,
        "by_tier": by_tier,
        "unclassified": unclassified,
        "ttl_s": ttl_s,
        "refresh_interval_s": REFRESH_INTERVAL_S,
    }


def result_field_names() -> tuple[str, ...]:
    """The declared field names of :class:`ProbeResult`. Used by the test that
    pins colour out of the structure."""
    return tuple(f.name for f in fields(ProbeResult))
