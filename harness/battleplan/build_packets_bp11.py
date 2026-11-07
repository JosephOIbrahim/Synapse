# build_packets_bp11.py - token-saver context packets for the BP11 legs (author time, local code only).
# BP10's Opus builders re-read the codebase from scratch: contexts peaked at 330-397k tokens and cache reads
# were 42-57% of each builder's cost-weighted spend (runs/2026-09-21/ledger_orch_20260921-121433.json). The
# seat already located the code each BP11 target builds on; this script cuts those windows into one packet
# per leg under .token-saver/bp11/ (gitignored, .gitignore:202), capped in bytes. Fuzzy items go through
# token-saver's own select_context.py. Deterministic: same repo state -> same packets. Next step:
# harness/jev/jev_packet.py screens each packet per target (JEV-PACKET).
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(r"C:\Users\User\SYNAPSE")
OUT = REPO / ".token-saver" / "bp11"
SELECT = Path(r"C:\Users\User\.claude\skills\token-saver\scripts\select_context.py")
CAP = 28_000  # bytes per packet (~7k tokens); the seat's starting value, tuned by receipts' packet_gaps
CAP_BY_LEG = {"BP11-IDCORE": 34_000,   # IDCORE's T4/T5 windows (save callback, fake hou) were cut at 28k
              "BP11-SALIENCE": 34_000}  # SALIENCE gained T5 (LOP writes) at 11:45
P = "python/synapse/"
DL = "C:/Users/User/Downloads/"
CRUX10 = "bp10/crux:harness/battleplan/notes/BP10-CRUX_verdicts.md"

SPECS = {
    "BP11-IDCORE": [
        ("lines", P + "panel/selection_inspection.py", 1, 80),
        ("grep", P + "server/introspection.py", r"^def inspect_selection", 0, 45, 1),
        ("select", P + "server/introspection.py",
         "how inspect_selection builds per-node rows: include_parameters, parameter values, node type, errors, identities", 6000),
        ("lines", P + "cognitive/tools/sidefx_library.py", 1, 60),
        ("grep", P + "cognitive/tools/sidefx_library.py", r"^def (_search|candidates|query_library)\b", 0, 28, 3),
        ("grep", P + "server/main_thread.py", r"^def run_on_main", 0, 5, 1),
        ("grep", P + "server/marshal_guard.py", r"^(INLINE_BUDGET_ENV_VAR|DEFAULT_INLINE_BUDGET_S|def inline_budget_s)", 0, 6, 3),
        ("lines", DL + "synapse_identify_probe3.py", 1, 40),
        ("lines", DL + "synapse_identify_probe_report.txt", 1, 24),
        # repair 1 (JEV-PACKET THIN on T1-T5, 2026-09-28): row shape, SQL, undo + save-callback precedents, fake hou
        ("grep", P + "server/introspection.py", r'info\["parameters"\]', 30, 8, 1),
        ("grep", P + "cognitive/tools/sidefx_library.py", r"execute\(", 2, 6, 3),
        ("grep", P + "server/solaris_lookdev.py", r"undos", 2, 6, 1),
        ("grep", P + "host/job_watch.py", r"hipFile\.addEventCallback", 10, 10, 1),
        ("lines", "tests/conftest.py", 70, 100),
    ],
    "BP11-IDSURF": [
        ("grep", P + "panel/command_palette.py", r"^PANEL_ANSWERED_COMMANDS", 12, 14, 1),
        ("grep", P + "panel/command_palette.py", r"^(_SLASH_COMMANDS|PANEL_ROW_ORDER|PANEL_ROW_TITLES)\b", 0, 12, 3),
        ("grep", P + "panel/tool_palette.py", r"^def _load_entries", 0, 42, 1),
        ("grep", P + "panel/synapse_panel.py", r"def _send\b", 0, 34, 1),
        ("grep", P + "panel/synapse_panel.py", r"c\.Button\(", 2, 6, 4),
        ("grep", P + "panel/synapse_panel.py", r"SelectionInspectorDialog", 2, 10, 2),
        ("lines", P + "panel/selection_inspector.py", 21, 70),
        ("grep", P + "panel/selection_inspector.py", r"_tree\(", 0, 8, 3),
        ("grep", "tests/test_rope_switcher_wires_profile.py", r"class _FakePanel", 2, 30, 1),
        ("lines", "tests/panel/test_token_authority.py", 1, 45),
    ],
    "BP11-SALIENCE": [
        ("grep", P + "jev/adapter.py", r"^def (judge|enabled)\b", 0, 30, 2),
        ("select", P + "jev/selection_suggestions.py",
         "how SuggestionService builds the state and questions, calls adapter.judge with opt_in receipt should_abort from a worker, and projects answers", 7000),
        ("grep", P + "jev/selection_actions.py", r"instructions|criteria|Noul|Choice", 1, 4, 5),
        ("json", "harness/jev/questions.json", ["guards", "rerank"]),
        ("lines", "harness/jev/jev_rerank.py", 1, 50),
        ("lines", "tests/test_jev_product_boundary.py", 1, 40),
        ("grep", "tests/test_jev_selection_suggestions.py", r"def test_", 0, 12, 3),
        # repair 1 (JEV-PACKET THIN on T1-T4, 2026-09-28): preference read, build-time client, hython hash probes
        ("grep", P + "panel/selection_inspector.py", r"def _suggestions_enabled", 0, 10, 1),
        ("lines", "harness/jev/jev_client.py", 113, 160),
        ("lines", "scripts/probe_h1_topo_hash_cook.py", 1, 45),
        ("lines", "scripts/probe_stage_hash_floor.py", 1, 35),
        # T5 (added 11:45): the seat's LOP probe and IDCORE's facts/compose code it extends
        ("lines", ".token-saver/bp11/probe_lop_writes.py", 1, 31),
        ("git", "bp11/idcore:python/synapse/identify/facts.py", r"def _lop_writes", 3, 22),
        ("git", "bp11/idcore:python/synapse/identify/compose.py", r"writes", 4, 8),
    ],
    "BP11-HARDEN": [
        ("lines", ".github/workflows/ci.yml", 1, 140),
        ("lines", "tests/panel/test_token_authority.py", 1, 60),
    ],
    "BP11-FIXFWD": [
        ("git", CRUX10, r"^## BP10-SCAFFOLD", 0, 40),
        ("globgrep", "docs/decisions/ADR-0001*.md", r"^## Refused", 0, 16, 1),
        ("grep", "harness/battleplan/notes/JEV_HARVEST_BLUEPRINT.md", r"^#+ .*[Rr]isks and refusals", 0, 30, 1),
        ("lines", P + "_vendor/fxhoudinimcp/NOTICE.md", 1, 30),
    ],
    "BP11-FIXFWD2": [
        ("lines", ".token-saver/bp11/check_notice_hashes.py", 1, 34),
        ("git", "bp11/fixfwd:scripts/verify_vendor_notice.py", None, 1, 90),
        ("git", "bp11/fixfwd:tests/test_vendor_notice.py", None, 1, 60),
        ("git", "bp11/fixfwd:python/synapse/_vendor/fxhoudinimcp/NOTICE.md", None, 1, 16),
    ],
    "BP11-CRUX": [
        ("git", CRUX10, None, 1, 60),
        ("git", "bp10/crux:harness/notes/receipts/BP10-CRUX.json", None, 1, 40),
        ("git", "bp10/crux:harness/battleplan/notes/BP10-CRUX_mutations.json", None, 1, 30),
        ("grep", "harness/battleplan/notes/IDENTIFY_BLUEPRINT.md", r"^## 3\.", 0, 46, 1),
        ("grep", "harness/battleplan/notes/IDENTIFY_BLUEPRINT.md", r"^## 7\.", 0, 10, 1),
    ],
    "BP11-TIDY": [
        ("lines", "harness/battleplan/notes/BP10_TIDY.md", 1, 60),
    ],
}


def _path(p):
    q = Path(p)
    return q if q.is_absolute() else REPO / q


def _read(p):
    return _path(p).read_text(encoding="utf-8", errors="replace").splitlines()


def _number(lines, a, b):
    return "\n".join(f"{k + 1:>5}: {lines[k]}" for k in range(max(0, a), min(len(lines), b)))


def _windows(lines, rx, before, after, max_hits):
    hits = [i for i, s in enumerate(lines) if re.search(rx, s)][:max_hits]
    spans = []
    for i in hits:
        a, b = max(0, i - before), min(len(lines), i + after + 1)
        if spans and a <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    return "\n  ...\n".join(_number(lines, a, b) for a, b in spans) or f"(no match for /{rx}/)"


def _git(ref_path):
    r = subprocess.run(["git", "-C", str(REPO), "show", ref_path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return r.stdout.splitlines()


def _select(p, request, max_bytes):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "packet.txt"
        r = subprocess.run([sys.executable, str(SELECT), "--request", request, "--source", str(_path(p)),
                            "--max-packet-bytes", str(max_bytes), "--output", str(out)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"select_context exit {r.returncode}: {r.stderr.strip()[:200]}")
        return out.read_text(encoding="utf-8", errors="replace")


def render(item):
    kind, src = item[0], item[1]
    if kind == "lines":
        return f"{src}:{item[2]}-{item[3]}", _number(_read(src), item[2] - 1, item[3])
    if kind == "grep":
        return f"{src} /{item[2]}/", _windows(_read(src), item[2], item[3], item[4], item[5])
    if kind in ("globgrep", "globlines"):
        found = sorted(REPO.glob(src))
        if not found:
            return src, f"(no file matches {src})"
        rel = found[0].relative_to(REPO).as_posix()
        if kind == "globgrep":
            return f"{rel} /{item[2]}/", _windows(_read(rel), item[2], item[3], item[4], item[5])
        return f"{rel}:{item[2]}-{item[3]}", _number(_read(rel), item[2] - 1, item[3])
    if kind == "git":
        lines = _git(src)
        if item[2] is None:
            return f"git show {src}:{item[3]}-{item[4]}", _number(lines, item[3] - 1, item[4])
        return f"git show {src} /{item[2]}/", _windows(lines, item[2], item[3], item[4], 1)
    if kind == "json":
        node = json.loads(_path(src).read_text(encoding="utf-8"))
        for k in item[2]:
            node = node[k]
        return f"{src} {'.'.join(item[2])}", json.dumps(node, indent=1, ensure_ascii=False)
    if kind == "select":
        return f"{src} (token-saver select_context: {item[2][:60]}...)", _select(src, item[2], item[3])
    raise ValueError(kind)


def build(leg, items, sha):
    cap = CAP_BY_LEG.get(leg, CAP)
    head = (f"# BP11 context packet - {leg}\n\nBuilt {date.today().isoformat()} by harness/battleplan/"
            f"build_packets_bp11.py from master {sha}. These are the exact windows the seat located for your "
            "targets. Start here; search beyond this packet only for what it lacks, and list what it lacked in "
            "your receipt under packet_gaps.\n")
    body, used, index, skipped = [head], len(head.encode("utf-8")), [], []
    for item in items:
        try:
            label, text = render(item)
        except Exception as e:  # noqa: BLE001 - a missing window is reported in the packet, never fatal
            label, text = f"{item[0]} {item[1]}", f"(unavailable: {type(e).__name__}: {str(e)[:160]})"
        gone = text.startswith("(unavailable") or text.startswith("(no match") or text.startswith("(no file")
        block = f"\n### {label}\n```\n{text}\n```\n"
        size = len(block.encode("utf-8"))
        if used + size > cap:
            room = cap - used - 200
            if room < 1500:
                skipped.append(label)
                continue
            block = block.encode("utf-8")[:room].decode("utf-8", "ignore") + "\n[... truncated at packet cap]\n```\n"
            size = len(block.encode("utf-8"))
            index.append({"label": label, "bytes": size, "truncated": True, "missing": gone})
        else:
            index.append({"label": label, "bytes": size, "truncated": False, "missing": gone})
        body.append(block)
        used += size
    if skipped:
        body.append("\n### Not included (packet cap) - search these yourself if a target needs them\n"
                    + "\n".join(f"- {s}" for s in skipped) + "\n")
    text = "".join(body)
    (OUT / f"{leg}.packet.md").write_text(text, encoding="utf-8")
    return {"bytes": len(text.encode("utf-8")), "items": index, "skipped": skipped}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short=8", "master"],
                         capture_output=True, text=True).stdout.strip()
    report = {leg: build(leg, items, sha) for leg, items in SPECS.items()}
    (OUT / "packets.json").write_text(json.dumps({"master": sha, "cap_bytes": CAP, "legs": report}, indent=1),
                                      encoding="utf-8")
    for leg, r in report.items():
        trunc = sum(1 for i in r["items"] if i["truncated"])
        miss = [i["label"] for i in r["items"] if i["missing"]]
        print(f"{leg:<14} {r['bytes']:>6} B  items={len(r['items'])} truncated={trunc} "
              f"skipped={len(r['skipped'])} missing={len(miss)} {miss if miss else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
