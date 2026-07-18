"""Bounded JSONL append ledger — shared mechanics for the scene-model
measurement instruments (``server/read_ledger.py`` + ``panel/turns_ledger.py``).

One class, two thin record-shaping wrappers (the fix-pass extraction: two
near-verbatim copies of cap/rotation/one-time-warn machinery is guaranteed
drift). Env semantics stay in the WRAPPER modules — each passes a
``max_records_resolver`` callable so the env-var literal and its
``os.environ.get`` read live in the same file (the DOC-1 env-conformance
scanner requires quoted-literal adjacency per file).

Disciplines (inherited from existing repo idioms):

* **Never fails the caller.** Every exception swallowed after a ONE-TIME
  warning (the ``integrity_envelope._infra_warned`` idiom), logged under the
  WRAPPER's logger so warnings stay attributable per ledger.
* **Return truth follows the append, not the trim**: if the row reached disk
  but the post-append rotation failed, ``append()`` returns True (and warns
  once) — a persistently broken rotation must not misreport written rows.
* **Bounded on disk** (the FloorGate max-records idiom): cap resolved at
  call time; ``<= 0`` disables rotation; count reconciled from disk once per
  path per process, incremented per append after that.
* **Trim hysteresis**: rewrite only when ``count > cap + slack`` (slack =
  ``max(1, cap // 10)``), trimming down to ``cap`` newest lines via atomic
  ``.tmp + os.replace``. Without slack, steady state past the cap would
  full-file rewrite on EVERY append (the fix-pass efficiency finding);
  with it the rewrite is amortized ~1-in-(cap//10) appends.
* **Rotation reads tolerate corruption**: reconcile/trim reads use
  ``errors="replace"`` (matching the report reader) so one undecodable byte
  from external corruption cannot permanently disable rotation.
* **Thread-safe** via a per-instance lock (append + rotation + count cache).

Multi-process caveat (same class as ``logfile.py``'s RotatingFileHandler
note): two processes appending to the same file may lose lines across a
concurrent rotation rewrite. Acceptable for a measurement instrument.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

_module_log = logging.getLogger(__name__)

#: slack = max(1, cap // TRIM_SLACK_DIVISOR) — the hysteresis window.
TRIM_SLACK_DIVISOR = 10


class BoundedJsonlLedger:
    """One instance per ledger file kind (module singleton in each wrapper)."""

    def __init__(
        self,
        filename: str,
        max_records_resolver: Callable[[], int],
        logger: Optional[logging.Logger] = None,
        warn_label: str = "ledger",
    ) -> None:
        self._filename = filename
        self._resolve_max = max_records_resolver
        self._log = logger or _module_log
        self._warn_label = warn_label
        self._lock = threading.Lock()
        # path -> known line count. Reconciled from disk ONCE per path per
        # process (the FloorGate ``_reconciled`` idiom), then incremented.
        self._counts: Dict[str, int] = {}
        self._write_warned = False

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def path(self) -> str:
        """``<logs dir>/<filename>`` via ``core.logfile.log_dir()`` —
        resolved at call time so env changes take effect without re-import."""
        from .logfile import log_dir
        return os.path.join(log_dir(), self._filename)

    def append(self, record: Dict[str, Any]) -> bool:
        """Append one record. NEVER raises.

        Returns True when the row is on disk — including when the
        post-append rotation failed (warned once). False only when the
        append itself failed or serialization broke.
        """
        try:
            line = json.dumps(record, sort_keys=True, separators=(",", ":"))
            path = self.path()
            with self._lock:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a", encoding="utf-8", newline="\n") as fh:
                    fh.write(line + "\n")
                try:
                    self._bump_and_rotate_locked(path)
                except Exception:
                    self.warn_once(
                        "rotation failed -- the ledger may grow past its "
                        "cap until this is fixed")
            return True
        except Exception:
            self.warn_once(
                "append failed -- records will be missing until this is "
                "fixed")
            return False

    def warn_once(self, message: str) -> None:
        """ONE-TIME warning under the wrapper's logger; silent after."""
        if not self._write_warned:
            self._write_warned = True
            self._log.warning(
                "%s: %s", self._warn_label, message, exc_info=True)

    def reset_state(self) -> None:
        """Test/diagnostic helper (the ``logfile.reset_file_logging``
        idiom): drop the count cache, re-arm the one-time warning."""
        with self._lock:
            self._counts.clear()
            self._write_warned = False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _bump_and_rotate_locked(self, path: str) -> None:
        """Caller holds ``self._lock``. Track the line count and FIFO-trim
        past ``cap + slack`` down to ``cap``, keeping the NEWEST lines via
        atomic ``.tmp + os.replace``."""
        if path in self._counts:
            self._counts[path] += 1
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                self._counts[path] = sum(1 for _ in fh)

        cap = self._resolve_max()
        if cap <= 0:
            return
        slack = max(1, cap // TRIM_SLACK_DIVISOR)
        if self._counts[path] <= cap + slack:
            return

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        keep = lines[-cap:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.writelines(keep)
        os.replace(tmp, path)
        self._counts[path] = len(keep)
