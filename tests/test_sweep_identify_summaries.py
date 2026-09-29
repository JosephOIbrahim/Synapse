"""The Identify corpus sweep and its node-type probe (BP12 item 3).

``scripts/sweep_identify_summaries.py`` reads the SideFX library and a
node-type list; ``scripts/probe_node_help_urls.py`` writes that list inside
Houdini. Both run here on stock Python, against a temp library and a fake
``hou``, so the two scripts are pinned to the same list shape.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import types
from pathlib import Path

from synapse.cognitive.tools import sidefx_library as SL
from synapse.identify import library as LIB

REPO = Path(__file__).resolve().parents[1]


def _script(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _library(tmp_path, pages):
    """A temp library with one page-top chunk per ``(key, body)``; returns its root."""
    root = tmp_path / "corpus"
    (root / "indexes").mkdir(parents=True)
    (root / "current.json").write_text(json.dumps({
        "schema": "sidefx_library_pointer/v1", "generation": "gen1",
        "database": "indexes/gen1.sqlite3", "coverage": {"docs": 1}}), encoding="utf-8")
    con = sqlite3.connect(root / "indexes" / "gen1.sqlite3")
    con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, source_url TEXT, "
                "title TEXT, body TEXT, metadata TEXT, domain TEXT)")
    for cid, (key, body) in enumerate(pages, 1):
        con.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?)",
                    (cid, f"https://www.sidefx.com/docs/houdini/{key}.md", key, body, "{}", "docs"))
    con.commit()
    con.close()
    return root


_PAGES = [
    ("nodes/sop/labs--widget-1.0", "Labs Widget\nLabs Widget\n# Labs Widget\n\nMakes widgets."),
    ("nodes/obj/geo", "Geometry\n\nHolds geometry. More."),
    ("nodes/dop/widgetsolver", "Widget Solver\nParameters\n## Parameters\n\nSize:\n    How big."),
]

_TYPES = [
    {"category": "Sop", "name": "labs::widget::1.0", "hda": True,
     "help_url": "operator:Sop/widget?namespace=labs&version=1.0",
     "embedded_help": '= Labs Widget =\n\n""" Makes widgets. """'},
    {"category": "Object", "name": "geo", "hda": False,
     "help_url": "operator:Object/geo", "embedded_help": None},
    {"category": "Data", "name": "highpass", "hda": True,
     "help_url": "operator:Data/highpass?scopeop=cop/filterfrequencies", "embedded_help": None},
]


def test_sweep_counts_pages_and_the_pages_node_types_reach(tmp_path, monkeypatch):
    monkeypatch.setenv(SL.ROOT_ENV, str(_library(tmp_path, _PAGES)))
    listed = tmp_path / "types.json"
    listed.write_text(json.dumps({"houdini": "22.0.400", "types": _TYPES}), encoding="utf-8")
    out = tmp_path / "report.json"
    assert _script("sweep_identify_summaries").main(["--types", str(listed), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["library"]["counts"] == {"prose": 2, "unknown": 1}
    assert report["library"]["unknown"] == ["nodes/dop/widgetsolver"]
    reach = report["reachable"]
    assert reach["types_without_a_page"] == 1                  # the scoped Data type
    assert reach["pages"]["counts"] == {"prose": 2}
    assert reach["hda_help"]["counts"] == {"prose": 1}


def test_sweep_exits_1_when_markup_reaches_a_what_line(tmp_path, monkeypatch):
    monkeypatch.setenv(SL.ROOT_ENV, str(_library(tmp_path, _PAGES)))
    monkeypatch.setattr(LIB, "summary_text", lambda body: "Makes **bold** widgets.")
    assert _script("sweep_identify_summaries").main([]) == 1


def test_sweep_exits_2_when_the_library_cannot_be_read(tmp_path, monkeypatch):
    monkeypatch.setenv(SL.ROOT_ENV, str(tmp_path / "missing"))
    assert _script("sweep_identify_summaries").main([]) == 2


class _FakeError(Exception):
    pass


def _fake_hou():
    def node_type(url, help_text=None):
        definition = None
        if help_text is not None:
            definition = types.SimpleNamespace(embeddedHelp=lambda: help_text)
        return types.SimpleNamespace(defaultHelpUrl=lambda: url, definition=lambda: definition)

    def broken():
        raise _FakeError("no help URL")

    sop = types.SimpleNamespace(nodeTypes=lambda: {
        "labs::widget::1.0": node_type("operator:Sop/widget?namespace=labs&version=1.0",
                                       '""" Makes widgets. """'),
        "box": node_type("operator:Sop/box"),
        "odd": types.SimpleNamespace(defaultHelpUrl=broken, definition=lambda: None),
    })
    return types.SimpleNamespace(Error=_FakeError, nodeTypeCategories=lambda: {"Sop": sop},
                                 applicationVersionString=lambda: "22.0.400")


def test_probe_writes_the_rows_the_sweep_reads(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "hou", _fake_hou())
    out = tmp_path / "types.json"
    counts = _script("probe_node_help_urls").dump(str(out))
    assert counts == {"types": 3, "hda": 1, "with_help": 1, "errors": 1, "out": str(out)}
    listed = json.loads(out.read_text(encoding="utf-8"))
    assert listed["houdini"] == "22.0.400"
    widget = next(row for row in listed["types"] if row["name"] == "labs::widget::1.0")
    assert set(widget) == {"category", "name", "help_url", "hda", "embedded_help"}
    reach = _script("sweep_identify_summaries").sweep_types(
        listed["types"], {"nodes/sop/labs--widget-1.0": "Labs Widget\n\nMakes widgets."})
    assert reach["pages"]["counts"] == {"prose": 1}
    assert reach["hda_help"]["counts"] == {"prose": 1}
