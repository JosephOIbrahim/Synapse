"""Agent.usd Ledger — durable provenance records (per-record file = source of truth).

The Ledger is SYNAPSE's stream of verified findings (Confirmations, DeadEnds,
DocConformance checks, Deferred risks, SubstrateAssumptions, CRUCIBLE verdicts).
It lives today as a hand-maintained markdown file (``docs/SCIENCE_HARNESS_LEDGER.md``);
this module is its durable, typed home per ``docs/RFC_agent_usd_ledger.md``.

Ratified model (RFC §10):

* **D-1** — each record is ONE immutable per-record JSON file = the **source of
  truth**. The ``/SYNAPSE/agent/ledger/`` USD prim tree is a *derived
  read-projection*, regenerable from the files.
* **D-2** — the schema is the rich markdown superset (RFC §3.3) PLUS a generic
  ``extra: dict[str, str]`` catch-all that captures ANY ``**field:**`` not
  explicitly modeled — guaranteeing lossless backfill.
* **D-3** — prim names are sanitized by ``agent_state._safe_prim_name`` (no ``Tf``).
* **D-4** — the subtree is ``/SYNAPSE/agent/ledger/``.
* **D-5** — deposit is FILE FIRST (unconditional), THEN best-effort USD projection;
  Moneta is optional/off (a no-op hook).
* **D-6** — the per-record files go through the atomic ``write_report`` primitive;
  the Save() gap on the derived ``agent.usd`` is accepted.

**Zero ``hou`` import.** USD authoring is best-effort: no-``pxr`` degrades
gracefully (file write still stands), and any USD authoring error never
propagates out of :func:`deposit`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Dict, List, Optional

from synapse.cognitive.tools.write_report import write_report
from synapse.memory.agent_state import _safe_prim_name
from synapse.science.rungs import RUNGS, migrate_verified_by

# OpenUSD API — best-effort projection only. The per-record file is the source
# of truth (D-1); USD is a derived read-projection that degrades to a no-op
# without pxr. Patchable (PXR_AVAILABLE / Usd / Sdf) by the FakeStage test harness.
try:
    from pxr import Usd, Sdf  # type: ignore
    PXR_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via the no_pxr fixture
    Usd = Sdf = None
    PXR_AVAILABLE = False

LEDGER_SUBTREE = "/SYNAPSE/agent/ledger"

# The default per-record file backup count (DR recovery point; D-6).
DEFAULT_BACKUPS = 1

# Build-pinning cutover (v5 runbook Task B / decision #1). Every VerifiedClaim
# names the build it was verified against: live/interactive/render/flipbook-pixel
# rungs → 671; headless/CI/logic rungs → 631. Legacy markdown entries predate the
# policy (they carry verified_by but no against_build); the reader treats them as
# the conservative CI/logic tier. ``backfill`` stamps this build onto such records
# (the derived per-record file only — the source markdown is never mutated).
CUTOVER_BUILD = "21.0.631"

# Kinds the live Ledger actually carries (RFC §3.3). ``kind`` is an OPEN string —
# the deposit does not reject an unknown value; this set is guidance + the
# round-trip pin's coverage, not a closed enum.
KNOWN_KINDS = (
    "Confirmation",
    "DeadEnd",
    "DocConformance",
    "Deferred",
    "SubstrateAssumption",
    "CRUCIBLE",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LedgerRecord:
    """One Ledger finding. The §3.3 universal field-set + kind-specific blocks +
    a generic ``extra`` catch-all so no markdown ``**field:**`` is ever dropped.

    ``verified_by`` AND ``against_build`` are MANDATORY (RFC §11.2 / the LEDGER
    header rule + the v5 build-pinning policy). A record with EITHER empty is
    rejected at :func:`deposit` (fail-closed). ``against_build`` names the build
    the claim was verified against (671 = live/interactive/render · 631 =
    headless/CI/logic); :data:`CUTOVER_BUILD` is the legacy/backfill default.
    """

    # ── universal fields (every Ledger kind) ──
    kind: str = ""
    verified_by: str = ""           # MANDATORY — e.g. "V1"
    against_build: str = ""
    change_applied: str = ""
    measured_delta: str = ""
    artifact_path: List[str] = field(default_factory=list)
    probe: List[str] = field(default_factory=list)
    question: str = ""
    direction: str = ""
    crucible: str = ""
    notes: str = ""                 # free-form: note / caveat / why_it_matters / rejection_reason / mechanism
    timestamp: str = ""
    title: str = ""                 # the entry header title (### <Kind> — <title>)
    session: str = ""               # the enclosing "## Session ..." header text
    # Session-preamble provenance (bold ``**field:**`` lines between a ``## Session``
    # header and its first ``### entry`` — e.g. **Running build:** / **Bridge:** /
    # **Instrument:** / **Operator ratification:**). Stamped onto every record under
    # that session so this session-level provenance is never dropped (lossless).
    session_meta: Dict[str, str] = field(default_factory=dict)

    # ── DocConformance-only fields ──
    claim_text: str = ""
    claim_locus: str = ""
    code_locus: str = ""
    bound_by: str = ""
    holds: str = ""                 # kept as the verbatim source string ("true"/"false"/...)

    # ── Deferred-only fields ──
    area: str = ""
    stakes: str = ""
    probed: str = ""

    # ── Allocation-only fields (v5 §2 / RFC §2, kind="Allocation") ──
    target: str = ""
    verdict: str = ""               # admit | downstream | defer
    thesis_locus: str = ""          # authoring | composition | proof | adjacent | downstream | out-of-scope
    rationale: str = ""
    decided_by: str = ""            # gate | operator-override

    # ── generic catch-all — anything not explicitly modeled (D-2) ──
    extra: Dict[str, str] = field(default_factory=dict)


# Canonical field-name → dataclass-attr mapping for the markdown bullet keys.
# Several source keys fold into the free-form ``notes`` channel (RFC §3.3).
_NOTES_KEYS = ("note", "caveat", "why_it_matters", "rejection_reason", "mechanism")
_LIST_KEYS = ("artifact_path", "probe")

# Source bullet key (lower, spaces/dashes → underscores) → dataclass attr name.
_FIELD_ALIASES: Dict[str, str] = {
    "kind": "kind",
    "verified_by": "verified_by",
    "against_build": "against_build",
    "change_applied": "change_applied",
    "measured_delta": "measured_delta",
    "artifact_path": "artifact_path",
    "probe": "probe",
    "question": "question",
    "direction": "direction",
    "crucible": "crucible",
    "ts": "timestamp",
    "timestamp": "timestamp",
    "claim_text": "claim_text",
    "claim_locus": "claim_locus",
    "code_locus": "code_locus",
    "bound_by": "bound_by",
    "holds": "holds",
    "area": "area",
    "stakes": "stakes",
    "probed": "probed",
    "target": "target",
    "verdict": "verdict",
    "thesis_locus": "thesis_locus",
    "rationale": "rationale",
    "decided_by": "decided_by",
}

# The set of attrs that are real modeled dataclass fields (for serialization).
_MODELED_ATTRS = {f.name for f in fields(LedgerRecord)}


def _normalize_key(raw: str) -> str:
    """Markdown bullet key → canonical lookup key: lowercase, spaces/dashes → ``_``."""
    return raw.strip().lower().replace(" ", "_").replace("-", "_")


def _canonical_serialize(rec: "LedgerRecord") -> str:
    """Deterministic JSON of the record (sort_keys, default=str). Same record →
    same bytes → same sha8 → same filename → idempotent dedup (RFC §11.3)."""
    return json.dumps(asdict(rec), sort_keys=True, default=str)


def _record_sha8(rec: "LedgerRecord") -> str:
    return hashlib.sha256(_canonical_serialize(rec).encode("utf-8")).hexdigest()[:8]


def _sanitize_ts(ts: str) -> str:
    """Turn an ISO-ish timestamp into a filename-safe token."""
    safe = "".join(c if (c.isalnum()) else "_" for c in (ts or "").strip())
    return safe or "nots"


def record_stem(rec: "LedgerRecord") -> str:
    """``<kind>_<ts>_<sha8>`` — the per-record file stem and the USD prim name.

    The sha8 is over the *canonical-serialized record*, so the SAME record
    always maps to the SAME stem (idempotent dedup, D-1/§11.3)."""
    kind = _safe_prim_name(rec.kind or "Record")
    ts = _sanitize_ts(rec.timestamp)
    return f"{kind}_{ts}_{_record_sha8(rec)}"


def record_filename(rec: "LedgerRecord") -> str:
    """``<kind>_<ts>_<sha8>.json`` — the durable per-record filename."""
    return record_stem(rec) + ".json"


def ledger_dir() -> str:
    """Resolve the Ledger root WITHOUT importing ``hou``.

    ``$SYNAPSE_LEDGER_DIR`` if set, else ``<repo-root>/.synapse/ledger``.
    Mirrors ``floor_gate.resolve_provenance_dir`` (repo root is three dirs up:
    ``memory`` → ``synapse`` → ``python`` → repo-root)."""
    base_dir = os.environ.get("SYNAPSE_LEDGER_DIR")
    if base_dir:
        return base_dir
    here = os.path.dirname(os.path.abspath(__file__))  # .../python/synapse/memory
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(repo_root, ".synapse", "ledger")


# ── USD projection (best-effort, D-1/D-5) ───────────────────────────────────


def _project_to_usd(rec: "LedgerRecord", stem: str, agent_usd_path: str) -> bool:
    """Author ``/SYNAPSE/agent/ledger/<stem>`` with ``synapse:*`` attrs.

    Best-effort: returns True if the prim was authored, False otherwise. Never
    raises — any USD failure (no pxr, missing/corrupt stage) leaves the durable
    file write standing (D-1)."""
    if not PXR_AVAILABLE or not agent_usd_path:
        return False
    try:
        if os.path.exists(agent_usd_path):
            stage = Usd.Stage.Open(agent_usd_path)
        else:
            stage = Usd.Stage.CreateNew(agent_usd_path)
        if stage is None:
            return False

        prim = stage.DefinePrim(f"{LEDGER_SUBTREE}/{stem}", "Xform")

        # String scalars (universal + kind-specific). Lists join via newline;
        # USD typing preserves embedded slashes/quotes verbatim.
        for attr in _MODELED_ATTRS:
            if attr == "extra":
                continue
            value = getattr(rec, attr)
            if attr in _LIST_KEYS:
                str_val = "\n".join(value)
            else:
                str_val = str(value)
            prim.CreateAttribute(
                f"synapse:{attr}", Sdf.ValueTypeNames.String
            ).Set(str_val)

        # Catch-all extras as individual namespaced attrs.
        for ekey, eval_ in rec.extra.items():
            prim.CreateAttribute(
                f"synapse:extra_{_safe_prim_name(ekey)}", Sdf.ValueTypeNames.String
            ).Set(str(eval_))

        stage.GetRootLayer().Save()
        return True
    except Exception:
        # Projection is derived/regenerable — never fail the deposit on it.
        return False


# Optional Moneta hook (D-5). Default no-op; Moneta is default-off (v5.10.0).
def _deposit_to_moneta(rec: "LedgerRecord") -> None:  # pragma: no cover - no-op seam
    return None


# ── deposit ─────────────────────────────────────────────────────────────────


def deposit(rec: "LedgerRecord", *, agent_usd_path: Optional[str] = None) -> Dict:
    """Deposit one Ledger record. FILE FIRST (unconditional), THEN USD (best-effort).

    Rejects a record whose ``verified_by`` is empty/missing (RFC §11.2). The
    per-record JSON file is the source of truth and MUST succeed; USD projection
    is best-effort and never raises out of here.

    Idempotent: the same record maps to the same ``<kind>_<ts>_<sha8>.json`` file,
    so re-depositing overwrites that single file (no duplicate)."""
    vb = (rec.verified_by or "").strip()
    if not vb:
        raise ValueError(
            "LedgerRecord.verified_by is mandatory (empty/missing) — "
            "the Ledger header rule rejects unverified entries."
        )
    if vb not in RUNGS:
        raise ValueError(
            f"LedgerRecord.verified_by={vb!r} is not a v5 rung {RUNGS} (fail-closed: "
            "empty AND unknown rejected). Legacy tokens (V0/V1) must be migrated via "
            "science.rungs.migrate_verified_by before deposit; backfill does this."
        )
    if not (rec.against_build or "").strip():
        raise ValueError(
            "LedgerRecord.against_build is mandatory (empty/missing) — the v5 "
            "build-pinning policy: every VerifiedClaim names the build it was "
            "verified against (671 live/interactive · 631 headless/CI/logic). "
            "Fail-closed. Backfill of legacy entries stamps CUTOVER_BUILD."
        )

    stem = record_stem(rec)
    filename = stem + ".json"
    base = ledger_dir()

    # (a) Durable per-record file — the source of truth. Must succeed.
    write_result = write_report(
        filename,
        _canonical_serialize(rec),
        overwrite=True,
        base_dir=base,
        backups=DEFAULT_BACKUPS,
    )

    # (b) Best-effort USD projection (derived; D-1/D-5).
    usd_projected = _project_to_usd(rec, stem, agent_usd_path) if agent_usd_path else False

    # (c) Optional Moneta enrichment (default no-op; D-5).
    try:
        _deposit_to_moneta(rec)
    except Exception:
        pass

    return {
        "ok": True,
        "stem": stem,
        "filename": filename,
        "path": write_result.get("path"),
        "usd_projected": usd_projected,
    }


# ── markdown parser ──────────────────────────────────────────────────────────

# "## Session 2026-06-05 — Phase 0.0 · ..."
_SESSION_RE = re.compile(r"^##\s+(.*\S)\s*$")
# "### Confirmation — Q1: execute_python round-trips"  /  "### INT-1 — sequenced ..."
_ENTRY_RE = re.compile(r"^###\s+(.*\S)\s*$")
# "- **field:** value"  (leading bullet + bold key)
_BULLET_RE = re.compile(r"^[-*]\s+\*\*(?P<key>[^*]+?):\*\*\s*(?P<rest>.*)$")
# "**field:** value"  (bold key with NO leading bullet — session-preamble lines)
_BOLD_FIELD_RE = re.compile(r"^\*\*(?P<key>[^*]+?):\*\*\s*(?P<val>.*)$")
# Inline dotted form pieces:  "**k:** v"
_INLINE_KV_RE = re.compile(r"\*\*(?P<key>[^*]+?):\*\*\s*(?P<val>.*?)\s*$")


def _apply_kv(rec: "LedgerRecord", raw_key: str, value: str) -> None:
    """Map a parsed ``key → value`` onto the record. Unknown keys → ``extra``."""
    key = _normalize_key(raw_key)
    value = value.strip()

    if key in _NOTES_KEYS:
        # Fold all note-channel keys into ``notes`` (append if multiple).
        if rec.notes:
            rec.notes = f"{rec.notes}\n{value}"
        else:
            rec.notes = value
        return
    if key == "notes":
        rec.notes = f"{rec.notes}\n{value}".strip() if rec.notes else value
        return

    attr = _FIELD_ALIASES.get(key)
    if attr is None:
        # Unknown field — preserve verbatim in extra (D-2: lossless backfill).
        if key in rec.extra:
            rec.extra[key] = f"{rec.extra[key]}\n{value}"
        else:
            rec.extra[key] = value
        return

    if attr in _LIST_KEYS:
        # Split a comma/`·`-separated artifact/probe list into items.
        items = [p.strip().strip("`") for p in re.split(r"[,·]", value) if p.strip()]
        getattr(rec, attr).extend(items)
        return

    setattr(rec, attr, value)


def _split_inline(rest: str) -> List[tuple]:
    """Split the inline dotted form ``**k:** v · **k2:** v2`` into (key, val) pairs.

    Returns [] if ``rest`` is not the dotted form (a single ``**k:** v`` is one pair)."""
    parts = [p for p in rest.split(" · ") if p.strip()]
    pairs: List[tuple] = []
    for part in parts:
        m = _INLINE_KV_RE.search(part.strip())
        if m:
            pairs.append((m.group("key"), m.group("val")))
        else:
            # A dotted segment with no bold key — not parseable as KV; skip
            # rather than corrupt (the bulleted forms carry the real data).
            return pairs if len(parts) > 1 else []
    return pairs if len(pairs) > 1 else []


def parse_ledger_markdown(path: str) -> List[LedgerRecord]:
    """Parse the markdown Ledger into ``LedgerRecord`` objects (RFC §8 backfill step 1).

    Handles the REAL format:
      * ``## Session ...`` headers set the session context for following entries.
      * ``### <Kind> — <title>`` entry headers start a new record (title captured).
      * ``- **field:** value`` bullets (value continues on non-bullet lines).
      * the inline ``- **k:** v · **k2:** v2 · ...`` dotted form (split on `` · ``).
    Unknown ``**field:**`` keys land in ``extra`` so nothing is dropped (D-2)."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    records: List[LedgerRecord] = []
    current_session = ""
    current_session_meta: Dict[str, str] = {}
    rec: Optional[LedgerRecord] = None
    pending_attr: Optional[str] = None  # the attr a continuation line appends to

    def _finish() -> None:
        nonlocal rec, pending_attr
        if rec is not None:
            records.append(rec)
        rec = None
        pending_attr = None

    for line in lines:
        stripped = line.strip()

        # Session header — resets the per-session preamble context.
        m_sess = _SESSION_RE.match(stripped)
        if m_sess:
            _finish()
            current_session = m_sess.group(1).strip()
            current_session_meta = {}
            continue

        # Entry header (### ...).
        m_entry = _ENTRY_RE.match(stripped)
        if m_entry:
            _finish()
            title = m_entry.group(1).strip()
            rec = LedgerRecord(
                session=current_session,
                title=title,
                session_meta=dict(current_session_meta),
            )
            pending_attr = None
            continue

        if rec is None:
            # Session preamble: bold ``**field:**`` provenance lines (no bullet)
            # before the first entry. Capture them so they are not dropped; they
            # are stamped onto each record under this session via session_meta.
            m_meta = _BOLD_FIELD_RE.match(stripped)
            if m_meta:
                current_session_meta[m_meta.group("key").strip()] = (
                    m_meta.group("val").strip()
                )
            continue  # other prose between entries / before the first entry

        # Bullet line "- **key:** value" (possibly inline-dotted).
        m_bullet = _BULLET_RE.match(stripped)
        if m_bullet:
            first_key = m_bullet.group("key")
            rest = m_bullet.group("rest")

            # Reconstruct the full inline string to detect the dotted form, which
            # carries the FIRST key/value plus subsequent `· **k:** v` segments.
            inline = f"**{first_key}:** {rest}"
            pairs = _split_inline(inline)
            if pairs:
                for k, v in pairs:
                    _apply_kv(rec, k, v)
                pending_attr = None
            else:
                _apply_kv(rec, first_key, rest)
                # Track the attr for multi-line continuation (string fields only).
                key = _normalize_key(first_key)
                attr = _FIELD_ALIASES.get(key)
                if attr and attr not in _LIST_KEYS:
                    pending_attr = attr
                elif key in _NOTES_KEYS or key == "notes":
                    pending_attr = "notes"
                else:
                    pending_attr = None
            continue

        # Blank line / separator ends a continuation.
        if not stripped or stripped.startswith("---"):
            pending_attr = None
            continue

        # Continuation of the previous bullet's value (a wrapped line).
        if pending_attr is not None:
            prev = getattr(rec, pending_attr)
            if isinstance(prev, str):
                setattr(rec, pending_attr, f"{prev} {stripped}".strip())
            continue
        # Otherwise (bold-text paragraph etc.) — ignore; not a field.

    _finish()
    return records


def backfill(markdown_path: str, *, agent_usd_path: Optional[str] = None) -> Dict:
    """One-time backfill: parse the markdown Ledger → deposit each record (RFC §8).

    Returns ``{records, kinds, files_written}``. Records missing ``verified_by``
    are skipped (they cannot deposit) and counted under ``skipped``."""
    parsed = parse_ledger_markdown(markdown_path)
    kinds: Dict[str, int] = {}
    files_written = 0
    skipped = 0
    for rec in parsed:
        kinds[rec.kind or "(none)"] = kinds.get(rec.kind or "(none)", 0) + 1
        # Rung migration (v5 §2 read shim): legacy verified_by (V0/V1/V1-degraded,
        # incl. annotated forms) → conservative v5 rung BEFORE the strict deposit.
        # Empty/truly-unknown → skip (cannot deposit; fail-closed). The source
        # markdown is NOT mutated — only the derived per-record file carries the
        # migrated rung, with the raw annotation preserved in `extra` (D-2 lossless).
        original_vb = (rec.verified_by or "").strip()
        migrated = migrate_verified_by(rec.verified_by)
        if not migrated:
            skipped += 1
            continue
        if original_vb and original_vb != migrated:
            rec.extra.setdefault("verified_by_raw", original_vb)
        rec.verified_by = migrated
        # Build-pinning cutover (Task B.2): legacy entries predate the
        # against_build policy → read as the conservative CI/logic tier (631).
        if not (rec.against_build or "").strip():
            rec.against_build = CUTOVER_BUILD
        deposit(rec, agent_usd_path=agent_usd_path)
        files_written += 1
    return {
        "records": len(parsed),
        "kinds": kinds,
        "files_written": files_written,
        "skipped": skipped,
    }
