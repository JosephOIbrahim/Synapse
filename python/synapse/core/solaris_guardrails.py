"""
Solaris production-rules catalog — single-source, advisory, pure-Python.

This module is the durable, *importable* form of SYNAPSE's common-error catalog
for the USD/Solaris/Karma path. Until now these rules lived only as retrievable
prose in ``rag/skills/houdini21-reference/common_errors.md`` (the "Common
Mistakes" section + the per-diagnostic notes) and as checks scattered inline
across handlers. There was no single place to import, enumerate, or unit-pin
them. This catalog is that place.

Source of record: ``rag/skills/houdini21-reference/common_errors.md``. The
encoding-dependent rows defer to :mod:`synapse.core.usd_punycode` — they store a
friendly *alias* (``"intensity"``, ``"color"``, ``"radius"``) and resolve the
live punycode literal through :func:`synapse.core.usd_punycode.encoded` so no
punycode literal is ever re-hardcoded here. If an alias is not in the
single-source map, :func:`rule_encoding` returns ``None``; if it is present but
still an unverified placeholder there, that status lives in usd_punycode — the
catalog defers either way and never guesses.

Scope & posture:
    * **Advisory / declarative only.** Nothing here mutates a node, a parm, or a
      handler. The catalog is data plus a handful of *pure* predicate helpers
      (``check_light_intensity``, ``check_camera_target``, ``check_tuple_parm``).
      Wiring these into the live handlers is a deliberate follow-up pass.
    * **Pure-Python, zero ``hou``.** Importable in CI/standalone exactly like
      :mod:`synapse.core.usd_punycode`. No Houdini, USD, or PySide import.

Each :class:`ProductionRule` carries: a stable ``id``, a one-line ``rule`` (the
imperative), a ``rationale`` (why it bites), the verified ``fact`` it depends on,
and — for encoding-dependent rules — an ``encoding_alias`` into the punycode map.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .usd_punycode import PUNYCODE_PARMS, TUPLE_ALIASES, encoded

__all__ = [
    "ProductionRule",
    "Advisory",
    "PRODUCTION_RULES",
    "RULES_BY_ID",
    "get_rule",
    "rule_encoding",
    "check_light_intensity",
    "check_camera_target",
    "check_tuple_parm",
    "LIGHTING_LAW_INTENSITY",
    "HOUDINI_NETWORK_ROOTS",
]

# The studio "Lighting Law": UsdLux light ``intensity`` stays pinned at this
# value; brightness is dialled with ``exposure`` (stops), never raw intensity.
LIGHTING_LAW_INTENSITY: float = 1.0

# Network-context roots that mark a string as a *Houdini node path* rather than a
# *USD prim path*. A Karma/usdrender ``camera`` parm wants the prim path inside
# the stage (e.g. ``/cameras/cam1``), not a node path under one of these roots.
HOUDINI_NETWORK_ROOTS: Tuple[str, ...] = (
    "/obj",
    "/stage",
    "/out",
    "/mat",
    "/shop",
    "/ch",
    "/img",
    "/vex",
    "/tasks",
)


@dataclass(frozen=True)
class ProductionRule:
    """One durable Solaris production rule.

    ``encoding_alias`` (when set) is a key into
    :data:`synapse.core.usd_punycode.PUNYCODE_PARMS`. Resolve the live literal
    via :func:`rule_encoding` — never paste a punycode literal into this file.
    """

    id: str
    rule: str
    rationale: str
    fact: str
    encoding_alias: Optional[str] = None
    source: str = "rag/skills/houdini21-reference/common_errors.md"


@dataclass(frozen=True)
class Advisory:
    """Result of a pure advisory check. ``ok=True`` means no violation.

    Advisory by construction: callers decide what to do with a flagged result.
    Nothing here blocks, raises, or mutates.
    """

    ok: bool
    message: str
    rule_id: str


# ---------------------------------------------------------------------------
# The catalog. Ordered roughly by where they bite in a build (assets → render).
# ---------------------------------------------------------------------------
PRODUCTION_RULES: Tuple[ProductionRule, ...] = (
    ProductionRule(
        id="materiallibrary_cook_before_child",
        rule="Cook a materiallibrary LOP (cook(force=True)) before createNode "
        "for shader children.",
        rationale="The library's internal subnet does not exist until the node "
        "has cooked once; createNode returns None silently before that, so the "
        "shader is never built and the failure is invisible.",
        fact="materiallibrary.createNode(...) returns None until the node has "
        "been force-cooked at least once (common_errors Diagnostic 1).",
    ),
    ProductionRule(
        id="karma_camera_prim_path",
        rule="Set a Karma/usdrender 'camera' parm to a USD PRIM PATH "
        "(e.g. /cameras/cam1), never a Houdini node path (e.g. /obj/cam1).",
        rationale="The camera parm resolves against the USD stage scenegraph. A "
        "Houdini node path resolves to no prim, so the render has no camera and "
        "comes out black with no hard error.",
        fact="'camera' is a USD prim-path string on the stage, not a /obj node "
        "path (common_errors Diagnostic 7 + 'Common Mistakes').",
    ),
    ProductionRule(
        id="vector_color_parmtuple",
        rule="Set vector/color parms (translate 't', light 'color') via "
        "node.parmTuple(name), not node.parm(name).",
        rationale="A tuple parm name returns None from node.parm(), so the write "
        "silently misses. The color3f light parm is a parmTuple BASE whose "
        "components are name + r/g/b.",
        fact="node.parm('t') is None — 't' is a 3-tuple; use parmTuple. The "
        "light 'color' alias is a punycode tuple base (TUPLE_ALIASES) "
        "(common_errors Diagnostic 6).",
        encoding_alias="color",
    ),
    ProductionRule(
        id="lighting_law_intensity",
        rule="Keep UsdLux light 'intensity' at 1.0; drive brightness with "
        "'exposure' (stops).",
        rationale="intensity > 1.0 violates the studio Lighting Law and is the "
        "usual firefly source in Karma. Exposure scales radiant energy in stops "
        "without the firefly risk.",
        fact="Lighting Law: intensity pinned at 1.0, brightness via exposure; "
        "intensity > 1.0 produces fireflies (common_errors Diagnostic 8 + "
        "'Common Mistakes').",
        encoding_alias="intensity",
    ),
    ProductionRule(
        id="usdrender_output_agreement",
        rule="usdrender_rop output ('picture'/outputimage) must be set and agree "
        "with the render product it writes.",
        rationale="An unset or mismatched output path writes nothing, or writes "
        "to a path the pipeline never reads — both surface as an empty/black "
        "result with no error.",
        fact="The render ROP LOP type is 'usdrender_rop' (plain 'usdrender' is "
        "phantom on 21.0.671); its 'picture' parm must be set and consistent "
        "with the product (common_errors Diagnostic 7).",
    ),
    ProductionRule(
        id="karma_xpu_file_flush_delay",
        rule="After a Karma XPU render, allow for a file-flush delay before "
        "asserting the output exists — poll/retry, don't stat immediately.",
        rationale="XPU flushes the image to disk asynchronously, so an immediate "
        "existence check races the writer and reports a false 'render produced "
        "nothing'.",
        fact="Karma XPU has a post-render file-flush delay; the file appears a "
        "beat after render() returns (live-verified, 21.0.671 render notes).",
    ),
    ProductionRule(
        id="lop_sphere_radius_encoding",
        rule="Resolve a LOP sphere's 'radius' through the single-source punycode "
        "map, never the friendly name.",
        rationale="The sphere's radius surfaces under a punycode-encoded parm "
        "name; node.parm('radius') is None, so a friendly-name write silently "
        "misses — the same class of bug as the light color parm.",
        fact="LOP sphere radius is an 'inputs:'-namespaced, punycode-encoded "
        "parm. The encoding is build-specific and must come from usd_punycode, "
        "not be hardcoded here.",
        encoding_alias="radius",
    ),
)

RULES_BY_ID = {r.id: r for r in PRODUCTION_RULES}


def get_rule(rule_id: str) -> Optional[ProductionRule]:
    """Return the :class:`ProductionRule` with ``rule_id``, or ``None``."""
    return RULES_BY_ID.get(rule_id)


def rule_encoding(rule: ProductionRule) -> Optional[str]:
    """Resolve a rule's live punycode encoding via the single-source map.

    Returns the punycode literal for the rule's ``encoding_alias`` when it is in
    :data:`synapse.core.usd_punycode.PUNYCODE_PARMS`, else ``None`` — either the
    rule is not encoding-dependent, or the alias is not (yet) single-sourced
    (a visible gap, not a silent wrong literal). Never raises.
    """
    if rule.encoding_alias is None:
        return None
    return encoded(rule.encoding_alias)


# ---------------------------------------------------------------------------
# Pure advisory checks. None of these touch hou; all are referentially
# transparent over their arguments.
# ---------------------------------------------------------------------------
def check_light_intensity(intensity: float) -> Advisory:
    """Flag a UsdLux light intensity that breaks the Lighting Law.

    ``intensity <= 1.0`` is OK (no firefly risk). ``intensity > 1.0`` flags:
    brightness above the law should come from ``exposure``, not raw intensity.
    """
    rule_id = "lighting_law_intensity"
    if intensity > LIGHTING_LAW_INTENSITY:
        return Advisory(
            ok=False,
            message=(
                f"intensity={intensity} > {LIGHTING_LAW_INTENSITY} violates the "
                f"Lighting Law and risks fireflies in Karma — pin intensity at "
                f"{LIGHTING_LAW_INTENSITY} and raise brightness via 'exposure'."
            ),
            rule_id=rule_id,
        )
    return Advisory(
        ok=True,
        message=f"intensity={intensity} within the Lighting Law.",
        rule_id=rule_id,
    )


def check_camera_target(target: str) -> Advisory:
    """Flag a camera target that looks like a node path, not a USD prim path.

    A Karma/usdrender 'camera' parm wants a stage prim path (``/cameras/cam1``).
    Flags: empty, not absolute ('/'-rooted), or rooted at a Houdini network
    context (``/obj``, ``/stage``, ``/out``, ...).
    """
    rule_id = "karma_camera_prim_path"
    candidate = (target or "").strip()
    if not candidate:
        return Advisory(
            ok=False,
            message="camera target is empty — set it to a USD prim path like "
            "/cameras/cam1.",
            rule_id=rule_id,
        )
    if not candidate.startswith("/"):
        return Advisory(
            ok=False,
            message=f"camera target {candidate!r} is not an absolute prim path "
            f"— USD prim paths start with '/'.",
            rule_id=rule_id,
        )
    for root in HOUDINI_NETWORK_ROOTS:
        if candidate == root or candidate.startswith(root + "/"):
            return Advisory(
                ok=False,
                message=f"camera target {candidate!r} looks like a Houdini node "
                f"path (rooted at {root}), not a USD prim path — use the stage "
                f"prim path (e.g. /cameras/cam1).",
                rule_id=rule_id,
            )
    return Advisory(
        ok=True,
        message=f"camera target {candidate!r} looks like a USD prim path.",
        rule_id=rule_id,
    )


def check_tuple_parm(alias: str) -> Advisory:
    """Advise whether a friendly parm ``alias`` must be set via parmTuple.

    References :data:`synapse.core.usd_punycode.TUPLE_ALIASES` (the single source
    of which aliases are color3f tuple bases). ``ok=False`` here is not an error
    — it is the affirmative instruction "use node.parmTuple, not node.parm".
    """
    rule_id = "vector_color_parmtuple"
    if alias in TUPLE_ALIASES:
        return Advisory(
            ok=False,
            message=f"parm {alias!r} is a color3f tuple base — set it via "
            f"node.parmTuple, not node.parm (which returns None for a tuple).",
            rule_id=rule_id,
        )
    return Advisory(
        ok=True,
        message=f"parm {alias!r} is not a known tuple parm.",
        rule_id=rule_id,
    )
