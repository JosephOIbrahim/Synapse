from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Record:
    surface: str
    kind: str
    status: str  # "champion" | "dead_end"
    detail: str = ""
    context: str = ""
    timestamp: int = 0


class Registry:
    """Append-only, dedup-indexed store for probe verdicts.

    Maintains an in-memory index keyed by (surface, kind). New records are
    appended to an optional JSONL fallback and forwarded to an optional
    deposit callback (the Moneta / synapse_write_report injection point).
    """

    def __init__(self, jsonl_path: str | None = None, deposit_fn=None) -> None:
        self._jsonl_path = jsonl_path
        self._deposit_fn = deposit_fn
        self._index: dict[tuple[str, str], Record] = {}
        # Order-preserving list of records as they became known.
        self._records: list[Record] = []

        # Load existing JSONL into the dedup index (best-effort; tolerate
        # malformed lines so a single bad row never breaks startup).
        if jsonl_path and os.path.exists(jsonl_path):
            try:
                with open(jsonl_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except (ValueError, TypeError):
                            continue
                        if not isinstance(data, dict):
                            continue
                        try:
                            rec = Record(
                                surface=data["surface"],
                                kind=data["kind"],
                                status=data["status"],
                                detail=data.get("detail", ""),
                                context=data.get("context", ""),
                                timestamp=data.get("timestamp", 0),
                            )
                        except (KeyError, TypeError):
                            continue
                        key = (rec.surface, rec.kind)
                        if key not in self._index:
                            self._index[key] = rec
                            self._records.append(rec)
            except OSError:
                pass

    def record(self, rec: Record) -> bool:
        """Record a verdict.

        Returns True if newly recorded; False if (surface, kind) is already
        known (no duplicate write, no deposit, no JSONL append).
        """
        key = (rec.surface, rec.kind)
        if key in self._index:
            return False

        self._index[key] = rec
        self._records.append(rec)

        if self._jsonl_path:
            try:
                with open(self._jsonl_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(rec)) + "\n")
            except OSError:
                pass

        if self._deposit_fn is not None:
            self._deposit_fn(asdict(rec))

        return True

    def known(self, surface: str, kind: str) -> Record | None:
        return self._index.get((surface, kind))

    def all(self) -> list[Record]:
        return list(self._records)
