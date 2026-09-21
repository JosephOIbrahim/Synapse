"""BP10-GUIDES Target 2: the four-step transform + phantom gate + chunker for the 31
fxhoudinimcp workflow guides.

For each vendored guide (``python/synapse/_vendor/fxhoudinimcp/guides/<name>.md``) this does,
in order (HARVEST_SPEC.md sec. "Target 2", "Transform, in order"):

1. **Strip framing.** Remove the ``Goal: {description}`` line and the opening
   "You are setting up ..." sentence -- prompt framing, not knowledge.
2. **Rewrite tool refs** from ``rag/ingest/tool_map.json``: a ``kind:tool`` key with a
   ``synapse`` name is rewritten to that name; ``synapse:null`` with ``drop:true`` is removed
   and the drop logged with file:line; ``help_page`` / ``symbol`` keys are left untouched.
3. **Resolve every backticked candidate token** against three sources, in order:
   (1) ``h22_symbol_table.json`` exact  (2) node/parm/attribute names -- node **types** from the
   live catalogue ``rag/catalog/h22.0.400/`` (the gate authority, per CLAUDE.md and the
   BP10-CORPUS handoff finding "gate authority = live catalogue not symbol-table"), parameter
   names from the ``rag/corpus/h22_nodes.json`` datasheet, and the canonical geometry attributes
   (3) ``difflib`` close match at cutoff 0.85. Any token
   that fails all three quarantines the WHOLE guide to ``rag/quarantine/guides/<name>.md``
   with the failing tokens listed at the top. Quarantine is a place to fix from, not a filter.
4. **Chunk by ``##`` section**, one chunk per section, the guide name + section title carried
   on every chunk. Write ``rag/corpus/guides/<name>.jsonl`` with the Target-1 record shape plus
   ``origin = fxhoudinimcp@29b6695b:prompts/markdown/workflows/<name>.md`` and ``licence = mit``.

Promotion out of quarantine is a human act; this module only sorts. It also writes
``harness/notes/harvest/ingest_report.json`` -- the residual tokens (with context and the three
nearest symbols) and the tool refs -- which the JEV-HARVEST guard reads to triage the quarantine.

Pure Python: no ``hou``. Run headless with either interpreter::

    hython rag/ingest/guides.py --build      # the G2 gate command (HARVEST_SPEC)
    python  rag/ingest/guides.py --build      # identical; guides.py needs no hou
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

VENDOR = REPO / "python" / "synapse" / "_vendor" / "fxhoudinimcp" / "guides"
TOOL_MAP = HERE / "tool_map.json"
SYMBOL_TABLE = REPO / "python" / "synapse" / "cognitive" / "tools" / "data" / "h22_symbol_table.json"
NODE_CATALOG = REPO / "rag" / "catalog" / "h22.0.400"
NODE_CORPUS = REPO / "rag" / "corpus" / "h22_nodes.json"
CORPUS_OUT = REPO / "rag" / "corpus" / "guides"
QUARANTINE_OUT = REPO / "rag" / "quarantine" / "guides"
REPORT_OUT = REPO / "harness" / "notes" / "harvest" / "ingest_report.json"

ORIGIN_PREFIX = "fxhoudinimcp@29b6695b:prompts/markdown/workflows"
BUILD = "22.0.400"
LICENCE = "mit"
DIFFLIB_CUTOFF = 0.85

# Canonical Houdini geometry attributes and simulation fields (SideFX standard intrinsic
# names -- P/N/Cd/v/pscale/... and the pyro/FLIP/vellum field names). They are "attribute
# names" in the tier-2 sense; a backticked reference to a standard attribute is not a phantom.
CANONICAL_ATTRS = {
    "p", "n", "cd", "alpha", "v", "vel", "w", "id", "pscale", "orient", "up", "rest", "rest2",
    "uv", "pivot", "scale", "width", "name", "class", "accel", "age", "life", "nage", "mass",
    "group", "ptnum", "primnum", "vtxnum", "force", "targetv", "restlength", "materialpath",
    "shop_materialpath", "path", "tangentu", "tangentv", "area", "perimeter", "com", "gravity",
    "density", "temperature", "heat", "fuel", "burn", "flame", "divergence", "div", "vorticity",
    "pressure", "surface", "collision", "collisionvel", "sourceprim", "sourceprimuv", "sink",
    "stopped", "sleeping", "active", "instance", "instancefile", "idattrib", "useidattrib",
    "height", "mask", "source", "output", "vel", "torque", "distance", "curvature",
}


# --------------------------------------------------------------------------- #
#  Resolver sources (tier 1: symbol table, tier 2: node datasheet + attrs)     #
# --------------------------------------------------------------------------- #
def load_symbols(path: Path = SYMBOL_TABLE) -> set[str]:
    """Tier 1: the exact ``hou.*`` symbol set from the introspected H22 symbol table."""
    d = json.loads(path.read_text(encoding="utf-8"))
    return set(d.get("symbols", []))


def load_catalog(base: Path = NODE_CATALOG) -> set[str]:
    """Tier-2 node authority: every node **type** name from the live H22 catalogue
    (``rag/catalog/h22.0.400/<Category>.json`` -> ``types``), lowercased. This is the live
    catalogue the rulebook names as the node-type authority; it reflects THIS build's installed
    packages, so a genuinely-absent node (an uninstalled Labs asset) correctly fails the gate."""
    out: set[str] = set()
    if not base.exists():
        return out
    for f in sorted(base.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        types = d.get("types") if isinstance(d, dict) else None
        if isinstance(types, dict):
            out |= {t.lower() for t in types}
        elif isinstance(types, list):
            out |= {str(t).lower() for t in types}
    return out


def load_datasheet(path: Path = NODE_CORPUS) -> set[str]:
    """Tier 2 (parameter/attribute half): parameter internal ids / channels from the H22 node
    datasheet corpus, lowercased. Node **types** come from the live catalogue (``load_catalog``);
    this adds the parameter names a guide backticks (``voxelsize``, ``dissipation``)."""
    parm_names: set[str] = set()
    if not path.exists():
        return parm_names
    d = json.loads(path.read_text(encoding="utf-8"))
    for e in d.get("entries", []):
        for p in e.get("parameters", []) or []:
            if not isinstance(p, dict):
                continue
            for key in ("id", "name", "channel"):
                val = p.get(key)
                if isinstance(val, str) and val:
                    parm_names.add(val.lower())
            for ch in p.get("channels") or []:
                if isinstance(ch, str) and ch:
                    parm_names.add(ch.lower())
    return parm_names


class Resolver:
    """The three-tier token resolver. ``resolve(tok)`` -> (ok, tier, nearest[3])."""

    def __init__(self, symbols: set[str], node_types: set[str], parm_names: set[str]):
        self.symbols = symbols
        self.symbols_lower = {s.lower() for s in symbols}
        self.node_types = node_types
        self.parm_names = parm_names
        self.tier2 = node_types | parm_names | CANONICAL_ATTRS
        # difflib universe: catalogue node types + attrs (the surfaces a guide typo/rename would
        # hit). Node-name space, not the 36k hou API list -- a rename target for a backticked node
        # name is another node name, and difflib over 36k tokens per call is both slow and noisy.
        self.fuzzy_universe = sorted(node_types | CANONICAL_ATTRS)

    def resolve(self, tok: str):
        low = tok.lower()
        if tok in self.symbols or low in self.symbols_lower:
            return True, "symbol_table", []
        if low in self.tier2:
            return True, "datasheet", []
        if difflib.get_close_matches(low, self.fuzzy_universe, n=1, cutoff=DIFFLIB_CUTOFF):
            return True, "difflib", []
        nearest = difflib.get_close_matches(low, self.fuzzy_universe, n=3, cutoff=0.0)
        return False, None, nearest


# --------------------------------------------------------------------------- #
#  Step 1: strip prompt framing                                                #
# --------------------------------------------------------------------------- #
def strip_framing(text: str) -> str:
    """Remove the ``Goal:`` line and a leading "You are ..." sentence."""
    lines = [ln for ln in text.splitlines() if not re.match(r"^\s*Goal:\s", ln)]
    text = "\n".join(lines)
    # drop a leading "You are ..." sentence (up to the first '. ' or newline)
    m = re.match(r"^\s*You are\b.*?(?:\.\s|\n)", text, flags=re.DOTALL)
    if m:
        text = text[m.end():]
    return text.lstrip("\n")


# --------------------------------------------------------------------------- #
#  Step 2: rewrite tool references                                             #
# --------------------------------------------------------------------------- #
def tool_entries(tool_map: dict) -> dict:
    """The kind==tool entries only (help_page/symbol keys never rewrite)."""
    return {k: v for k, v in tool_map.items()
            if isinstance(v, dict) and v.get("kind") == "tool"}


def rewrite_tools(text: str, name: str, tools: dict):
    """Rewrite / drop tool references. Longest keys first so ``connect_nodes_batch`` is not
    eaten by ``connect_nodes``. Matches the token backticked or bare, on a word boundary.
    Returns (text, refs, drops): refs are rewrites kept (for equivalent_does_the_job),
    drops are removed refs logged with file:line."""
    refs, drops = [], []
    for key in sorted(tools, key=len, reverse=True):
        entry = tools[key]
        pattern = re.compile(r"`?\b" + re.escape(key) + r"\b`?")
        if not pattern.search(text):
            continue
        line_no = next((i for i, ln in enumerate(text.splitlines(), 1) if key in ln), None)
        sentence = _sentence_of(text, key)
        if entry.get("synapse"):
            repl = entry["synapse"]
            text = pattern.sub(repl, text)
            refs.append({"token": key, "synapse": repl, "doc": entry.get("doc", ""),
                         "guide_name": name, "section_title": _section_of(text, repl),
                         "sentence": sentence, "_unsure": bool(entry.get("_unsure"))})
        elif entry.get("drop"):
            # remove the reference; tidy a doubled space it may leave behind
            text = re.sub(r"\s*" + pattern.pattern + r"\s*", " ", text)
            drops.append({"token": key, "file": f"guides/{name}.md", "line": line_no,
                          "reason": entry.get("reason", "")})
    return text, refs, drops


# --------------------------------------------------------------------------- #
#  Step 3: resolve backticked candidate tokens                                 #
# --------------------------------------------------------------------------- #
_BACKTICK = re.compile(r"`([^`]+)`")


def _is_candidate(tok: str) -> bool:
    """A backticked token that MUST resolve: a bare identifier that looks like a node/parm/
    attribute/API name. Excludes help-page paths, numbers, UI labels, phrases and VEX syntax."""
    if "/" in tok:                       # help-page path (pyro/lookdev)
        return False
    if tok.startswith("__") and tok.endswith("__"):   # SideFX wiki bold UI label
        return False
    if any(c.isspace() for c in tok):    # multi-word phrase
        return False
    if any(c in tok for c in "@$%\"'"):  # VEX/channel binding syntax, quotes
        return False
    if re.fullmatch(r"[-+0-9.,x×*]+", tok):           # number / range / literal
        return False
    if len(tok) < 2:                     # single char (too ambiguous, e.g. `v`)
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_:.]*", tok))


def candidate_tokens(text: str):
    """Unique backticked candidate tokens with their (section_title, sentence) context."""
    seen, out = set(), []
    for m in _BACKTICK.finditer(text):
        tok = m.group(1).strip()
        if tok in seen or not _is_candidate(tok):
            continue
        seen.add(tok)
        out.append({"token": tok, "section_title": _section_of(text, "`" + tok + "`"),
                    "sentence": _sentence_of(text, tok)})
    return out


# --------------------------------------------------------------------------- #
#  Step 4: chunk by ## section                                                 #
# --------------------------------------------------------------------------- #
def chunk_sections(text: str, name: str):
    """One chunk per ``##`` section. The pre-first-## intro is dropped (framing-adjacent);
    the knowledge lives under the headings (HARVEST_SPEC: 'chunk by ## section')."""
    parts = re.split(r"(?m)^(##\s+.*)$", text)
    chunks, idx = [], 0
    # parts = [intro, '## Title', body, '## Title', body, ...]
    for i in range(1, len(parts), 2):
        title = parts[i].lstrip("#").strip()
        body = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        if not body:
            continue
        chunk_text = (parts[i].strip() + "\n\n" + body).strip()
        chunks.append(_record(name, idx, title, chunk_text))
        idx += 1
    return chunks


def _record(name: str, idx: int, title: str, text: str) -> dict:
    origin = f"{ORIGIN_PREFIX}/{name}.md"
    return {
        "id": f"guide:{name}#{idx}",
        "scope": "guide",
        "page": name,
        "title": title,
        "chunk_index": idx,
        "text": text,
        "source": origin,
        "build": BUILD,
        "content_sha": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "licence": LICENCE,
        "origin": origin,
    }


# --------------------------------------------------------------------------- #
#  Small context helpers                                                        #
# --------------------------------------------------------------------------- #
def _sentence_of(text: str, needle: str) -> str:
    i = text.find(needle)
    if i < 0:
        return ""
    start = max(text.rfind("\n", 0, i), text.rfind(". ", 0, i)) + 1
    end = text.find("\n", i)
    end = end if end >= 0 else len(text)
    return re.sub(r"\s+", " ", text[start:end]).strip()[:240]


def _section_of(text: str, needle: str) -> str:
    i = text.find(needle)
    if i < 0:
        return ""
    head = text.rfind("\n## ", 0, i)
    if head < 0:
        return ""
    end = text.find("\n", head + 1)
    return text[head + 4:end].strip() if end > head else ""


# --------------------------------------------------------------------------- #
#  Per-guide transform                                                          #
# --------------------------------------------------------------------------- #
def transform_guide(path: Path, resolver: Resolver, tools: dict) -> dict:
    name = path.stem
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = strip_framing(raw)                                   # 1
    text, refs, drops = rewrite_tools(text, name, tools)        # 2
    unresolved = []                                             # 3
    for c in candidate_tokens(text):
        ok, _tier, nearest = resolver.resolve(c["token"])
        if not ok:
            unresolved.append({**c, "nearest_symbols": nearest})
    result = {"name": name, "refs": refs, "drops": drops, "unresolved": unresolved}
    if unresolved:
        result["status"] = "quarantine"
        result["chunks"] = []
    else:
        result["status"] = "corpus"
        result["chunks"] = chunk_sections(text, name)           # 4
    return result


def write_quarantine(name: str, unresolved: list[dict]) -> Path:
    QUARANTINE_OUT.mkdir(parents=True, exist_ok=True)
    p = QUARANTINE_OUT / f"{name}.md"
    toks = sorted({u["token"] for u in unresolved})
    lines = [
        f"# QUARANTINED: {name}.md",
        "",
        f"Failed the phantom gate on {len(toks)} unresolved backticked token(s). Not read at "
        "retrieval time; a place to fix from, not a filter. Promotion to `rag/corpus/guides/` "
        "is a human act (JEV-HARVEST triages, Joe decides).",
        "",
        "## Failing tokens",
        "",
    ]
    for u in unresolved:
        near = ", ".join(u["nearest_symbols"]) or "(none)"
        lines.append(f"- `{u['token']}`  ->  nearest: {near}")
        if u.get("sentence"):
            lines.append(f"  - in: {u['sentence']}")
    lines += ["", f"origin: `{ORIGIN_PREFIX}/{name}.md` · licence: mit", ""]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_corpus(name: str, chunks: list[dict]) -> Path:
    CORPUS_OUT.mkdir(parents=True, exist_ok=True)
    p = CORPUS_OUT / f"{name}.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return p


# --------------------------------------------------------------------------- #
#  build                                                                         #
# --------------------------------------------------------------------------- #
def _clean_outputs() -> None:
    """Remove this module's own generated files so a guide that moved buckets (quarantine ->
    corpus after a fix) never leaves a stale twin behind -- G2 needs each guide in EXACTLY one
    bucket. Only touches guides.py's own artifacts (*.jsonl here, *.md there)."""
    for f in CORPUS_OUT.glob("*.jsonl"):
        f.unlink()
    for f in QUARANTINE_OUT.glob("*.md"):
        f.unlink()


def build(vendor: Path = VENDOR, write: bool = True) -> dict:
    tool_map = json.loads(TOOL_MAP.read_text(encoding="utf-8"))
    tools = tool_entries(tool_map)
    resolver = Resolver(load_symbols(), load_catalog(), load_datasheet())
    if write:
        CORPUS_OUT.mkdir(parents=True, exist_ok=True)
        QUARANTINE_OUT.mkdir(parents=True, exist_ok=True)
        _clean_outputs()
    guides = sorted(vendor.glob("*.md"))
    report = {"build": BUILD, "corpus": {}, "quarantine": {}, "tool_refs": [], "drops": [],
              "counts": {}}
    n_corpus = n_quar = n_chunks = 0
    for path in guides:
        r = transform_guide(path, resolver, tools)
        report["tool_refs"].extend(r["refs"])
        report["drops"].extend(r["drops"])
        if r["status"] == "quarantine":
            n_quar += 1
            report["quarantine"][r["name"]] = r["unresolved"]
            if write:
                write_quarantine(r["name"], r["unresolved"])
        else:
            n_corpus += 1
            n_chunks += len(r["chunks"])
            report["corpus"][r["name"]] = len(r["chunks"])
            if write:
                write_corpus(r["name"], r["chunks"])
    report["counts"] = {
        "total": len(guides), "corpus": n_corpus, "quarantine": n_quar, "chunks": n_chunks,
        "tool_rewrites": len(report["tool_refs"]), "tool_drops": len(report["drops"]),
    }
    if write:
        REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
        REPORT_OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ingest the 31 fxhoudinimcp workflow guides (Target 2)")
    ap.add_argument("--build", action="store_true", help="write corpus + quarantine + report")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    a = ap.parse_args(argv)
    rep = build(write=not a.dry_run)
    c = rep["counts"]
    print(f"guides: {c['total']} | corpus {c['corpus']} ({c['chunks']} chunks) | "
          f"quarantine {c['quarantine']} | tool rewrites {c['tool_rewrites']} | drops {c['tool_drops']}")
    if rep["quarantine"]:
        print("quarantined:", ", ".join(sorted(rep["quarantine"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
