"""Science → Ledger deposit adapter (RFC_agent_usd_ledger §7.2 — the deposit_fn seam).

Bridges the science ``Registry``'s ``deposit_fn`` callback (which receives
``asdict(Record)``) to the durable Ledger (:func:`synapse.memory.ledger.deposit`):
champions land as ``Confirmation`` records, dead-ends as ``DeadEnd``. Probe
verdicts are membership tests, so they carry the ``V0_membership`` rung —
existence, not verification (v5 §2); ``is_verifying`` stays False for them.

Zero ``hou`` import at module scope. ``against_build`` is stamped from the
running session (``hou.applicationVersionString()``) when available, else the
conservative headless tier :data:`synapse.memory.ledger.CUTOVER_BUILD`.

A deposit failure NEVER breaks the probe run — the Registry's JSONL fallback
is the count authority; failures are collected on ``.failures`` for the
entrypoint to surface (no silent drop, no fatal raise).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from synapse.memory.ledger import CUTOVER_BUILD, LedgerRecord, deposit

# science Record.status → Ledger kind (both in ledger.KNOWN_KINDS).
_STATUS_TO_KIND = {"champion": "Confirmation", "dead_end": "DeadEnd"}


def _against_build() -> str:
    """The build this probe ran against: live session when hou is importable,
    else the conservative headless/CI tier (CUTOVER_BUILD)."""
    try:
        import hou  # type: ignore

        return hou.applicationVersionString()
    except Exception:  # noqa: BLE001 — hou is a soft dependency here
        return CUTOVER_BUILD


def _iso_ts(epoch: int) -> str:
    """science Record.timestamp (epoch int, 0 = unset) → Ledger ISO string."""
    if not epoch:
        return ""
    try:
        return datetime.fromtimestamp(epoch, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (OverflowError, OSError, ValueError):
        return ""


class LedgerDeposit:
    """The ``deposit_fn`` callable: science probe verdict dict → Ledger deposit.

    Usage::

        sink = LedgerDeposit()
        registry = Registry(jsonl_path=path, deposit_fn=sink)
        ...
        # sink.deposited / sink.failures for the run summary
    """

    def __init__(self) -> None:
        self.deposited: int = 0
        self.failures: List[str] = []

    def __call__(self, record: Dict) -> None:
        surface = str(record.get("surface", ""))
        status = str(record.get("status", ""))
        rec = LedgerRecord(
            kind=_STATUS_TO_KIND.get(status, "DeadEnd"),
            verified_by="V0_membership",
            against_build=_against_build(),
            title=surface,
            probe=[surface] if surface else [],
            notes=str(record.get("detail", "")),
            timestamp=_iso_ts(record.get("timestamp", 0)),
            extra={
                "science_kind": str(record.get("kind", "")),
                "science_status": status,
                "science_context": str(record.get("context", "")),
            },
        )
        try:
            deposit(rec)
            self.deposited += 1
        except Exception as exc:  # noqa: BLE001 — JSONL fallback is the authority
            self.failures.append(f"{surface}: {exc}")
