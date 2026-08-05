"""Rope L5-2 — layout manifests + compositor resolve, headless (no Qt).

Pins the task's three claims: the three profile manifests validate against the
schema, resolve without error, and an unknown widget id skip-logs instead of
crashing. Plus the L5 invariant the profiles exist to keep: identical
capability in every profile (nothing hidden, nothing collapsed), with
``expert`` matching the v5.42.0 wiring exactly.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from synapse.panel import compositor
from synapse.panel.manifests import (
    MANIFESTS,
    ManifestError,
    PROMINENCE_LEVELS,
    SPEC_KEYS,
    get_manifest,
    validate_manifest,
)

PROFILES = ("curious", "expert", "ml")
V5420_REGION_ORDER = ["rail", "context_ribbon", "mode_bar", "faces"]

# Declared folds per profile (L5-19). A collapsed widget is present in the
# layout at zero height and one click away — paced, never withheld. Expert
# is untouched and declares none. A new fold must be added here
# deliberately, never smuggled.
DECLARED_FOLDS = {
    "curious": {("rail", "token_meter"), ("rail", "activity_meter")},
}


def test_registry_is_exactly_the_three_profiles():
    assert sorted(MANIFESTS) == sorted(PROFILES)


@pytest.mark.parametrize("name", PROFILES)
def test_manifest_validates(name):
    assert validate_manifest(MANIFESTS[name]) == []


@pytest.mark.parametrize("name", PROFILES)
def test_manifest_resolves(name):
    plan = compositor.resolve(get_manifest(name))
    assert plan["profile"] == name
    assert [r["id"] for r in plan["regions"]] == V5420_REGION_ORDER
    for region in plan["regions"]:
        assert region["builder"] == compositor.REGION_BUILDERS[region["id"]]
        assert region["widgets"], "region %r resolved empty" % region["id"]
        for spec in region["widgets"]:
            for key in SPEC_KEYS:
                assert key in spec, "widget %r missing %r" % (spec["id"], key)
            assert spec["prominence"] in PROMINENCE_LEVELS
            # L5: identical capability in every profile — prominence, the
            # prompt overlay and declared folds may differ, but nothing is
            # ever hidden. A fold is present at zero height, one click
            # away; a new one must be declared in DECLARED_FOLDS.
            assert spec["visible"] is True
            if spec["collapsed"]:
                assert (region["id"], spec["id"]) in DECLARED_FOLDS.get(
                    name, set()), "undeclared fold in %r: %s/%s" % (
                    name, region["id"], spec["id"])


def test_expert_is_the_v5420_wiring():
    plan = compositor.resolve(get_manifest("expert"))
    assert plan["system_prompt_overlay"] == ""
    stretches = {r["id"]: r["stretch"] for r in plan["regions"]}
    assert stretches == {"rail": 0, "context_ribbon": 0, "mode_bar": 0,
                         "faces": 1}
    for spec in (s for r in plan["regions"] for s in r["widgets"]):
        assert spec["prominence"] == "standard"


def test_unknown_widget_id_skip_logs(caplog):
    manifest = get_manifest("expert")
    manifest["regions"][0]["widgets"].append("flux_capacitor")
    with caplog.at_level(logging.WARNING):
        plan = compositor.resolve(manifest)
    rail_ids = [w["id"] for w in plan["regions"][0]["widgets"]]
    assert "flux_capacitor" not in rail_ids
    assert "mark" in rail_ids  # the known neighbours survived
    assert "flux_capacitor" in caplog.text


def test_unknown_region_id_skip_logs(caplog):
    manifest = get_manifest("expert")
    manifest["regions"].insert(0, {"id": "jumbotron", "widgets": ["mark"]})
    with caplog.at_level(logging.WARNING):
        plan = compositor.resolve(manifest)
    assert [r["id"] for r in plan["regions"]] == V5420_REGION_ORDER
    assert "jumbotron" in caplog.text


def test_invalid_manifest_raises_manifest_error():
    with pytest.raises(ManifestError) as exc:
        compositor.resolve({"profile": "broken"})
    assert exc.value.problems  # every problem carried, not just the first


def test_unknown_profile_falls_back_to_expert(caplog):
    with caplog.at_level(logging.WARNING):
        manifest = get_manifest("wizard")
    assert manifest["profile"] == "expert"
    assert "wizard" in caplog.text


def test_get_manifest_returns_a_private_copy():
    a = get_manifest("expert")
    a["regions"][0]["widgets"].append("scribble")
    assert "scribble" not in MANIFESTS["expert"]["regions"][0]["widgets"]


def test_headless_import_without_qt():
    """The resolve seam must import and run with Qt structurally absent —
    blocked in a subprocess so nothing leaks into this test session."""
    code = (
        "import sys;"
        "sys.modules['PySide6'] = None; sys.modules['PySide2'] = None;"
        "from synapse.panel import compositor;"
        "from synapse.panel.manifests import get_manifest;"
        "plan = compositor.resolve(get_manifest('expert'));"
        "assert plan['regions'];"
        "print('HEADLESS_OK')"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "python") + os.pathsep + env.get(
        "PYTHONPATH", "")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, env=env, cwd=str(REPO), timeout=120)
    assert "HEADLESS_OK" in out.stdout, out.stderr
