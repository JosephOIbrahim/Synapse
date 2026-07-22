"""Corpus conformance: the authored RAG skills must not TEACH a deprecated LOP.

The code/corpus divergence trap (see the [[synapse-code-corpus-divergence]]
note and tests/test_corpus_encoding_conformance.py): fixing a node type in
SYNAPSE's code is not enough, because the ``rag/`` corpus re-teaches the old
spelling through scout / knowledge_lookup. B9 fixed the emitters
(karmarenderproperties -> karmarendersettings); this pins the corpus so it
cannot quietly re-introduce it.

Scope is deliberately narrow: only ``createNode("<deprecated>")`` /
``stage.node("<deprecated>...")`` -- i.e. the corpus *instructing* the reader to
author or fetch the node. A prose mention ("karmarenderproperties is
deprecated") is legitimate documentation and is NOT flagged; the point is to
stop the corpus teaching the wrong verb, not to erase the old name's history.

Deprecation truth comes from the committed live catalog
(harness/notes/h22_lop_catalog_live_22.0.368.json), so a FUTURE deprecation is
caught on the build that introduces it -- the same posture as the emit-side
guard in tests/test_solaris_graph.py::TestNoDeprecatedTypesEmitted.

Pure-Python: reads the catalog + corpus text. No ``hou`` import.
"""

import json
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_CATALOG = _REPO / "harness" / "notes" / "h22_lop_catalog_live_22.0.368.json"
_CORPUS_DIRS = [
    _REPO / "rag" / "skills" / "houdini21-reference",
]


def _deprecated_types():
    if not _CATALOG.exists():
        return None
    types = json.loads(_CATALOG.read_text(encoding="utf-8"))["types"]
    return {n for n, r in types.items() if r.get("deprecated")}


def _authored_corpus_files():
    files = []
    for d in _CORPUS_DIRS:
        if d.exists():
            files.extend(sorted(d.glob("*.md")))
    return files


def test_catalog_marks_karma_pair_deprecated():
    """Guards the guard -- if the catalog stopped flagging these, the sweep
    below would pass vacuously."""
    dep = _deprecated_types()
    if dep is None:
        pytest.skip("no 22.0.368 catalog in this tree")
    assert "karmarenderproperties" in dep
    assert "karmarendersettings" not in dep


def test_corpus_does_not_teach_creating_a_deprecated_lop():
    dep = _deprecated_types()
    if dep is None:
        pytest.skip("no 22.0.368 catalog in this tree")
    files = _authored_corpus_files()
    assert files, "no authored corpus files found -- path drift?"

    # createNode("x") / createNode('x') / stage.node("x1") -- the reader is being
    # told to AUTHOR or FETCH the node, not merely told the name exists.
    teach = re.compile(
        r"""(?:createNode|\.node)\s*\(\s*["']([A-Za-z0-9_:]+?)\d*["']""")
    offenders = {}
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        for m in teach.finditer(text):
            base = m.group(1).split("::")[0]
            if base in dep:
                offenders.setdefault(fp.name, set()).add(base)
    offenders = {k: sorted(v) for k, v in offenders.items()}
    assert not offenders, (
        "RAG corpus teaches createNode/node() for deprecated LOP type(s): %s "
        "-- migrate to the successor (the corpus re-teaches via scout)"
        % offenders)
