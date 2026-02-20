#!/usr/bin/env python3
"""
Phase 4: Help Documentation → Intent Mapping

Parses Houdini wiki-format help docs into (intent, operation) training pairs
for SYNAPSE's natural language → MCP tool routing.
"""

import json
import os
import re
from pathlib import Path

STAGING_ROOT = Path(os.environ.get("STAGING_ROOT", r"G:\SYNAPSE_STAGING\SideFXLabs"))
CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"G:\HOUDINI21_RAG_SYSTEM\corpus\sidefxlabs"))

HELP_ROOT = STAGING_ROOT / "help"
OTLS_ROOT = STAGING_ROOT / "otls"
OUTPUT = CORPUS_ROOT / "intent_pairs"


def parse_help_file(filepath: Path) -> dict:
    """
    Parse Houdini wiki-format help file.

    Format uses:
    = Title =           (h1)
    == Section ==       (h2)
    :param_name:        parameter documentation
    #type: node         metadata
    #context: sop       context
    """
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return {}

    doc = {
        "file": str(filepath.relative_to(HELP_ROOT)) if filepath.is_relative_to(HELP_ROOT) else filepath.name,
        "title": "",
        "summary": "",
        "context": "",
        "node_type": "",
        "parameters": {},
        "tips": [],
        "related": [],
    }

    # Extract title: = Title = or #title: Title
    title_match = re.search(r'^= (.+?) =$', content, re.MULTILINE)
    if not title_match:
        title_match = re.search(r'^#title:\s*(.+)$', content, re.MULTILINE)
    if title_match:
        doc["title"] = title_match.group(1).strip()

    # Extract context: #context: sop
    ctx_match = re.search(r'^#context:\s*(\w+)', content, re.MULTILINE)
    if ctx_match:
        doc["context"] = ctx_match.group(1)

    # Extract node type: #type: node
    type_match = re.search(r'^#type:\s*(\w+)', content, re.MULTILINE)
    if type_match:
        doc["node_type"] = type_match.group(1)

    # Extract summary — text between title and first section/parameter
    if doc["title"]:
        # Find content after title line, before first == or :param:
        after_title = re.split(r'^= .+ =$', content, maxsplit=1, flags=re.MULTILINE)
        if len(after_title) > 1:
            rest = after_title[1]
            # Take text before first == section or :param: block
            summary_end = re.search(r'^(?:==|:[a-zA-Z])', rest, re.MULTILINE)
            if summary_end:
                summary_text = rest[:summary_end.start()]
            else:
                summary_text = rest[:800]

            # Clean up
            summary_text = re.sub(r'#\w+:.*$', '', summary_text, flags=re.MULTILINE)
            summary_text = summary_text.strip()
            # Remove wiki formatting
            summary_text = re.sub(r'\[([^\]]*)\]', r'\1', summary_text)
            doc["summary"] = summary_text[:500]

    # Extract parameter documentation blocks
    # Format: :param_name:
    #     #id: param_id
    #     Description text
    param_blocks = re.finditer(
        r'^:(\w+):\s*\n((?:\s+[^\n]+\n)*)',
        content,
        re.MULTILINE,
    )
    for m in param_blocks:
        param_name = m.group(1)
        param_body = m.group(2).strip()
        # Remove #id lines
        param_body = re.sub(r'#\w+:.*$', '', param_body, flags=re.MULTILINE).strip()
        if param_body:
            doc["parameters"][param_name] = param_body[:300]

    # Extract tips (TIP: or NOTE: blocks)
    tips = re.findall(r'(?:TIP|NOTE|WARNING):\s*(.+?)(?=\n\n|\Z)', content, re.DOTALL)
    doc["tips"] = [t.strip()[:200] for t in tips[:5]]

    # Extract related/see also
    related = re.findall(r'\[(?:Node:)?([^\]]+)\]', content)
    doc["related"] = list(set(related))[:10]

    return doc


def build_intent_pairs(docs: list) -> list:
    """
    Convert parsed help docs into (intent, operation) training pairs.

    Each pair maps a natural language description to:
    - The tool/node it refers to
    - Its context (SOP, LOP, etc.)
    - Parameters available
    """
    pairs = []

    for doc in docs:
        if not doc.get("title"):
            continue

        # Primary intent pair: summary → tool
        if doc.get("summary"):
            pairs.append({
                "intent": doc["summary"][:300],
                "title": doc["title"],
                "context": doc.get("context", ""),
                "node_type": doc.get("node_type", ""),
                "parameters": list(doc.get("parameters", {}).keys()),
                "parameter_docs": doc.get("parameters", {}),
                "tips": doc.get("tips", []),
                "related": doc.get("related", []),
                "source": "SideFXLabs",
            })

        # Secondary pairs: individual parameter docs as micro-intents
        for pname, pdoc in doc.get("parameters", {}).items():
            if len(pdoc) > 20:  # Skip trivial docs
                pairs.append({
                    "intent": f"Set {pname}: {pdoc[:150]}",
                    "title": doc["title"],
                    "context": doc.get("context", ""),
                    "parameter": pname,
                    "parameter_doc": pdoc,
                    "source": "SideFXLabs",
                    "type": "parameter_intent",
                })

    return pairs


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    all_docs = []

    if not HELP_ROOT.exists():
        # Help might be in a different location
        alt_help = STAGING_ROOT / "toolbar" / "help"
        if alt_help.exists():
            print(f"Using alternate help path: {alt_help}")
            help_root = alt_help
        else:
            print(f"WARNING: Help directory not found at {HELP_ROOT}")
            print("Checking for help content in HDAs...")
            help_root = None
    else:
        help_root = HELP_ROOT

    # Parse help directory
    if help_root:
        for help_file in help_root.rglob("*"):
            if help_file.is_file() and help_file.suffix in (".txt", ".md", ""):
                doc = parse_help_file(help_file)
                if doc.get("title"):
                    all_docs.append(doc)

    # Also extract Help sections from expanded HDAs
    if OTLS_ROOT.exists():
        for help_file in OTLS_ROOT.rglob("Help"):
            if help_file.is_file():
                doc = parse_help_file(help_file)
                if doc.get("title"):
                    doc["source_type"] = "hda_embedded"
                    all_docs.append(doc)

    print(f"Parsed {len(all_docs)} help documents")

    # Build intent pairs
    pairs = build_intent_pairs(all_docs)

    # Write outputs
    (OUTPUT / "intent_pairs.json").write_text(
        json.dumps(pairs, indent=2), encoding="utf-8"
    )
    (OUTPUT / "help_docs_raw.json").write_text(
        json.dumps(all_docs, indent=2), encoding="utf-8"
    )

    # Summary
    tool_pairs = [p for p in pairs if p.get("type") != "parameter_intent"]
    param_pairs = [p for p in pairs if p.get("type") == "parameter_intent"]
    print(f"Generated {len(tool_pairs)} tool-level intent pairs")
    print(f"Generated {len(param_pairs)} parameter-level intent pairs")
    print(f"Total: {len(pairs)} intent pairs")

    contexts = set(d.get("context", "") for d in all_docs if d.get("context"))
    print(f"Contexts found: {contexts}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
