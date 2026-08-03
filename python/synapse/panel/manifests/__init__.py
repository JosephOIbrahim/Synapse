"""Layout manifests — the data that drives SynapsePanel's region composition.

A manifest is a plain dict. Nothing in this package imports Qt — it must load
headless so tests and tooling can validate layouts without PySide:

    {
      "profile": "expert",                   # registry key
      "defaults": {                          # folded into every region + widget
          "visible": True, "collapsed": False,
          "stretch": 0, "prominence": "standard",
      },
      "system_prompt_overlay": "",           # appended to the built system prompt
      "regions": [                           # ordered — real root-layout order
          {"id": "rail", "widgets": ["mark", ...]},
          {"id": "faces", "stretch": 1, "widgets": ["faces_stack"]},
      ],
    }

A ``widgets`` entry is either a bare id string (all defaults) or a dict
``{"id": ..., "visible": ..., "collapsed": ..., "stretch": ..., "prominence": ...}``
overriding any subset. ``prominence`` (quiet / standard / hero) is styling
metadata the compositor stamps onto the widget as a Qt dynamic property so QSS
can key on it.

Law L5 (pays out at your pace): the three profiles differ in prominence and
system-prompt overlay ONLY — identical capability in every profile; ``expert``
is the v5.42.0 wiring exactly.
"""

import copy
import logging

from .curious import MANIFEST as _CURIOUS
from .expert import MANIFEST as _EXPERT
from .ml import MANIFEST as _ML

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = "expert"

PROMINENCE_LEVELS = ("quiet", "standard", "hero")

# The per-region / per-widget knobs and their required types. ``stretch`` must
# exclude bool explicitly — bool is an int subclass.
SPEC_KEYS = {
    "visible": bool,
    "collapsed": bool,
    "stretch": int,
    "prominence": str,
}

MANIFESTS = {
    "curious": _CURIOUS,
    "expert": _EXPERT,
    "ml": _ML,
}


class ManifestError(ValueError):
    """A manifest failed schema validation. Carries every problem at once."""

    def __init__(self, profile, problems):
        self.profile = profile
        self.problems = list(problems)
        super().__init__(
            "manifest %r invalid: %s" % (profile, "; ".join(self.problems))
        )


def _check_spec_keys(owner, entry, problems, skip=()):
    """Type-check the spec knobs present on one dict (defaults / region /
    widget entry). Keys in ``skip`` belong to the container shape, not the
    spec, and are validated by the caller."""
    for key, value in entry.items():
        if key in skip:
            continue
        expected = SPEC_KEYS.get(key)
        if expected is None:
            problems.append("%s: unknown key %r" % (owner, key))
        elif expected is int and isinstance(value, bool):
            problems.append("%s: %r must be int, got bool" % (owner, key))
        elif not isinstance(value, expected):
            problems.append(
                "%s: %r must be %s" % (owner, key, expected.__name__)
            )
        elif key == "prominence" and value not in PROMINENCE_LEVELS:
            problems.append(
                "%s: prominence %r not in %s"
                % (owner, value, PROMINENCE_LEVELS)
            )
        elif key == "stretch" and value < 0:
            problems.append("%s: stretch must be >= 0" % owner)


def validate_manifest(manifest):
    """Schema check. Returns a list of problem strings — empty means valid.

    Unknown widget/region *ids* are NOT validation errors: they validate fine
    here and are skip-logged at resolve time (the compositor owns the
    vocabulary; a vocabulary drift must never crash the panel)."""
    if not isinstance(manifest, dict):
        return ["manifest must be a dict, got %s" % type(manifest).__name__]
    problems = []
    profile = manifest.get("profile")
    if not isinstance(profile, str) or not profile:
        problems.append("'profile' must be a non-empty string")
    defaults = manifest.get("defaults")
    if not isinstance(defaults, dict) or set(defaults) != set(SPEC_KEYS):
        problems.append(
            "'defaults' must be a dict with exactly the keys %s"
            % sorted(SPEC_KEYS)
        )
    else:
        _check_spec_keys("defaults", defaults, problems)
    if not isinstance(manifest.get("system_prompt_overlay"), str):
        problems.append("'system_prompt_overlay' must be a string (may be empty)")
    regions = manifest.get("regions")
    if not isinstance(regions, list) or not regions:
        problems.append("'regions' must be a non-empty list")
        regions = []
    seen_regions = set()
    for i, region in enumerate(regions):
        where = "regions[%d]" % i
        if not isinstance(region, dict):
            problems.append("%s: must be a dict" % where)
            continue
        rid = region.get("id")
        if not isinstance(rid, str) or not rid:
            problems.append("%s: 'id' must be a non-empty string" % where)
        elif rid in seen_regions:
            problems.append("%s: duplicate region id %r" % (where, rid))
        else:
            seen_regions.add(rid)
        _check_spec_keys(where, region, problems, skip=("id", "widgets"))
        widgets = region.get("widgets")
        if not isinstance(widgets, list):
            problems.append("%s: 'widgets' must be a list" % where)
            continue
        seen_widgets = set()
        for j, entry in enumerate(widgets):
            wwhere = "%s.widgets[%d]" % (where, j)
            if isinstance(entry, str):
                wid = entry
            elif isinstance(entry, dict):
                wid = entry.get("id")
                if not isinstance(wid, str) or not wid:
                    problems.append(
                        "%s: 'id' must be a non-empty string" % wwhere
                    )
                    wid = None
                _check_spec_keys(wwhere, entry, problems, skip=("id",))
            else:
                problems.append(
                    "%s: must be a widget id string or a dict" % wwhere
                )
                continue
            if wid is not None:
                if wid in seen_widgets:
                    problems.append(
                        "%s: duplicate widget id %r" % (wwhere, wid)
                    )
                seen_widgets.add(wid)
    return problems


def get_manifest(name, default=DEFAULT_PROFILE):
    """The manifest for ``name`` — a deep copy, so callers may mutate freely.

    An unknown profile frays visibly (L2): warn and fall back to ``default``
    rather than crash — the panel must always build."""
    manifest = MANIFESTS.get(name)
    if manifest is None:
        logger.warning(
            "manifests: unknown profile %r — falling back to %r", name, default
        )
        manifest = MANIFESTS[default]
    return copy.deepcopy(manifest)
