"""Convert the Solaris Blueprint v3 .docx (or its extracted text) to Markdown.

Usage:
    python harness/solaris_v3/convert_blueprint.py <blueprint.docx|blueprint.txt> <out.md>

Verbatim conversion: paragraphs kept as lines, "NN / ENGINEERING BLUEPRINT"
page markers become H2 headers, tables are flattened one cell per line
(python-docx is not a dependency of this repo; the docx is unzipped by hand).
"""
from __future__ import annotations

import html
import re
import sys
import zipfile
from pathlib import Path


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf8")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


def to_markdown(text: str) -> str:
    out = [
        "# SYNAPSE / Solaris Recipes x H22 -- Blueprint v3.0",
        "",
        "> Source: SYNAPSE_Solaris_Blueprint_v3.docx (Joe, 04 September 2026). "
        "Converted verbatim for the bp5 swarm; tables flattened to one cell per line. "
        "STATUS in the source: design proposal, not implemented.",
        "",
    ]
    for raw in text.splitlines():
        line = raw.rstrip()
        page = re.match(r"^(\d\d)\s+/\s+ENGINEERING BLUEPRINT$", line)
        if page:
            out.extend(["", f"## Page {page.group(1)}", ""])
            continue
        out.append(line)
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    src, dst = Path(argv[1]), Path(argv[2])
    text = docx_text(src) if src.suffix.lower() == ".docx" else src.read_text(encoding="utf8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(to_markdown(text), encoding="utf8")
    print(f"wrote {dst} ({len(text.split())} words)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
