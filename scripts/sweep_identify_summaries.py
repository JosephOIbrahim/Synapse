"""Sweep the local SideFX library through Identify's What line (BP12 item 3).

Run from the repo root with system Python::

    python scripts/sweep_identify_summaries.py [--types TYPES.json] [--out REPORT.json]

The library is found the way SYNAPSE finds it: ``SYNAPSE_SIDEFX_CORPUS_ROOT``,
else ``.synapse/sidefx_library.json``. For every node page the sweep takes the
page-top chunk that ``help_summary`` serves (the earliest chunk per
``page_key``), turns it into a What line with ``library.summary_text``, and
counts the lines that are prose, honestly unknown, or carry help markup by
``library.RESIDUE``, the pattern the corpus-gated test also uses.

``--types`` reads the node-type list that ``scripts/probe_node_help_urls.py``
writes inside Houdini. The sweep then reports, the same way, the pages those
types reach through ``library.derive_help_keys`` and the HDA help texts in the
list.

Exit status: 0 when no What line carries markup, 1 when one does, 2 when the
library cannot be read. Nothing is written unless ``--out`` is given.
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from synapse.cognitive.tools import sidefx_library as SL  # noqa: E402
from synapse.identify import library as LIB  # noqa: E402

#: How many example keys a report line names.
_SHOWN = 12


def page_top_bodies() -> tuple[dict[str, str], str]:
    """Every node page's page-top chunk body by key, and the library generation."""
    root = SL._configured_root()
    if root is None:
        raise SL.LibraryUnavailable("no SideFX library is configured")
    pointer = SL._read_json(SL._within(root, root / "current.json"))
    database = SL._database_path(root, pointer.get("database"))
    bodies: dict[str, str] = {}
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as con:
        con.execute("PRAGMA query_only = ON")
        rows = con.execute("SELECT id, source_url, body FROM chunks WHERE domain = 'docs' "
                           "AND source_url LIKE '%nodes/%' ORDER BY id")
        for _cid, url, body in rows:
            key = SL.page_key(url)
            if key and key not in bodies:          # the earliest chunk is the page top
                bodies[key] = str(body or "").strip()
    return bodies, str(pointer.get("generation"))


def classify(line: str) -> str:
    """``prose``, ``unknown`` (no line) or ``markup`` (help markup reached the line)."""
    if not line:
        return "unknown"
    return "markup" if LIB.RESIDUE.search(line) else "prose"


def sweep(texts: dict[str, str]) -> dict:
    """Counts, and the keys behind any markup or unknown line, for {key: help text}."""
    counts: collections.Counter = collections.Counter()
    markup, unknown = [], []
    for key in sorted(texts):
        line = LIB.summary_text(texts[key])
        kind = classify(line)
        counts[kind] += 1
        if kind == "markup":
            markup.append({"key": key, "line": line[:160]})
        elif kind == "unknown":
            unknown.append(key)
    return {"texts": len(texts), "counts": dict(counts), "markup": markup, "unknown": unknown}


def sweep_types(types: list[dict], bodies: dict[str, str]) -> dict:
    """The pages a Houdini's node types reach, and the HDA help texts among them."""
    reached: dict[str, str] = {}
    helps: dict[str, str] = {}
    without_page = 0
    for row in types:
        keys = LIB.derive_help_keys(row.get("help_url") or "")
        page = next((key for key in keys if key in bodies), None)
        if page:
            reached[page] = bodies[page]
        else:
            without_page += 1
        if row.get("embedded_help"):
            helps[f"{row.get('category')}/{row.get('name')}"] = row["embedded_help"]
    return {"types": len(types), "types_without_a_page": without_page,
            "pages": sweep(reached), "hda_help": sweep(helps)}


def _line(label: str, report: dict) -> str:
    counts = report["counts"]
    text = (f"{label}: {report['texts']} (prose {counts.get('prose', 0)}, "
            f"unknown {counts.get('unknown', 0)}, markup {counts.get('markup', 0)})")
    for item in report["markup"][:_SHOWN]:
        text += f"\n  markup  {item['key']}: {item['line']}"
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--types", type=Path,
                        help="node-type list written by scripts/probe_node_help_urls.py")
    parser.add_argument("--out", type=Path, help="write the full report here as JSON")
    args = parser.parse_args(argv)
    try:
        bodies, generation = page_top_bodies()
    except (SL.LibraryUnavailable, OSError, ValueError, sqlite3.Error) as exc:
        print(f"sweep: the SideFX library cannot be read: {exc}", file=sys.stderr)
        return 2

    report = {"generation": generation, "library": sweep(bodies)}
    print(f"library generation {generation}")
    print(_line("node pages", report["library"]))
    if args.types:
        listed = json.loads(args.types.read_text(encoding="utf-8"))
        reach = sweep_types(listed.get("types", []), bodies)
        report["reachable"] = reach
        print(f"node types {reach['types']} from Houdini {listed.get('houdini', '?')}; "
              f"{reach['types_without_a_page']} reach no library page")
        print(_line("pages they reach", reach["pages"]))
        if reach["pages"]["unknown"]:
            print("  unknown: " + ", ".join(reach["pages"]["unknown"][:_SHOWN])
                  + (" ..." if len(reach["pages"]["unknown"]) > _SHOWN else ""))
        print(_line("HDA help texts", reach["hda_help"]))
    if args.out:
        args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    leaks = len(report["library"]["markup"])
    if "reachable" in report:
        leaks += len(report["reachable"]["pages"]["markup"]) + len(report["reachable"]["hda_help"]["markup"])
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
