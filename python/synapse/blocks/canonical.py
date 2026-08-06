"""BLOCKS canonicalizer -- the ONE source of truth for c3 canonicalization.

Lifted here from ``harness/autoresearch/probes.py`` (commit 1e13629f) so the
product reconciler and the evidence harness cannot drift apart. probes.py now
imports these names rather than defining them; there is exactly one filter
list in the tree and ``tests/test_blocks_reconciler.py`` pins that fact.

Why it matters: a fixture's committed baseline sha256 is only meaningful
against a named canonicalizer. Two copies of the filter list = two silently
different oracles, and the first divergence would read as a reconciler bug.

Pure Python. No ``hou``, no ``pxr``, no I/O. ``houdini_env_map`` takes the
expander as a CALLABLE argument precisely so this module never imports ``hou``.

Canonicalization rules (version c3)
-----------------------------------
1. ``strip_comment_lines``           -- leading '#': headers and tool chatter
2. ``strip_iso_timestamp_lines``     -- session metadata
3. ``strip_anon_identifier_lines``   -- per-process anonymous layer handles
4. ``strip_houdini_node_provenance`` -- HoudiniCreatorNode / HoudiniEditorNodes /
   HoudiniPrimEditorNodes customData: session node IDs, same class as anon:
5. ``normalize_houdini_env_paths``   -- environment-derived absolute paths are
   rewritten back to their variable token (c3; see below)

A change to any rule is a RE-BASELINE EVENT for every fixture in the tree.
Bump ``CANONICALIZER_VERSION`` in the same commit.

Rule 5 -- the c3 rule (R-M5-1, ruled 2026-08-06)
------------------------------------------------
The principle, which is why this rule is not written to one symptom: **$HIP is
ENVIRONMENT, not scene content.** It is the same category as the session node
IDs rule 4 strips and the ``anon:`` handles rule 3 strips -- this is the third
instance of that class. Any authored path that resolves through a Houdini
environment variable is session-local, and a stage differing ONLY in such a
path is the same stage.

What the composed text actually contains (VERIFIED-RUNTIME 2026-08-06, build
22.0.368, ``harness/notes/_m5b_envpath_probe.py``): the variables are ALREADY
EXPANDED. ``karmarendersettings.picture`` is authored as
``$HIP/render/$HIPNAME.$OS.$F4.exr`` but reaches the flattened stage as 240
time-sampled absolute paths, plus ``HoudiniSavePath`` and a ``savepath=`` query
argument embedded MID-LINE. Zero lines contain a literal ``$``. So the rule
cannot match on the token -- it has to recognise the expansion, which means it
needs the environment to compare against. Hence the ``env`` argument.

**Substitution, not line-stripping**, and the evidence forced it: 242 of 643
composed lines carry the $HIP expansion. Dropping them would blind the oracle
to whether render products are authored at all, and could not touch the
mid-line ``savepath=`` case regardless. Rewriting the expansion back to
``$HIP`` leaves every other byte of the line intact, so a fixture that changes
its output filename still changes the hash. The oracle stays sharp; only the
machine-local prefix leaves.

**Only ABSOLUTE-PATH-valued variables are substituted**, enforced by
``_is_env_path_value``. This is a safety property, not an optimisation:
``$HIPNAME`` expands to the bare word ``untitled`` (240 hits in the composed
text) and ``$OS`` expands to the NODE NAME (``render_settings``). Substituting
those by value would rewrite genuine scene content -- a prim legitimately named
``untitled``, or every occurrence of a node's own name -- and destroy exactly
what the hash exists to protect. They are also not machine-local: an unsaved
scene is ``untitled`` on every host, and $OS is fixture-declared. The guard
makes the dangerous case structurally impossible rather than trusting callers.

Fails when: the same fixture is built under two different $HIP values and the
composed hashes differ anyway -- that is invariant F-6 in
``harness/blocks/invariants_m5.py``, paired with control C-6 which shows the
same two builds DO differ under c2 (which is finding M5-F1).
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Mapping, Optional, Tuple

CANONICALIZER_VERSION = "c3"

_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
# c2 (evidence-driven, run solaris_basic_20260805_181026): Houdini embeds
# session node IDs as provenance customData (HoudiniCreatorNode,
# HoudiniEditorNodes, HoudiniPrimEditorNodes). Session state, never scene
# content -- same class as anon:.
_HOUDINI_PROV_RE = re.compile(r"\bHoudini\w*Nodes?\s*=")

C1_RULES = (
    "strip_comment_lines",
    "strip_iso_timestamp_lines",
    "strip_anon_identifier_lines",
    "strip_houdini_node_provenance",
    "normalize_houdini_env_paths",
)

# The session-local environment class (R-M5-1). The ruling named $HIP, $HIPNAME,
# $JOB, $OS, $TEMP; $HFS and $HOUDINI_TEMP_DIR are the same category and are
# included for the same reason -- $HFS is the Houdini INSTALL directory, so a
# fixture referencing an HFS asset would otherwise hash differently on 22.0.368
# and 22.0.397 of the same major. Membership in this tuple is not sufficient for
# substitution: the value must also pass _is_env_path_value.
ENV_VARS: Tuple[str, ...] = (
    "$HIP",
    "$HIPNAME",
    "$JOB",
    "$OS",
    "$TEMP",
    "$HFS",
    "$HOUDINI_TEMP_DIR",
)

# A value shorter than this is never treated as a path prefix. Substituting a
# 1-3 character value would shred the document.
_MIN_ENV_PATH_LEN = 4

# Absolute path, the only shape safe to substitute by value: a drive letter
# (C:/... or C:\...), a POSIX root, or a UNC share.
_ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")

__all__ = [
    "C1_RULES",
    "CANONICALIZER_VERSION",
    "ENV_VARS",
    "canonicalize_usda",
    "houdini_env_map",
]


def _is_env_path_value(value: object) -> bool:
    """Is this expansion safe to rewrite by value?

    Fails when: the expansion is a bare word rather than an absolute path --
    ``$HIPNAME`` -> ``untitled``, ``$OS`` -> ``render_settings``. Those are the
    cases that would corrupt scene content, so the guard is what keeps rule 5
    from being more dangerous than the drift it fixes.
    """
    if not isinstance(value, str):
        return False
    v = value.strip()
    if len(v) < _MIN_ENV_PATH_LEN:
        return False
    return bool(_ABS_PATH_RE.match(v))


def _env_substitutions(env: Mapping[str, str]) -> List[Tuple[str, str]]:
    """``[(needle, token), ...]`` in a DETERMINISTIC application order.

    Order is pinned because it is observable: VERIFIED-RUNTIME 22.0.368,
    ``$JOB`` and ``$HIP`` expand to the SAME directory, so whichever is applied
    first is the token that appears in the canonical text. Sorting by
    ``(-len(value), name)`` makes that choice stable across processes and also
    guarantees a longer path is consumed before any shorter path that prefixes
    it (``C:/a/b`` before ``C:/a``), which is the only order that is correct.

    Both slash orientations are emitted: ``$TEMP`` expands with backslashes on
    Windows while the USD text is written with forward slashes.
    """
    subs: List[Tuple[str, str]] = []
    names = [n for n in env if _is_env_path_value(env.get(n))]
    names.sort(key=lambda n: (-len(str(env[n]).strip()), n))
    for name in names:
        value = str(env[name]).strip()
        token = name if name.startswith("$") else "$" + name
        seen: List[str] = []
        for variant in (value, value.replace("\\", "/"), value.replace("/", "\\")):
            if variant and variant not in seen:
                seen.append(variant)
                subs.append((variant, token))
    return subs


def houdini_env_map(
    expand: Callable[[str], str],
    names: Optional[Tuple[str, ...]] = None,
) -> Dict[str, str]:
    """Build the c3 environment map from a caller-supplied expander.

    ``expand`` is normally ``hou.text.expandString``. It is passed IN rather
    than imported so this module stays ``hou``-free and importable from pytest,
    the MCP process and plain-python tooling.

    Only entries that pass ``_is_env_path_value`` are kept, so the returned map
    can never carry a bare-word expansion into ``canonicalize_usda``.

    Fails when: a variable is undefined in this session -- the expander raises
    or returns something non-path, and the variable is simply absent from the
    map rather than poisoning it.
    """
    out: Dict[str, str] = {}
    for name in (names if names is not None else ENV_VARS):
        try:
            value = expand(name)
        except Exception:       # noqa: BLE001 - an unset variable is not an error
            continue
        if _is_env_path_value(value):
            out[name] = str(value).strip()
    return out


def canonicalize_usda(text: str, env: Optional[Mapping[str, str]] = None) -> str:
    """c3 canonicalization -- see ``C1_RULES``.

    Trailing whitespace stripped, LF-joined, single trailing newline.
    Deterministic scene content in, deterministic bytes out.

    Args:
        text: A flattened USD stage exported with ``ExportToString()``.
        env:  ``{"$HIP": "C:/...", ...}`` -- normally ``houdini_env_map(
              hou.text.expandString)``. Anything that is not an absolute path
              is ignored.

              **A baseline producer MUST pass this.** With ``env`` omitted the
              first four rules still apply but rule 5 has nothing to match, so
              the result is a c2-shaped hash wearing a c3 label -- machine-local
              and portable-looking, which is the worst of both. Pinned by
              ``tests/test_blocks_reconciler.py::
              test_every_baseline_producer_passes_env``.

    Returns:
        The canonical text whose sha256 is the fixture baseline.
    """
    subs = _env_substitutions(env or {})
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        if _TS_RE.search(line):
            continue
        if "anon:" in line:
            continue
        if _HOUDINI_PROV_RE.search(line):
            continue
        line = line.rstrip()
        for needle, token in subs:
            if needle in line:
                line = line.replace(needle, token)
        keep.append(line)
    return "\n".join(keep) + "\n"
