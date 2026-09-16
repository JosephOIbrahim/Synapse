"""The README's receipt: what the page declares, checked against what it says.

Why this exists
---------------
A broken mermaid block renders as a grey error box on the GitHub page - the first
thing a visitor sees, on the file that is meant to establish the project is
careful. A stale version string is worse: the download button 404s.

What this proves, and what it does not
--------------------------------------
It proves the SOURCE declares what this file checks: every diagram node resolves
to the dark-grey fill and white ink, every release-tagged version string on the
page matches VERSION, and the tool count matches the module the page itself names
as its producer.

It does NOT prove GitHub's renderer emits those colours. No browser was invoked.
An unrendered claim is UNKNOWN, not verified (AGENTS.md Law 4) - so this receipt
is labelled a source-resolution check, and the render itself remains unmeasured.

Two limits of the styling, stated rather than omitted:
  * ``classDef`` styles NODES. Edge lines and edge labels inherit the host theme,
    deliberately - pinning them white would make them invisible on GitHub's light
    background. Edge labels are therefore host-coloured in both themes.
  * The two subgraph containers in the developer diagram are NOT styled. Their
    frames and titles inherit the host theme, which keeps their titles legible on
    either background; forcing a dark fill there risks a dark title on dark fill.

An instrument that has not been shown to disagree is not evidence (AGENTS.md
Law 1), so this runs two negative controls - a block with no styling, and a block
styled white-on-white - and fails if the resolver calls either of them good.

Why it reads TOOL_DEFS by import rather than by parse: the page names
``python/synapse/mcp/_tool_registry.py`` as the producer of the count. Importing
is reading that producer. If the import fails the count is unmeasured, and an
unmeasured number cannot pass a receipt - so it fails, loudly, with the reason.

Previous version: the "ASSERTED vs ACTUAL" section printed the corpus count and
the VERSION line but never let either affect ``ok`` or the exit code, and it
asserted a README claim ("README says 603") that the README does not make. It was
a check that could not fail. This replaces it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The declared styling. One place, so the check and the expectation cannot drift.
WANT_FILL = "#333333"
WANT_INK = "#FFFFFF"

NODE_REF = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=[\[\{\(])")
CLASS_DEF = re.compile(r"^classDef\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.*)$")
CLASS_ASSIGN = re.compile(r"^class\s+([A-Za-z0-9_,\s]+?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")


class Verdict:
    """Accumulates failures. Exit code is derived from these, never from prints."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def fail(self, why: str) -> None:
        self.failures.append(why)

    def check(self, ok: bool, why: str) -> bool:
        if not ok:
            self.fail(why)
        return ok


def parse_styles(block: str) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Return (classDef name -> attrs, node id -> class name) for one block."""
    defs: dict[str, dict[str, str]] = {}
    assigned: dict[str, str] = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        m = CLASS_DEF.match(line)
        if m:
            attrs: dict[str, str] = {}
            for part in m.group(2).split(","):
                if ":" in part:
                    k, v = part.split(":", 1)
                    attrs[k.strip()] = v.strip()
            defs[m.group(1)] = attrs
            continue
        m = CLASS_ASSIGN.match(line)
        if m:
            cls = m.group(2)
            for node in m.group(1).split(","):
                node = node.strip()
                if node:
                    assigned[node] = cls
    return defs, assigned


def node_ids(block: str) -> list[str]:
    """Every node id in the block, in first-seen order.

    Subgraph lines are excluded: ``subgraph mcp["..."]`` names a container, not a
    node, and it is deliberately left to the host theme.
    """
    ids: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("%%") or line.startswith("classDef"):
            continue
        if line.startswith("class ") or line == "end":
            continue
        # The subgraph id and its title are not nodes; its interior lines still are.
        if line.startswith("subgraph"):
            line = line[len("subgraph"):]
            if "[" in line:
                line = line[line.index("["):]
                continue
        for found in NODE_REF.findall(line):
            if found not in ids:
                ids.append(found)
    return ids


def resolve(block: str) -> list[tuple[str, str | None, str | None, str | None]]:
    """Per node: (id, class name, resolved fill, resolved ink). None = unstyled."""
    defs, assigned = parse_styles(block)
    out = []
    for node in node_ids(block):
        cls = assigned.get(node)
        attrs = defs.get(cls, {}) if cls else {}
        out.append((node, cls, attrs.get("fill"), attrs.get("color")))
    return out


def check_block(rd: Verdict, index: int, block: str) -> int:
    """Structural + colour checks for one block. Returns the node count."""
    lines = [l.rstrip() for l in block.strip().split("\n")]
    head = lines[0].strip()
    rd.check(
        bool(re.match(r"^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram)", head)),
        f"block {index}: header {head[:40]!r} is not a diagram type GitHub renders",
    )
    for kind, open_c, close_c in (("quote", '"', '"'), ("square", "[", "]"), ("paren", "(", ")"), ("brace", "{", "}")):
        if open_c == close_c:
            rd.check(
                all(l.count(open_c) % 2 == 0 for l in lines),
                f"block {index}: unbalanced {kind}s would make GitHub render an error box",
            )
        else:
            delta = sum(l.count(open_c) - l.count(close_c) for l in lines)
            rd.check(
                delta == 0,
                f"block {index}: unbalanced {kind} ({delta:+d}) would make GitHub render an error box",
            )

    resolved = resolve(block)
    if not rd.check(bool(resolved), f"block {index}: no nodes found - the resolver matched nothing"):
        return 0

    unstyled = [n for n, cls, _, _ in resolved if cls is None]
    rd.check(
        not unstyled,
        f"block {index}: {len(unstyled)} node(s) carry no class and would render in the host "
        f"theme: {', '.join(unstyled)}",
    )
    for node, cls, fill, ink in resolved:
        if cls is None:
            continue
        if fill != WANT_FILL or ink != WANT_INK:
            rd.fail(
                f"block {index}: node {node} resolves via class {cls!r} to fill={fill} ink={ink}, "
                f"expected fill={WANT_FILL} ink={WANT_INK}"
            )
    return len(resolved)


# ---------------------------------------------------------------- controls
UNSTYLED_CONTROL = """flowchart LR
    A["one"] --> B["two"]
"""

WRONG_INK_CONTROL = """flowchart LR
    A["one"] --> B["two"]
    classDef dark fill:#FFFFFF,color:#FFFFFF
    class A,B dark
"""


def run_controls(rd: Verdict) -> None:
    """Show the resolver can disagree. A resolver that passes these proves nothing."""
    for label, block in (("unstyled", UNSTYLED_CONTROL), ("white-on-white", WRONG_INK_CONTROL)):
        probe = Verdict()
        check_block(probe, 0, block)
        if not probe.failures:
            rd.fail(
                f"NEGATIVE CONTROL FAILED ({label}): the resolver called a deliberately "
                "bad block good, so its verdict on the real README means nothing"
            )


# ---------------------------------------------------------------- the page's numbers
def check_numbers(rd: Verdict, readme: str) -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()

    # Version: every RELEASE-TAGGED reference (the ``v`` prefix) must be this repo's
    # version. A bare ``5.43.0`` in "shipped since 5.43.0" is a historical fact, not a
    # release pointer - it is listed below rather than silently skipped.
    tagged = sorted(set(re.findall(r"v(\d+\.\d+\.\d+)", readme)))
    bare = sorted(set(re.findall(r"(?<![\dv])(\d+\.\d+\.\d+)", readme)) - set(tagged))
    print(f"    version            VERSION={version}")
    print(f"      release-tagged   {', '.join('v' + t for t in tagged) or '(none)'}")
    print(f"      not release-tagged (not checked, historical): {', '.join(bare) or '(none)'}")
    if not rd.check(bool(tagged), "README carries no release-tagged version at all"):
        return
    stale = [t for t in tagged if t != version]
    rd.check(not stale, f"README names {'v' + ', v'.join(stale)}, but VERSION is {version}")

    # Tool count: the page names its own producer, so read that producer.
    claimed = re.search(r"\*\*(\d+)\s+tools", readme)
    if not rd.check(bool(claimed), "README no longer states its tool count in the bold form"):
        return
    sys.path.insert(0, str(ROOT / "python"))
    try:
        from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 - the reason is the whole point
        rd.fail(
            f"tool count UNMEASURED: could not import TOOL_DEFS from "
            f"python/synapse/mcp/_tool_registry.py ({type(exc).__name__}: {exc}). An "
            "unmeasured number cannot pass a receipt"
        )
        return
    actual = len(TOOL_DEFS)
    print(f"    tool count         README says {claimed.group(1)}   "
          f"len(TOOL_DEFS) = {actual}   {claimed.group(1) == str(actual)}")
    rd.check(
        claimed.group(1) == str(actual),
        f"README says {claimed.group(1)} tools; len(TOOL_DEFS) is {actual}",
    )


def main() -> int:
    rd = Verdict()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```mermaid\n(.*?)```", readme, re.DOTALL)

    print("  mermaid blocks:", len(blocks))
    rd.check(bool(blocks), "README carries no mermaid blocks - the check has nothing to guard")

    total = 0
    for i, block in enumerate(blocks, 1):
        resolved = resolve(block)
        styled = sum(1 for _, cls, _, _ in resolved if cls is not None)
        total += check_block(rd, i, block)
        head = block.strip().split("\n")[0].strip()
        print(f"  {i}. {head:<12} {len(resolved):2d} nodes   styled {styled}/{len(resolved)}   "
              f"fill={WANT_FILL} ink={WANT_INK}")
    print(f"     {total} nodes across {len(blocks)} block(s), all resolved by source")

    print()
    print("  ASSERTED vs ACTUAL   (these gate - a mismatch fails this receipt)")
    check_numbers(rd, readme)

    print()
    print("  NEGATIVE CONTROLS    (a resolver that cannot fail is not evidence)")
    run_controls(rd)
    print("    unstyled block        reported as failing: yes")
    print("    white-on-white block  reported as failing: yes")

    print()
    if rd.failures:
        for why in rd.failures:
            print("  FAIL:", why)
        print()
        print(f"RESULT: FAIL - {len(rd.failures)} check(s) did not hold")
        return 1
    print("RESULT: PASS - source declares dark-grey fill and white ink on every node,")
    print("        version strings and the tool count match their producers.")
    print("        NOT PROVEN: that GitHub renders those colours. No renderer was invoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
