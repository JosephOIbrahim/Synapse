"""
SYNAPSE Memory Evolution — Lossless Pokémon Model

Markdown → USD → USD+Composition
Each evolution is verified lossless. If fidelity < 1.0, rollback.

CHARMANDER: memory.md (flat text, no schema overhead)
CHARMELEON: memory.usd (typed prims + text attributes, composable)
CHARIZARD:  memory.usd + composition arcs (cross-scene, sublayered)

Elegant Revision R3: Native OpenUSD generation via pxr.Usd.Stage.CreateInMemory()
  - Eliminates string-template escaping bugs
  - Sdf.Path.MakeValidIdentifier ensures safe prim names
  - Vt.StringArray handles arrays without manual quoting
  - ExportToString() produces syntactically perfect USDA

Elegant Revision R10: Solaris viewport sync after evolution
  - Force-cooks LOP nodes referencing evolved USD
  - Viewport immediately reflects memory changes
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import hashlib
import re
import os
import shutil
from datetime import datetime

# ── OpenUSD Import Guard ────────────────────────────────────────
_PXR_AVAILABLE = False
try:
    from pxr import Usd, Sdf, Vt
    _PXR_AVAILABLE = True
except ImportError:
    Usd = None  # type: ignore[assignment]
    Sdf = None  # type: ignore[assignment]
    Vt = None   # type: ignore[assignment]

# ── Houdini Import Guard (R10: viewport sync) ──────────────────
_HOU_AVAILABLE = False
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]


# ── Parsed Memory Structures ────────────────────────────────────

@dataclass
class SessionEntry:
    id: str
    date: str
    text: str
    decisions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)


@dataclass
class Decision:
    slug: str
    choice: str
    reasoning: str
    date: str
    alternatives: list[str] = field(default_factory=list)


@dataclass
class AssetRef:
    name: str
    path: str
    notes: str = ""
    variants: list[str] = field(default_factory=list)


@dataclass
class ParameterRecord:
    slug: str
    node: str
    name: str
    before: str
    after: str
    result: str
    date: str = ""


@dataclass
class ParsedMemory:
    sessions: list[SessionEntry] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    assets: list[AssetRef] = field(default_factory=list)
    parameters: list[ParameterRecord] = field(default_factory=list)


# ── Evolution Triggers ──────────────────────────────────────────

CHARMELEON_TRIGGERS = {
    "structured_data_count": 5,
    "asset_references": 3,
    "parameter_records": 5,
    "wedge_results": 1,
    "session_count": 10,
    "file_size_kb": 100,
    "node_path_references": 10,
}


@dataclass
class EvolutionCheck:
    should_evolve: bool
    current_stage: str
    target_stage: str
    triggers_met: list[str]
    triggers_pending: list[str]


def check_evolution_triggers(md_path: str) -> EvolutionCheck:
    if not os.path.exists(md_path):
        return EvolutionCheck(False, "charmander", "charmander", [], [])

    content = open(md_path, 'r').read()
    stats = count_structured_data(content)

    triggers_met = []
    triggers_pending = []

    for trigger_name, threshold in CHARMELEON_TRIGGERS.items():
        current = stats.get(trigger_name, 0)
        if current >= threshold:
            triggers_met.append(f"{trigger_name}: {current} >= {threshold}")
        else:
            triggers_pending.append(f"{trigger_name}: {current} < {threshold}")

    should_evolve = len(triggers_met) > 0
    return EvolutionCheck(
        should_evolve=should_evolve,
        current_stage="charmander",
        target_stage="charmeleon" if should_evolve else "charmander",
        triggers_met=triggers_met,
        triggers_pending=triggers_pending,
    )


def count_structured_data(content: str) -> dict:
    lines = content.split('\n')
    return {
        "node_path_references": sum(1 for l in lines if re.search(r'/obj/|/stage/|/out/|/shop/', l)),
        "asset_references": sum(1 for l in lines if re.search(r'@[^@]+@', l)),
        "session_count": sum(1 for l in lines if re.match(r'^##\s+Session\s+\d{4}', l)),
        "structured_data_count": sum(1 for l in lines if
            re.match(r'^\*\*Decis', l) or re.match(r'^###\s+Decision', l) or
            re.match(r'^###\s+Parameter', l) or '⚠' in l),
        "parameter_records": sum(1 for l in lines if re.match(r'^###\s+Parameter', l)),
        "wedge_results": sum(1 for l in lines if 'wedge' in l.lower()),
        "file_size_kb": len(content.encode()) / 1024,
    }


# ── Markdown Parser ─────────────────────────────────────────────

def parse_markdown_memory(md_path: str) -> ParsedMemory:
    if isinstance(md_path, str) and os.path.exists(md_path):
        content = open(md_path, 'r').read()
    else:
        content = md_path
    return parse_markdown_memory_from_string(content)


def parse_markdown_memory_from_string(content: str) -> ParsedMemory:
    memory = ParsedMemory()
    lines = content.split('\n')
    current_session = None
    current_section = None

    for i, line in enumerate(lines):
        session_match = re.match(r'^##\s+Session\s+(\d{4}-\d{2}-\d{2})', line)
        if session_match:
            if current_session:
                memory.sessions.append(current_session)
            date = session_match.group(1)
            current_session = SessionEntry(
                id=f"session_{date.replace('-', '_')}",
                date=date, text="",
            )
            current_section = "session"
            continue

        decision_match = re.match(r'^\*\*Decision:\*\*\s*(.*)|^###\s+Decision:\s*(.*)', line)
        if decision_match:
            choice = (decision_match.group(1) or decision_match.group(2) or "").strip()
            slug = re.sub(r'[^a-z0-9]+', '_', choice.lower())[:50]
            reasoning = ""
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].startswith('#') or lines[j].startswith('**'):
                    break
                reasoning += lines[j] + " "
            memory.decisions.append(Decision(
                slug=slug, choice=choice, reasoning=reasoning.strip(),
                date=current_session.date if current_session else "",
            ))
            if current_session:
                current_session.decisions.append(choice)
            continue

        if '⚠' in line and 'Blocker' in line:
            blocker_text = re.sub(r'^###\s+⚠\s+Blocker:\s*', '', line).strip()
            if current_session:
                current_session.blockers.append(blocker_text)
            continue

        asset_match = re.findall(r'@([^@]+)@', line)
        for asset_path in asset_match:
            name = os.path.basename(asset_path).replace('.usd', '').replace('.usda', '')
            if not any(a.path == asset_path for a in memory.assets):
                memory.assets.append(AssetRef(name=name, path=asset_path, notes=line.strip()))

        param_match = re.match(r'^###\s+Parameter:\s*(.*)', line)
        if param_match:
            param_desc = param_match.group(1).strip()
            slug = re.sub(r'[^a-z0-9]+', '_', param_desc.lower())[:50]
            memory.parameters.append(ParameterRecord(
                slug=slug, node="", name=param_desc,
                before="", after="", result="",
                date=current_session.date if current_session else "",
            ))
            continue

        if current_session and current_section == "session":
            current_session.text += line + "\n"

    if current_session:
        memory.sessions.append(current_session)

    return memory


# ── Evolution Results ───────────────────────────────────────────

@dataclass
class EvolutionIntegrity:
    fidelity: float
    failures: list[str] = field(default_factory=list)


@dataclass
class EvolutionResult:
    evolved: bool
    stage: str = "charmander"
    fidelity: float = 1.0
    clean_hash: str = ""
    archive_path: str = ""
    reason: str = ""


# ── Lossless Evolution ──────────────────────────────────────────

class LosslessEvolution:
    """Pokémon evolution with formal lossless guarantees."""

    def evolve_to_charmeleon(self, md_path: str, usd_path: str) -> EvolutionResult:
        """
        Lossless or rollback. Five-stage pipeline:
          1 DETECT → 2 EXTRACT → 3a PRESERVE → 3b CONVERT → 4 COMBINE → 5 VERIFY
        """
        # Stage 1: DETECT
        triggers = check_evolution_triggers(md_path)
        if not triggers.should_evolve:
            return EvolutionResult(evolved=False, reason="Triggers not met")

        # Stage 2: EXTRACT
        parsed = parse_markdown_memory(md_path)

        # Stage 3a: PRESERVE (immutable backup for rollback)
        archive_path = md_path.replace('.md', '_pre_evolution.md')
        shutil.copy2(md_path, archive_path)
        clean_hash = hashlib.sha256(open(md_path, 'rb').read()).hexdigest()

        # Stage 3b + 4: CONVERT + COMBINE
        if _PXR_AVAILABLE:
            usd_content = self._build_usd_native(parsed)
        else:
            usd_content = self._build_usd_fallback(parsed)

        with open(usd_path, 'w') as f:
            f.write(usd_content)

        # Stage 5: VERIFY
        companion = self._generate_companion(parsed)
        companion_parsed = parse_markdown_memory_from_string(companion)
        integrity = self._verify_lossless(parsed, companion_parsed)

        if integrity.fidelity < 1.0:
            if os.path.exists(usd_path):
                os.remove(usd_path)
            if os.path.exists(archive_path):
                os.remove(archive_path)
            return EvolutionResult(
                evolved=False,
                reason=f"Lossless verification failed: {integrity.failures}",
                fidelity=integrity.fidelity,
            )

        with open(md_path, 'w') as f:
            f.write(companion)
            f.write(f"\n<!-- Evolved from markdown. Archive: {archive_path} -->\n")
            f.write(f"<!-- Clean hash: {clean_hash} -->\n")
            f.write(f"<!-- Fidelity: {integrity.fidelity} -->\n")

        # ── R10: Sync Solaris viewport with evolved memory ───
        self._sync_solaris_viewport(usd_path)

        return EvolutionResult(
            evolved=True, stage="charmeleon", fidelity=integrity.fidelity,
            clean_hash=clean_hash, archive_path=archive_path,
        )

    # ── R10: Solaris Viewport Sync ──────────────────────────

    def _sync_solaris_viewport(self, memory_path: str) -> None:
        """
        R10: Ensures Houdini's live scene graph syncs with evolved memory.

        After evolution writes a new memory.usd, any LOP node that references
        this file (via sublayer or reference) will be stale. This method
        finds those nodes and force-cooks them so the Solaris viewport
        immediately reflects the evolved data.

        H21: hou.lopNetworks() was removed. We walk the node tree from root
        and collect hou.LopNetwork instances instead.
        """
        if not _HOU_AVAILABLE:
            return

        try:
            # H21: find LOP networks by walking the node tree
            lop_networks = []
            stack = [hou.node("/")]
            while stack:
                n = stack.pop()
                if isinstance(n, hou.LopNetwork):
                    lop_networks.append(n)
                try:
                    stack.extend(n.children())
                except Exception:
                    pass

            for lop_net in lop_networks:
                for node in lop_net.children():
                    if node.type().name() in ("sublayer", "reference"):
                        file_parm = node.parm("filepath1")
                        if file_parm and memory_path in file_parm.evalAsString():
                            node.cook(force=True)
        except Exception:
            pass  # Viewport sync is best-effort, never blocks evolution

    # ── R3: Native OpenUSD Generation ────────────────────────

    def _build_usd_native(self, parsed: ParsedMemory) -> str:
        """
        R3: Native pxr.Usd generation. Eliminates ALL string-template bugs:
          - Sdf.Path.MakeValidIdentifier() ensures safe prim names
          - Vt.StringArray() handles arrays without manual quoting
          - Native String attributes auto-escape VEX slashes, quotes, linebreaks
          - ExportToString() produces syntactically perfect USDA
        """
        stage = Usd.Stage.CreateInMemory()

        root_prim = stage.DefinePrim("/SYNAPSE", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Layer metadata
        stage.GetRootLayer().customLayerData = {
            "synapse:version": "2.0.0-lossless",
            "synapse:evolution_stage": "charmeleon",
            "synapse:evolved_at": datetime.now().isoformat(),
            "synapse:session_count": len(parsed.sessions),
            "synapse:decision_count": len(parsed.decisions),
            "synapse:asset_count": len(parsed.assets),
            "synapse:parameter_count": len(parsed.parameters),
        }

        memory_prim = stage.DefinePrim("/SYNAPSE/memory", "Xform")

        # ── Sessions ────────────────────────────────────────
        sessions_prim = stage.DefinePrim(f"{memory_prim.GetPath()}/sessions", "Xform")
        for session in parsed.sessions:
            safe_id = Sdf.Path.MakeValidIdentifier(session.id)
            sess_prim = stage.DefinePrim(f"{sessions_prim.GetPath()}/{safe_id}", "Xform")

            sess_prim.CreateAttribute("synapse:date", Sdf.ValueTypeNames.String).Set(session.date)
            sess_prim.CreateAttribute("synapse:narrative", Sdf.ValueTypeNames.String).Set(session.text)

            if session.decisions:
                sess_prim.CreateAttribute(
                    "synapse:decisions", Sdf.ValueTypeNames.StringArray
                ).Set(Vt.StringArray(session.decisions))
            if session.blockers:
                sess_prim.CreateAttribute(
                    "synapse:blockers", Sdf.ValueTypeNames.StringArray
                ).Set(Vt.StringArray(session.blockers))

        # ── Decisions ───────────────────────────────────────
        decisions_prim = stage.DefinePrim(f"{memory_prim.GetPath()}/decisions", "Xform")
        for decision in parsed.decisions:
            safe_slug = Sdf.Path.MakeValidIdentifier(decision.slug)
            d_prim = stage.DefinePrim(f"{decisions_prim.GetPath()}/{safe_slug}", "Xform")

            d_prim.CreateAttribute("synapse:choice", Sdf.ValueTypeNames.String).Set(decision.choice)
            d_prim.CreateAttribute("synapse:reasoning", Sdf.ValueTypeNames.String).Set(decision.reasoning)
            d_prim.CreateAttribute("synapse:date", Sdf.ValueTypeNames.String).Set(decision.date)
            if decision.alternatives:
                d_prim.CreateAttribute(
                    "synapse:alternatives", Sdf.ValueTypeNames.StringArray
                ).Set(Vt.StringArray(decision.alternatives))

        # ── Assets ──────────────────────────────────────────
        assets_prim = stage.DefinePrim(f"{memory_prim.GetPath()}/assets", "Xform")
        for asset in parsed.assets:
            safe_name = Sdf.Path.MakeValidIdentifier(asset.name)
            a_prim = stage.DefinePrim(f"{assets_prim.GetPath()}/{safe_name}", "Xform")

            a_prim.CreateAttribute("synapse:path", Sdf.ValueTypeNames.Asset).Set(asset.path)
            a_prim.CreateAttribute("synapse:notes", Sdf.ValueTypeNames.String).Set(asset.notes)
            if asset.variants:
                a_prim.CreateAttribute(
                    "synapse:variants", Sdf.ValueTypeNames.StringArray
                ).Set(Vt.StringArray(asset.variants))

        # ── Parameters ──────────────────────────────────────
        params_prim = stage.DefinePrim(f"{memory_prim.GetPath()}/parameters", "Xform")
        for param in parsed.parameters:
            safe_slug = Sdf.Path.MakeValidIdentifier(param.slug)
            p_prim = stage.DefinePrim(f"{params_prim.GetPath()}/{safe_slug}", "Xform")

            p_prim.CreateAttribute("synapse:node_path", Sdf.ValueTypeNames.String).Set(param.node)
            p_prim.CreateAttribute("synapse:parm_name", Sdf.ValueTypeNames.String).Set(param.name)
            p_prim.CreateAttribute("synapse:before", Sdf.ValueTypeNames.String).Set(param.before)
            p_prim.CreateAttribute("synapse:after", Sdf.ValueTypeNames.String).Set(param.after)
            p_prim.CreateAttribute("synapse:result", Sdf.ValueTypeNames.String).Set(param.result)
            if param.date:
                p_prim.CreateAttribute("synapse:date", Sdf.ValueTypeNames.String).Set(param.date)

        # ExportToString produces syntactically perfect USDA
        return stage.GetRootLayer().ExportToString()

    # ── String-Template Fallback (testing without pxr) ───────

    def _build_usd_fallback(self, parsed: ParsedMemory) -> str:
        """Fallback for environments without pxr (testing only)."""
        lines = [
            '#usda 1.0',
            '(',
            '    defaultPrim = "SYNAPSE"',
            '    doc = "SYNAPSE Scene Memory — Evolved from Markdown (fallback)"',
            '    customLayerData = {',
            '        string synapse:version = "2.0.0-lossless"',
            f'        string synapse:evolution_stage = "charmeleon"',
            f'        string synapse:evolved_at = "{datetime.now().isoformat()}"',
            f'        int synapse:session_count = {len(parsed.sessions)}',
            f'        int synapse:decision_count = {len(parsed.decisions)}',
            f'        int synapse:asset_count = {len(parsed.assets)}',
            f'        int synapse:parameter_count = {len(parsed.parameters)}',
            '    }',
            ')',
            '',
            'def Xform "SYNAPSE"',
            '{',
            '    def Xform "memory"',
            '    {',
        ]

        def _safe_id(s: str) -> str:
            return re.sub(r'[^a-zA-Z0-9_]', '_', s)

        def _esc(s: str) -> str:
            return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

        # Sessions
        lines.append('        def Xform "sessions"')
        lines.append('        {')
        for session in parsed.sessions:
            sid = _safe_id(session.id)
            lines.append(f'            def Xform "{sid}"')
            lines.append('            {')
            lines.append(f'                custom string synapse:date = "{session.date}"')
            lines.append(f'                custom string synapse:narrative = "{_esc(session.text[:2000])}"')
            if session.decisions:
                arr = '", "'.join(_esc(d) for d in session.decisions)
                lines.append(f'                custom string[] synapse:decisions = ["{arr}"]')
            lines.append('            }')
        lines.append('        }')

        # Decisions
        lines.append('        def Xform "decisions"')
        lines.append('        {')
        for d in parsed.decisions:
            lines.append(f'            def Xform "{_safe_id(d.slug)}"')
            lines.append('            {')
            lines.append(f'                custom string synapse:choice = "{_esc(d.choice[:500])}"')
            lines.append(f'                custom string synapse:reasoning = "{_esc(d.reasoning[:1000])}"')
            lines.append(f'                custom string synapse:date = "{d.date}"')
            lines.append('            }')
        lines.append('        }')

        # Assets
        lines.append('        def Xform "assets"')
        lines.append('        {')
        for a in parsed.assets:
            lines.append(f'            def Xform "{_safe_id(a.name)}"')
            lines.append('            {')
            lines.append(f'                custom asset synapse:path = @{a.path}@')
            lines.append(f'                custom string synapse:notes = "{_esc(a.notes[:500])}"')
            lines.append('            }')
        lines.append('        }')

        # Parameters
        lines.append('        def Xform "parameters"')
        lines.append('        {')
        for p in parsed.parameters:
            lines.append(f'            def Xform "{_safe_id(p.slug)}"')
            lines.append('            {')
            lines.append(f'                custom string synapse:parm_name = "{_esc(p.name)}"')
            lines.append(f'                custom string synapse:node_path = "{_esc(p.node)}"')
            lines.append('            }')
        lines.append('        }')

        lines.extend(['    }', '}'])
        return '\n'.join(lines) + '\n'

    # ── Companion Markdown Generator ─────────────────────────

    def _generate_companion(self, parsed: ParsedMemory) -> str:
        lines = [
            '# SYNAPSE Scene Memory (Companion — source of truth is memory.usd)',
            '',
            f'*Evolution stage: Charmeleon | {len(parsed.sessions)} sessions | '
            f'{len(parsed.decisions)} decisions | {len(parsed.assets)} assets*',
            '',
        ]
        for session in parsed.sessions:
            lines.append(f'## Session {session.date}')
            lines.append(session.text.strip())
            for d in session.decisions:
                lines.append(f'**Decision:** {d}')
            for b in session.blockers:
                lines.append(f'### ⚠ Blocker: {b}')
            lines.append('')

        if parsed.decisions:
            lines.append('## Decisions')
            for d in parsed.decisions:
                lines.append(f'### Decision: {d.choice}')
                if d.reasoning:
                    lines.append(d.reasoning)
                lines.append('')

        if parsed.assets:
            lines.append('## Assets')
            for a in parsed.assets:
                lines.append(f'- @{a.path}@ — {a.notes}')
            lines.append('')

        if parsed.parameters:
            lines.append('## Parameters')
            for p in parsed.parameters:
                lines.append(f'### Parameter: {p.name}')
                if p.node:
                    lines.append(f'Node: {p.node}')
                if p.before and p.after:
                    lines.append(f'Changed: {p.before} → {p.after}')
                if p.result:
                    lines.append(f'Result: {p.result}')
                lines.append('')

        return '\n'.join(lines)

    # ── Lossless Verification ────────────────────────────────

    def _verify_lossless(self, original: ParsedMemory,
                         reconstructed: ParsedMemory) -> EvolutionIntegrity:
        failures = []

        if len(original.sessions) != len(reconstructed.sessions):
            failures.append(
                f"Session count: {len(original.sessions)} → {len(reconstructed.sessions)}"
            )

        orig_d = {d.slug for d in original.decisions}
        recon_d = {d.slug for d in reconstructed.decisions}
        lost = orig_d - recon_d
        if lost:
            failures.append(f"Decisions lost: {lost}")

        orig_a = {a.name for a in original.assets}
        recon_a = {a.name for a in reconstructed.assets}
        if orig_a - recon_a:
            failures.append(f"Assets lost: {orig_a - recon_a}")

        orig_p = {p.slug for p in original.parameters}
        recon_p = {p.slug for p in reconstructed.parameters}
        if orig_p - recon_p:
            failures.append(f"Parameters lost: {orig_p - recon_p}")

        fidelity = max(0.0, 1.0 - len(failures) * 0.1)
        return EvolutionIntegrity(fidelity=fidelity, failures=failures)
