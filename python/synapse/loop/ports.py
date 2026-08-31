"""ports.py — blueprint §4 contract surface for THE LOOP v5.1.

VERBATIM signatures (blueprint §4):
    PortResult   NamedTuple(status, payload, error_message)  status ∈ SUCCESS|UNAVAILABLE|BLOCKED
    SafetyPort   evaluate_path(agent_id, path_history_hash, recent_actions, proposed_action, scene_state_digest)
    MemoryPort   query_and_filter(relation_keys, task_context_tokens)
    LedgerPort   author_precommit(claim_predicate, probability, world_ref)
    StagePort    compose_sanitized_stage(stage_identifier)

Honest-seam rule: a port whose live substrate is absent reports UNAVAILABLE
with a reason (phantom-API law). Only Moneta is live today. Hanish/SALUS/
Octavius/jacobian-monologue are spec-grounded only — their ports satisfy the
contract surface; their live gates are later rungs.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

# ---------------------------------------------------------------------------
# PortResult + STATUS
# ---------------------------------------------------------------------------

STATUS = frozenset({"SUCCESS", "UNAVAILABLE", "BLOCKED"})


class PortResult(NamedTuple):
    """Uniform result envelope for every port method (blueprint §4)."""

    status: str  # "SUCCESS" | "UNAVAILABLE" | "BLOCKED"
    payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    @classmethod
    def ok(cls, payload: Optional[Dict[str, Any]] = None) -> "PortResult":
        return cls(status="SUCCESS", payload=payload)

    @classmethod
    def unavailable(cls, reason: str) -> "PortResult":
        return cls(status="UNAVAILABLE", error_message=reason)

    @classmethod
    def blocked(cls, reason: str) -> "PortResult":
        return cls(status="BLOCKED", error_message=reason)


def _require_status(result: PortResult) -> PortResult:
    if result.status not in STATUS:
        raise ValueError(
            f"status {result.status!r} not in {sorted(STATUS)} — ports may only "
            "return SUCCESS|UNAVAILABLE|BLOCKED (blueprint §4)"
        )
    return result


# ---------------------------------------------------------------------------
# Repo-relative ledger location (no hardcoded user paths)
# ---------------------------------------------------------------------------

# python/synapse/loop/ports.py -> parents[3] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_LEDGER_FILE = "v00_precommits.jsonl"


def ledger_dir() -> Path:
    """The ledger directory: env SYNAPSE_LOOP_LEDGER_DIR override, else the
    repo-relative harness/loop/ledger/. One oracle for the file location."""
    env_dir = os.environ.get("SYNAPSE_LOOP_LEDGER_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return _REPO_ROOT / "harness" / "loop" / "ledger"


# ---------------------------------------------------------------------------
# Ports (blueprint §4)
# ---------------------------------------------------------------------------


class SafetyPort:
    """f(I, S_k, a_{k+1}, Ω) — path safety. V0.1 rung: SALUS live gate.

    SALUS is spec-grounded, not installed -> every evaluation reports
    UNAVAILABLE naming the absent substrate. Never a fabricated ALLOW.
    """

    def evaluate_path(self, agent_id, path_history_hash, recent_actions,
                      proposed_action, scene_state_digest) -> PortResult:
        return _require_status(PortResult.unavailable(
            "SALUS substrate not installed (substrate_presence.salus=absent); "
            "SafetyPort.evaluate_path is contract-surface-only until V0.1"
        ))


# ---------------------------------------------------------------------------
# Moneta binding: one URI parser, one settlement vocabulary
# ---------------------------------------------------------------------------

MONETA_URI_SCHEME = "moneta-file://"

#: Blueprint §3 step 9 settles exactly these. Hanish models the same space on
#: two axes (Terminal x Verdict, hanish/past/events.py:27,34) and structurally
#: forbids a MISS built from absence -- absence surfaces as UNRESOLVABLE. The
#: flat trio is the SYNAPSE-side deposit vocabulary; nothing here invents a
#: fourth outcome.
SETTLEMENT_OUTCOMES = frozenset({"HIT", "MISS", "UNRESOLVABLE"})


def storage_dir_from_uri(storage_uri: str) -> Optional[Path]:
    """``moneta-file://<absolute posix path>`` -> Path, else None.

    One parser for the URI SYNAPSE itself mints (moneta_store.py:285). A URI
    that does not parse is never guessed at -- the caller reports UNAVAILABLE
    naming the malformed value.
    """
    if not isinstance(storage_uri, str):
        return None
    if not storage_uri.startswith(MONETA_URI_SCHEME):
        return None
    raw = storage_uri[len(MONETA_URI_SCHEME):].strip()
    return Path(raw) if raw else None


# ---------------------------------------------------------------------------
# Recall honesty envelope (docs/BATTLEPLAN.md §5; memory-recall-honesty.yaml)
# ---------------------------------------------------------------------------
#
# MemoryPort recall (``query_and_filter``) can never return empty-success. Same
# failure class as BASTION B1 (cook success-noop): a green light that cannot
# report failure. The honesty rides ENTIRELY in the envelope — no §4 parameter
# name and no ``STATUS`` value changes (tests/test_loop_contracts.py pins both).

_MISSING = object()  # sentinel: an attribute genuinely absent vs present-and-None

#: A bound recall that cannot OBSERVE its substrate returns UNAVAILABLE with one
#: of these as ``error_message`` — the machine-greppable gate name; human detail
#: rides in the payload. ``env_unset`` / ``plugin_unregistered`` are bind-time
#: gates (the Moneta package env never registered / registered-but-unimportable)
#: whose remedy is launch-path, operator-side
#: (harness/battleplan/notes/LAUNCH_PATH_FIX.md). ``layer_uncomposed`` is a
#: bound store whose ECS memory layer is not composed.
RECALL_UNOBSERVABLE_REASONS = frozenset({"env_unset", "plugin_unregistered", "layer_uncomposed"})

#: A recall that RAN and observed its layer but kept nothing returns SUCCESS
#: with ``payload["hit"] is False`` and one of these reasons — never an empty
#: list under a bare SUCCESS. ``predicate_nomatch``: no candidate matched the
#: relation keys. ``quota_pruned``: candidates matched but PG-DRM dropped them
#: all (the ``dropped`` breakdown says which rule).
RECALL_NOMATCH_REASONS = frozenset({"predicate_nomatch", "quota_pruned"})


def _moneta_env_gate() -> str:
    """Split a 'Moneta not importable' bind failure into its canonical gate.

    ``env_unset`` — neither ``$MONETA_SRC`` nor ``$PXR_PLUGINPATH_NAME`` is
        present, so packages/synapse.json never loaded and its env block never
        ran. This is the launch-path defect BP1-TRIAGE bucketed as ``env`` on
        2026-08-31 (hython resolves the classic prefs dir, which has no
        synapse.json). Remedy is operator-side:
        harness/battleplan/notes/LAUNCH_PATH_FIX.md.
    ``plugin_unregistered`` — the env IS present but the package still will not
        import (a drifted or broken adapter).
    """
    env_present = bool(os.environ.get("MONETA_SRC") or os.environ.get("PXR_PLUGINPATH_NAME"))
    return "plugin_unregistered" if env_present else "env_unset"


class MemoryPort:
    """Recall with task-context filtering (PG-DRM), backed by Moneta.

    Moneta's laws (blueprint §1) are enforced at THIS seam:

    * **Max 1 handle per storage_uri.** Moneta owns the actual lock
      (``_ACTIVE_URIS``, api.py:169; enforced in ``Moneta.__init__``
      api.py:198-204, raising ``MonetaResourceLockedError``). This class keeps
      a per-URI handle CACHE so a second ``MemoryPort`` on the same URI
      returns the SAME handle instead of tripping that lock, and translates
      the lock error into an honest BLOCKED when something outside SYNAPSE
      already holds the URI. The cache never replaces the lock -- Moneta's
      lock is single-process, so it stays the authority.
    * **No LLM calls.** Filtering is exact-token set logic over values Moneta
      already computed. Nothing here calls a model.
    * **No background threads.** Nothing spawns; the lock below guards
      re-entrancy on the cache only.
    * **No implicit config.** A port built with no ``storage_uri`` is UNBOUND
      and says so. It never invents a default store location.
    * **No 4th decay point.** Utility is READ off the Moneta row. Decay is
      evaluated at exactly three places inside Moneta (``query`` api.py:401,
      ``reduce_attention_log`` attention_log.py:131, ``run_pass``
      consolidation.py:161) over one pure function (decay.py:48). Recomputing
      ``e^(-λt)`` here would be a second authority for the same number, which
      is precisely what that prohibition forbids.

    Because ``U_now = max(protected_floor, U_last * exp(-λΔt))`` (decay.py:1-22),
    ``protected_floor`` is a FLOOR that keeps an entry alive -- utility can
    never fall below it. So "drop when utility < protected_floor" is
    unreachable by construction and is not the decay filter. The real knobs
    are ``utility_floor`` (drop exhausted entries) and token contamination.

    Honest-seam rule still holds: unbound, or bound to an absent substrate,
    reports UNAVAILABLE naming what is missing -- never a fabricated SUCCESS
    carrying an empty payload (phantom-API law).
    """

    #: storage_uri -> live store handle. Class-level: the law is per process.
    _handles: Dict[str, Any] = {}
    _handles_lock = threading.RLock()

    def __init__(self, storage_uri: Optional[str] = None, *,
                 utility_floor: float = 0.0,
                 distance_threshold: float = 0.85) -> None:
        """Bind to one Moneta store, or stay honestly UNBOUND.

        ``storage_uri`` is optional so the §4 contract surface stays
        constructible with no arguments; it is NOT an implicit default store
        (an unbound port reads nothing and says so).

        ``distance_threshold`` and ``utility_floor`` are constructor config,
        deliberately NOT parameters of :meth:`query_and_filter` -- blueprint §4
        pins that signature to ``(relation_keys, task_context_tokens)`` verbatim
        and tests/test_loop_contracts.py asserts it exactly.
        """
        self._storage_uri = storage_uri
        self._utility_floor = float(utility_floor)
        self._distance_threshold = float(distance_threshold)
        self._store: Optional[Any] = None
        self._bind_error: Optional[str] = None
        self._bind_blocked = False
        if storage_uri is not None:
            self._store, self._bind_error, self._bind_blocked = self._acquire(storage_uri)

    # -- binding ------------------------------------------------------------

    @property
    def storage_uri(self) -> Optional[str]:
        return self._storage_uri

    @property
    def handle(self) -> Optional[Any]:
        """The live store handle, or None when unbound/unavailable."""
        return self._store

    @classmethod
    def _acquire(cls, storage_uri: str) -> Tuple[Optional[Any], Optional[str], bool]:
        """Return (handle, error, blocked) for ``storage_uri``.

        Main-thread ownership (blueprint §1 Synapse law: no ``hou.*`` off the
        main thread, host owns store init) is checked BEFORE any open, so a
        panel/worker thread is refused rather than quietly creating a second
        owner.
        """
        current = threading.current_thread()
        if current is not threading.main_thread():
            return None, (
                "MemoryPort store initialization is main-thread only (host law: "
                "the main Houdini thread owns store init); refused on thread "
                f"{current.name!r}. Panel and workers must read memory state over "
                "the WebSocket observation channel, not by binding a store."
            ), True
        with cls._handles_lock:
            cached = cls._handles.get(storage_uri)
            if cached is not None:
                return cached, None, False
            store, err, blocked = cls._open(storage_uri)
            if store is not None:
                cls._handles[storage_uri] = store
            return store, err, blocked

    @staticmethod
    def _open(storage_uri: str) -> Tuple[Optional[Any], Optional[str], bool]:
        storage_dir = storage_dir_from_uri(storage_uri)
        if storage_dir is None:
            return None, (
                f"storage_uri {storage_uri!r} is not a Moneta URI (expected "
                f"{MONETA_URI_SCHEME}<absolute-path>)"
            ), True
        try:
            from ..memory import moneta_runtime as mr
        except Exception as exc:  # pragma: no cover - import-shape guard
            return None, f"synapse.memory.moneta_runtime unimportable: {exc}", False
        if not mr.moneta_available():
            return None, (
                f"Moneta substrate not importable: {mr.import_error()}; install "
                "the moneta package or point $MONETA_SRC at its source root"
            ), False
        try:
            from ..memory.moneta_store import MonetaBackedStore
            return MonetaBackedStore.from_storage_dir(storage_dir), None, False
        except Exception as exc:
            name = type(exc).__name__
            # Moneta's own single-handle lock (api.py:198-204). Another owner
            # holds this URI -- that is a refusal, not an outage.
            if "Locked" in name:
                return None, (
                    f"Moneta refused a second handle for {storage_uri!r} "
                    f"({name}: {exc}); max 1 handle per storage_uri"
                ), True
            return None, f"Moneta store open failed at {storage_dir}: {name}: {exc}", False

    @classmethod
    def release(cls, storage_uri: Optional[str] = None) -> None:
        """Drop cached handle(s) and close them, releasing Moneta's URI lock.

        Called by the host on teardown, and by tests between cases.
        """
        with cls._handles_lock:
            keys = [storage_uri] if storage_uri is not None else list(cls._handles)
            for key in keys:
                store = cls._handles.pop(key, None)
                close = getattr(store, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:  # pragma: no cover - teardown is best-effort
                        pass

    @staticmethod
    def _unobservable(gate: str, detail: str) -> PortResult:
        """UNAVAILABLE whose ``error_message`` is the canonical gate token and
        whose payload carries the operator detail plus ``candidates_seen=None``
        (recall never got far enough to count). The token is the greppable
        reason; the detail is the human sentence. (docs/BATTLEPLAN.md §5.)"""
        return _require_status(PortResult(
            status="UNAVAILABLE",
            payload={"gate": gate, "detail": detail, "candidates_seen": None},
            error_message=gate,
        ))

    @staticmethod
    def _bind_gate_token(detail: str) -> Optional[str]:
        """Canonical env/plugin gate for a non-blocked bind failure, else None.

        Only the two 'Moneta not importable' failures in :meth:`_open` are
        env/plugin observability gates; both carry ``importable`` in their
        detail. A generic store-open failure carries no such marker and keeps
        its descriptive UNAVAILABLE. env_unset vs plugin_unregistered per
        :func:`_moneta_env_gate`.
        """
        if detail and "importable" in detail:
            return _moneta_env_gate()
        return None

    def _layer_observable(self) -> bool:
        """Whether recall can OBSERVE rows to answer (the layer_uncomposed gate).

        A Moneta-backed store carries a ``_handle``; its rows live on
        ``_handle.ecs`` and are observable only once that layer is composed. A
        store that is not Moneta-backed (no ``_handle``) carries its own rows
        and is always observable via :meth:`_fetch_raw_memories`. Returning
        False here is the ``layer_uncomposed`` gate — the distinction between
        'bound but the memory layer is absent' (UNAVAILABLE) and 'layer present,
        zero rows matched' (an honest SUCCESS no-match) that a bare empty list
        erased. Overridable seam.
        """
        handle = getattr(self._store, "_handle", _MISSING)
        if handle is _MISSING:
            return True
        return getattr(handle, "ecs", None) is not None

    def _guard(self) -> Optional[PortResult]:
        """UNAVAILABLE/BLOCKED when this port cannot honestly answer."""
        if self._storage_uri is None:
            return PortResult.unavailable(
                "MemoryPort is UNBOUND (no storage_uri): PG-DRM cannot filter "
                "without a Moneta handle. Construct with "
                f"{MONETA_URI_SCHEME}<path> to bind."
            )
        if self._store is None:
            detail = self._bind_error or "Moneta handle unavailable"
            if self._bind_blocked:
                return PortResult.blocked(detail)
            # A bind that failed because Moneta would not import is an env/plugin
            # observability gate — name it (env_unset | plugin_unregistered) so
            # recall's UNAVAILABLE vocabulary matches the §5 envelope. A generic
            # open failure keeps its descriptive reason.
            gate = self._bind_gate_token(detail)
            if gate is not None:
                return self._unobservable(gate, detail)
            return PortResult.unavailable(detail)
        return None

    # -- blueprint §3 step 2: Wake ------------------------------------------

    def wake_scene_relations(self, usd_relation_keys) -> PortResult:
        """Wake the candidate memory set for USD relation predicates.

        Deterministic: exact relation-key matching against what the rows
        already carry. Step 2's declared fallback is "no matching relations:
        proceed with flat prompt", so an empty woken set is a real SUCCESS,
        not a failure.
        """
        guard = self._guard()
        if guard is not None:
            return _require_status(guard)
        keys = [k for k in (usd_relation_keys or []) if isinstance(k, str)]
        woken = [m["id"] for m in self._fetch_raw_memories(keys)]
        return _require_status(PortResult.ok({
            "requested_keys": keys,
            "woken_keys": woken,
            "count": len(woken),
        }))

    # -- blueprint §3 step 3: Recall & Filter (PG-DRM) -----------------------

    def query_and_filter(self, relation_keys, task_context_tokens) -> PortResult:
        """Pre-Generation Diagnostic Retrieval Monitoring — the honest recall.

        Drops task-contaminated and exhausted chunks BEFORE prompt assembly,
        using only exact string tokens and the utility Moneta computed. Zero
        LLM inference, zero decay recomputation.

        Recall can never return empty-success (docs/BATTLEPLAN.md §5). The
        envelope lives entirely inside the ratified §4 surface — the signature
        ``(relation_keys, task_context_tokens)`` and the ``STATUS`` set are
        unchanged; the honesty is in the payload:

        * cannot observe the substrate -> UNAVAILABLE, ``error_message`` a gate
          name (env_unset | plugin_unregistered | layer_uncomposed);
        * observed the layer, kept nothing -> SUCCESS, ``payload["hit"] is
          False`` with a ``reason`` (predicate_nomatch | quota_pruned) and
          ``candidates_seen``;
        * kept results -> SUCCESS, ``payload["hit"] is True``.

        An empty ``filtered_memories`` under a bare SUCCESS is unreturnable.
        """
        guard = self._guard()
        if guard is not None:
            return _require_status(guard)

        # The memory layer must be observable or recall cannot honestly answer.
        # A bound store whose ECS layer is not composed is UNAVAILABLE naming the
        # gate — NOT a SUCCESS carrying an empty list. That empty list, returned
        # as if it were a real "nothing recalled", is the silent-recall lie this
        # leg makes unshippable.
        if not self._layer_observable():
            return self._unobservable(
                "layer_uncomposed",
                "bound store carries no composed memory layer (Moneta "
                "_handle.ecs is absent); recall cannot observe rows to filter",
            )

        keys = [k for k in (relation_keys or []) if isinstance(k, str)]
        tokens = {t for t in (task_context_tokens or []) if isinstance(t, str)}

        candidates = self._fetch_raw_memories(keys)
        candidates_seen = len(candidates)

        clean: List[Dict[str, Any]] = []
        dropped = {"exhausted": 0, "contaminated": 0, "unevaluable": 0}

        for memory in candidates:
            utility = memory.get("utility")
            if not isinstance(utility, (int, float)) or isinstance(utility, bool):
                # Unevaluable is NOT "fine". Mirrors mapper.GATE_POLICY: a value
                # that cannot be read blocks rather than passing silently.
                dropped["unevaluable"] += 1
                continue
            if float(utility) <= self._utility_floor:
                dropped["exhausted"] += 1
                continue
            blocked = memory.get("blocked_tokens") or []
            if tokens & {t for t in blocked if isinstance(t, str)}:
                dropped["contaminated"] += 1
                continue
            clean.append(memory)

        payload: Dict[str, Any] = {
            "filtered_memories": clean,
            "count": len(clean),
            "dropped": dropped,
            "candidates_seen": candidates_seen,
            "utility_floor": self._utility_floor,
            "distance_threshold": self._distance_threshold,
        }
        if clean:
            payload["hit"] = True
            return _require_status(PortResult.ok(payload))

        # Ran, observed the layer, kept nothing: an EXPLICIT no-match, never an
        # empty list smuggled under a bare SUCCESS. quota_pruned when candidates
        # matched the relation-key predicate but PG-DRM dropped them all (the
        # ``dropped`` breakdown says which rule); predicate_nomatch when nothing
        # matched the relation keys in the first place.
        payload["hit"] = False
        payload["reason"] = "quota_pruned" if candidates_seen else "predicate_nomatch"
        return _require_status(PortResult.ok(payload))

    # -- blueprint §3 step 9: Settle & Learn --------------------------------

    def deposit_settlement(self, claim_id, outcome,
                           protected_floor: float = 0.2) -> PortResult:
        """Write a settlement deposit to Moneta with a protected floor.

        ``outcome`` must be one of :data:`SETTLEMENT_OUTCOMES`. An unknown
        outcome is BLOCKED rather than coerced -- inventing a verdict is the
        one thing this architecture will not do.
        """
        if not isinstance(claim_id, str) or not claim_id.strip():
            return _require_status(PortResult.blocked(
                "claim_id must be a non-empty string"))
        if outcome not in SETTLEMENT_OUTCOMES:
            return _require_status(PortResult.blocked(
                f"outcome must be one of {sorted(SETTLEMENT_OUTCOMES)}, got {outcome!r}"))
        if isinstance(protected_floor, bool) or \
                not isinstance(protected_floor, (int, float)) or \
                not (0.0 <= protected_floor <= 1.0):
            return _require_status(PortResult.blocked(
                f"protected_floor must be a number in [0,1], got {protected_floor!r}"))

        guard = self._guard()
        if guard is not None:
            return _require_status(guard)

        deposit = {
            "event": "settlement",
            "claim_id": claim_id,
            "outcome": outcome,
            "requested_protected_floor": float(protected_floor),
        }
        try:
            effective = self._write_settlement(deposit)
        except Exception as exc:
            return _require_status(PortResult.unavailable(
                f"settlement deposit failed: {type(exc).__name__}: {exc}"))
        return _require_status(PortResult.ok({
            "deposited": deposit,
            "effective_protected_floor": effective,
        }))

    # -- substrate reads (overridable seams) --------------------------------

    def _fetch_raw_memories(self, keys) -> List[Dict[str, Any]]:
        """Candidate rows for ``keys``, normalized to plain dicts.

        Reads Moneta's ECS rows so ``utility`` and ``protected_floor`` arrive
        exactly as Moneta computed them. Row schema is pinned by
        moneta_store.py:382-384. A row whose payload will not parse is skipped
        rather than failing the whole read.
        """
        ecs = getattr(getattr(self._store, "_handle", None), "ecs", None)
        if ecs is None:
            return []
        wanted = set(keys or [])
        out: List[Dict[str, Any]] = []
        for row in ecs.iter_rows():
            try:
                record = json.loads(getattr(row, "payload", "") or "{}")
            except (TypeError, ValueError):
                continue
            if not isinstance(record, dict):
                continue
            relations = [r for r in (record.get("node_paths") or []) if isinstance(r, str)]
            if wanted and not wanted & set(relations):
                continue
            out.append({
                "id": getattr(row, "entity_id", None) or record.get("id", ""),
                "utility": getattr(row, "utility", None),
                "protected_floor": getattr(row, "protected_floor", None),
                "state": getattr(row, "state", None),
                "last_evaluated": getattr(row, "last_evaluated", None),
                "relation_keys": relations,
                "blocked_tokens": [t for t in (record.get("blocked_tokens") or [])
                                   if isinstance(t, str)],
                "payload": record,
            })
        return out

    def _write_settlement(self, deposit: Dict[str, Any]) -> Optional[float]:
        """Persist one settlement deposit. Returns the floor Moneta applied.

        Routed through the store's public ``add`` so the deposit is embedded,
        floored and snapshotted by the ONE authority that owns those rules
        (moneta_store.py:630-663) rather than by a second code path here.
        """
        from ..memory.models import Memory, MemoryType

        memory = Memory(
            content=json.dumps(deposit, sort_keys=True),
            summary=f"settlement {deposit['outcome']} for {deposit['claim_id']}",
            memory_type=MemoryType.DECISION,   # protected tier: settlements resist decay
            source="gate",
            tags=["settlement", deposit["outcome"].lower()],
        )
        self._store.add(memory)
        return getattr(self._store, "_protected_floor", None)


class LedgerPort:
    """Append-only precommit ledger. The V0.0 invariant: precommit authored
    BEFORE any mutating act, every turn. settle() stays honest-UNAVAILABLE
    until Hanish lands, so every turn verdict is EXPOSED."""

    def __init__(self, ledger_dir_override: Optional[Path] = None) -> None:
        # run_recipe threads its ledger_dir here; the classmethod ledger_path()
        # stays the zero-arg oracle the probes ask.
        self._dir = Path(ledger_dir_override).resolve() if ledger_dir_override else ledger_dir()

    @classmethod
    def ledger_path(cls) -> Path:
        """One oracle: env override or repo-relative default, with the file name."""
        return ledger_dir() / _DEFAULT_LEDGER_FILE

    @property
    def ledger(self) -> Path:
        return self._dir / _DEFAULT_LEDGER_FILE

    def author_precommit(self, claim_predicate, probability, world_ref) -> PortResult:
        """Append one durable precommit line BEFORE the mutating act.

        probability is a number in [0,1] the AUTHOR asserts for the predicate
        at author time — V0.0 honest value is 0.0 (no observed outcome yet,
        the predicate is a pre-registration, not a posterior). A bool is not a
        probability (True is an int subclass) — rejected.
        """
        if isinstance(probability, bool) or \
                not isinstance(probability, (int, float)) or \
                not (0.0 <= probability <= 1.0):
            return _require_status(PortResult.blocked(
                f"probability must be a number in [0,1], got {probability!r}"))
        if not isinstance(claim_predicate, str) or not claim_predicate.strip():
            return _require_status(PortResult.blocked("claim_predicate must be a non-empty string"))
        if not isinstance(world_ref, str) or not world_ref.strip():
            return _require_status(PortResult.blocked("world_ref must be a non-empty string"))

        line = {
            "event": "precommit",
            "claim_predicate": claim_predicate,
            "probability": float(probability),
            "world_ref": world_ref,
            "author": "v0.0-recipe",
            "seq": self._next_seq(),
        }
        # Append + flush + fsync: durable BEFORE the mutation step runs. Never
        # rename over an existing ledger (append-only discipline). A write
        # failure is an honest UNAVAILABLE — never a crash, never a fabricated
        # SUCCESS (blueprint §3 step-6 fallback: log error, turn stays exposed).
        try:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return _require_status(PortResult.unavailable(
                f"ledger dir create failed: {e}"))
        try:
            with open(self.ledger, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            return _require_status(PortResult.unavailable(
                f"ledger write failed: {e}"))
        return _require_status(PortResult.ok({"seq": line["seq"]}))

    def settle(self, turn_id) -> PortResult:
        """Settlement. Hanish (settlement substrate) is absent -> honest
        UNAVAILABLE; the turn stays EXPOSED. Never a fabricated HIT/MISS."""
        return _require_status(PortResult.unavailable(
            "Hanish substrate not installed (substrate_presence.hanish=absent); "
            "settlement honest-UNAVAILABLE until V0.2"
        ))

    def _next_seq(self) -> int:
        if not self.ledger.exists():
            return 1
        n = 0
        for ln in self.ledger.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if rec.get("event") == "precommit":
                    n = max(n, int(rec.get("seq", 0)))
        return n + 1


class StagePort:
    """Sanitized USD stage composition. V0.3 rung: quine filter + drain points.

    Octavius is absent -> compose_sanitized_stage reports UNAVAILABLE naming
    the absent substrate and writes NOTHING to disk (V0.0 gate: closes
    without the Octavius stage present).
    """

    def compose_sanitized_stage(self, stage_identifier) -> PortResult:
        # Deliberately zero side effects: no files, no ledger, no state.
        return _require_status(PortResult.unavailable(
            f"Octavius substrate not installed (substrate_presence.octavius=absent); "
            f"StagePort.compose_sanitized_stage('{stage_identifier}') is "
            "contract-surface-only until V0.3"
        ))
