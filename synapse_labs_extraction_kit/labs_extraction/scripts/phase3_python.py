#!/usr/bin/env python3
"""
Phase 3: Python Pattern Extraction

Analyzes Labs Python code for hou.* API usage patterns using AST analysis.
Extracts from scripts/, python_panels/, viewer_states/, and HDA callbacks.
"""

import ast
import json
import os
import re
from collections import defaultdict
from pathlib import Path

STAGING_ROOT = Path(os.environ.get("STAGING_ROOT", r"G:\SYNAPSE_STAGING\SideFXLabs"))
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))

SCRIPT_ROOTS = [
    STAGING_ROOT / "scripts",
    STAGING_ROOT / "python_panels",
    STAGING_ROOT / "viewer_states",
]
OTLS_ROOT = STAGING_ROOT / "otls"
OUTPUT = CORPUS_ROOT / "python_patterns"


class HouCallVisitor(ast.NodeVisitor):
    """AST visitor that extracts hou.* API call patterns."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.calls = []
        self.imports = []
        self.error_handling = []
        self.node_creation = []  # hou.node().createNode() patterns
        self.parm_setting = []   # .parm().set() patterns

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)

    def visit_Call(self, node):
        try:
            call_str = ast.unparse(node.func)
        except Exception:
            call_str = None

        if call_str:
            if "hou." in call_str:
                self.calls.append({
                    "call": call_str,
                    "line": node.lineno,
                })

            # Detect node creation patterns
            if "createNode" in call_str:
                # Try to extract node type argument
                if node.args:
                    try:
                        arg = ast.unparse(node.args[0])
                        self.node_creation.append({
                            "call": call_str,
                            "node_type": arg,
                            "line": node.lineno,
                        })
                    except Exception:
                        pass

            # Detect parameter setting patterns
            if ".set(" in call_str or ".parm(" in call_str:
                self.parm_setting.append({
                    "call": call_str,
                    "line": node.lineno,
                })

        self.generic_visit(node)

    def visit_Try(self, node):
        body_str = ast.dump(node)
        if "hou" in body_str:
            handlers = []
            for h in node.handlers:
                if h.type:
                    try:
                        handlers.append(ast.unparse(h.type))
                    except Exception:
                        handlers.append("?")
                else:
                    handlers.append("bare_except")

            self.error_handling.append({
                "handlers": handlers,
                "line": node.lineno,
            })
        self.generic_visit(node)


def analyze_file(filepath: Path) -> dict | None:
    """Analyze a single Python file for hou API patterns."""
    try:
        source = filepath.read_text(errors="replace")
        tree = ast.parse(source)
    except SyntaxError:
        return None
    except Exception:
        return None

    visitor = HouCallVisitor(str(filepath))
    visitor.visit(tree)

    if not visitor.calls:
        return None

    return {
        "file": str(filepath),
        "hou_calls": [c["call"] for c in visitor.calls],
        "call_count": len(visitor.calls),
        "imports": visitor.imports,
        "error_patterns": visitor.error_handling,
        "node_creation": visitor.node_creation,
        "parm_setting": visitor.parm_setting,
    }


def extract_viewer_state_patterns(vs_root: Path) -> list:
    """Extract viewer state interaction patterns."""
    patterns = []

    if not vs_root.exists():
        return patterns

    for py_file in vs_root.rglob("*.py"):
        try:
            source = py_file.read_text(errors="replace")
        except Exception:
            continue

        entry = {
            "file": py_file.name,
            "has_onMouseEvent": "onMouseEvent" in source,
            "has_onDraw": "onDraw" in source,
            "has_onGenerate": "onGenerate" in source,
            "has_onSelection": "onSelection" in source,
            "has_onMenuAction": "onMenuAction" in source,
            "drawable_types": list(set(re.findall(r'hou\.(\w*Drawable\w*)', source))),
            "gadget_types": list(set(re.findall(r'hou\.(\w*Gadget\w*)', source))),
        }

        if any(v for k, v in entry.items() if k.startswith("has_")):
            patterns.append(entry)

    return patterns


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    all_analyses = []
    hou_api_frequency = defaultdict(int)

    # Scan script directories
    for root in SCRIPT_ROOTS:
        if not root.exists():
            print(f"Skipping (not found): {root}")
            continue
        for py_file in root.rglob("*.py"):
            result = analyze_file(py_file)
            if result:
                all_analyses.append(result)
                for call in result["hou_calls"]:
                    hou_api_frequency[call] += 1

    # Scan Python inside HDAs (callbacks, PythonModule, etc.)
    if OTLS_ROOT.exists():
        hda_count = 0
        for py_file in OTLS_ROOT.rglob("*.py"):
            result = analyze_file(py_file)
            if result:
                result["context"] = "hda_callback"
                all_analyses.append(result)
                hda_count += 1
                for call in result["hou_calls"]:
                    hou_api_frequency[call] += 1

        # Also check PythonModule sections (no .py extension)
        for pm_file in OTLS_ROOT.rglob("PythonModule"):
            if pm_file.is_file():
                result = analyze_file(pm_file)
                if result:
                    result["context"] = "hda_python_module"
                    all_analyses.append(result)
                    hda_count += 1
                    for call in result["hou_calls"]:
                        hou_api_frequency[call] += 1

        print(f"Found {hda_count} Python files in HDAs")

    # Write full analysis
    (OUTPUT / "hou_api_patterns.json").write_text(
        json.dumps(all_analyses, indent=2), encoding="utf-8"
    )

    # Write frequency-sorted API usage
    sorted_api = sorted(hou_api_frequency.items(), key=lambda x: -x[1])
    (OUTPUT / "hou_api_frequency.json").write_text(
        json.dumps(dict(sorted_api), indent=2), encoding="utf-8"
    )

    # Write node creation patterns
    all_node_creation = []
    all_parm_setting = []
    for a in all_analyses:
        all_node_creation.extend(a.get("node_creation", []))
        all_parm_setting.extend(a.get("parm_setting", []))

    (OUTPUT / "node_creation_patterns.json").write_text(
        json.dumps(all_node_creation, indent=2), encoding="utf-8"
    )
    (OUTPUT / "parm_setting_patterns.json").write_text(
        json.dumps(all_parm_setting, indent=2), encoding="utf-8"
    )

    # Extract viewer state patterns
    vs_patterns = extract_viewer_state_patterns(STAGING_ROOT / "viewer_states")
    (OUTPUT / "viewer_state_patterns.json").write_text(
        json.dumps(vs_patterns, indent=2), encoding="utf-8"
    )

    # Summary
    print(f"Analyzed {len(all_analyses)} Python files with hou.* calls")
    print(f"Unique hou.* API calls: {len(hou_api_frequency)}")
    print(f"Node creation patterns: {len(all_node_creation)}")
    print(f"Parm setting patterns: {len(all_parm_setting)}")
    print(f"Viewer state patterns: {len(vs_patterns)}")
    print(f"\nTop 15 hou.* calls:")
    for call, count in sorted_api[:15]:
        print(f"  {count:4d}x  {call}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
