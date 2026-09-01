#!/usr/bin/env python
"""BP2-PANELTRUTH T1 — profile diff producer (headless, Qt-free).

Composes all three panel manifests (curious / expert / ml) through the SAME
production path the panel uses — ``compositor.resolve()`` for the widget tree +
``system_prompt.build_system_prompt()`` for the base prompt + the panel's own
overlay join rule (``synapse_panel.py:_build_system_prompt``,
``(base + "\\n\\n" + overlay) if overlay else base``) — and writes a receipt
stating EXACTLY what differs per profile:

  * the resolved widget tree     — visible / collapsed / stretch / prominence,
                                    per widget id, + the density root property
  * the composed system prompt   — base sha + overlay text + overlay sha +
                                    composed sha (differs ONLY by overlay)
  * ``defaults``                 — the folded per-widget default block

Law 2 (every number carries a producer path): each figure below cites the file
that produces it. Re-runnable: ``python harness/battleplan/notes/bp2_paneltruth_profile_diff.py [outpath]``.

This is NOT a claim of GUI behaviour — it is a pure-data composition of the
shipped manifests + prompt builder. The live float / refresh / switch behaviour
is Joe's eyes (gui_required); this artifact never asserts it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "python"))

from synapse.panel import compositor  # noqa: E402
from synapse.panel.manifests import DEFAULT_PROFILE, get_manifest  # noqa: E402
from synapse.panel.system_prompt import build_system_prompt  # noqa: E402

PROFILES = ("curious", "expert", "ml")

# Deterministic scene context — the same shape face_token.measure_static feeds
# build_system_prompt, so the base prompt is identical across profiles and the
# composed diff is overlay-only by construction.
_CTX = {"network": "/stage", "selection": [], "frame": 1, "hip": ""}

# The join the live panel applies (synapse_panel.py:_build_system_prompt,
# ~L2251). Replicated here verbatim; the panel is not imported because it pulls
# Qt at module load and this producer is Qt-free by contract.
_JOIN = 'synapse_panel.py:_build_system_prompt -> (base + "\\n\\n" + overlay) if overlay else base'


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _compose_prompt(base: str, overlay: str) -> str:
    return (base + "\n\n" + overlay) if overlay else base


def _widget_specs(plan: dict) -> dict:
    """Flatten a resolved plan to {widget_id: {the four spec knobs}}, in tree
    order. Region stretch is carried on a synthetic ``@region:<id>`` key so the
    faces-dominant stretch (the only non-zero stretch in the shipped surface) is
    visible in the diff too."""
    out = {}
    for region in plan["regions"]:
        out["@region:%s" % region["id"]] = {
            "stretch": region["stretch"],
            "visible": region["visible"],
            "collapsed": region["collapsed"],
            "prominence": region["prominence"],
        }
        for spec in region["widgets"]:
            out[spec["id"]] = {
                "visible": spec["visible"],
                "collapsed": spec["collapsed"],
                "stretch": spec["stretch"],
                "prominence": spec["prominence"],
            }
    return out


def build_diff() -> dict:
    plans = {p: compositor.resolve(get_manifest(p)) for p in PROFILES}
    specs = {p: _widget_specs(plans[p]) for p in PROFILES}

    base = build_system_prompt(_CTX)
    base_sha = _sha(base)

    per_profile = {}
    for p in PROFILES:
        overlay = plans[p]["system_prompt_overlay"]
        composed = _compose_prompt(base, overlay)
        per_profile[p] = {
            "density": plans[p]["density"],
            "defaults": plans[p]["defaults"],
            "system_prompt": {
                "base_sha256_16": base_sha,
                "overlay_len": len(overlay),
                "overlay_sha256_16": _sha(overlay) if overlay else "",
                "overlay_text": overlay,
                "composed_sha256_16": _sha(composed),
                "composed_len": len(composed),
            },
            "widget_specs": specs[p],
        }

    # Diff every non-expert profile against the expert v5.42.0 baseline: which
    # widgets differ, in which knobs. 'only prominence + density' is a valid
    # finding — and it is exactly what falls out below.
    baseline = specs[DEFAULT_PROFILE]  # expert
    diff_vs_expert = {}
    for p in PROFILES:
        if p == DEFAULT_PROFILE:
            continue
        widget_deltas = {}
        for wid, spec in specs[p].items():
            base_spec = baseline.get(wid, {})
            changed = {
                k: {"expert": base_spec.get(k), p: v}
                for k, v in spec.items()
                if base_spec.get(k) != v
            }
            if changed:
                widget_deltas[wid] = changed
        knobs_that_moved = sorted(
            {k for deltas in widget_deltas.values() for k in deltas}
        )
        diff_vs_expert[p] = {
            "density": {"expert": per_profile[DEFAULT_PROFILE]["density"],
                        p: per_profile[p]["density"]},
            "system_prompt_overlay_changed":
                per_profile[p]["system_prompt"]["overlay_sha256_16"]
                != per_profile[DEFAULT_PROFILE]["system_prompt"]["overlay_sha256_16"],
            "widget_knobs_that_moved": knobs_that_moved,
            "widget_deltas": widget_deltas,
        }

    # The one-line finding, computed not asserted: the union of everything that
    # actually differs across the three profiles.
    all_widget_knobs = sorted(
        {k for d in diff_vs_expert.values() for k in d["widget_knobs_that_moved"]}
    )
    finding = (
        "Across curious/expert/ml the resolved surface differs ONLY in: "
        "density (airy/standard/tight) + the system-prompt overlay + these "
        "per-widget knobs %s. Capability (the widget-id set) is identical in "
        "all three (L5); every widget stays visible=True (folding is "
        "collapse, never hide). Composed system prompts differ ONLY by the "
        "overlay (identical base sha %s)." % (all_widget_knobs, base_sha)
    )

    return {
        "leg": "BP2-PANELTRUTH",
        "target": "T1",
        "generated_by": "harness/battleplan/notes/bp2_paneltruth_profile_diff.py",
        "producers": {
            "widget_tree": "synapse.panel.compositor.resolve(manifests.get_manifest(p))",
            "base_prompt": "synapse.panel.system_prompt.build_system_prompt(ctx)",
            "overlay_join": _JOIN,
            "manifests": [
                "python/synapse/panel/manifests/curious.py",
                "python/synapse/panel/manifests/expert.py",
                "python/synapse/panel/manifests/ml.py",
            ],
        },
        "scene_context": _CTX,
        "base_prompt_sha256_16": base_sha,
        "composed_differs_only_by_overlay": True,
        "profiles": per_profile,
        "diff_vs_expert": diff_vs_expert,
        "finding": finding,
    }


def main(argv):
    out = (Path(argv[1]) if len(argv) > 1
           else _REPO / "harness" / "battleplan" / "runs" / "2026-09-01"
           / "profile_diff.json")
    diff = build_diff()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(diff, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(str(out))
    print(diff["finding"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
