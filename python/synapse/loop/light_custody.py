"""Bounded LIGHT custody through the existing LedgerPort writer.

This is durable LOCAL precommit custody, never Hanish settlement. A cooperative
exclusive claim and strict rereads detect replay, interrupted runs, corruption
and drift. A stale claim is never cleared automatically. It is not protection
against hostile code rewriting this interpreter or the filesystem.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from .ports import LedgerPort


class CustodyUnavailable(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CustodyUnavailable("Duplicate custody JSON field")
        result[key] = value
    return result


def _loads(value):
    try:
        return json.loads(value, object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(CustodyUnavailable("Nonfinite custody data")))
    except (ValueError, TypeError) as exc:
        raise CustodyUnavailable("Malformed custody JSON") from exc


def _plain_path(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise CustodyUnavailable("Linked custody path is unsupported")
    return path


class LightCustody:
    """Borrow one explicit existing port; no memory handle or new outbox writer.

    The caller must use a dedicated disposable/qualified ledger directory.
    No default production directory is selected by this class.
    """
    schema = "synapse.light.local-custody.v1"

    def __init__(self, port):
        if type(port) is not LedgerPort or port.worker is not None:
            raise CustodyUnavailable("An explicit local LedgerPort owner is required")
        self.port = port
        self.path = _plain_path(port.ledger)
        self.lock = self.path.with_name(self.path.name + ".light.claim")
        self.identity = self.path.with_name(self.path.name + ".light.identity")
        self.ack = self.path.with_name(self.path.name + ".light.ack")
        self.ack_pending = self.path.with_name(self.path.name + ".light.ack.pending")
        self._ack_bytes = None
        self._held = False
        self._expected = None
        self.nonce = None

    def __enter__(self):
        if self._held:
            raise CustodyUnavailable("Custody claim is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _plain_path(self.path.parent)
        try:
            descriptor = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise CustodyUnavailable("Custody busy or interrupted; no automatic claim removal") from exc
        except OSError as exc:
            raise CustodyUnavailable("Custody claim unavailable: " + str(exc)) from exc
        self._held = True
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(canonical({"pid": os.getpid(), "schema": self.schema}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._claim_bytes = self.lock.read_bytes()
        try:
            if self.ack_pending.exists():
                raise CustodyUnavailable("Interrupted acknowledgement update; preserve pending evidence")
            if self.identity.exists():
                identity = _loads(_plain_path(self.identity).read_bytes())
                if (type(identity) is not dict or set(identity) != {"schema", "nonce"} or identity["schema"] != self.schema
                        or type(identity["nonce"]) is not str or not re.fullmatch(r"[0-9a-f]{32}", identity["nonce"])):
                    raise CustodyUnavailable("Custody identity is invalid")
                self.nonce = identity["nonce"]
                if not self.ack.is_file():
                    raise CustodyUnavailable("Custody acknowledgement missing or interrupted; never adopt current ledger")
                self._ack_bytes = _plain_path(self.ack).read_bytes()
            else:
                if self.path.exists() or self.ack.exists():
                    raise CustodyUnavailable("Existing ledger/acknowledgement has no LIGHT identity; never adopt it")
                self.nonce = uuid4().hex
                with self.identity.open("xb") as stream:
                    stream.write((canonical({"schema": self.schema, "nonce": self.nonce}) + "\n").encode())
                    stream.flush()
                    os.fsync(stream.fileno())
                self._write_ack(b"", 0)
            self._identity_bytes = self.identity.read_bytes()
            self._expected = self.path.read_bytes() if self.path.exists() else b""
            self.records()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self._held:
            self._held = False
            if _plain_path(self.lock).read_bytes() != self._claim_bytes:
                raise CustodyUnavailable("Custody claim changed; preserve it for owner inspection")
            self.lock.unlink()

    def records(self):
        if not self._held or _plain_path(self.port.ledger) != self.path:
            raise CustodyUnavailable("Bound custody owner/path changed")
        if _plain_path(self.identity).read_bytes() != self._identity_bytes:
            raise CustodyUnavailable("Custody identity changed during ownership")
        current = _plain_path(self.path).read_bytes() if self.path.exists() else b""
        if current != self._expected or (current and not current.endswith(b"\n")):
            raise CustodyUnavailable("Custody drift or incomplete final record")
        if self.ack_pending.exists() or _plain_path(self.ack).read_bytes() != self._ack_bytes:
            raise CustodyUnavailable("Custody acknowledgement changed or update interrupted")
        records = self._parse_records(current)
        acknowledgement = _loads(self._ack_bytes)
        if (type(acknowledgement) is not dict or type(acknowledgement.get("count")) is not int
                or acknowledgement != self._ack_state(current, len(records))):
            raise CustodyUnavailable("Ledger differs from independently acknowledged count/digest; rollback refused")
        return records

    def _ack_state(self, raw, count):
        return {"schema": "synapse.light.ack.v1", "nonce": self.nonce, "count": count,
                "ledger_sha256": hashlib.sha256(raw).hexdigest()}

    def _write_ack(self, raw, count):
        """Ledger fsync precedes atomic ack replacement; any interrupted gap refuses.

        Pending evidence is never repaired automatically. This detects ledger-only
        truncation/restoration, not rollback of the ledger AND its anchor together.
        """
        if not self._held or self.ack_pending.exists():
            raise CustodyUnavailable("Acknowledgement claim unavailable or interrupted")
        if self._ack_bytes is not None and _plain_path(self.ack).read_bytes() != self._ack_bytes:
            raise CustodyUnavailable("Acknowledgement drift before publication")
        encoded = (canonical(self._ack_state(raw, count)) + "\n").encode()
        try:
            with _plain_path(self.ack_pending).open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(self.ack_pending, _plain_path(self.ack))
            with self.ack.open("r+b") as stream:
                os.fsync(stream.fileno())
                if stream.read() != encoded:
                    raise CustodyUnavailable("Acknowledgement readback differs")
        except OSError as exc:
            raise CustodyUnavailable("Acknowledgement update interrupted; preserve ledger/pending evidence: " + str(exc)) from exc
        self._ack_bytes = encoded

    def _parse_records(self, current):
        if current and not current.endswith(b"\n"):
            raise CustodyUnavailable("Incomplete custody final record")
        records = []
        for index, line in enumerate(current.splitlines(), 1):
            outer = _loads(line)
            if (type(outer) is not dict or set(outer) != {"event", "claim_predicate", "probability", "world_ref", "author", "seq"}
                    or outer["event"] != "precommit" or outer["author"] != "v0.0-recipe"
                    or type(outer["seq"]) is not int or outer["seq"] != index
                    or type(outer["probability"]) is not float or outer["probability"] != 0.0):
                raise CustodyUnavailable("Unexpected existing-port custody record")
            body = _loads(outer["claim_predicate"])
            if (type(body) is not dict or set(body) != {"schema", "nonce", "kind", "run_id", "scope", "request_sha256", "profile_sha256", "payload"}
                    or body["schema"] != self.schema or body["nonce"] != self.nonce
                    or outer["world_ref"] != digest(body) or type(body["payload"]) is not dict):
                raise CustodyUnavailable("Custody record identity/content mismatch")
            records.append(body)
        return records

    def append(self, kind, run_id, scope, request_sha256, profile_sha256, payload):
        prior = self.records()
        if kind not in {"BEGIN", "FORECAST", "OBSERVED", "DECISION", "RECOVERY", "TERMINAL"}:
            raise CustodyUnavailable("Unknown LIGHT custody event")
        if kind == "OBSERVED":
            cost = payload.get("execution_ms") if type(payload) is dict else None
            if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
                raise CustodyUnavailable("Observed execution fuel must be finite and nonnegative")
        if any(not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", token) for token in (run_id, scope)):
            raise CustodyUnavailable("Bound run/scope identities required")
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in (request_sha256, profile_sha256)):
            raise CustodyUnavailable("Bound request/profile digests required")
        body = {"schema": self.schema, "nonce": self.nonce, "kind": kind, "run_id": run_id, "scope": scope,
                "request_sha256": request_sha256, "profile_sha256": profile_sha256, "payload": payload}
        encoded = canonical(body)
        body = _loads(encoded)  # freeze JSON semantics before the writer/reread binding
        expected_digest = digest(body)
        result = self.port.author_precommit(encoded, 0.0, expected_digest)
        # Do not accept a status-shaped acknowledgement without actual custody.
        after = _plain_path(self.path).read_bytes() if self.path.exists() else b""
        if (result.status != "SUCCESS" or result.error_message is not None or result.payload != {"seq": len(prior) + 1}
                or not after.startswith(self._expected) or len(after.splitlines()) != len(prior) + 1):
            raise CustodyUnavailable("Existing port did not persist the exact next forecast/custody record")
        following = self._parse_records(after)
        if following != prior + [body]:
            raise CustodyUnavailable("Persisted custody differs from the bound acknowledgement")
        self._write_ack(after, len(following))
        self._expected = after
        if self.records() != following:
            raise CustodyUnavailable("Acknowledged ledger readback differs")
        return expected_digest

    def begin(self, run_id, scope, request_sha256, profile_sha256, max_attempts, max_execution_ms):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 4 or type(max_execution_ms) not in (int, float) or not 0 < max_execution_ms <= 60_000:
            raise CustodyUnavailable("Explicit finite LIGHT fuel is required")
        records = self.records()
        if any(row["run_id"] == run_id for row in records):
            raise CustodyUnavailable("Run identity already used; replay/restart refused")
        begun = {row["run_id"] for row in records if row["scope"] == scope and row["kind"] == "BEGIN"}
        ended = {row["run_id"] for row in records if row["scope"] == scope and row["kind"] == "TERMINAL"
                 and row["payload"].get("scope_reusable") is True}
        if begun - ended:
            raise CustodyUnavailable("Scope has an interrupted/unknown prior run; no retry")
        return self.append("BEGIN", run_id, scope, request_sha256, profile_sha256,
                           {"max_attempts": max_attempts, "max_execution_ms": float(max_execution_ms), "settlement": "UNAVAILABLE", "custody": "DURABLE_LOCAL_EXPOSED"})

    def forecast(self, run_id, scope, request_sha256, profile_sha256, values, prestate_sha256, *, pretrial_peak=None):
        rows = [row for row in self.records() if row["run_id"] == run_id]
        if not rows or rows[0]["kind"] != "BEGIN" or any(row["kind"] == "TERMINAL" for row in rows):
            raise CustodyUnavailable("Active bound run required before dispatch")
        if any((row["scope"], row["request_sha256"], row["profile_sha256"]) != (scope, request_sha256, profile_sha256) for row in rows):
            raise CustodyUnavailable("Run policy/request identity changed")
        forecasts = [row for row in rows if row["kind"] == "FORECAST"]
        observed = [row for row in rows if row["kind"] == "OBSERVED"]
        recovered = [row for row in rows if row["kind"] == "RECOVERY" and row["payload"].get("restored") is True]
        if len(forecasts) >= rows[0]["payload"]["max_attempts"] or len(recovered) != len(forecasts):
            raise CustodyUnavailable("Fuel exhausted or previous candidate not independently restored")
        spent = sum(row["payload"]["execution_ms"] for row in observed)
        if spent >= rows[0]["payload"]["max_execution_ms"]:
            raise CustodyUnavailable("Measured execution fuel exhausted")
        if type(values) not in (tuple, list) or len(values) != 6 or any(type(x) not in (int, float) for x in values):
            raise CustodyUnavailable("Exactly six numeric forecast values required")
        if not all(math.isfinite(value) for value in values) or not isinstance(prestate_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", prestate_sha256):
            raise CustodyUnavailable("Finite forecasts and exact prestate digest required")
        payload = {"attempt": len(forecasts) + 1, "values": list(values), "prestate_sha256": prestate_sha256}
        if pretrial_peak is not None:
            if (type(pretrial_peak) is not dict or set(pretrial_peak) != {"pid", "peak_bytes", "peak_memory_mb", "window", "producer"}
                    or pretrial_peak["pid"] != os.getpid() or type(pretrial_peak["peak_bytes"]) is not int or pretrial_peak["peak_bytes"] <= 0
                    or pretrial_peak["peak_memory_mb"] != pretrial_peak["peak_bytes"] / 1_000_000
                    or pretrial_peak["window"] != "PROCESS_LIFETIME_PEAK_WORKING_SET_AT_OBSERVATION"
                    or pretrial_peak["producer"] != "Windows.GetProcessMemoryInfo.PeakWorkingSetSize"):
                raise CustodyUnavailable("Bound own-process pre-trial peak provenance required")
            payload["pretrial_peak"] = pretrial_peak
        return self.append("FORECAST", run_id, scope, request_sha256, profile_sha256, payload)

    def verify(self, acknowledgement):
        return any(digest(row) == acknowledgement for row in self.records())
