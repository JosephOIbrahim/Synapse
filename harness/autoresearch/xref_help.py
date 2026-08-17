"""C3 — the help-cache cross-reference referee (plain Python, no ``hou``).

WHAT THIS IS
------------
Houdini writes a *parsed-help cache* under
``OneDrive\\Documents\\houdini22.0\\config\\Help\\cache\\nodes`` — one JSON per
node page that has been browsed/indexed locally. Each APEX-related page carries
exactly the shape C1 (``apex_truth``) probes for from the runtime: typed
inputs/outputs, ``since`` version, deprecation status with a successor link,
context, namespace. That makes the cache an **independent second witness** to
the same claims the runtime makes.

This module parses those cache entries into the ``apex_truth`` claim schema and
runs a **three-way diff** per node across three witnesses:

    runtime  (apex_truth artifact, consumed via the bus when WA1-TRUTH publishes)
    docs     (this help cache)
    recipes  (the type names emitted by python/synapse/panel/apex_recipes.py)

THE ONE RULE THAT MAKES THIS HONEST (encoded in code, not just prose)
--------------------------------------------------------------------
The cache is **high-precision, low-recall**: it holds only what has been
browsed locally (~18-26 APEX entries), NOT the full product surface. Therefore:

  * **Absence from the cache is NO-EVIDENCE, never product-absence.** A node the
    cache never indexed is not "undocumented" in any damning sense and is never
    a phantom on that ground alone. ``DocState.ABSENT`` means "the referee has
    nothing to say", and every verdict that could punish a node treats it that
    way.

  * **A quarantine candidate (doc-present / runtime-absent) can only be raised
    when the runtime was ACTUALLY CONSUMED.** If ``apex_truth`` has not been
    published, the runtime column renders ``UNKNOWN`` for every node and NO
    quarantine candidate is emitted — you cannot call a node "runtime-absent"
    against a runtime you never read. This is the ``RuntimeState.UNKNOWN`` path
    and it is the difference between a referee and a rumour mill.

  * **Every mismatch finding carries both anchors** — the cache file it came
    from AND the runtime artifact entry it disagreed with. A finding with only
    one side is an unanchored claim and is not emitted.

VERDICT TAXONOMY
----------------
Per (surface, node) the diff assigns exactly one verdict — zero unclassified
rows:

    confirmed          docs present AND runtime present (membership agrees)
    type-mismatch      docs present AND runtime present AND a port type differs
    undocumented       runtime present AND docs absent (a runtime surface the
                       low-recall cache never indexed — expected, informational)
    quarantine-candidate
                       docs present AND runtime KNOWN-absent — a deprecation or
                       a phantom; filed to harness/phantoms/ with both anchors
    runtime-unknown    docs present AND runtime UNKNOWN — the honest pending
                       state before apex_truth is consumed. Collapses into one
                       of the four terminal verdicts the moment the runtime
                       artifact lands. It is a classification, not a gap.

CONTEXT / NAME-SPACES (why alignment is surface-aware)
------------------------------------------------------
The three cache directories speak three different name-spaces and this module
keeps them apart so a graph-internal callback is never mistaken for a SOP type:

    nodes/apex/*.json          -> APEX graph-internal callbacks   surface=apex_callback
                                  (attrs.internal already is ns::name, e.g.
                                   rig::CurveIK)
    nodes/sop/apex--*.json     -> SOP node types                  surface=sop_type
                                  (type = attrs.namespace::attrs.internal,
                                   e.g. apex::sceneinvoke)
    nodes/lop/apexsoprigbuilder.json -> LOP node type             surface=lop_type
                                  (type = attrs.internal, e.g. apexsoprigbuilder)

The runtime catalog (apex_truth) spells node types the flat Houdini way
(``apex::invokegraph``, ``kinefx::twoboneik``) and the recipes emit the same
flat SOP spellings, so sop_type/lop_type rows align directly; apex_callback rows
align against apex_truth's callback-discovery entries when present.

Pure-Python, zero ``hou`` — runs under stock pytest. Tests drive it with fixture
cache dirs; the live cache is only read by ``main()``.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Paths / build resolution
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The live cache. Overridable via env so the CLI is not hardwired to one user's
# OneDrive (CLAUDE.md: "No hardcoded user paths"). The default is the observed
# location for this workstation; absence renders no-evidence, never a crash.
_ENV_CACHE = "SYNAPSE_APEX_HELP_CACHE"
_DEFAULT_CACHE_CANDIDATES = (
    Path(os.path.expanduser("~")) / "OneDrive" / "Documents"
    / "houdini22.0" / "config" / "Help" / "cache",
    Path(os.path.expanduser("~")) / "Documents"
    / "houdini22.0" / "config" / "Help" / "cache",
)

# Where the recipes corpus lives (read-only scan target).
_RECIPES_PATH = _REPO_ROOT / "python" / "synapse" / "panel" / "apex_recipes.py"


def default_cache_root() -> Optional[Path]:
    """Resolve the live help cache, or ``None`` if not found.

    ``None`` is a first-class answer (no-evidence), never an exception: a
    machine that has never browsed APEX help has no cache and the referee
    simply has nothing to say.
    """
    env = os.environ.get(_ENV_CACHE)
    if env:
        p = Path(env)
        return p if p.exists() else None
    for cand in _DEFAULT_CACHE_CANDIDATES:
        if cand.exists():
            return cand
    return None


_CACHE_CONFIG_RE = re.compile(r"houdini(\d+\.\d+)", re.IGNORECASE)


def cache_config_version(cache_root: Path) -> Optional[str]:
    """The Houdini config major (e.g. ``22.0``) read from the cache path.

    An observed fact about the docs source — NOT a runtime build. The patch
    level (``.400`` vs ``.368``) is unknowable from the cache alone.
    """
    m = _CACHE_CONFIG_RE.search(str(cache_root))
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# The claim schema (mirrors apex_truth: typed ports, since, status, successor)
# ---------------------------------------------------------------------------

# Houdini-canonical version folding: a base entry keeps its bare name; a ``2.0``
# entry becomes ``name::2.0`` so cache, runtime and recipes all spell the same
# string. Empty / null / "1.0" version == base.
#
# IDEMPOTENT by contract: the live cache is internally inconsistent — most v2.0
# entries carry attrs.internal WITHOUT the version (rig::Sample + version=2.0),
# but at least one carries it inline (rig::...ToArray::2.0 + version=2.0). Fold
# must not double-append, or the alignment key becomes ``name::2.0::2.0`` and can
# never match the runtime/recipe spelling. See _strip_embedded_version.
def _fold_version(name: str, version: Optional[str]) -> str:
    if version and str(version).strip() not in ("", "1.0"):
        suffix = f"::{version}"
        return name if name.endswith(suffix) else f"{name}{suffix}"
    return name


def _strip_embedded_version(name: str, version: Optional[str]) -> str:
    """Remove a trailing ``::<version>`` already baked into a name.

    Normalises the cache's inconsistent internal-name convention so every v2.0
    sibling shares one base identity; the version is re-folded into ``type_name``
    exactly once by ``_fold_version``. A no-op for the common (version-free
    internal) shape."""
    if version and str(version).strip() not in ("", "1.0"):
        suffix = f"::{version}"
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


@dataclass
class HelpClaim:
    """One APEX node's help-cache claim, in the apex_truth-compatible shape."""

    node: str                      # canonical identity (attrs.internal, ns::name for apex)
    type_name: str                 # cross-source alignment key (Houdini-canonical, version-folded)
    surface: str                   # apex_callback | sop_type | lop_type
    context: str                   # apex | sop | lop
    namespace: Optional[str]       # true namespace (callback ns for apex; attrs.namespace else)
    version: Optional[str]         # "" / "2.0" / None as recorded
    since: Optional[str]           # 'since' version string
    status: str                    # 'current' | 'deprecated'
    successor: Optional[str]       # decoded successor node (from the deprecation link)
    successor_link: Optional[str]  # raw link value/fullpath, for anchor traceability
    inputs: list[dict]             # [{'name','type'}], typed
    outputs: list[dict]            # [{'name','type'}], typed
    ports_present: bool            # did the entry carry an inputs/outputs section at all?
    summary: str
    source_file: str               # cache-root-relative path — the docs anchor

    def to_dict(self) -> dict:
        return asdict(self)


# --- filename decode (for link resolution; identity itself comes from attrs) --

def decode_help_filename(stem: str) -> tuple[Optional[str], str, Optional[str]]:
    """Decode a help-cache basename stem into (namespace, name, version).

    ``rig--CurveIK``                -> ('rig', 'CurveIK', None)
    ``rig--SampleSplineTransforms-``-> ('rig', 'SampleSplineTransforms', '')
    ``rig--SampleSplineTransforms-2.0`` -> ('rig', 'SampleSplineTransforms', '2.0')
    ``apex--sceneinvoke-``          -> ('apex', 'sceneinvoke', '')
    ``apexsoprigbuilder``           -> (None, 'apexsoprigbuilder', None)

    Used only to resolve link targets to node identities; the authoritative
    identity of a parsed entry is ``attrs.internal``.
    """
    if "--" in stem:
        namespace, rest = stem.split("--", 1)
    else:
        namespace, rest = None, stem
    version: Optional[str] = None
    # trailing -<version> or a bare trailing '-' (version "")
    m = re.search(r"-(\d+\.\d+)$", rest)
    if m:
        version = m.group(1)
        rest = rest[: m.start()]
    elif rest.endswith("-"):
        version = ""
        rest = rest[:-1]
    return namespace, rest, version


def _link_target_to_node(link_value: str) -> Optional[str]:
    """Map a help link like ``/nodes/apex/rig--SampleSplineTransforms`` to the
    node identity ``rig::SampleSplineTransforms``. Returns None if unparseable."""
    if not link_value:
        return None
    stem = link_value.rstrip("/").rsplit("/", 1)[-1]
    stem = re.sub(r"\.html?$", "", stem)
    ns, name, ver = decode_help_filename(stem)
    if ns:
        base = f"{ns}::{name}"
    else:
        base = name
    return _fold_version(base, ver)


# --- port extraction ---------------------------------------------------------

def _iter_blocks(node: Any):
    """Yield every dict block in a help body tree (depth-first)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _iter_blocks(v)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_blocks(item)


def _extract_ports(section: dict, item_type: str) -> list[dict]:
    """Pull [{'name','type'}] from an inputs_section / outputs_section block.

    A port item is ``{'type': '<item_type>', 'text': ['portname'],
    'attrs': {'type': 'Geometry'}}``. Missing type attrs -> 'unknown' (the
    honesty default; never silently 'Any')."""
    ports: list[dict] = []
    for block in _iter_blocks(section):
        if block.get("type") != item_type:
            continue
        text = block.get("text")
        name = ""
        if isinstance(text, list) and text and isinstance(text[0], str):
            name = text[0].strip()
        elif isinstance(text, str):
            name = text.strip()
        attrs = block.get("attrs") or {}
        ptype = attrs.get("type", "unknown")
        ports.append({"name": name, "type": ptype})
    return ports


def _extract_successor(body: Any) -> tuple[Optional[str], Optional[str]]:
    """Return (successor_node, raw_link) from a deprecation warning, if any.

    Looks for a link node inside a warning_group's para. The first link that
    points at ``/nodes/...`` wins."""
    for block in _iter_blocks(body):
        if block.get("type") != "link":
            continue
        val = block.get("value") or block.get("fullpath") or ""
        if "/nodes/" in val:
            node = _link_target_to_node(val)
            if node:
                return node, val
    return None, None


def parse_cache_entry(data: dict, source_file: str) -> Optional[HelpClaim]:
    """Parse one loaded help-cache JSON dict into a HelpClaim.

    Returns ``None`` for non-node pages (``attrs.type != 'node'`` — e.g. the
    ``include`` fragments ``_transform_shared.json`` / ``_wip.json``)."""
    attrs = data.get("attrs") or {}
    if attrs.get("type") != "node":
        return None

    context = attrs.get("context") or "unknown"
    internal = attrs.get("internal") or ""
    ns_attr = attrs.get("namespace")
    version = attrs.get("version")
    # Normalise the cache's inconsistent internal convention: some v2.0 entries
    # bake the version into internal (rig::X::2.0), most do not. Strip it so the
    # base identity is consistent across siblings; _fold_version re-adds it once.
    internal = _strip_embedded_version(internal, version)

    # Surface + canonical identity + alignment key, per context.
    if context == "apex":
        # internal already ns::name (e.g. rig::CurveIK); the true namespace is
        # the prefix before '::' — attrs.namespace is the useless help value
        # ("apex") for these.
        surface = "apex_callback"
        node = internal
        true_ns = internal.split("::", 1)[0] if "::" in internal else ns_attr
        type_name = _fold_version(internal, version)
    elif context == "sop":
        surface = "sop_type"
        node = f"{ns_attr}::{internal}" if ns_attr else internal
        true_ns = ns_attr
        type_name = _fold_version(node, version)
    elif context == "lop":
        surface = "lop_type"
        node = f"{ns_attr}::{internal}" if ns_attr else internal
        true_ns = ns_attr
        type_name = _fold_version(node, version)
    else:
        surface = "unknown"
        node = f"{ns_attr}::{internal}" if ns_attr else internal
        true_ns = ns_attr
        type_name = _fold_version(node, version)

    status = "deprecated" if attrs.get("status") == "deprecated" else "current"

    body = data.get("body") or []
    inputs: list[dict] = []
    outputs: list[dict] = []
    ports_present = False
    for block in body:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "inputs_section":
            ports_present = True
            inputs = _extract_ports(block, "inputs_item")
        elif block.get("type") == "outputs_section":
            ports_present = True
            outputs = _extract_ports(block, "outputs_item")

    successor, successor_link = (None, None)
    if status == "deprecated":
        successor, successor_link = _extract_successor(body)

    summary = ""
    raw_summary = data.get("summary")
    if isinstance(raw_summary, list) and raw_summary and isinstance(raw_summary[0], str):
        summary = raw_summary[0].strip()
    elif isinstance(raw_summary, str):
        summary = raw_summary.strip()

    return HelpClaim(
        node=node,
        type_name=type_name,
        surface=surface,
        context=context,
        namespace=true_ns,
        version=version,
        since=attrs.get("since"),
        status=status,
        successor=successor,
        successor_link=successor_link,
        inputs=inputs,
        outputs=outputs,
        ports_present=ports_present,
        summary=summary,
        source_file=source_file,
    )


def _apex_cache_files(cache_root: Path) -> list[Path]:
    """The APEX-related cache files, per the C3 target globs. Deterministic
    order so the artifact is stable across runs."""
    out: list[Path] = []
    apex_dir = cache_root / "nodes" / "apex"
    if apex_dir.is_dir():
        # skip include fragments (leading underscore); parse_cache_entry also
        # rejects them by attrs.type, this is just to avoid the read.
        out += [p for p in sorted(apex_dir.glob("*.json")) if not p.name.startswith("_")]
    sop_dir = cache_root / "nodes" / "sop"
    if sop_dir.is_dir():
        out += sorted(sop_dir.glob("apex--*.json"))
    lop_file = cache_root / "nodes" / "lop" / "apexsoprigbuilder.json"
    if lop_file.is_file():
        out.append(lop_file)
    return out


def parse_help_cache(cache_root: Optional[Path]) -> list[HelpClaim]:
    """Parse every APEX-related cache entry present. Missing cache / missing
    files -> empty list (no-evidence). A single malformed file is skipped, not
    fatal — a torn cache write must not blind the whole referee."""
    if cache_root is None or not cache_root.exists():
        return []
    claims: list[HelpClaim] = []
    for path in _apex_cache_files(cache_root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        rel = path.relative_to(cache_root).as_posix()
        claim = parse_cache_entry(data, rel)
        if claim is not None:
            claims.append(claim)
    return claims


# ---------------------------------------------------------------------------
# Runtime witness — the apex_truth artifact, consumed when TRUTH publishes
# ---------------------------------------------------------------------------

# Per-node runtime states.
PRESENT = "present"
ABSENT = "absent"
UNKNOWN = "unknown"


@dataclass
class RuntimeCatalog:
    """A parsed apex_truth artifact, or the honest empty 'not consumed' state.

    ``consumed=False`` means no artifact was read: every lookup returns UNKNOWN
    and no node can ever be called runtime-absent. This is the state that keeps
    the referee from inventing phantoms before WA1-TRUTH has spoken.
    """

    consumed: bool
    build: Optional[str] = None
    artifact_path: Optional[str] = None
    # surface -> { type_name: {'state', 'ports', 'entry_ref'} } — EXPLICIT records
    # (type_exists + port_signature + generic fallback). Row-worthy and bounded.
    _by_surface: dict = field(default_factory=dict)
    # Enumerated callback membership (from apex_callback_catalog:<ns>). A WITNESS
    # used only by lookup(), NEVER a row source — its 2286 names would restate the
    # DOCS low-recall gap as 2286 noise 'undocumented' rows.
    _callback_present: dict = field(default_factory=dict)   # name -> entry_ref
    _callback_complete: bool = False                        # the '*' catalog was complete
    _callback_catalog_ref: Optional[str] = None             # anchor that PROVES absence

    def lookup(self, surface: str, type_name: str) -> dict:
        """Return {'state', 'ports', 'entry_ref'} for a node.

        Not consumed -> UNKNOWN everywhere. Then, in order:
          1. an explicit record (type_exists / port_signature) wins — it carries
             ports and an exact membership verdict;
          2. apex_callback only: presence in the enumerated catalog -> PRESENT;
          3. apex_callback only: the enumeration was COMPLETE and this name is not
             in it -> ABSENT (authoritative — the callback registry is fully
             enumerated). The runtime anchor is the catalog entry that proves it;
          4. otherwise UNKNOWN — silence for a PROBED-SUBSET surface (SOP/LOP
             type_exists) is not absence."""
        if not self.consumed:
            return {"state": UNKNOWN, "ports": None, "entry_ref": None}
        rec = self._by_surface.get(surface, {}).get(type_name)
        if rec is not None:
            return rec
        if surface == "apex_callback":
            if type_name in self._callback_present:
                return {"state": PRESENT, "ports": None,
                        "entry_ref": self._callback_present[type_name]}
            if self._callback_complete:
                return {"state": ABSENT, "ports": None,
                        "entry_ref": self._callback_catalog_ref}
        return {"state": UNKNOWN, "ports": None, "entry_ref": None}

    def present_type_names(self, surface: str) -> set[str]:
        """Explicit-record PRESENT names only — bounded, row-worthy. The
        enumerated callback catalog is deliberately excluded (witness, not rows)."""
        return {t for t, rec in self._by_surface.get(surface, {}).items()
                if rec.get("state") == PRESENT}

    def callback_namespaces(self) -> set[str]:
        """Namespaces that have at least one registered callback. Lets the
        referee tell a genuine phantom from a NON-callback concept (a rig
        component / control gadget whose namespace simply is not a callback
        namespace) — the two want different human dispositions."""
        out = set()
        for name in self._callback_present:
            out.add(name.split("::", 1)[0] if "::" in name else name)
        return out


def _classify_runtime_value(value: Any) -> str:
    """Map an apex_truth entry 'value' to PRESENT/ABSENT/UNKNOWN, tolerantly.

    apex_truth is authored by WA1-TRUTH ahead of this consumer, so the exact
    value encoding is read defensively: an explicit exists flag wins; the
    string 'UNKNOWN' (constitution's unobtainable marker) maps to UNKNOWN;
    anything unrecognised is UNKNOWN, never a fabricated PRESENT."""
    if isinstance(value, str):
        v = value.strip().upper()
        if v == "UNKNOWN":
            return UNKNOWN
        if v in ("TRUE", "PRESENT", "EXISTS"):
            return PRESENT
        if v in ("FALSE", "ABSENT", "MISSING"):
            return ABSENT
        return UNKNOWN
    if isinstance(value, bool):
        return PRESENT if value else ABSENT
    if isinstance(value, dict):
        # Common shapes: {'exists': true}, {'present': false}, {'state': 'UNKNOWN'}
        for key in ("exists", "present", "found"):
            if key in value:
                iv = value[key]
                # Honesty gate: only a real bool asserts membership. None or any
                # non-bool/non-str junk (0, 42, [1,2], 0.5) renders UNKNOWN — it
                # is NEVER truthiness-coerced into PRESENT/ABSENT. A fabricated
                # membership here would flip 'consumed' and could file a phantom
                # quarantine (crucible honesty-gate finding, 2026-08-17).
                if isinstance(iv, bool):
                    return PRESENT if iv else ABSENT
                if isinstance(iv, str):
                    return _classify_runtime_value(iv)
                return UNKNOWN
        st = value.get("state") or value.get("status")
        if isinstance(st, str):
            return _classify_runtime_value(st)
        return UNKNOWN
    return UNKNOWN


_CALLBACK_NS = ("rig", "component", "controlgadget", "geo", "transform", "constraint")


def _runtime_key(claim_or_surface: str, raw_name: str) -> tuple[str, str]:
    """Infer (surface, type_name) for a runtime entry from its claim/surface
    string. Handles the documented 'nodetypes.<type>' form and callback forms.
    """
    name = raw_name
    # strip a leading 'nodetypes.' / 'nodetype.' surface prefix
    for pref in ("nodetypes.", "nodetype.", "callbacks.", "callback."):
        if name.startswith(pref):
            name = name[len(pref):]
            break
    # decide surface: a callback namespace (rig::, component::, ...) => apex_callback;
    # 'nodetypes.' or an apex::/kinefx:: flat type => sop_type; bare lop name => lop_type
    head = name.split("::", 1)[0] if "::" in name else name
    if head in _CALLBACK_NS and "callback" not in claim_or_surface.lower():
        # a bare rig::/component:: without an explicit nodetypes prefix is a callback
        surface = "apex_callback"
    elif "callback" in claim_or_surface.lower():
        surface = "apex_callback"
    elif name == "apexsoprigbuilder" or "/lop/" in claim_or_surface.lower():
        surface = "lop_type"
    else:
        surface = "sop_type"
    return surface, name


def load_runtime_catalog(artifact_path: Optional[str]) -> RuntimeCatalog:
    """Consume an apex_truth_*.json artifact into a RuntimeCatalog.

    A missing / unreadable / shape-unrecognised artifact yields the honest
    ``consumed=False`` catalog — every lookup UNKNOWN. Only an artifact that
    actually parses into node records flips ``consumed=True``."""
    if not artifact_path:
        return RuntimeCatalog(consumed=False)
    p = Path(artifact_path)
    if not p.exists():
        return RuntimeCatalog(consumed=False)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RuntimeCatalog(consumed=False)

    meta = data.get("meta") or {}
    build = meta.get("build") or meta.get("target_build")
    entries = data.get("entries")
    if not isinstance(entries, list):
        return RuntimeCatalog(consumed=False, build=build, artifact_path=str(p))

    by_surface: dict = {}
    callback_present: dict = {}
    callback_complete = False
    callback_catalog_ref: Optional[str] = None
    saw_membership = False

    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            continue
        claim = str(e.get("claim") or e.get("surface") or "")
        value = e.get("value")
        ref = f"{p.name}#entries[{i}]:{claim}"

        # --- FAMILY A: apex_callback_catalog:<ns> — enumerated callback names ---
        if (claim.startswith("apex_callback_catalog:")
                and isinstance(value, dict) and isinstance(value.get("names"), list)):
            for nm in value["names"]:
                if isinstance(nm, str):
                    callback_present.setdefault(nm, ref)
            # The '*' catalog is authoritative IFF its declared count matches the
            # names it actually carries (guards a truncated dump). Only a complete
            # enumeration licenses calling an absent callback ABSENT.
            if claim == "apex_callback_catalog:*":
                if isinstance(value.get("count"), int) and value["count"] == len(value["names"]):
                    callback_complete = True
                    callback_catalog_ref = ref
            saw_membership = True
            continue

        # --- FAMILY B: apex_port_signature:<callback> — exists + port arity ------
        if claim.startswith("apex_port_signature:") and isinstance(value, dict):
            name = claim.split(":", 1)[1]
            state = _classify_runtime_value(value)  # value carries {'exists': bool}
            by_surface.setdefault("apex_callback", {})[name] = {
                "state": state,
                "ports": {"inputs": value.get("inputs"), "outputs": value.get("outputs"),
                          "input_count": value.get("input_count"),
                          "output_count": value.get("output_count")},
                "entry_ref": ref,
            }
            if state in (PRESENT, ABSENT):
                saw_membership = True
            continue

        # --- FAMILY C: type_exists[*]:<type> — SOP/LOP node-type existence -------
        # Match the real bracketed claim only; the generic 'type_existence:' form
        # (ahead-of-producer fixtures) falls through to the tolerant fallback so
        # its namespace-based surface routing is preserved.
        if claim.startswith("type_exists[") and isinstance(value, dict) and "exists" in value:
            name = claim.split(":", 1)[1] if ":" in claim else ""
            if name:
                state = _classify_runtime_value(value)
                cats = [str(c).lower() for c in (value.get("found_in_categories") or [])]
                surface = "lop_type" if (name == "apexsoprigbuilder"
                                         or any("lop" in c for c in cats)) else "sop_type"
                by_surface.setdefault(surface, {})[name] = {
                    "state": state, "ports": None, "entry_ref": ref,
                    "deprecated": bool(value.get("deprecated")),
                }
                if state in (PRESENT, ABSENT):
                    saw_membership = True
                continue

        # --- FALLBACK: generic / tolerant shapes (ahead-of-producer fixtures) ----
        # Non-membership diagnostics (invoke/cook/hash smokes) must NEVER enter the
        # membership surface. A greedy bare-':' capture would misroute e.g.
        # 'invoke_geo_hash:apex::sceneinvoke' into sop_type and OVERWRITE a real
        # type_exists PRESENT record, silently demoting it to UNKNOWN (crucible
        # realformat-fidelity finding, 2026-08-17). Skip them explicitly, and drop
        # the bare-':' regex alternative so only an EXPLICIT membership prefix
        # (nodetypes. / type_existence: / callback:) or a name key qualifies.
        probe = str(e.get("probe") or e.get("kind") or "")
        NONMEMBERSHIP_PREFIXES = ("invoke_geo_hash:", "chain_hash:", "invoke_", "cook_", "hash:")
        NONMEMBERSHIP_PROBES = ("chain_hash", "invoke", "cook")
        if claim.startswith(NONMEMBERSHIP_PREFIXES) or probe in NONMEMBERSHIP_PROBES:
            continue
        raw_name = ""
        for key in ("type", "nodetype", "name", "target"):
            if isinstance(e.get(key), str):
                raw_name = e[key]
                break
        if not raw_name:
            m = re.search(r"(?:nodetypes?\.|type_existence[:=]|callback[:=])\s*"
                          r"([A-Za-z0-9_]+(?:::[A-Za-z0-9_.]+)*)", claim)
            if m:
                raw_name = m.group(1)
        if not raw_name:
            continue
        surface, type_name = _runtime_key(claim, raw_name)
        state = _classify_runtime_value(value)
        ports = None
        if isinstance(value, dict):
            for pk in ("ports", "signature", "inputs_outputs"):
                if isinstance(value.get(pk), (dict, list)):
                    ports = value[pk]
                    break
            if ports is None and ("inputs" in value or "outputs" in value):
                ports = {"inputs": value.get("inputs"), "outputs": value.get("outputs")}
        by_surface.setdefault(surface, {})[type_name] = {
            "state": state, "ports": ports, "entry_ref": ref}
        if state in (PRESENT, ABSENT):
            saw_membership = True

    # 'consumed' requires at least one real membership record; a file with only
    # unparseable entries is treated as not-consumed (honest UNKNOWN) rather
    # than a spuriously authoritative empty catalog.
    return RuntimeCatalog(
        consumed=saw_membership,
        build=build,
        artifact_path=str(p),
        _by_surface=by_surface,
        _callback_present=callback_present,
        _callback_complete=callback_complete,
        _callback_catalog_ref=callback_catalog_ref,
    )


def find_latest_apex_truth(runs_dir: Optional[Path] = None) -> Optional[Path]:
    """Newest apex_truth_*.json under autoresearch/runs, or None.

    A convenience for the CLI. The bus is the primary handoff (a peer posts the
    exact path); this is the on-disk fallback."""
    base = runs_dir or (_REPO_ROOT / "harness" / "autoresearch" / "runs")
    if not base.exists():
        return None
    candidates = sorted(base.glob("*/apex_truth_*.json"))
    return candidates[-1] if candidates else None


# ---------------------------------------------------------------------------
# Recipes witness — read-only AST scan of apex_recipes.py (one writer per
# surface: XREF flags, WA1-RECIPE fixes)
# ---------------------------------------------------------------------------

@dataclass
class RecipeName:
    type_name: str        # emitted node type, e.g. 'apex::buildfkgraph'
    recipe: Optional[str] # containing recipe key, if resolvable
    lineno: int           # 1-based line in apex_recipes.py — the recipes anchor
    surface: str = "sop_type"  # recipe node types are SOP-creatable


def scan_recipe_names(recipes_path: Optional[Path] = None) -> list[RecipeName]:
    """Extract every emitted node-type name from apex_recipes.py, read-only.

    AST-based (never imports the module — no design-system side effects, and it
    yields exact line anchors). Every ``{'type': '<str>'}`` inside the recipe
    node lists is captured; those dicts are the only place a bare ``type`` key
    appears in that module."""
    path = recipes_path or _RECIPES_PATH
    if path is None or not Path(path).exists():
        return []
    src = Path(path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    # Map lineno ranges -> recipe key, by finding the APEX_RECIPES dict.
    recipe_spans: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "APEX_RECIPES" and isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            start = getattr(v, "lineno", k.lineno)
                            end = getattr(v, "end_lineno", start)
                            recipe_spans.append((start, end, k.value))

    def _recipe_for(lineno: int) -> Optional[str]:
        for start, end, key in recipe_spans:
            if start <= lineno <= end:
                return key
        return None

    out: list[RecipeName] = []
    seen: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if (isinstance(k, ast.Constant) and k.value == "type"
                    and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                key = (v.value, v.lineno)
                if key in seen:
                    continue
                seen.add(key)
                out.append(RecipeName(
                    type_name=v.value,
                    recipe=_recipe_for(v.lineno),
                    lineno=v.lineno,
                ))
    out.sort(key=lambda r: (r.type_name, r.lineno))
    return out


# ---------------------------------------------------------------------------
# The three-way diff
# ---------------------------------------------------------------------------

# Verdicts
V_CONFIRMED = "confirmed"
V_UNDOCUMENTED = "undocumented"
V_QUARANTINE = "quarantine-candidate"
V_TYPE_MISMATCH = "type-mismatch"
V_RUNTIME_UNKNOWN = "runtime-unknown"

_ALL_VERDICTS = (V_CONFIRMED, V_UNDOCUMENTED, V_QUARANTINE, V_TYPE_MISMATCH, V_RUNTIME_UNKNOWN)


@dataclass
class XrefRow:
    surface: str
    type_name: str
    verdict: str
    docs: str        # 'present' | 'absent'
    runtime: str     # PRESENT | ABSENT | UNKNOWN
    recipes: str     # 'present' | 'absent'
    # anchors
    docs_anchor: Optional[str] = None      # cache file
    runtime_anchor: Optional[str] = None   # apex_truth entry ref
    recipes_anchors: list[str] = field(default_factory=list)  # file:line list
    # detail
    status: Optional[str] = None           # deprecated | current (docs)
    successor: Optional[str] = None
    since: Optional[str] = None
    port_mismatches: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _runtime_ports_map(ports: Any) -> dict[str, str]:
    """Normalise a runtime ports blob to {name: type}, best-effort.

    Skips ports whose name OR type is null/None — WA1-TRUTH's apex_port_signature
    exposes port ARITY but null names/types (even for non-hidden callbacks), so a
    null must never seed a typed comparison. An empty map => no type-mismatch is
    measurable, which is the honest outcome, not a false 'confirmed'."""
    def _add(out, name, typ):
        if name in (None, "") or typ in (None, ""):
            return
        out[str(name)] = str(typ)

    out: dict[str, str] = {}
    if isinstance(ports, dict):
        if "inputs" in ports or "outputs" in ports:
            for side in ("inputs", "outputs"):
                for item in (ports.get(side) or []):
                    if isinstance(item, dict):
                        _add(out, item.get("name"), item.get("type"))
        else:
            for k, v in ports.items():
                if k in ("input_count", "output_count"):
                    continue
                _add(out, k, v if not isinstance(v, dict) else v.get("type"))
    elif isinstance(ports, list):
        for item in ports:
            if isinstance(item, dict):
                _add(out, item.get("name"), item.get("type"))
    return out


def _compare_ports(doc_claim: HelpClaim, runtime_ports: Any) -> list[dict]:
    """Return per-port mismatches where BOTH sides name a type. Ports present
    on only one side are NOT mismatches (low-recall / partial-signature
    discipline)."""
    rt = _runtime_ports_map(runtime_ports)
    if not rt:
        return []
    mismatches: list[dict] = []
    for side, ports in (("input", doc_claim.inputs), ("output", doc_claim.outputs)):
        for p in ports:
            pname, ptype = p.get("name"), p.get("type")
            if pname in rt and rt[pname] != ptype and ptype != "unknown" and rt[pname] != "unknown":
                mismatches.append({
                    "port": pname, "side": side,
                    "docs_type": ptype, "runtime_type": rt[pname],
                })
    return mismatches


def three_way_diff(
    help_claims: list[HelpClaim],
    runtime: RuntimeCatalog,
    recipe_names: list[RecipeName],
) -> list[XrefRow]:
    """Produce one XrefRow per (surface, node) across all three witnesses.

    The node universe is the union of: every cache claim, every runtime PRESENT
    member, and every recipe name. Absence from a witness is recorded as
    'absent' for docs/recipes and via the runtime lookup for runtime (which is
    UNKNOWN unless the catalog was consumed)."""
    # index docs by (surface, type_name)
    docs_index: dict[tuple[str, str], HelpClaim] = {}
    for c in help_claims:
        docs_index[(c.surface, c.type_name)] = c
    # index recipes by (surface, type_name) -> list of anchors
    recipes_index: dict[tuple[str, str], list[RecipeName]] = {}
    for r in recipe_names:
        recipes_index.setdefault((r.surface, r.type_name), []).append(r)

    # universe of keys
    keys: set[tuple[str, str]] = set(docs_index) | set(recipes_index)
    if runtime.consumed:
        for surface in ("sop_type", "lop_type", "apex_callback"):
            for tname in runtime.present_type_names(surface):
                keys.add((surface, tname))

    rows: list[XrefRow] = []
    for surface, tname in sorted(keys):
        doc = docs_index.get((surface, tname))
        recs = recipes_index.get((surface, tname), [])
        rt = runtime.lookup(surface, tname)
        rt_state = rt["state"]

        docs_state = "present" if doc is not None else "absent"
        recipes_state = "present" if recs else "absent"

        port_mismatches: list[dict] = []
        notes: list[str] = []

        # ---- verdict decision (honest, runtime-gated) --------------------
        if doc is not None:
            if rt_state == PRESENT:
                port_mismatches = _compare_ports(doc, rt.get("ports"))
                verdict = V_TYPE_MISMATCH if port_mismatches else V_CONFIRMED
            elif rt_state == ABSENT:
                verdict = V_QUARANTINE
                if doc.status == "deprecated":
                    notes.append(
                        "docs mark this DEPRECATED; runtime-absent is consistent "
                        "with removal — successor: %s" % (doc.successor or "none"))
                else:
                    notes.append(
                        "docs present but runtime KNOWN-absent — phantom or "
                        "removed; not marked deprecated in docs")
                # Distinguish a genuine phantom from a NON-callback concept: if the
                # node's namespace has zero registered callbacks, the help page is
                # likely a rig-component / control-gadget concept mis-filed under
                # the callback dir, NOT a phantom. Human adjudicates; never a delete.
                if surface == "apex_callback" and doc.namespace:
                    cb_ns = runtime.callback_namespaces()
                    if cb_ns and doc.namespace not in cb_ns:
                        notes.append(
                            "namespace '%s' has NO registered callbacks in the "
                            "runtime registry — likely a non-callback concept "
                            "(rig component / control gadget), not necessarily a "
                            "phantom; disposition is the human's" % doc.namespace)
            else:  # UNKNOWN
                verdict = V_RUNTIME_UNKNOWN
                if not runtime.consumed:
                    notes.append(
                        "runtime column UNKNOWN — apex_truth not consumed; "
                        "cannot confirm or quarantine (low-recall referee, "
                        "no-evidence != absence)")
                else:
                    notes.append(
                        "runtime catalog consumed but this node was not probed "
                        "/ recorded UNKNOWN — pending")
        else:
            # docs absent (no-evidence from the low-recall cache)
            if rt_state == PRESENT:
                verdict = V_UNDOCUMENTED
                notes.append(
                    "runtime-present, docs-absent — a surface the low-recall "
                    "cache never indexed (expected; informational, not a fault)")
            elif rt_state == ABSENT:
                # recipes-present + runtime-absent = a recipes phantom (RECIPE's
                # to fix); still classified, and surfaced as a finding, but NOT
                # a harness/phantoms doc-vs-runtime filing.
                verdict = V_QUARANTINE
                notes.append(
                    "recipes emit this name but runtime KNOWN-absent and docs "
                    "have no entry — recipes-side phantom candidate for "
                    "WA1-RECIPE (not a doc-vs-runtime quarantine)")
            else:
                verdict = V_RUNTIME_UNKNOWN
                notes.append(
                    "recipes-emitted name, no docs entry, runtime UNKNOWN — "
                    "cannot adjudicate until apex_truth is consumed")

        rows.append(XrefRow(
            surface=surface,
            type_name=tname,
            verdict=verdict,
            docs=docs_state,
            runtime=rt_state,
            recipes=recipes_state,
            docs_anchor=(doc.source_file if doc else None),
            runtime_anchor=rt.get("entry_ref"),
            recipes_anchors=[f"python/synapse/panel/apex_recipes.py:{r.lineno}" for r in recs],
            status=(doc.status if doc else None),
            successor=(doc.successor if doc else None),
            since=(doc.since if doc else None),
            port_mismatches=port_mismatches,
            notes=notes,
        ))
    return rows


# ---------------------------------------------------------------------------
# Quarantine candidates (doc-present / runtime-absent) — for harness/phantoms/
# ---------------------------------------------------------------------------

def quarantine_candidates(rows: list[XrefRow]) -> list[dict]:
    """The doc-present / runtime-KNOWN-absent rows — the acceptance-#3 set.

    Each carries BOTH anchors (cache file + runtime artifact entry). A row whose
    runtime is UNKNOWN is NOT here — you cannot quarantine against a runtime you
    never read. Recipes-side phantoms (docs absent) are excluded too; those go
    to WA1-RECIPE as findings, keeping one writer per surface."""
    out = []
    for r in rows:
        if r.verdict == V_QUARANTINE and r.docs == "present" and r.runtime == ABSENT:
            # Both anchors required, enforced in code (not merely by observation):
            # a finding missing the cache file OR the runtime entry is unanchored
            # and is not filed (crucible anchor-completeness hardening, 2026-08-17).
            if not (r.docs_anchor and r.runtime_anchor):
                continue
            out.append({
                "symbol": r.type_name,
                "surface": r.surface,
                "docs_anchor": r.docs_anchor,
                "runtime_anchor": r.runtime_anchor,
                "status": r.status,
                "successor": r.successor,
                "deprecated": r.status == "deprecated",
                "notes": r.notes,
            })
    return out


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_report(
    rows: list[XrefRow],
    help_claims: list[HelpClaim],
    runtime: RuntimeCatalog,
    recipe_names: list[RecipeName],
    cache_root: Optional[Path],
    timestamp: Optional[str] = None,
) -> dict:
    """The machine artifact: meta + per-node three-way rows + summary."""
    counts = {v: 0 for v in _ALL_VERDICTS}
    for r in rows:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1

    build = runtime.build if runtime.consumed else "UNKNOWN"
    cfg = cache_config_version(cache_root) if cache_root else None

    # Did the runtime expose any TYPED port? WA1-TRUTH's apex_port_signature gives
    # arity but null names/types, so type-mismatch is honestly unmeasurable — say
    # so rather than let a zero read as 'all ports agree'.
    port_types_measurable = False
    for surf_recs in runtime._by_surface.values():
        for rec in surf_recs.values():
            if _runtime_ports_map(rec.get("ports")):
                port_types_measurable = True
                break
        if port_types_measurable:
            break

    return {
        "meta": {
            "artifact": "apex_help_xref",
            "leg": "WA1-XREF",
            "schema_version": "1.0.0",
            "generated": timestamp or _utc_now(),
            "runtime_build": build,
            "runtime_consumed": runtime.consumed,
            "runtime_artifact": runtime.artifact_path,
            "runtime_callback_catalog_size": len(runtime._callback_present),
            "runtime_callback_catalog_complete": runtime._callback_complete,
            "runtime_port_types_measurable": port_types_measurable,
            "cache_root": str(cache_root) if cache_root else None,
            "cache_config_version": cfg,
            "cache_entries_parsed": len(help_claims),
            "recipe_names_scanned": len(recipe_names),
            "referee_caveat": (
                "The help cache is HIGH-PRECISION, LOW-RECALL: it holds only "
                "locally-browsed pages, not the full product surface. Absence "
                "from the cache is NO-EVIDENCE, never product-absence. A "
                "quarantine candidate is emitted ONLY when the runtime was "
                "actually consumed (runtime_consumed=true); otherwise the "
                "runtime column is UNKNOWN and no node is called absent."
            ),
            "verdict_legend": {
                V_CONFIRMED: "docs+runtime agree (membership)",
                V_TYPE_MISMATCH: "docs+runtime present but a port type differs",
                V_UNDOCUMENTED: "runtime present, docs absent (low-recall gap)",
                V_QUARANTINE: "docs present, runtime KNOWN-absent (deprecation/phantom)",
                V_RUNTIME_UNKNOWN: "docs present, runtime UNKNOWN (apex_truth not yet consumed)",
            },
        },
        "summary": {
            "rows_total": len(rows),
            "verdict_counts": counts,
            "unclassified": sum(1 for r in rows if r.verdict not in _ALL_VERDICTS),
            "quarantine_candidates": len(quarantine_candidates(rows)),
            "deprecated_in_docs": sum(1 for c in help_claims if c.status == "deprecated"),
        },
        "docs_claims": [c.to_dict() for c in help_claims],
        "rows": [r.to_dict() for r in rows],
        "quarantine_candidates": quarantine_candidates(rows),
    }


def render_markdown(report: dict) -> str:
    """Human-readable report. ADHD-friendly: scannable, honest, anchored."""
    m = report["meta"]
    s = report["summary"]
    L: list[str] = []
    L.append("# APEX help-cache cross-reference — WA1-XREF (C3 referee)")
    L.append("")
    L.append(f"*Generated {m['generated']}*")
    L.append("")
    L.append("## Runtime witness")
    if m["runtime_consumed"]:
        L.append(f"- **Consumed:** yes — build `{m['runtime_build']}`")
        L.append(f"- Artifact: `{m['runtime_artifact']}`")
    else:
        L.append("- **Consumed:** NO — `apex_truth` not published/consumed at run time.")
        L.append("- The runtime column renders **UNKNOWN** for every node. No")
        L.append("  quarantine candidate can be raised against an unread runtime.")
    L.append("")
    L.append("## Referee caveat (low-recall, encoded in the verdicts)")
    L.append(f"> {m['referee_caveat']}")
    L.append("")
    L.append("## Sources")
    L.append(f"- Docs cache: `{m['cache_root']}` (config {m['cache_config_version']})")
    L.append(f"- Cache entries parsed: **{m['cache_entries_parsed']}**")
    L.append(f"- Recipe names scanned: **{m['recipe_names_scanned']}**")
    L.append("")
    L.append("## Verdict tally")
    L.append("")
    L.append("| verdict | count | meaning |")
    L.append("|---|---|---|")
    for v in _ALL_VERDICTS:
        L.append(f"| `{v}` | {s['verdict_counts'].get(v,0)} | {m['verdict_legend'][v]} |")
    L.append(f"| **unclassified** | **{s['unclassified']}** | must be 0 |")
    L.append("")
    L.append(f"- Deprecated in docs: **{s['deprecated_in_docs']}**")
    L.append(f"- Quarantine candidates (doc-present / runtime-absent): "
             f"**{s['quarantine_candidates']}**")
    L.append("")
    L.append("## Per-node rows")
    L.append("")
    L.append("| surface | node | verdict | docs | runtime | recipes | docs anchor | runtime anchor |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in report["rows"]:
        L.append(
            f"| {r['surface']} | `{r['type_name']}` | `{r['verdict']}` | "
            f"{r['docs']} | {r['runtime']} | {r['recipes']} | "
            f"{r['docs_anchor'] or '—'} | {r['runtime_anchor'] or '—'} |"
        )
    L.append("")
    if report["quarantine_candidates"]:
        L.append("## Quarantine candidates (both anchors required)")
        L.append("")
        for q in report["quarantine_candidates"]:
            L.append(f"- `{q['symbol']}` ({q['surface']}) — "
                     f"docs=`{q['docs_anchor']}` runtime=`{q['runtime_anchor']}` "
                     f"deprecated={q['deprecated']} successor={q['successor']}")
        L.append("")
    else:
        L.append("## Quarantine candidates")
        L.append("")
        if m["runtime_consumed"]:
            L.append("_None: no doc-present node was runtime-absent._")
        else:
            L.append("_None adjudicable: runtime UNKNOWN (apex_truth not consumed). "
                     "This is no-evidence, not a clean bill._")
        L.append("")
    # deprecated surface (always useful, runtime-independent)
    deps = [c for c in report["docs_claims"] if c["status"] == "deprecated"]
    if deps:
        L.append("## Deprecations recorded in docs (runtime-independent)")
        L.append("")
        for c in deps:
            L.append(f"- `{c['node']}` → successor `{c['successor']}` "
                     f"(since {c['since']}, `{c['source_file']}`)")
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_xref(
    cache_root: Optional[Path],
    runtime_artifact: Optional[str],
    recipes_path: Optional[Path] = None,
    timestamp: Optional[str] = None,
) -> dict:
    """End-to-end: parse cache, consume runtime (if any), scan recipes, diff."""
    help_claims = parse_help_cache(cache_root)
    runtime = load_runtime_catalog(runtime_artifact)
    recipe_names = scan_recipe_names(recipes_path)
    rows = three_way_diff(help_claims, runtime, recipe_names)
    return build_report(rows, help_claims, runtime, recipe_names, cache_root, timestamp)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("apex_help_xref_%Y%m%d_%H%M%S")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="C3 help-cache cross-reference referee")
    ap.add_argument("--cache", help="help cache root (default: resolve OneDrive)")
    ap.add_argument("--runtime", help="apex_truth artifact path (default: newest on disk / none)")
    ap.add_argument("--out", help="output run dir (default: autoresearch/runs/<stamp>)")
    ap.add_argument("--no-auto-runtime", action="store_true",
                    help="do NOT auto-discover apex_truth on disk (bus-only handoff)")
    args = ap.parse_args(argv)

    cache_root = Path(args.cache) if args.cache else default_cache_root()
    runtime_artifact = args.runtime
    if not runtime_artifact and not args.no_auto_runtime:
        found = find_latest_apex_truth()
        runtime_artifact = str(found) if found else None

    report = run_xref(cache_root, runtime_artifact)
    build = report["meta"]["runtime_build"]

    stamp_dir = Path(args.out) if args.out else (
        _REPO_ROOT / "harness" / "autoresearch" / "runs" / _stamp())
    stamp_dir.mkdir(parents=True, exist_ok=True)
    art_path = stamp_dir / f"apex_help_xref_{build}.json"
    rep_path = stamp_dir / f"apex_help_xref_{build}.md"
    art_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    rep_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({
        "artifact": str(art_path),
        "report": str(rep_path),
        "runtime_consumed": report["meta"]["runtime_consumed"],
        "rows": report["summary"]["rows_total"],
        "verdict_counts": report["summary"]["verdict_counts"],
        "quarantine_candidates": report["summary"]["quarantine_candidates"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
