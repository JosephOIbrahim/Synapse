"""BP10-CORPUS T4/G0: rag/ingest/help_archive.py, on fixtures, with NO hou.

Round-trips a fixture zip + loose dir, checks the wiki->markdown converter against 10
hand-checked pages (tests/fixtures/help/pages/), proves a planted phantom node reference
lands in quarantine with a reason (never in the corpus), and pins the chunk record + STAMP
fields and the phantom_gate_status CURRENT/STALE/UNKNOWN contract.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rag" / "ingest"))
import help_archive as ha  # noqa: E402

PAGES = ROOT / "tests" / "fixtures" / "help" / "pages"
BUILD = "22.0.400"


def _page(name):
    return (PAGES / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
#  Fixture $HFS + catalogue                                                    #
# --------------------------------------------------------------------------- #
def _make_hfs(tmp_path):
    """A tmp $HFS/houdini/help with one zip (+ a skipped images/ entry) and one loose dir
    (+ a skipped licenses/ entry), assembled from the committed fixture pages."""
    help_dir = tmp_path / "hfs" / "houdini" / "help"
    help_dir.mkdir(parents=True)
    zpath = help_dir / "demo.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("basic.txt", _page("node_basic.txt"))
        zf.writestr("sub/phantom.txt", _page("node_phantom.txt"))
        zf.writestr("images/skip.txt", "= Skipped =\nimage caption, not prose.\n")
    loose = help_dir / "mpm"
    (loose / "licenses").mkdir(parents=True)
    (loose / "autosleep.txt").write_text(_page("loose_style.txt"), encoding="utf-8")
    (loose / "licenses" / "skip.txt").write_text("licence text, skip me", encoding="utf-8")
    return tmp_path / "hfs"


def _make_catalogue(tmp_path):
    """A tmp rag/ with a live-catalogue authority (h<build>/) covering the real refs but NOT
    the planted phantom 'frobnicator'."""
    cat = tmp_path / "rag" / "catalog" / f"h{BUILD}"
    cat.mkdir(parents=True)
    (cat / "Sop.json").write_text(json.dumps({
        "category": "Sop", "build": BUILD,
        "types": {"scatter": {}, "mpmsource": {}, "adjacency": {}},
    }), encoding="utf-8")
    (cat / "Cop.json").write_text(json.dumps({
        "category": "Cop", "build": BUILD, "types": {"geotoadjacency": {}},
    }), encoding="utf-8")
    (cat / "_manifest.json").write_text('{"note":"ignored by the loader"}', encoding="utf-8")
    return tmp_path / "rag"


# --------------------------------------------------------------------------- #
#  Path rules + round-trip                                                     #
# --------------------------------------------------------------------------- #
def test_iter_pages_round_trip(tmp_path):
    hfs = _make_hfs(tmp_path)
    got = {page: (scope, suffix) for scope, page, _raw, suffix in ha.iter_pages(hfs)}
    # forward-slash, extension-dropped page keys scoped by zip stem / loose dir name
    assert set(got) == {"demo/basic", "demo/sub/phantom", "mpm/autosleep"}
    # the skipped subtrees never appear
    assert not any("skip" in p for p in got)
    assert got["demo/basic"] == ("demo", "demo.zip")
    assert got["mpm/autosleep"] == ("mpm", "mpm/")


def test_skip_segments_excluded():
    assert ha._keep_txt("sop/scatter.txt")
    assert not ha._keep_txt("images/diagram.txt")
    assert not ha._keep_txt("licenses/eula.txt")
    assert not ha._keep_txt("nodes/sop/scatter.png")


# --------------------------------------------------------------------------- #
#  Converter, on 10 hand-checked pages                                         #
# --------------------------------------------------------------------------- #
def test_node_page_title_summary_headings():
    title, md = ha.wiki_to_markdown(_page("node_basic.txt"))
    assert title == "Scatter"
    assert "Scatters new points across a surface." in md   # tagline, quotes stripped
    assert "## Parameters" in md and "## Generation" in md  # @parameters + == Section ==
    assert "#internal" not in md and "#id" not in md        # directives stripped from body
    assert "[Node:sop/scatter]" in md                       # node xref preserved verbatim


def test_links_labels_kept_targets_dropped():
    _t, md = ha.wiki_to_markdown(_page("links.txt"))
    assert "cable" in md and "/copernicus/cables" not in md   # [label|target] -> label
    assert "compositing guide" in md
    assert "[Node:cop/geotoadjacency]" in md                  # node xref (no pipe) preserved


def test_bold_bullets_italic():
    _t, md = ha.wiki_to_markdown(_page("bold_bullets.txt"))
    assert "**strong emphasis**" in md          # __x__ -> **x**
    assert "*light emphasis*" in md             # inline *italic* untouched
    assert "- first item" in md and "- second item" in md


def test_callouts():
    _t, md = ha.wiki_to_markdown(_page("callouts.txt"))
    assert "**NOTE:**" in md and "**TIP:**" in md and "**WARNING:**" in md


def test_multiline_summary_joined():
    title, md = ha.wiki_to_markdown(_page("summary_multiline.txt"))
    assert title == "Adjacency"
    assert "in your network over texture seams." in md


def test_plain_prose_title_and_bullets():
    title, md = ha.wiki_to_markdown(_page("plain_prose.txt"))
    assert title == "Introduction to Houdini"
    assert "## Overview" in md
    assert "- You can go back" in md


def test_chunking_splits_on_h2():
    _t, md = ha.wiki_to_markdown(_page("headings.txt"))
    chunks = ha.chunk_markdown(md)
    assert len(chunks) == 3                       # intro + two H2 sections
    assert chunks[0].startswith("Intro paragraph")
    assert any(c.startswith("## First section") for c in chunks)
    assert "### A subsection" in "\n".join(chunks)  # H3 folded into its H2 chunk


# --------------------------------------------------------------------------- #
#  Phantom gate                                                                #
# --------------------------------------------------------------------------- #
def test_node_refs_and_apex_exemption():
    _t, md = ha.wiki_to_markdown(_page("apex_exempt.txt"))
    assert ha.node_refs(md) == set()                       # apex context is exempt
    assert ha.phantom_hits(ha.node_refs(md), set()) == []  # never a phantom even with empty auth


def test_phantom_hits_catches_absent_type():
    _t, md = ha.wiki_to_markdown(_page("node_phantom.txt"))
    refs = ha.node_refs(md)
    assert ("sop", "frobnicator") in refs
    assert ha.phantom_hits(refs, {"scatter", "box"}) == ["sop/frobnicator"]
    assert ha.phantom_hits(refs, {"frobnicator"}) == []    # present -> clean


def test_unqual_strips_namespace_and_version():
    assert ha._unqual("kinefx::motionclip::2.0") == "motionclip"
    assert ha._unqual("mynamespace--otherasset-2.0") == "otherasset"
    assert ha._unqual("cop/geotoadjacency") == "geotoadjacency"
    assert ha._unqual("box2") == "box2"                     # a trailing digit is not a version


# --------------------------------------------------------------------------- #
#  End-to-end build: corpus records, quarantine, stamp                         #
# --------------------------------------------------------------------------- #
def test_build_writes_corpus_quarantine_and_stamp(tmp_path):
    hfs = _make_hfs(tmp_path)
    rag = _make_catalogue(tmp_path)
    stats = ha.build(hfs, rag, BUILD)

    assert stats["scope_count"] == 2 and stats["page_count"] == 3
    assert stats["chunk_count"] >= 3 and stats["quarantine_count"] >= 1

    out = rag / "corpus" / "h22_prose"
    corpus = [json.loads(l) for f in out.glob("*.jsonl") for l in f.read_text(encoding="utf-8").splitlines()]
    # every corpus record carries the spec's chunk fields, a NON-EMPTY source, and a real sha
    for rec in corpus:
        for k in ("id", "scope", "page", "title", "chunk_index", "text",
                  "source", "build", "content_sha", "licence"):
            assert k in rec, f"missing {k}"
        assert rec["source"]                                   # G1: zero chunks with empty source
        assert rec["build"] == BUILD and rec["licence"] == "sidefx-eula"
        assert rec["id"].startswith("h22:")
        assert rec["content_sha"] == hashlib.sha256(rec["text"].encode("utf-8")).hexdigest()
    # the planted phantom is NOT in the corpus...
    assert not any(r["page"] == "demo/sub/phantom" and "frobnicator" in r["text"] for r in corpus)
    # ...it is in quarantine, with the failing ref and a reason
    quar = [json.loads(l) for f in (rag / "quarantine" / "prose").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines()]
    planted = [q for q in quar if "sop/frobnicator" in q["failing_refs"]]
    assert planted and planted[0]["reason"] and "text" not in planted[0]  # metadata-only (EULA-clean)

    stamp = json.loads((out / "STAMP.json").read_text(encoding="utf-8"))
    for k in ("build", "scope_count", "page_count", "chunk_count",
              "quarantine_count", "ingest_ts", "help_archive_sha"):
        assert k in stamp
    assert stamp["build"] == BUILD
    assert len(stamp["help_archive_sha"]) == 64                # sha256 hex of help_archive.py


# --------------------------------------------------------------------------- #
#  Target 2: phantom_gate_status                                               #
# --------------------------------------------------------------------------- #
def test_status_current_stale_unknown():
    assert ha._status("22.0.400", "22.0.400") == "CURRENT"
    assert ha._status("22.0.368", "22.0.400") == "STALE"
    assert ha._status(None, "22.0.400") == "UNKNOWN"          # unmeasurable is never a pass
    assert ha._status("22.0.400", None) == "UNKNOWN"


def test_phantom_gate_status_reads_stamp(tmp_path):
    hfs = _make_hfs(tmp_path)
    rag = _make_catalogue(tmp_path)
    ha.build(hfs, rag, BUILD)
    stamp_path = rag / "corpus" / "h22_prose" / "STAMP.json"
    assert ha.phantom_gate_status(stamp_path, "22.0.400")["status"] == "CURRENT"
    assert ha.phantom_gate_status(stamp_path, "22.0.368")["status"] == "STALE"
    assert ha.phantom_gate_status(tmp_path / "nope.json", "22.0.400")["status"] == "UNKNOWN"
