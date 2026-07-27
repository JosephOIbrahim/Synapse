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
* **D-5** — deposit is FILE FIRST (unconditional), THEN best-effort USD projection,
  THEN best-effort Moneta enrichment. The Moneta leg is live (not a stub): it is
  gated on ``$SYNAPSE_MEMORY_BACKEND`` selecting ``moneta``/``shadow`` AND on
  ``moneta_runtime.moneta_available()``, and it reports its own outcome under the
  ``moneta`` key of the deposit result. It can never fail, delay, or condition
  the file write.
* **D-6** — the per-record files go through the atomic ``write_report`` primitive;
  the Save() gap on the derived ``agent.usd`` is accepted.

**Zero ``hou`` import.** USD authoring is best-effort: no-``pxr`` degrades
gracefully (file write still stands), and any USD authoring error never
propagates out of :func:`deposit`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
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


# ── Moneta enrichment seam (D-5) ────────────────────────────────────────────
#
# Ledger findings are deposited into the Moneta substrate so they are RECALLABLE,
# not merely archived. This is an enrichment: the per-record file (deposit step
# (a)) is unconditional and never depends on anything below.
#
# Two independent conditions gate it, and BOTH are load-bearing:
#   1. $SYNAPSE_MEMORY_BACKEND selects moneta|shadow. One selector decides what
#      SYNAPSE's substrate is (store.py:_make_store); this seam obeys the same
#      switch rather than inventing a second, divergent one. Under `jsonl` the
#      seam is off -- otherwise choosing jsonl would leave a Moneta writer live.
#   2. moneta_runtime.moneta_available(). Availability is NOT re-derived here;
#      the adapter owns the import guard and the $MONETA_SRC path injection.
#
# The Moneta package is never imported at module scope -- ledger.py is a
# zero-`hou`, zero-heavy-dependency module and must import cleanly with no
# Moneta present.

MONETA_BACKENDS = ("moneta", "shadow")

# What ``deposited: True`` does and does not mean. MonetaBackedStore.add() writes
# to the in-memory ECS and returns; there is no per-deposit save, the snapshot
# daemon is deliberately not started (it races the single-writer ECS), and the
# WAL is inert. The engine snapshots on close()/atexit, so a HARD exit between a
# deposit and process teardown loses the row. `deposited` is therefore an honest
# report of acceptance, NOT of durability -- and the two are separate fields
# rather than one field and a footnote (CRUCIBLE finding, 2026-07-26).
#
# This is survivable precisely because the per-record JSON file is the source of
# truth (D-1) and IS durable: a lost Moneta row is re-derivable from the files.
# Nothing re-derives it today -- see for_ruling in the LEDGER leg receipt.
MONETA_DURABILITY = (
    "in-memory on accept; snapshotted on close()/atexit. A hard exit loses "
    "unsnapshotted rows. The per-record JSON file is the durable copy."
)

# One process-wide store, built lazily. Moneta enforces single-owner URI
# locking, so a per-deposit handle would fight itself; the key is the resolved
# ledger dir so a re-pointed $SYNAPSE_LEDGER_DIR rebuilds instead of writing to
# the previous root.
_MONETA_STORE = None
_MONETA_STORE_KEY: Optional[str] = None
_MONETA_LOCK = threading.Lock()

logger = logging.getLogger(__name__)


def moneta_backend_enabled() -> bool:
    """True when ``$SYNAPSE_MEMORY_BACKEND`` selects a Moneta-backed substrate."""
    return os.environ.get("SYNAPSE_MEMORY_BACKEND", "").strip().lower() in MONETA_BACKENDS


def _ledger_memory(rec: "LedgerRecord", stem: str, revision: Optional[str]):
    """Project a LedgerRecord into a SYNAPSE ``Memory`` for recall.

    Deliberately NOT lossless: the per-record JSON file is the source of truth
    (D-1) and the memory points back at it by stem. What lands here is the
    semantic surface -- the text a later recall must match on.

    ``MemoryTier.SHOW`` is chosen because ``MonetaBackedStore._is_protected``
    maps SHOW to a protected floor: a verified finding must not silently decay
    out of the substrate on a sleep pass.
    """
    from .models import Memory, MemoryTier, MemoryType

    kind = rec.kind or "Record"
    headline = f"{kind} — {rec.title}".strip(" —") if rec.title else kind
    lines = [headline]
    for label, value in (
        ("question", rec.question),
        ("direction", rec.direction),
        ("change_applied", rec.change_applied),
        ("measured_delta", rec.measured_delta),
        ("crucible", rec.crucible),
        ("notes", rec.notes),
    ):
        if value:
            lines.append(f"{label}: {value}")
    if rec.probe:
        lines.append("probe: " + ", ".join(rec.probe))
    lines.append(f"record: {stem}.json")

    tags = ["ledger", kind.lower()]
    for value in (rec.verified_by, rec.against_build):
        if value:
            tags.append(value)
    if revision:
        # The substrate revision that wrote this memory, carried BY the memory
        # so the trace survives the process that produced it (defect 2).
        tags.append(f"moneta_rev:{revision[:12]}")

    keywords = sorted({
        w.lower() for w in re.split(r"[^\w.]+", f"{rec.title} {' '.join(rec.probe)}")
        if len(w) > 2
    })[:12]

    return Memory(
        content="\n".join(lines),
        summary=headline[:200],
        memory_type=MemoryType.NOTE,
        tier=MemoryTier.SHOW,
        tags=tags,
        keywords=keywords,
        source="ledger",
        # The record's own timestamp, so re-depositing the same finding builds
        # the same Memory.id (Moneta is append-only and has no dedup key, so
        # id-equality is the only handle a reader has on a duplicate).
        #
        # CONDITIONAL, and say so: Memory.__post_init__ defaults an empty
        # created_at to "now" at 1-second resolution, so a record with NO
        # timestamp only round-trips to the same id within the same UTC second.
        # Every record the live producer emits carries one (science/deposit.py
        # stamps _iso_ts); hand-built records without one get id stability only
        # by luck, which is not a method.
        created_at=(rec.timestamp or "").strip(),
    )


def ledger_moneta_store():
    """The process-wide Moneta store for ledger findings, or None when the seam
    is off/unavailable.

    Rooted at :func:`ledger_dir`. Under the DEFAULT roots that is a distinct
    ``moneta-file://`` URI from the project memory store (``<repo>/.synapse/
    ledger`` vs the project ``.synapse``), so the two do not contend for
    Moneta's single-owner lock. That separation is a property of the paths, NOT
    a guarantee: point ``$SYNAPSE_LEDGER_DIR`` at the project storage dir and
    the second handle raises ``MonetaResourceLockedError``, which surfaces as a
    reported ``error:`` status and never touches the file write. Stated because
    an earlier draft of this docstring claimed "never contend", which is false
    (CRUCIBLE finding, 2026-07-26).

    Public because a reader (recall over verified findings) needs a named door
    into this store rather than a private global.
    """
    global _MONETA_STORE, _MONETA_STORE_KEY

    if not moneta_backend_enabled():
        return None
    from . import moneta_runtime as mr
    if not mr.moneta_available():
        return None

    key = os.path.abspath(ledger_dir())
    with _MONETA_LOCK:
        if _MONETA_STORE is not None and _MONETA_STORE_KEY == key:
            return _MONETA_STORE
        if _MONETA_STORE is not None:
            try:
                _MONETA_STORE.close()  # release the previous URI lock
            except Exception as exc:  # noqa: BLE001
                logger.warning("Closing the previous ledger Moneta store failed: %s", exc)
            _MONETA_STORE, _MONETA_STORE_KEY = None, None
        from .moneta_store import MonetaBackedStore
        os.makedirs(key, exist_ok=True)
        _MONETA_STORE = MonetaBackedStore.from_storage_dir(key)
        _MONETA_STORE_KEY = key
        return _MONETA_STORE


def reset_moneta_store() -> None:
    """Close and forget the ledger's Moneta store (tests; a re-pointed root)."""
    global _MONETA_STORE, _MONETA_STORE_KEY
    with _MONETA_LOCK:
        if _MONETA_STORE is not None:
            try:
                _MONETA_STORE.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Closing the ledger Moneta store failed: %s", exc)
        _MONETA_STORE, _MONETA_STORE_KEY = None, None


def _deposit_to_moneta(rec: "LedgerRecord", stem: str) -> Dict:
    """Deposit one record into the Moneta substrate. Returns what HAPPENED.

    Never raises: a substrate failure must not touch the file write, which is
    the contract. The outcome is reported as an explicit ``deposited`` flag plus
    a ``reason`` -- not as an advisory note hung off a success status, because
    the caller must not have to read prose to learn the record did not land.
    """
    status: Dict = {"deposited": False, "reason": "backend-off",
                    "memory_id": None, "provenance": None,
                    "durable": False, "durability": MONETA_DURABILITY}
    if not moneta_backend_enabled():
        return status

    from . import moneta_runtime as mr
    if not mr.moneta_available():
        status["reason"] = f"unavailable: {mr.import_error()}"
        return status

    provenance = mr.moneta_provenance()
    status["provenance"] = {
        "file": provenance.get("file"),
        "version": provenance.get("version"),
        "revision": provenance.get("revision"),
        "revision_ref": provenance.get("revision_ref"),
        "revision_source": provenance.get("revision_source"),
        "revision_scope": provenance.get("revision_scope"),
    }
    try:
        store = ledger_moneta_store()
        if store is None:
            status["reason"] = "no-store"
            return status
        memory = _ledger_memory(rec, stem, provenance.get("revision"))
        status["memory_id"] = store.add(memory)
        status["deposited"] = True
        status["reason"] = "deposited"
    except Exception as exc:  # noqa: BLE001 -- enrichment never fails the deposit
        status["reason"] = f"error: {type(exc).__name__}: {exc}"
        logger.warning("Ledger -> Moneta deposit failed for %s: %s", stem, exc)
    return status


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

    # (c) Moneta enrichment (gated; D-5). Reports its own outcome and never
    # raises out of here — but the belt-and-braces guard stays, and it RECORDS
    # rather than swallows, so a future edit that reintroduces a raise cannot
    # silently turn into a success.
    try:
        moneta_result = _deposit_to_moneta(rec, stem)
    except Exception as exc:  # noqa: BLE001
        moneta_result = {"deposited": False, "memory_id": None, "provenance": None,
                         "reason": f"error: {type(exc).__name__}: {exc}"}
        logger.warning("Ledger -> Moneta seam raised for %s: %s", stem, exc)

    return {
        "ok": True,
        "stem": stem,
        "filename": filename,
        "path": write_result.get("path"),
        "usd_projected": usd_projected,
        "moneta": moneta_result,
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

    Returns ``{records, kinds, files_written, skipped, moneta_deposited,
    moneta_failures}``. Records missing ``verified_by`` are skipped (they cannot
    deposit) and counted under ``skipped``. The Moneta counters are reported
    rather than assumed: with the seam off they are ``0``/``[]``, which is a
    fact, not a failure."""
    parsed = parse_ledger_markdown(markdown_path)
    kinds: Dict[str, int] = {}
    files_written = 0
    skipped = 0
    # Moneta outcomes are COUNTED and returned. A status nobody reads is the
    # same defect as a stub nobody calls: a substrate leg that fails on every
    # single record would otherwise report a clean "N files written".
    moneta_deposited = 0
    moneta_failures: List[str] = []
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
        result = deposit(rec, agent_usd_path=agent_usd_path)
        files_written += 1
        moneta = result.get("moneta") or {}
        if moneta.get("deposited"):
            moneta_deposited += 1
        elif moneta.get("reason", "").startswith("error:"):
            moneta_failures.append(f"{result['stem']}: {moneta['reason']}")
    return {
        "records": len(parsed),
        "kinds": kinds,
        "files_written": files_written,
        "skipped": skipped,
        "moneta_deposited": moneta_deposited,
        "moneta_failures": moneta_failures,
    }
