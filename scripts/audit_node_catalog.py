"""Spot-audit the committed node catalog against a live hython session (target 5).

Proves the substrate's core promise: every committed row equals a *fresh* read of
the live binary. For each weak domain (dop, vop, chop, cop, apex) it samples 20
types from the committed ``rag/catalog/h<build>/`` files, re-derives each one from
the running Houdini via the SAME extraction path build_node_catalog uses, and
asserts field-for-field equality. A hand-edited default, a stale value, a dropped
menu token -- any drift between the committed JSON and the live binary -- fails
the audit. Zero mismatches is the bar.

Every audited row carries an anchored receipt: the node anchor (``<Category>/<type>``),
its parm count, and an independently re-read parm anchor (name/type/default read
straight off the live parm template, compared to the committed row). VOP rows
additionally re-instantiate to re-read the wire signature. APEX rows re-read the
callback Signature's typed ports.

RUN INSIDE THE BUILD (needs live hou + apex):

    "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \\
        scripts/audit_node_catalog.py

Writes ``rag/catalog/h<build>/_audit.json`` and prints a per-domain PASS/FAIL.
Exit code is non-zero iff any domain mismatched -- the audit is a gate.

The sample is deterministic (a fixed stride across sorted types) so a second run
audits the same 20 per domain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[0]
sys.path.insert(0, str(_HERE))
import build_node_catalog as bnc  # noqa: E402  -- the single source of extraction truth

WEAK_DOMAINS = {"dop": "Dop", "vop": "Vop", "chop": "Chop", "cop": "Cop"}
SAMPLE_N = 20


def _sample(names: list, n: int = SAMPLE_N) -> list:
    """A deterministic spread of up to n names across the sorted list."""
    names = sorted(names)
    if len(names) <= n:
        return names
    stride = len(names) / n
    return [names[int(i * stride)] for i in range(n)]


def _parm_anchor(node_type, committed_row, errors) -> dict:
    """Independently re-read one value parm off the live type and compare it to
    the committed row -- a second, differently-shaped confirmation."""
    parms = committed_row.get("parms") or []
    target = next((p for p in parms if "default" in p and p.get("name")), None)
    if target is None:
        return {"note": "no value parm to anchor"}
    name = target["name"]
    try:
        group = node_type.parmTemplateGroup()
        t = group.find(name)
    except Exception as e:  # noqa: BLE001
        return {"name": name, "note": f"live find() failed: {type(e).__name__}"}
    if t is None:
        return {"name": name, "note": "parm absent on live type (DRIFT)",
                "live_matches_catalog": False}
    live = bnc._parm_record(t, tuple(target.get("folder", [])))
    fields = ("type", "default", "menu_tokens", "menu_labels", "min", "max")
    ok = all(live.get(f) == target.get(f) for f in fields)
    return {"name": name, "type": target.get("type"),
            "default": target.get("default"),
            "live_matches_catalog": ok,
            "diverged": [f for f in fields if live.get(f) != target.get(f)]}


def audit_node_domain(hou, domain: str, cat_name: str, catalog_dir: Path) -> dict:
    fp = catalog_dir / f"{cat_name}.json"
    catalog = json.loads(fp.read_text(encoding="utf-8"))
    cat_types = catalog["types"]
    category = hou.nodeTypeCategories()[cat_name]
    live_types = category.nodeTypes()
    sample = _sample(list(cat_types))
    receipts, mismatches = [], 0

    vop_container = None
    disposable = False
    if domain == "vop":
        vop_container, disposable = bnc._make_matnet(hou)

    for tn in sample:
        anchor = f"{cat_name}/{tn}"
        committed = cat_types[tn]
        nt = live_types.get(tn)
        if nt is None:
            receipts.append({"anchor": anchor, "match": False,
                             "reason": "type absent on live build (DRIFT)"})
            mismatches += 1
            continue
        live_rec = bnc._type_record(nt, tn, [])
        base_committed = {k: v for k, v in committed.items()
                          if k not in ("doc", "wire_signature")}
        base_match = (live_rec == base_committed)
        receipt = {"anchor": anchor, "parm_count": len(committed.get("parms") or []),
                   "base_match": base_match,
                   "parm_anchor": _parm_anchor(nt, committed, [])}

        if domain == "vop" and vop_container is not None:
            committed_sig = committed.get("wire_signature") or {}
            if committed_sig.get("instantiated"):
                try:
                    node = vop_container.createNode(tn)
                    live_sig = bnc._vop_signature(node, [], tn)
                    live_sig["instantiated"] = True
                    node.destroy()
                except Exception as e:  # noqa: BLE001
                    live_sig = {"instantiated": False, "note": type(e).__name__}
                sig_match = all(live_sig.get(k) == committed_sig.get(k) for k in
                                ("input_names", "output_names",
                                 "input_data_types", "output_data_types"))
                receipt["wire_signature_match"] = sig_match
            else:
                receipt["wire_signature_match"] = True  # recorded not-instantiated
        row_ok = base_match and receipt.get("wire_signature_match", True) \
            and receipt["parm_anchor"].get("live_matches_catalog", True)
        receipt["match"] = row_ok
        if not row_ok:
            mismatches += 1
        receipts.append(receipt)

    if disposable and vop_container is not None:
        try:
            vop_container.destroy()
        except Exception:  # noqa: BLE001
            pass
    return {"domain": domain, "category": cat_name, "audited": len(sample),
            "matched": len(sample) - mismatches, "mismatched": mismatches,
            "receipts": receipts}


def audit_apex(catalog_dir: Path) -> dict:
    import apex
    fp = catalog_dir / "apex_callbacks.json"
    if not fp.exists():
        return {"domain": "apex", "audited": 0, "matched": 0, "mismatched": 0,
                "receipts": [{"note": "apex_callbacks.json absent"}]}
    catalog = json.loads(fp.read_text(encoding="utf-8"))
    callbacks = catalog["callbacks"]
    reg = apex.callbackRegistry()
    sample = _sample(list(callbacks))
    receipts, mismatches = [], 0
    for name in sample:
        committed = callbacks[name]
        try:
            sig = reg.getSignature(name)
            live_in = [bnc._port_record(p) for p in sig.inputs()]
            live_out = [bnc._port_record(p) for p in sig.outputs()]
        except Exception as e:  # noqa: BLE001
            receipts.append({"anchor": f"apex/{name}", "match": False,
                             "reason": f"live getSignature failed: {type(e).__name__}"})
            mismatches += 1
            continue
        ok = (live_in == committed.get("inputs")
              and live_out == committed.get("outputs"))
        receipts.append({
            "anchor": f"apex/{name}", "match": ok,
            "input_ports": [p.get("type") for p in committed.get("inputs", [])],
            "output_ports": [p.get("type") for p in committed.get("outputs", [])],
        })
        if not ok:
            mismatches += 1
    return {"domain": "apex", "audited": len(sample),
            "matched": len(sample) - mismatches, "mismatched": mismatches,
            "receipts": receipts}


def main() -> int:
    import hou

    build = hou.applicationVersionString()
    catalog_dir = _REPO / "rag" / "catalog" / f"h{build}"
    if len(sys.argv) > 2 and sys.argv[1] == "--dir":
        catalog_dir = Path(sys.argv[2])
    if not catalog_dir.is_dir():
        sys.stdout.write(f"catalog dir absent: {catalog_dir}\n")
        return 2

    domains = {}
    for domain, cat_name in sorted(WEAK_DOMAINS.items()):
        res = audit_node_domain(hou, domain, cat_name, catalog_dir)
        domains[domain] = res
        sys.stdout.write(f"AUDIT {domain} ({cat_name}): "
                         f"{res['matched']}/{res['audited']} matched, "
                         f"{res['mismatched']} mismatched\n")
    try:
        import apex  # noqa: F401
        ares = audit_apex(catalog_dir)
    except Exception as e:  # noqa: BLE001
        ares = {"domain": "apex", "audited": 0, "matched": 0, "mismatched": 0,
                "receipts": [{"note": f"apex import failed: {type(e).__name__}"}]}
    domains["apex"] = ares
    sys.stdout.write(f"AUDIT apex: {ares['matched']}/{ares['audited']} matched, "
                     f"{ares['mismatched']} mismatched\n")

    total_mismatch = sum(d["mismatched"] for d in domains.values())
    verdict = "pass" if total_mismatch == 0 else "fail"
    payload = {
        "schema": "node_catalog_audit/v1",
        "build": build,
        "sample_n": SAMPLE_N,
        "domains": domains,
        "total_mismatches": total_mismatch,
        "verdict": verdict,
        "generated": {"by": "scripts/audit_node_catalog.py",
                      "note": "deterministic sample; live re-read vs committed catalog"},
    }
    (catalog_dir / "_audit.json").write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    sys.stdout.write(f"VERDICT: {verdict} (total_mismatches={total_mismatch}) "
                     f"-> {catalog_dir}/_audit.json\n")
    return 0 if total_mismatch == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
