"""Source-only rhythm inventory; never import the panel, Qt, or the host.

Counts are source sites, not runtime widgets. Hex sites deliberately include
comments and token-valued fallbacks outside designsystem/. Expressions stay
unevaluated. A successful process exit is NOT an acceptance verdict: consumers
must inspect measurement_complete/errors; LEVER owns enforcement.
"""

from __future__ import annotations

import argparse
import ast
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tokenize


REPO = Path(__file__).resolve().parents[2]
SPACING = {"setSpacing", "setContentsMargins"}
GRID_SPACING = {"setHorizontalSpacing", "setVerticalSpacing"}
HEX = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-zA-Z_])")
EXEMPT = re.compile(r"#\s*rhythm-exempt:\s*(.*)")

# Source selectors, not assertions of runtime visibility. Re-resolved on every
# scan: removed builders become UNKNOWN, and an absent recall module is ABSENT.
CAMERA = (
    ("profile_tab_strip", "Profile tab strip", "row", {
        "synapse_panel.py": ["SynapsePanel._build_mode_bar"],
    }),
    ("header_ribbon", "Header/ribbon", "group / label", {
        "synapse_panel.py": ["SynapsePanel._build_rail", "SynapsePanel._build_context_ribbon"],
    }),
    ("chat_transcript", "Chat transcript", "group / label", {
        "synapse_panel.py": ["SynapsePanel._build_converse", "SynapsePanel._build_direct_face"],
        "chat_display.py": ["ChatDisplay"],
    }),
    ("verb_rail", "Verb rail", "group / label", {
        "synapse_panel.py": ["SynapsePanel._build_act", "SynapsePanel._verb"],
    }),
    ("recall_result", "Recall result", "card / tag", {"recall_card.py": [""]}),
    ("token_face", "TOKEN face", "parm_row / group / label", {
        "synapse_panel.py": ["SynapsePanel._build_token_face"],
        "face_token.py": ["FaceToken", "TokenField"],
        "token_readout.py": [""],
    }),
)


def _literal(node):
    try:
        value = ast.literal_eval(node)
        json.dumps(value)
        return value
    except (ValueError, TypeError, SyntaxError):
        return {"expression": ast.unparse(node)}


def scan_source(source, path="fixture.py"):
    """Inventory a source string without importing or evaluating its contents."""
    result = {"path": path, "sha256": hashlib.sha256(source.encode()).hexdigest(),
              "errors": [], "spacing": [], "grid_spacing": [],
              "inline_styles": [], "object_names": [], "layouts": [],
              "scopes": [], "hex_sites": [], "exempt_tags": []}
    lines = source.splitlines()
    for match in HEX.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        result["hex_sites"].append({"line": line,
            "column": match.start() - source.rfind("\n", 0, match.start()),
            "value": match.group().lower()})
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                match = EXEMPT.search(token.string)
                if match:
                    result["exempt_tags"].append({"line": token.start[0],
                        "reason": match.group(1).strip()})
    except (tokenize.TokenError, IndentationError) as exc:
        result["errors"].append(str(exc))
    tags = {tag["line"]: tag["reason"] for tag in result["exempt_tags"]}
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        result["errors"].append(str(exc))
        tree = ast.Module(body=[], type_ignores=[])

    class Inventory(ast.NodeVisitor):
        def __init__(self):
            self.scope = []

        def visit_scope(self, node):
            self.scope.append(node.name)
            result["scopes"].append({"scope": ".".join(self.scope),
                "line": node.lineno, "end_line": node.end_lineno})
            self.generic_visit(node)
            self.scope.pop()

        visit_ClassDef = visit_scope
        visit_FunctionDef = visit_scope
        visit_AsyncFunctionDef = visit_scope

        def visit_Assign(self, node):
            value = node.value
            if isinstance(value, ast.Call):
                constructor = ast.unparse(value.func)
                if constructor.split(".")[-1] in {
                    "QVBoxLayout", "QHBoxLayout", "QGridLayout", "QFormLayout",
                    "QStackedLayout", "QBoxLayout",
                }:
                    result["layouts"].append({"line": node.lineno,
                        "scope": ".".join(self.scope), "constructor": constructor,
                        "receiver": ast.unparse(node.targets[0]),
                        "owner": ast.unparse(value.args[0]) if value.args else "UNKNOWN"})
            self.generic_visit(node)

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute):
                method = node.func.attr
                bucket = ("spacing" if method in SPACING else
                          "grid_spacing" if method in GRID_SPACING else
                          {"setStyleSheet": "inline_styles", "setObjectName": "object_names"}.get(method))
                if bucket:
                    site = {"line": node.lineno, "end_line": node.end_lineno,
                            "scope": ".".join(self.scope), "method": method,
                            "receiver": ast.unparse(node.func.value),
                            "arguments": [ast.unparse(arg) for arg in node.args],
                            "values": [_literal(arg) for arg in node.args],
                            "keywords": {arg.arg or "**": ast.unparse(arg.value) for arg in node.keywords},
                            "source": ast.get_source_segment(source, node),
                            "exempt_reason": tags.get(node.lineno)}
                    if bucket == "object_names":
                        site["name"] = (node.args[0].value if node.args and
                            isinstance(node.args[0], ast.Constant) and
                            isinstance(node.args[0].value, str) else None)
                    result[bucket].append(site)
            self.generic_visit(node)

    Inventory().visit(tree)
    for site in result["hex_sites"]:
        site["exempt_reason"] = tags.get(site["line"])
        site["source"] = lines[site["line"] - 1].strip()
    result["counts"] = summarize([result])
    return result


def summarize(files):
    names = [site["name"] for f in files for site in f["object_names"] if site["name"] is not None]
    ds_names = [name for name in names if name.startswith("Ds")]
    return {
        "files": len(files),
        "spacing_sites": sum(len(f["spacing"]) for f in files),
        "grid_spacing_sites": sum(len(f["grid_spacing"]) for f in files),
        "inline_stylesheet_sites": sum(len(f["inline_styles"]) for f in files),
        "hex_raw_sites": sum(len(f["hex_sites"]) for f in files),
        "hex_distinct_values": sorted({s["value"] for f in files for s in f["hex_sites"]}),
        "hex_distinct_count": len({s["value"] for f in files for s in f["hex_sites"]}),
        "object_name_sites": sum(len(f["object_names"]) for f in files),
        "object_names": sorted(set(names)),
        "ds_object_name_sites": len(ds_names),
        "ds_distinct_names": sorted(set(ds_names)),
        "ds_distinct_count": len(set(ds_names)),
        "exempt_tags": sum(len(f["exempt_tags"]) for f in files),
    }


def density_rules(source):
    """Read QSS string templates via AST, substituting opaque expression slots.

    Count rule blocks separately from comma-separated selectors. No stylesheet
    function or token expression is executed. Source line points to the first
    selector; each property value is an unevaluated template.
    """
    rules = []
    tree = ast.parse(source)
    strings = [n for n in ast.walk(tree) if isinstance(n, ast.JoinedStr)]
    # Literal-only QSS templates are supported too; exclude JoinedStr children.
    children = {id(v) for n in strings for v in n.values}
    strings += [n for n in ast.walk(tree) if isinstance(n, ast.Constant)
                and isinstance(n.value, str) and id(n) not in children]
    for node in strings:
        cursor = node.lineno - 1
        template = ("".join(v.value if isinstance(v, ast.Constant) else "EXPR"
                            for v in node.values) if isinstance(node, ast.JoinedStr) else node.value)
        template = re.sub(r"/\*.*?\*/", "", template, flags=re.S)
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", template):
            selectors = [s.strip() for s in match[1].split(",")]
            selectors = [s for s in selectors if re.search(r'\[density\s*=\s*[\"\']', s)]
            if not selectors:
                continue
            source_lines = source.splitlines()
            line = next((i + 1 for i in range(cursor, node.end_lineno)
                         if selectors[0] in source_lines[i]), node.lineno)
            cursor = line
            properties = re.findall(r"([\w-]+)\s*:", match[2])
            rules.append({"line": line, "selectors": selectors,
                "properties": properties, "body_template": match[2].strip()})
    return {"rule_blocks": len(rules),
            "selectors": sum(len(r["selectors"]) for r in rules),
            "margin_rule_blocks": sum(any(p.startswith("margin") for p in r["properties"]) for r in rules),
            "padding_rule_blocks": sum(any(p.startswith("padding") for p in r["properties"]) for r in rules),
            "rules": rules}


def camera_regions(files):
    by_name = {f["path"].removeprefix("python/synapse/panel/"): f for f in files}
    regions = []
    for key, title, role, selectors in CAMERA:
        entry = {"id": key, "region": title, "target_role": role,
                 "status": "VERIFIED_STATIC", "owners": [], "missing_selectors": []}
        for filename, scopes in selectors.items():
            f = by_name.get(filename)
            if f is None:
                entry["missing_selectors"].append(filename)
                continue
            for scope in scopes:
                anchors = [s for s in f["scopes"] if s["scope"] == scope]
                if scope and not anchors:
                    entry["missing_selectors"].append(filename + ":" + scope)
                    continue
                def selected(s):
                    return not scope or s["scope"] == scope or s["scope"].startswith(scope + ".")
                entry["owners"].append({"path": f["path"], "scope": scope or "<module>",
                    "line": anchors[0]["line"] if anchors else 1,
                    **{bucket: [s for s in f[bucket] if selected(s)] for bucket in
                       ("spacing", "grid_spacing", "inline_styles", "object_names", "layouts")}})
        if entry["missing_selectors"]:
            entry["status"] = "ABSENT" if key == "recall_result" and not entry["owners"] else "UNKNOWN"
        entry["reachability"] = {
            "named": any(o["object_names"] for o in entry["owners"]),
            "styled_inline": any(o["inline_styles"] for o in entry["owners"]),
            "layout_owned": any(o["layouts"] for o in entry["owners"]),
            "basis": "Direct source sites in selected scopes; inherited/factory names and runtime visibility are not inferred.",
        }
        if entry["status"] != "VERIFIED_STATIC":
            entry["reachability"].update({k: "UNKNOWN" for k in ("named", "styled_inline", "layout_owned")})
        regions.append(entry)
    return regions


def census(panel_dir):
    panel_dir = Path(panel_dir)
    report = {"schema_version": 1, "date": date.today().isoformat(),
              "measurement_complete": True, "errors": [], "files": []}
    paths = sorted(panel_dir.rglob("*.py")) if panel_dir.is_dir() else []
    if not paths:
        report["errors"].append("No Python sources found in panel directory")
    ds_files = []
    for path in paths:
        relative = path.relative_to(panel_dir).as_posix()
        try:
            source = path.read_text(encoding="utf-8-sig")
            label = "python/synapse/panel/" + relative
            f = scan_source(source, label)
            report["errors"].extend(label + ": " + e for e in f["errors"])
            if "designsystem" in Path(relative).parts:
                ds_files.append(f)
            else:
                report["files"].append(f)
            if relative == "designsystem/qss.py":
                report["density_qss"] = {"path": label, **density_rules(source)}
        except (OSError, UnicodeError, SyntaxError) as exc:
            report["errors"].append(relative + ": " + str(exc))
    report["measurement_complete"] = not report["errors"]
    report["totals"] = summarize(report["files"])
    report["designsystem_object_names"] = [
        {"path": f["path"], **site} for f in ds_files for site in f["object_names"]]
    combined = summarize(report["files"] + ds_files)
    report["panel_including_designsystem_names"] = {
        k: v for k, v in combined.items() if k.startswith("ds_") or k.startswith("object_name")}
    report["runtime_ds_widget_count"] = "UNKNOWN: source sites may execute zero, one, or many times"
    report.setdefault("density_qss", {"status": "UNKNOWN", "reason": "designsystem/qss.py absent"})
    report["camera_regions"] = camera_regions(report["files"])
    return report


def markdown(report):
    t = report["totals"]
    rows = ["# Panel rhythm census", "", "Source-only; no host or Qt imports. "
            "Counts are source sites, including dormant modules, not runtime widget instances.", "",
            f"Measurement complete: **{report['measurement_complete']}**. Date: {report['date']}.", "",
            f"Totals: **{t['spacing_sites']}** spacing; **{t['inline_stylesheet_sites']}** inline sheets; "
            f"**{t['hex_raw_sites']}** raw hex / **{t['hex_distinct_count']}** distinct; "
            f"**{t['exempt_tags']}** exemption tags. Additional grid-spacing sites: **{t['grid_spacing_sites']}**.", "",
            "Hex means every six-digit source occurrence outside designsystem/, including comments and "
            "token-valued fallbacks; case folded. Calls are AST calls (comments/string lookalikes excluded). "
            "Exemptions are Python comments only, associated with sites on their starting line. "
            "Values preserve expressions without evaluation. See JSON for every site, owner, line and hash.", "",
            "| File (under python/synapse/panel/) | Spacing | Inline sheets | Hex raw / distinct | Ds sites / names | Exempt |",
            "|---|---:|---:|---:|---:|---:|"]
    for f in report["files"]:
        c = f["counts"]
        rows.append(f"| {f['path'].removeprefix('python/synapse/panel/')} | {c['spacing_sites']} | "
                    f"{c['inline_stylesheet_sites']} | {c['hex_raw_sites']} / {c['hex_distinct_count']} | "
                    f"{c['ds_object_name_sites']} / {c['ds_distinct_count']} | {c['exempt_tags']} |")
    combined = report["panel_including_designsystem_names"]
    rows += ["", f"Outside designsystem/: {t['ds_object_name_sites']} Ds naming sites, {t['ds_distinct_count']} names. "
             f"Including designsystem/: {combined['ds_object_name_sites']} sites, {combined['ds_distinct_count']} names. "
             f"Runtime Ds widget count: {report['runtime_ds_widget_count']}.", "",
             "## Density QSS (source templates)", "", "```json", json.dumps(report["density_qss"], indent=2), "```", "",
             "## Camera reachability", "", "Flags describe direct source evidence in the listed scopes, not every child. "
             "Factory/inherited names require the region map; ABSENT/UNKNOWN never implies a clean camera path.", "",
             "| Region | Status | Named | Inline styled | Layout owned | Owners |", "|---|---|---|---|---|---|"]
    for region in report["camera_regions"]:
        r = region["reachability"]
        owners = "; ".join(f"{o['path']}:{o['line']} {o['scope']}" for o in region["owners"]) or "ABSENT"
        rows.append(f"| {region['region']} | {region['status']} | {r['named']} | {r['styled_inline']} | {r['layout_owned']} | {owners} |")
    if report["errors"]:
        rows += ["", "## Measurement errors", "", *report["errors"]]
    return "\n".join(rows) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default = REPO / "harness/panel_pd/runs" / date.today().isoformat()
    parser.add_argument("--panel-dir", type=Path, default=REPO / "python/synapse/panel")
    parser.add_argument("--json", type=Path, default=default / "rhythm_census.json")
    parser.add_argument("--md", type=Path, default=default / "rhythm_census.md")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 0
    try:
        report = census(args.panel_dir)
        write_errors = []
        for path, content in ((args.json, json.dumps(report, indent=2) + "\n"), (args.md, markdown(report))):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            except OSError as exc:
                write_errors.append(str(exc))
                print(f"UNKNOWN: cannot write {path}: {exc}", file=sys.stderr)
        print(json.dumps({"measurement_complete": report["measurement_complete"],
                          "outputs_complete": not write_errors, "write_errors": write_errors,
                          "totals": report["totals"], "errors": report["errors"]}))
    except Exception as exc:
        print(f"UNKNOWN: census failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
