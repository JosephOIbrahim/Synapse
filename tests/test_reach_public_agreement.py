"""REACH P1-R2 pins — public-face agreement (blueprint sec.4 R2 +
.synapse/contracts/reach-public-agreement.yaml).

Pure Python, NO hou, NO git (tags are injected; git is only asked in
production). These lock the additive public-face contract so a future edit
that weakens it fails loud:

  * readme_banner joined the in-tree chain (VERSION == ... == README banner);
  * public_agreement is red on real drift (stale face, banner != VERSION,
    missing banner, stale/ahead tags-claim) and green in the release window
    (face ahead of the newest tag);
  * unmeasurable is never a verdict: no git / no tags is 'nothing to compare';
  * --fix heals ONLY a stale tags-claim forward.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _load_va():
    spec = importlib.util.spec_from_file_location(
        "reach_version_agreement", _ROOT / "harness" / "verify" / "version_agreement.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


va = _load_va()

# Delimiter mirrors the real banner (README.md:11) and the ROOT_FILES regex:
# '<sub>vX.Y.Z · Houdini' with the literal middle dot.
_BANNER = ('<p align="center"><sub>v{v} · Houdini 22.0.400 (doc pin) '
           '· Python 3.13<br>tags: v{t} is latest</sub></p>')


def _readme(tmp_path, version="5.52.0", tag_claim="5.52.0", claim=True):
    txt = _BANNER.format(v=version, t=tag_claim)
    if not claim:
        txt = txt.split("<br>")[0] + "</sub></p>"
    p = tmp_path / "README.md"
    p.write_text(txt, encoding="utf-8")
    return str(p)


def _check(verdict, name):
    for c in verdict["checks"]:
        if c["name"] == name:
            return c
    raise AssertionError("check %r missing from verdict" % name)


# --- version / tag parsing -------------------------------------------------

def test_parse_version_shapes():
    assert va.parse_version("5.52.0") == (5, 52, 0)
    assert va.parse_version("5.52") is None
    assert va.parse_version("v5.52.0") is None


def test_parse_release_tag_filters_non_release():
    assert va.parse_release_tag("v5.52.0") == (5, 52, 0)
    assert va.parse_release_tag("archive/wave8") is None
    assert va.parse_release_tag("v5.52.0-rc1") is None


def test_newest_release_tag_version_orders_not_lexical():
    # lexicographic max would pick v5.9.0; the check must not.
    newest = va.newest_release_tag(["v5.52.0", "v5.9.0", "v5.51.0", "junk"])
    assert newest == ("v5.52.0", (5, 52, 0))
    assert va.newest_release_tag([]) is None
    assert va.newest_release_tag(None) is None


# --- public_agreement arms -------------------------------------------------

def test_green_when_banner_tag_version_all_agree(tmp_path):
    v = va.public_agreement(
        canonical="5.52.0", readme_path=_readme(tmp_path),
        tags=["v5.50.0", "v5.51.0", "v5.52.0"])
    assert v["ok"] is True
    assert v["banner"] == "5.52.0"
    assert v["newest_tag"] == "v5.52.0"


def test_red_when_tag_outruns_public_face(tmp_path):
    # THE defect: v5.43.0 was tagged against a tree whose public face said 5.42.0.
    v = va.public_agreement(canonical="5.42.0",
                            readme_path=_readme(tmp_path, version="5.42.0",
                                                tag_claim="5.42.0"),
                            tags=["v5.42.0", "v5.43.0"])
    assert v["ok"] is False
    c = _check(v, "tag_not_ahead_of_banner")
    assert c["ok"] is False and "stale" in c["reason"]


def test_green_in_release_window_face_ahead_of_tag(tmp_path):
    # bump lands, README syncs, tag pushed after - this window must stay green
    # or every correct release fires red.
    v = va.public_agreement(canonical="5.53.0",
                            readme_path=_readme(tmp_path, version="5.53.0",
                                                tag_claim="5.53.0"),
                            tags=["v5.52.0"])
    assert v["ok"] is True
    assert _check(v, "tag_not_ahead_of_banner")["ok"] is True


def test_red_when_banner_differs_from_version(tmp_path):
    v = va.public_agreement(canonical="5.52.0",
                            readme_path=_readme(tmp_path, version="5.51.0",
                                                tag_claim="5.52.0"),
                            tags=["v5.52.0"])
    assert v["ok"] is False
    assert _check(v, "banner_matches_canonical")["ok"] is False


def test_red_when_banner_missing(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("no banner here", encoding="utf-8")
    v = va.public_agreement(canonical="5.52.0", readme_path=str(p),
                            tags=["v5.52.0"])
    assert v["ok"] is False
    assert _check(v, "readme_banner_present")["ok"] is False


def test_no_tags_is_nothing_to_compare_never_red(tmp_path):
    v = va.public_agreement(canonical="5.52.0",
                            readme_path=_readme(tmp_path), tags=[])
    assert _check(v, "tag_not_ahead_of_banner")["ok"] is True
    assert "nothing to compare" in _check(v, "tag_not_ahead_of_banner")["reason"]


def test_stale_tags_claim_is_red(tmp_path):
    v = va.public_agreement(canonical="5.52.0",
                            readme_path=_readme(tmp_path, tag_claim="5.50.0"),
                            tags=["v5.52.0"])
    assert v["ok"] is False
    c = _check(v, "tag_claim_current")
    assert c["ok"] is False and "stale" in c["reason"]


def test_ahead_tags_claim_is_red_with_distinct_reason(tmp_path):
    # A claim AHEAD of tag AND VERSION asserts a release the tree knows
    # nothing about - red, and the reason must not call it 'stale'.
    v = va.public_agreement(canonical="5.52.0",
                            readme_path=_readme(tmp_path, tag_claim="9.9.9"),
                            tags=["v5.52.0"])
    c = _check(v, "tag_claim_current")
    assert c["ok"] is False
    assert "stale" not in c["reason"] and "does not exist" in c["reason"]


def test_absent_tags_claim_is_allowed(tmp_path):
    v = va.public_agreement(canonical="5.52.0",
                            readme_path=_readme(tmp_path, claim=False),
                            tags=["v5.52.0"])
    assert v["ok"] is True
    assert _check(v, "tag_claim_current")["ok"] is True


# --- --fix half ------------------------------------------------------------

def test_fix_heals_stale_claim_only(tmp_path):
    p = _readme(tmp_path, tag_claim="5.50.0")
    healed = va._fix_tag_claim("5.52.0", readme_path=p)
    assert healed == "5.50.0"
    assert va.readme_tag_claim(p) == "5.52.0"
    # ahead-of-tree claims are never healed down (that would mask the anomaly)
    b = tmp_path / "b"
    b.mkdir()
    p2 = _readme(b, tag_claim="9.9.9")
    assert va._fix_tag_claim("5.52.0", readme_path=p2) is None
    assert va.readme_tag_claim(p2) == "9.9.9"


def test_fix_noop_without_claim(tmp_path):
    p = _readme(tmp_path, claim=False)
    assert va._fix_tag_claim("5.52.0", readme_path=p) is None


# --- live tree (the free check, pinned) ------------------------------------

def test_live_tree_banner_equals_version():
    # The R2 free check, pinned so it cannot silently regress: the README's
    # fronted version IS VERSION today. Reads the repo's own files; no git.
    banner = va._read(va.ROOT_FILES["readme_banner"][0], str(_ROOT / "README.md"))
    canonical = va._read(None, str(_ROOT / "VERSION"))
    assert banner is not None, "README must front a '<sub>vX.Y.Z' banner"
    assert banner == canonical.strip()
