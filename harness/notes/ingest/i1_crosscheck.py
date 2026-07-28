"""I1 -- the 20-node cross-check. Runs under ``hython`` on Houdini 22.0.368.

    "$HFS/bin/hython" harness/notes/ingest/i1_crosscheck.py

Takes 20 ingested entries, INSTANTIATES each node on the live build, and
compares the documented parameter surface against ``node.parms()`` --
the brief's wording, taken literally, because instantiating is the only way to
see the parameter names a node actually carries rather than the templates its
type declares.

Reports the agreement count on BOTH axes, separately and never averaged:

    LABEL  the join key (I0-F3, R97) -- documented label vs live parm labels
    #id    EVIDENCE, not the key -- documented internal name vs live parm names,
           tried against parmTuples() FIRST (I0: worth 2-8 points, costs nothing)

Selection is DETERMINISTIC: evenly-spaced picks through each context's sorted
ingested list, weighted 10 cop (all drawn from the 161 new Copernicus nodes) /
6 lop / 4 cop2. No seed, no shuffle -- a second run on this build picks the same
twenty, so the agreement count is a measurement rather than a draw.

PRODUCER: this file -> harness/notes/ingest/_i1_crosscheck.json
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import hou

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "h22_node_corpus.json"
OUT = HERE / "_i1_crosscheck.json"

PLAN = [("cop", 10, True), ("lop", 6, False), ("cop2", 4, False)]


def norm_label(s: str) -> str:
    """Byte-for-byte the extractor's normaliser. Duplicated rather than imported
    because this file runs under hython and must not drag the archive reader --
    and because a cross-check that shares the thing under test is not a check.
    """
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("…", "...")
    s = re.sub(r"\.\.\.$", "", s.strip())
    s = re.sub(r"\s+", " ", s)
    return s.strip().casefold()


def pick(entries: list, ctx: str, n: int, only_161: bool) -> list:
    pool = [e for e in entries if e["context"] == ctx and e["live_type_matched"]
            and (e["new_in_22"] if only_161 else True)
            and e["live_parm_tuples"]]
    pool.sort(key=lambda e: e["help_key"])
    if len(pool) <= n:
        return pool
    step = len(pool) / float(n)
    return [pool[int(i * step)] for i in range(n)]


def make_parent(ctx: str, holders: dict):
    if ctx == "lop":
        return hou.node("/stage")
    if ctx == "cop":
        if "cop" not in holders:
            holders["cop"] = hou.node("/obj").createNode("copnet", "i1_xc_cop")
        return holders["cop"]
    if "cop2" not in holders:
        img = hou.node("/img") or hou.node("/").createNode("imgnet", "img")
        holders["cop2"] = img.createNode("img", "i1_xc_img")
    return holders["cop2"]


def main() -> int:
    build = hou.applicationVersionString()
    if build != "22.0.368":
        print("REFUSING: expected 22.0.368, running %s" % build)
        return 2
    if not CORPUS.exists():
        print("REFUSING: %s absent -- build the corpus first" % CORPUS)
        return 2

    blob = json.loads(CORPUS.read_text(encoding="utf-8"))
    entries = blob["entries"]

    chosen = []
    for ctx, n, only161 in PLAN:
        chosen.extend(pick(entries, ctx, n, only161))

    holders: dict = {}
    rows = []
    tot = {"documented_params": 0, "label_agree": 0, "id_present": 0,
           "id_agree_tuple": 0, "id_agree_parm": 0, "channels_present": 0,
           "channels_agree": 0}

    for e in chosen:
        row = {"help_key": e["help_key"], "context": e["context"],
               "live_type": e["live_type"], "new_in_22": e["new_in_22"]}
        try:
            parent = make_parent(e["context"], holders)
            node = parent.createNode(e["live_type"])
            live_parms = [p.name() for p in node.parms()]
            live_parm_labels = {norm_label(p.parmTemplate().label()) for p in node.parms()}
            live_tuples = [t.name() for t in node.parmTuples()]
            live_tuple_labels = {norm_label(t.parmTemplate().label())
                                 for t in node.parmTuples()}
            live_labels = live_parm_labels | live_tuple_labels
            sp, st = set(live_parms), set(live_tuples)

            doc = e["parameters"]
            lab_ok = sum(1 for p in doc if p["label_norm"] in live_labels)
            id_present = sum(1 for p in doc if p["ids"])
            id_t = sum(1 for p in doc if any(i in st for i in p["ids"]))
            id_p = sum(1 for p in doc if any(i in sp for i in p["ids"]))
            ch_present = sum(1 for p in doc if p["channels"])
            ch_ok = sum(1 for p in doc if any(c in sp or c in st for c in p["channels"]))

            row.update({
                "documented_params": len(doc),
                "live_parms": len(live_parms),
                "live_parm_tuples": len(live_tuples),
                "label_agree": lab_ok,
                "label_agree_rate": round(lab_ok / len(doc), 4) if doc else None,
                "id_present": id_present,
                "id_agree_tuple_first": id_t,
                "id_agree_parm_level": id_p,
                "channels_present": ch_present,
                "channels_agree": ch_ok,
                "documented_not_live": sorted(
                    p["label"] for p in doc if p["label_norm"] not in live_labels)[:10],
                "ok": True,
            })
            for k in tot:
                if k == "id_agree_tuple":
                    tot[k] += id_t
                elif k == "id_agree_parm":
                    tot[k] += id_p
                elif k == "label_agree":
                    tot[k] += lab_ok
                elif k == "documented_params":
                    tot[k] += len(doc)
                elif k == "id_present":
                    tot[k] += id_present
                elif k == "channels_present":
                    tot[k] += ch_present
                elif k == "channels_agree":
                    tot[k] += ch_ok
            node.destroy()
        except Exception as exc:
            row.update({"ok": False, "error": str(exc)})
        rows.append(row)

    # ---- controls. Law 1: without these, "high agreement" is unfalsifiable.
    controls = []
    live_ref = None
    try:
        parent = make_parent("cop", holders)
        n = parent.createNode("chromakey")
        live_ref = {norm_label(p.parmTemplate().label()) for p in n.parms()}
        fabricated = norm_label("Unobtainium Threshold")
        controls.append({
            "id": "XC1", "class": "NEGATIVE",
            "asserts": "a fabricated label does NOT match a live parm label",
            "fails_if": "the label matcher says yes to everything, making every "
                        "agreement count above meaningless",
            "got": fabricated in live_ref, "expected": False,
            "pass": (fabricated in live_ref) is False,
        })
        real = norm_label("Screen Color")
        controls.append({
            "id": "XC2", "class": "POSITIVE",
            "asserts": "a known-real label DOES match on the same node",
            "fails_if": "the matcher says no to everything, which would also "
                        "produce a stable-looking number",
            "got": real in live_ref, "expected": True, "pass": real in live_ref,
        })
        n.destroy()
    except Exception as exc:                                       # pragma: no cover
        controls.append({"id": "XC-ERR", "error": str(exc), "pass": False})

    for h in holders.values():
        try:
            h.destroy()
        except Exception:
            pass

    ok_rows = [r for r in rows if r.get("ok")]
    out = {
        "schema": "i1_crosscheck/v1",
        "truth_tier": "VERIFIED-RUNTIME",
        "build": build,
        "producer": "harness/notes/ingest/i1_crosscheck.py (hython)",
        "method": "20 ingested entries, deterministically selected (evenly-spaced "
                  "through each context's sorted ingested list; 10 cop drawn from "
                  "the 161, 6 lop, 4 cop2). Each node INSTANTIATED on the live "
                  "build; documented parameters compared against node.parms() and "
                  "node.parmTuples().",
        "axis_rule": "LABEL and #id are reported separately and never averaged. "
                     "Label is the join key (I0-F3); #id is evidence.",
        "nodes_attempted": len(rows),
        "nodes_instantiated": len(ok_rows),
        "agreement": {
            "documented_parameters": tot["documented_params"],
            "label_agreement_count": tot["label_agree"],
            "label_agreement_rate": round(
                tot["label_agree"] / tot["documented_params"], 4)
            if tot["documented_params"] else None,
            "records_carrying_an_id": tot["id_present"],
            "id_agreement_count_tuple_first": tot["id_agree_tuple"],
            "id_agreement_count_parm_level": tot["id_agree_parm"],
            "id_agreement_rate_of_all_records": round(
                tot["id_agree_tuple"] / tot["documented_params"], 4)
            if tot["documented_params"] else None,
            "records_carrying_channels": tot["channels_present"],
            "channels_agreement_count": tot["channels_agree"],
        },
        "controls": controls,
        "controls_passed": sum(1 for c in controls if c.get("pass")),
        "controls_total": len(controls),
        "nodes": rows,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    a = out["agreement"]
    print("wrote %s" % OUT)
    print("instantiated %d/%d nodes" % (out["nodes_instantiated"], out["nodes_attempted"]))
    print("documented parameters      %d" % a["documented_parameters"])
    print("LABEL agreement            %d  (%.1f%%)   <- the join key"
          % (a["label_agreement_count"], 100.0 * (a["label_agreement_rate"] or 0)))
    print("#id  agreement (tuple-1st) %d  (%.1f%% of all records)   <- evidence"
          % (a["id_agreement_count_tuple_first"],
             100.0 * (a["id_agreement_rate_of_all_records"] or 0)))
    print("#id  agreement (parm-lvl)  %d" % a["id_agreement_count_parm_level"])
    print("#channels agreement        %d of %d carrying"
          % (a["channels_agreement_count"], a["records_carrying_channels"]))
    print("controls %d/%d" % (out["controls_passed"], out["controls_total"]))
    for r in rows:
        if not r.get("ok"):
            print("  FAILED %s: %s" % (r["help_key"], r.get("error")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
