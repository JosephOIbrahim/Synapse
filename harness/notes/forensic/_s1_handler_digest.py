"""S1 helper — dump the source of the handlers still needing classification.

Read-only. Writes harness/notes/forensic/s1_handler_digest.txt so the reader
classifies against ACTUAL CODE rather than against the grep tells.
"""

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
FOR = ROOT / "harness" / "notes" / "forensic"

ev = json.loads((FOR / "s1_evidence_index.json").read_text(encoding="utf-8"))
done = {
    t["tool"]
    for t in json.loads((FOR / "s1_agent_batch_1_3.json").read_text(encoding="utf-8"))[
        "tools"
    ]
}

only = sys.argv[1] if len(sys.argv) > 1 else None

rows = [t for t in ev["tools"] if t["tool"] not in done]
if only:
    rows = [r for r in rows if r["handler_def_sites"] and r["handler_def_sites"][0].split(":")[0].endswith(only)]

src_cache: dict[str, list[str]] = {}


def lines_of(rel: str) -> list[str]:
    if rel not in src_cache:
        src_cache[rel] = (ROOT / rel).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    return src_cache[rel]


def body_of(rel: str, lineno: int) -> str:
    ls = lines_of(rel)
    try:
        tree = ast.parse("\n".join(ls))
    except SyntaxError:
        return "<unparseable>"
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.lineno == lineno
        ):
            end = getattr(node, "end_lineno", lineno)
            return "\n".join(
                f"{i}\t{ls[i-1]}" for i in range(node.lineno, min(end, node.lineno + 90) + 1)
            )
    return "<not found>"


out = []
for r in sorted(rows, key=lambda r: (r["handler_def_sites"][0] if r["handler_def_sites"] else "", r["tool"])):
    out.append("=" * 78)
    out.append(
        f"TOOL {r['tool']}  cmd={r['command_type']}  ro={r['read_only']}  destr={r['destructive']}"
    )
    out.append(f"DESC {r['desc_head']}")
    out.append(
        f"TESTS n={r['test_count']} mock={len(r['tests_with_mock_hou'])} live={len(r['tests_live_gated'])} :: "
        + ", ".join(r["tests_naming_it"][:5])
    )
    for site in r["handler_def_sites"][:1]:
        rel, ln = site.rsplit(":", 1)
        out.append(f"--- {site} ---")
        out.append(body_of(rel, int(ln)))
    out.append("")

dest = FOR / ("s1_handler_digest.txt" if not only else f"s1_handler_digest_{only.replace('/','_')}.txt")
dest.write_text("\n".join(out), encoding="utf-8")
print(f"{len(rows)} handlers -> {dest} ({dest.stat().st_size} bytes)")
