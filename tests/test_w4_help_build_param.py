"""W4-HELP -- helpdoc/i1_extract build-pin parameterization.

The helpdoc corpus loader and the i1_extract importer used to hard-pin Houdini
22.0.368 in two module attributes (``helpdoc.BUILD`` / ``helpdoc.HELP_DIR``);
repointing to another build meant EDITING (mutating) the module. This suite pins
the parameterized replacement:

  1. A caller addresses a build by parameter (``HelpCorpus(build=...)`` /
     ``load_corpus(build=...)``) or by environment override
     (``SYNAPSE_HELP_BUILD`` / ``SYNAPSE_HELP_DIR``), defaulting to the current
     pin. Two builds resolve in one process; the module is never mutated.
  2. i1_extract parses a page from each build through that surface.
  3. An absent build FAILS LOUDLY and names the missing path -- the loud failure
     the pin was designed around is preserved, never softened into a fallback.
  4. The ingest importer carries no hardcoded build; the single default lives in
     exactly one place, overridable.

House rule honored: a build that is not installed is UNOBTAINABLE, so the
real-archive tests ``skip`` (recorded UNKNOWN) rather than fail or estimate. The
mechanism tests use a synthetic fixture archive and run on any machine.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

# --- import the modules under test off the harness tree -----------------------
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "harness" / "notes" / "h9"))
sys.path.insert(0, str(REPO / "harness" / "notes" / "ingest"))

import helpdoc          # noqa: E402  harness/notes/h9/helpdoc.py
import i1_extract as X  # noqa: E402  harness/notes/ingest/i1_extract.py

REAL_BUILDS = ("22.0.368", "22.0.400")
ABSENT_BUILD = "99.9.999"   # guaranteed not installed -> exercises the loud fail


def _installed(build: str) -> bool:
    # env-immune, matching how HelpCorpus(build=) actually resolves -- so a set
    # SYNAPSE_HELP_DIR cannot fool this skip gate into entering and then crashing
    # (house rule: an unobtainable build renders UNKNOWN/skip, never an error).
    return helpdoc._install_help_dir(build).joinpath("nodes.zip").exists()


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def synthetic_help(tmp_path: Path) -> Path:
    """A minimal ``houdini/help`` dir with a one-page nodes.zip.

    Lets the parameterized surface (``help_dir`` override) be exercised with no
    Houdini install, so the mechanism is provable in headless CI.
    """
    help_dir = tmp_path / "help"
    help_dir.mkdir()
    page = (
        "= My Node =\n"
        "#type: node\n"
        "#context: lop\n"
        '"""A synthetic node for the build-parameterization test."""\n'
        "@parameters\n"
        "Threshold:\n"
        "    #id: threshold\n"
        "    The cutoff value.\n"
    )
    with zipfile.ZipFile(help_dir / "nodes.zip", "w") as z:
        z.writestr("lop/mynode.txt", page)
    return help_dir


# ---------------------------------------------------------------- acceptance #1
def test_absent_archive_raises_and_names_path():
    """A requested build with no archive fails LOUD and names the missing path.

    SystemExit (not a swallowable Exception) keeps it loud; the message carries
    both the build and the absolute nodes.zip path so nothing silently serves
    another build's pages.
    """
    with pytest.raises(SystemExit) as ei:
        helpdoc.HelpCorpus(build=ABSENT_BUILD)
    msg = str(ei.value)
    assert ABSENT_BUILD in msg
    assert "nodes.zip" in msg
    assert str(helpdoc._install_help_dir(ABSENT_BUILD)) in msg


def test_two_real_builds_one_process_without_mutation():
    """.368 and .400 resolve by parameter in ONE process; module is untouched."""
    for b in REAL_BUILDS:
        if not _installed(b):
            pytest.skip(f"build {b} not installed -- real-archive claim UNKNOWN")

    before_build, before_dir, before_zip = (
        helpdoc.BUILD, helpdoc.HELP_DIR, helpdoc.NODES_ZIP)

    c368 = helpdoc.HelpCorpus(build="22.0.368")
    c400 = helpdoc.HelpCorpus(build="22.0.400")

    assert c368.build == "22.0.368" and c400.build == "22.0.400"
    assert "22.0.368" in str(c368.nodes_zip) and "22.0.400" in str(c400.nodes_zip)
    assert c368.nodes_zip != c400.nodes_zip
    assert len(c368.pages) > 100 and len(c400.pages) > 100
    assert c368.pages is not c400.pages          # independent corpora

    # nothing mutated the module while two builds were resolved
    assert (helpdoc.BUILD, helpdoc.HELP_DIR, helpdoc.NODES_ZIP) == (
        before_build, before_dir, before_zip)


def test_module_default_is_the_current_pin():
    """The default (no param, no env) is the current pin -- callers opt out of it."""
    assert helpdoc._DEFAULT_BUILD == "22.0.368"
    assert helpdoc.resolve_build() == "22.0.368"      # no env override in play
    assert helpdoc.resolve_build("22.0.400") == "22.0.400"


def test_env_override_is_call_time_and_reverts(monkeypatch, synthetic_help):
    """SYNAPSE_HELP_BUILD / SYNAPSE_HELP_DIR override at call time, no mutation."""
    before_build, before_dir = helpdoc.BUILD, helpdoc.HELP_DIR

    monkeypatch.setenv("SYNAPSE_HELP_BUILD", "22.0.400")
    assert helpdoc.resolve_build() == "22.0.400"

    # SYNAPSE_HELP_DIR points resolution at an arbitrary install location; a
    # zero-arg corpus then loads THAT dir -- proving env selects the archive
    # with no Houdini install and no module edit.
    monkeypatch.setenv("SYNAPSE_HELP_DIR", str(synthetic_help))
    assert helpdoc.help_dir_for() == synthetic_help
    corpus = helpdoc.HelpCorpus()
    assert corpus.help_dir == synthetic_help
    assert "nodes/lop/mynode" in corpus.pages

    # module attributes captured at import were never rewritten
    assert (helpdoc.BUILD, helpdoc.HELP_DIR) == (before_build, before_dir)

    monkeypatch.delenv("SYNAPSE_HELP_BUILD")
    monkeypatch.delenv("SYNAPSE_HELP_DIR")
    assert helpdoc.resolve_build() == "22.0.368"


def test_help_dir_param_loads_arbitrary_build(synthetic_help):
    """The ``help_dir`` parameter loads any archive and labels the build."""
    corpus = helpdoc.HelpCorpus(build="22.0.999-fixture", help_dir=synthetic_help)
    assert corpus.build == "22.0.999-fixture"
    assert corpus.help_dir == synthetic_help
    assert corpus.nodes_zip == synthetic_help / "nodes.zip"
    assert "nodes/lop/mynode" in corpus.pages


def test_explicit_build_ignores_env_dir_no_collapse(monkeypatch, synthetic_help):
    """An explicit build addresses its OWN install path -- SYNAPSE_HELP_DIR (a
    default-location override) must not collapse two explicit builds onto one
    dir and mislabel them. This is the target-3 'never silently serves another
    build's pages' guard for the env-override path."""
    monkeypatch.setenv("SYNAPSE_HELP_DIR", str(synthetic_help))
    # zero-arg DEFAULT resolution DOES honor the env dir ...
    assert helpdoc.HelpCorpus().help_dir == synthetic_help
    # ... but an explicit build derives its own per-build path, not the env dir
    for b in ("22.0.368", "22.0.400"):
        derived = helpdoc._install_help_dir(b)
        assert derived != synthetic_help
        assert b in str(derived)
    # and the two explicit builds resolve to DISTINCT dirs even with env set
    if _installed("22.0.368") and _installed("22.0.400"):
        c368 = helpdoc.HelpCorpus(build="22.0.368")
        c400 = helpdoc.HelpCorpus(build="22.0.400")
        assert c368.help_dir != synthetic_help and c400.help_dir != synthetic_help
        assert c368.help_dir != c400.help_dir


def test_label_follows_overridden_location():
    """When the LOCATION is overridden, the build label follows the actual dir --
    it can never disagree with the pages loaded (target 3, off the location axis).

    ``build_from_path`` reads the build the install path encodes, so pointing
    SYNAPSE_HELP_DIR (or help_dir=) at the .400 install labels the corpus .400,
    not the default .368 pin.
    """
    if not _installed("22.0.400"):
        pytest.skip("build 22.0.400 not installed -- label-follows-location UNKNOWN")
    real_400 = helpdoc._install_help_dir("22.0.400")
    assert helpdoc.build_from_path(real_400) == "22.0.400"

    # via the help_dir= parameter, no build= given
    c = helpdoc.HelpCorpus(help_dir=real_400)
    assert c.build == "22.0.400" and "22.0.400" in str(c.help_dir)


def test_env_dir_label_follows_location(monkeypatch):
    """SYNAPSE_HELP_DIR at the .400 install labels a zero-arg corpus .400, even
    if SYNAPSE_HELP_BUILD says otherwise -- the loaded dir is the truth."""
    if not _installed("22.0.400"):
        pytest.skip("build 22.0.400 not installed -- env-dir label UNKNOWN")
    monkeypatch.setenv("SYNAPSE_HELP_DIR", str(helpdoc._install_help_dir("22.0.400")))
    monkeypatch.setenv("SYNAPSE_HELP_BUILD", "22.0.368")   # deliberately divergent
    c = helpdoc.HelpCorpus()
    assert c.build == "22.0.400"                            # follows the dir, not the env build
    assert "22.0.400" in str(c.help_dir)


def test_build_helpdir_divergence_raises():
    """An explicit build= that contradicts the help_dir= path FAILS LOUD rather
    than stamping a wrong label onto a corpus (never a silent mislabel)."""
    if not _installed("22.0.368"):
        pytest.skip("build 22.0.368 not installed -- divergence guard UNKNOWN")
    real_368 = helpdoc._install_help_dir("22.0.368")
    with pytest.raises(SystemExit) as ei:
        helpdoc.HelpCorpus(build="22.0.400", help_dir=real_368)
    assert "disagree" in str(ei.value)


def test_module_build_frozen_against_env(monkeypatch):
    """helpdoc.BUILD is a stable constant (the pin). Setting SYNAPSE_HELP_BUILD
    repoints per-instance resolution, never the import-time module snapshot the
    zero-arg consumers assert against."""
    frozen = helpdoc.BUILD
    monkeypatch.setenv("SYNAPSE_HELP_BUILD", "22.0.400")
    assert helpdoc.BUILD == frozen == "22.0.368"          # module unchanged
    assert helpdoc.resolve_build() == "22.0.400"          # resolver honors env


# ---------------------------------------------------------------- acceptance #2
@pytest.mark.parametrize("build", REAL_BUILDS)
def test_i1_parses_sample_page_from_each_real_build(build):
    """i1_extract parses real pages from each build via the parameterized surface."""
    if not _installed(build):
        pytest.skip(f"build {build} not installed -- parse claim UNKNOWN")

    corpus = X.load_corpus(build=build)
    assert corpus.build == build

    common_ok = False
    sample = X.node_pages(corpus, "lop")[:20]
    assert sample, "no lop node pages found -- corpus did not load"
    for key in sample:
        page = X.parse_page(key, corpus)     # must not raise
        assert page.help_key == key
        if page.params:
            common_ok = True
    # the parser must actually produce structure on real data, not merely
    # decline to throw on empty pages
    assert common_ok, f"no parameters parsed on any sampled {build} lop page"


def test_i1_parses_the_same_page_from_both_real_builds():
    """The literal acceptance: one sample page, parsed from EACH build, zero errors."""
    for b in REAL_BUILDS:
        if not _installed(b):
            pytest.skip(f"build {b} not installed -- dual-build parse UNKNOWN")

    c368 = X.load_corpus(build="22.0.368")
    c400 = X.load_corpus(build="22.0.400")
    common = sorted(set(X.node_pages(c368, "lop")) & set(X.node_pages(c400, "lop")))
    assert common, "no lop node page common to both builds"
    key = common[0]
    p368 = X.parse_page(key, c368)
    p400 = X.parse_page(key, c400)
    assert p368.help_key == key and p400.help_key == key


def test_doc_deprecation_labels_the_parsed_build():
    """A record from a non-default corpus is stamped with THAT build, not the pin."""
    if not _installed("22.0.400"):
        pytest.skip("build 22.0.400 not installed -- label claim UNKNOWN")
    corpus = X.load_corpus(build="22.0.400")
    key = X.node_pages(corpus, "lop")[0]
    raw = corpus.pages[key]
    assert X.doc_deprecation(raw, {}, [], [], build=corpus.build)["build"] == "22.0.400"
    assert X.doc_deprecation(raw, {}, [], [])["build"] == "22.0.368"   # default pin


# ---------------------------------------------------------------- acceptance #3
def test_ingest_paths_have_no_hardcoded_build():
    """No governing 22.0.368 hardcode on the ingest importer; single overridable
    default on the parameterized surface."""
    i1_src = (REPO / "harness/notes/ingest/i1_extract.py").read_text(encoding="utf-8")
    assert "22.0.368" not in i1_src, "importer still carries a hardcoded build"

    hd_src = (REPO / "harness/notes/h9/helpdoc.py").read_text(encoding="utf-8")
    hits = [ln.strip() for ln in hd_src.splitlines() if "22.0.368" in ln]
    assert len(hits) == 1, f"expected exactly one (default) literal, got: {hits}"
    assert hits[0].startswith("_DEFAULT_BUILD ="), hits[0]
