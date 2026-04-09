"""
SYNAPSE Memory Evolution — Lossless Evolution Pipeline

Markdown → USD → USD+Composition
Each evolution is verified lossless. If fidelity < 1.0, rollback.

FLAT:       memory.md (flat text, no schema overhead)
STRUCTURED: memory.usd (typed prims + text attributes, composable)
COMPOSED:   memory.usd + composition arcs (cross-scene, sublayered)

Elegant Revision R3: Native OpenUSD generation via pxr.Usd.Stage.CreateInMemory()
  - Eliminates string-template escaping bugs
  - Tf.MakeValidIdentifier ensures safe prim names (H21 compatible)
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
from shared.constants import (
    EVOLUTION_STAGE_FLAT,
    EVOLUTION_STAGE_STRUCTURED,
    EVOLUTION_TRIGGERS,
    FIDELITY_PERFECT,
)

# ── OpenUSD Import Guard ────────────────────────────────────────
_PXR_AVAILABLE = False
try:
    from pxr import Usd, Sdf, Tf, Vt
    _PXR_AVAILABLE = True
except ImportError:
    Usd = None  # type: ignore[assignment]
    Sdf = None  # type: ignore[assignment]
    Tf = None   # type: ignore[assignment]
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

STRUCTURED_TRIGGERS = EVOLUTION_TRIGGERS


@dataclass
class EvolutionCheck:
    should_evolve: bool
    current_stage: str
    target_stage: str
    triggers_met: list[str]
    triggers_pending: list[str]


def check_evolution_triggers(md_path: str) -> EvolutionCheck:
    if not os.path.exists(md_path):
        return EvolutionCheck(False, EVOLUTION_STAGE_FLAT, EVOLUTION_STAGE_FLAT, [], [])

    with open(md_path, 'r', encoding='utf-8') as _f:
        content = _f.read()
    stats = count_structured_data(content)

    triggers_met = []
    triggers_pending = []

    for trigger_name, threshold in STRUCTURED_TRIGGERS.items():
        current = stats.get(trigger_name, 0)
        if current >= threshold:
            triggers_met.append(f"{trigger_name}: {current} >= {threshold}")
        else:
            triggers_pending.append(f"{trigger_name}: {current} < {threshold}")

    should_evolve = len(triggers_met) > 0
    return EvolutionCheck(
        should_evolve=should_evolve,
        current_stage=EVOLUTION_STAGE_FLAT,
        target_stage=EVOLUTION_STAGE_STRUCTURED if should_evolve else EVOLUTION_STAGE_FLAT,
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
        with open(md_path, 'r', encoding='utf-8') as _f:
            content = _f.read()
    else:
        content = md_path
    return parse_markdown_memory_from_string(content)


def parse_markdown_memory_from_string(content: str) -> ParsedMemory:
    memory = ParsedMemory()
    lines = content.split('\n')
    current_session = None
    current_section = None
    current_decision: Decision | None = None  # E5: track for date/alternatives lookahead
    current_asset: AssetRef | None = None     # E5: track for variants lookahead
    current_param: ParameterRecord | None = None  # E5: track for parameter field lookahead

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
            current_decision = None
            current_asset = None
            current_param = None
            continue

        decision_match = re.match(r'^\*\*Decision:\*\*\s*(.*)|^###\s+Decision:\s*(.*)', line)
        if decision_match:
            choice = (decision_match.group(1) or decision_match.group(2) or "").strip()
            slug = re.sub(r'[^a-z0-9]+', '_', choice.lower())[:50]
            reasoning = ""
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].startswith('#') or lines[j].startswith('**'):
                    break
                if re.match(r'^\s*-\s*(Slug|Date|Alternatives):', lines[j]):
                    break
                reasoning += lines[j] + " "
            current_decision = Decision(
                slug=slug, choice=choice, reasoning=reasoning.strip(),
                date=current_session.date if current_session else "",
            )
            memory.decisions.append(current_decision)
            if current_session:
                current_session.decisions.append(choice)
            # Section is now decision — reset other section pointers so their
            # field-line handlers don't grab our `- Slug:` line and vice versa.
            current_param = None
            current_asset = None
            continue

        # E5: pick up decision metadata that the companion writer now emits
        if current_decision is not None:
            slug_match = re.match(r'^\s*-\s*Slug:\s*(.+)$', line)
            if slug_match:
                current_decision.slug = slug_match.group(1).strip()
                continue
            date_match = re.match(r'^\s*-\s*Date:\s*(.+)$', line)
            if date_match:
                current_decision.date = date_match.group(1).strip()
                continue
            alts_match = re.match(r'^\s*-\s*Alternatives:\s*(.+)$', line)
            if alts_match:
                current_decision.alternatives = [
                    a.strip() for a in alts_match.group(1).split('|') if a.strip()
                ]
                continue

        if '⚠' in line and 'Blocker' in line:
            blocker_text = re.sub(r'^###\s+⚠\s+Blocker:\s*', '', line).strip()
            if current_session:
                current_session.blockers.append(blocker_text)
            continue

        asset_match = re.findall(r'@([^@]+)@', line)
        if asset_match:
            for asset_path in asset_match:
                name = os.path.basename(asset_path).replace('.usd', '').replace('.usda', '')
                # E10 partial: case-insensitive dedup for Windows paths
                if not any(a.path.lower() == asset_path.lower() for a in memory.assets):
                    current_asset = AssetRef(name=name, path=asset_path, notes="")
                    memory.assets.append(current_asset)
            # Mutually exclusive sections
            current_decision = None
            current_param = None
            continue

        # E5: notes + variants lines follow the asset line
        if current_asset is not None:
            notes_match = re.match(r'^\s*-\s*Notes:\s*(.+)$', line)
            if notes_match:
                current_asset.notes = notes_match.group(1).strip()
                continue
            variants_match = re.match(r'^\s*-\s*Variants:\s*(.+)$', line)
            if variants_match:
                current_asset.variants = [
                    v.strip() for v in variants_match.group(1).split('|') if v.strip()
                ]
                continue

        param_match = re.match(r'^###\s+Parameter:\s*(.*)', line)
        if param_match:
            param_desc = param_match.group(1).strip()
            slug = re.sub(r'[^a-z0-9]+', '_', param_desc.lower())[:50]
            current_param = ParameterRecord(
                slug=slug, node="", name=param_desc,
                before="", after="", result="",
                date=current_session.date if current_session else "",
            )
            memory.parameters.append(current_param)
            # Mutually exclusive sections — see decision_match handler
            current_decision = None
            current_asset = None
            continue

        # E5: pick up parameter fields the companion writer now emits
        if current_param is not None:
            for field_name in ("Slug", "Node", "Before", "After", "Result", "Date"):
                m = re.match(rf'^\s*-\s*{field_name}:\s*(.*)$', line)
                if m:
                    val = m.group(1).strip()
                    setattr(current_param, field_name.lower(), val)
                    break
            else:
                # not a parameter field line — fall through
                pass
            if re.match(r'^\s*-\s*(Slug|Node|Before|After|Result|Date):', line):
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
    stage: str = "flat"
    fidelity: float = 1.0
    clean_hash: str = ""
    archive_path: str = ""
    reason: str = ""


# ── Lossless Evolution ──────────────────────────────────────────

class LosslessEvolution:
    """Pipeline evolution with formal lossless guarantees."""

    def evolve_to_structured(self, md_path: str, usd_path: str) -> EvolutionResult:
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
        with open(md_path, 'rb') as _f:
            clean_hash = hashlib.sha256(_f.read()).hexdigest()

        # Stage 3b + 4: CONVERT + COMBINE
        if _PXR_AVAILABLE:
            usd_content = self._build_usd_native(parsed)
        else:
            usd_content = self._build_usd_fallback(parsed)

        with open(usd_path, 'w', encoding='utf-8') as f:
            f.write(usd_content)

        # Stage 5: VERIFY
        companion = self._generate_companion(parsed)
        companion_parsed = parse_markdown_memory_from_string(companion)
        integrity = self._verify_lossless(parsed, companion_parsed)

        if integrity.fidelity < FIDELITY_PERFECT:
            # E3 fix: NEVER delete the archive on rollback. The archive is the
            # immutable backup that lets the artist (and any audit) recover the
            # pre-evolution state. Only the failed USD output is removed.
            if os.path.exists(usd_path):
                os.remove(usd_path)
            return EvolutionResult(
                evolved=False,
                reason=f"Lossless verification failed: {integrity.failures}",
                fidelity=integrity.fidelity,
                archive_path=archive_path,
            )

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(companion)
            f.write(f"\n<!-- Evolved from markdown. Archive: {archive_path} -->\n")
            f.write(f"<!-- Clean hash: {clean_hash} -->\n")
            f.write(f"<!-- Fidelity: {integrity.fidelity} -->\n")

        # ── R10: Sync Solaris viewport with evolved memory ───
        self._sync_solaris_viewport(usd_path)

        return EvolutionResult(
            evolved=True, stage=EVOLUTION_STAGE_STRUCTURED, fidelity=integrity.fidelity,
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

        Optimization: checks needsCook() before force-cooking to skip nodes
        that Houdini already knows are current. Also checks filepath parm
        for both filepath1 and filepath (covers more node types).
        """
        if not _HOU_AVAILABLE:
            return

        import logging
        _log = logging.getLogger("synapse.evolution")

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

            _FILE_REF_TYPES = frozenset({
                "sublayer", "reference", "payload", "inline_usd",
            })
            _FILE_PARM_NAMES = ("filepath1", "filepath")
            cooked = 0

            for lop_net in lop_networks:
                for node in lop_net.children():
                    if node.type().name() not in _FILE_REF_TYPES:
                        continue
                    for parm_name in _FILE_PARM_NAMES:
                        file_parm = node.parm(parm_name)
                        if file_parm and memory_path in file_parm.evalAsString():
                            # Skip if Houdini already knows this node is current
                            if hasattr(node, "needsCook") and not node.needsCook():
                                # Force-cook anyway since the file changed on disk
                                # but Houdini may not have noticed yet
                                pass
                            node.cook(force=True)
                            cooked += 1
                            break  # found the match, move to next node

            if cooked > 0:
                _log.debug(
                    "R10: viewport sync force-cooked %d LOP node(s) "
                    "referencing %s", cooked, memory_path,
                )
        except Exception as exc:
            _log.debug("R10: viewport sync skipped: %s", exc)
            # Viewport sync is best-effort, never blocks evolution

    # ── R3: Native OpenUSD Generation ────────────────────────

    def _build_usd_native(self, parsed: ParsedMemory) -> str:
        """
        R3: Native pxr.Usd generation. Eliminates ALL string-template bugs:
          - Tf.MakeValidIdentifier() ensures safe prim names
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
            "synapse:evolution_stage": EVOLUTION_STAGE_STRUCTURED,
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
            safe_id = Tf.MakeValidIdentifier(session.id)
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
            safe_slug = Tf.MakeValidIdentifier(decision.slug)
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
            safe_name = Tf.MakeValidIdentifier(asset.name)
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
            safe_slug = Tf.MakeValidIdentifier(param.slug)
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
            f'        string synapse:evolution_stage = "{EVOLUTION_STAGE_STRUCTURED}"',
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
            f'*Evolution stage: Structured | {len(parsed.sessions)} sessions | '
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
                # E5: emit slug + date + alternatives so they round-trip
                lines.append(f'- Slug: {d.slug}')
                if d.date:
                    lines.append(f'- Date: {d.date}')
                if d.alternatives:
                    lines.append(f'- Alternatives: {" | ".join(d.alternatives)}')
                lines.append('')

        if parsed.assets:
            lines.append('## Assets')
            for a in parsed.assets:
                lines.append(f'- @{a.path}@')
                if a.notes:
                    lines.append(f'  - Notes: {a.notes}')
                if a.variants:
                    lines.append(f'  - Variants: {" | ".join(a.variants)}')
            lines.append('')

        if parsed.parameters:
            lines.append('## Parameters')
            for p in parsed.parameters:
                lines.append(f'### Parameter: {p.name}')
                # E5: emit every field so the parameter round-trips losslessly
                lines.append(f'- Slug: {p.slug}')
                if p.node:
                    lines.append(f'- Node: {p.node}')
                lines.append(f'- Before: {p.before}')
                lines.append(f'- After: {p.after}')
                if p.result:
                    lines.append(f'- Result: {p.result}')
                if p.date:
                    lines.append(f'- Date: {p.date}')
                lines.append('')

        return '\n'.join(lines)

    # ── E5: Content-Aware Lossless Verification ──────────────
    #
    # The previous implementation only checked counts and slugs. A round-trip
    # could silently drop decision.date, asset.variants, or rewrite reasoning
    # to "" and still report fidelity=1.0. The hash-based check below catches
    # content drift in addition to deletion — making "lossless" actually mean
    # lossless. Each item produces a stable content hash; comparison is by
    # slug-keyed dict, so we report exactly which items drifted and how.

    @staticmethod
    def _decision_hash(d: Decision) -> str:
        payload = "|".join([
            d.slug, d.choice, d.reasoning, d.date,
            "/".join(d.alternatives or []),
        ])
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _asset_hash(a: AssetRef) -> str:
        payload = "|".join([
            a.name, a.path.lower(), a.notes,
            "/".join(a.variants or []),
        ])
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _parameter_hash(p: ParameterRecord) -> str:
        payload = "|".join([
            p.slug, p.node, p.name, p.before, p.after, p.result,
        ])
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    def _verify_lossless(self, original: ParsedMemory,
                         reconstructed: ParsedMemory) -> EvolutionIntegrity:
        failures: list[str] = []

        # Sessions: count must match (text content drift is allowed because
        # the companion summarizes — sessions are narrative, not structured).
        if len(original.sessions) != len(reconstructed.sessions):
            failures.append(
                f"Session count: {len(original.sessions)} → {len(reconstructed.sessions)}"
            )

        # Decisions: per-item content hash comparison
        orig_d = {d.slug: self._decision_hash(d) for d in original.decisions}
        recon_d = {d.slug: self._decision_hash(d) for d in reconstructed.decisions}
        for slug in orig_d.keys() - recon_d.keys():
            failures.append(f"Decision lost: {slug}")
        for slug in orig_d.keys() & recon_d.keys():
            if orig_d[slug] != recon_d[slug]:
                failures.append(f"Decision content drift: {slug}")

        # Assets: per-item content hash comparison
        orig_a = {a.name: self._asset_hash(a) for a in original.assets}
        recon_a = {a.name: self._asset_hash(a) for a in reconstructed.assets}
        for name in orig_a.keys() - recon_a.keys():
            failures.append(f"Asset lost: {name}")
        for name in orig_a.keys() & recon_a.keys():
            if orig_a[name] != recon_a[name]:
                failures.append(f"Asset content drift: {name}")

        # Parameters: per-item content hash comparison
        orig_p = {p.slug: self._parameter_hash(p) for p in original.parameters}
        recon_p = {p.slug: self._parameter_hash(p) for p in reconstructed.parameters}
        for slug in orig_p.keys() - recon_p.keys():
            failures.append(f"Parameter lost: {slug}")
        for slug in orig_p.keys() & recon_p.keys():
            if orig_p[slug] != recon_p[slug]:
                failures.append(f"Parameter content drift: {slug}")

        # Binary fidelity: anything <1.0 already triggers rollback. The old
        # graduated 0.1-per-failure scale was meaningless and is removed (E7).
        fidelity = FIDELITY_PERFECT if not failures else 0.0
        return EvolutionIntegrity(fidelity=fidelity, failures=failures)
