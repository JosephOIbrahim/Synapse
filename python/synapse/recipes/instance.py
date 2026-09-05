"""Scene-local recipe identity over BLOCKS ownership, without reconciliation.

All host observation/storage callbacks run through ``run_on_main``. The
canonicalizer and complete authored-state capture are injected: the legacy
BLOCKS snapshot alone cannot certify expressions, nested shaders or ports.
Unknown metadata is never adopted as a freshly approved baseline.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from .contracts import ActionId, RecipeInstance, RecipeSpec, Refusal, RefusalKind


class LifecycleUnavailable(RuntimeError):
    """UNAVAILABLE: required observation, identity or host evidence is absent."""


class Canonicalizer(Protocol):
    def semantic_digest(self, state: Mapping[str, Any], *, version: str) -> str: ...


@dataclass(frozen=True)
class ScopeObservation:
    box_present: bool
    # Stable for this box's lifetime; different after delete/recreate or reload.
    scope_token: str
    owned_node_ids: Mapping[str, str]
    authored_state: Mapping[str, Any]
    complete: bool = False
    reason: str = "complete semantic capture is unavailable"


class ScopeObserver(Protocol):
    def __call__(self, stage_path: str, spec: RecipeSpec,
                 box_name: str) -> ScopeObservation: ...


class InstanceStore(Protocol):
    """Host-owned metadata, keyed by a scene/box lifetime, never just a path.

    ``save`` must be atomic (failure must preserve the prior record). A store
    persisting in HIP data must participate in the host transaction's undo.
    """
    def load(self, scope_token: str) -> RecipeInstance | None: ...
    def save(self, scope_token: str, instance: RecipeInstance) -> None: ...
    def after_undo(self, scope_token: str, before: RecipeInstance | None) -> None:
        """Restore session-only data, or verify HIP metadata was already undone.

        Must not issue scene writes. Persistent stores raise if the undo did
        not restore their record; that becomes UNKNOWN recovery.
        """
        ...


class MemoryInstanceStore:
    """Session-only store; reload needs a new token, or a persistent host store.

    Losing this store intentionally makes existing boxes UNAVAILABLE, rather
    than blessing artist changes. Callers serialize access on the host thread.
    """
    def __init__(self):
        self._records: dict[str, RecipeInstance] = {}

    def load(self, scope_token):
        return deepcopy(self._records.get(scope_token))

    def save(self, scope_token, instance):
        self._records[scope_token] = deepcopy(instance)

    def after_undo(self, scope_token, before):
        if before is None:
            self._records.pop(scope_token, None)
        else:
            self._records[scope_token] = deepcopy(before)


def on_main(fn: Callable[[], Any]) -> Any:
    from synapse.server.main_thread import run_on_main
    return run_on_main(fn, label="recipes:lifecycle")


class BlocksObserver:
    """Reuse ``blocks.runtime.observe``; supplement its deliberately narrow read.

    ``fixture`` is the SPEC adapter's BLOCKS fixture. ``capture`` must read the
    complete selected scope (including nested shaders, exact ports, authored
    expressions/flags), and identify the scene/box lifetime. No guessed names
    or hand-written third reconciler live here. Without capture we fail closed.
    """
    def __init__(self, fixture: Mapping[str, Any], capture: Callable | None = None):
        self.fixture = deepcopy(dict(fixture))
        self.capture = capture

    def __call__(self, stage_path, spec, box_name):
        from synapse.blocks.runtime import observe
        raw = observe(self.fixture, box_name, stage_path)
        if not raw["box_present"]:
            return ScopeObservation(False, "", {}, {}, True, "")
        if self.capture is None:
            raise LifecycleUnavailable(
                "UNAVAILABLE: BLOCKS observe lacks nested/expressions/port capture")
        captured = self.capture(raw, spec)
        if not isinstance(captured, ScopeObservation):
            raise LifecycleUnavailable("UNAVAILABLE: invalid complete scope capture")
        # A supplementary reader may not contradict the ownership authority.
        roots = {p.rsplit("/", 1)[-1] for p in captured.owned_node_ids.values()
                 if p.rsplit("/", 1)[0] == stage_path.rstrip("/")}
        if not captured.box_present or not roots.issubset(raw["box_members"]):
            raise LifecycleUnavailable("UNAVAILABLE: capture contradicts BLOCKS membership")
        return captured


class InstanceLifecycle:
    def __init__(self, stage_path: str, spec: RecipeSpec, *, observer: ScopeObserver,
                 canonicalizer: Canonicalizer, store: InstanceStore,
                 dispatch: Callable = on_main, box_name: str | None = None):
        from synapse.blocks.fixtures import box_name_for
        self.stage_path = stage_path
        self.spec = spec
        self.box_name = box_name or box_name_for({}, spec.recipe_id)
        self.observer, self.canonicalizer, self.store = observer, canonicalizer, store
        self.dispatch = dispatch
        self._tokens: dict[str, str] = {}

    def observe(self) -> ScopeObservation:
        return self.dispatch(lambda: self.observer(self.stage_path, self.spec, self.box_name))

    def _digest(self, observation: ScopeObservation) -> str:
        if not observation.complete:
            raise LifecycleUnavailable("UNAVAILABLE: " + observation.reason)
        if observation.box_present and not observation.scope_token:
            raise LifecycleUnavailable("UNAVAILABLE: scene/box lifetime is unknown")
        digest = self.canonicalizer.semantic_digest(
            deepcopy(observation.authored_state), version=self.spec.canonicalizer)
        if not isinstance(digest, str) or not digest:
            raise LifecycleUnavailable("UNAVAILABLE: canonicalizer returned no digest")
        return digest

    def discover(self, stage_path: str | None = None,
                 spec: RecipeSpec | None = None) -> RecipeInstance | None:
        if stage_path not in (None, self.stage_path) or spec not in (None, self.spec):
            raise ValueError("discover must use the lifecycle's bound stage/spec")
        def read():
            observed = self.observe()
            if not observed.box_present:
                return None
            self._digest(observed)
            record = self.store.load(observed.scope_token)
            if record is None:
                raise LifecycleUnavailable("UNAVAILABLE: owned box has no committed instance record")
            if (record.recipe_id, record.recipe_version, record.network_box) != (
                    self.spec.recipe_id, self.spec.version, self.box_name):
                raise LifecycleUnavailable("UNAVAILABLE: instance record/spec ownership mismatch")
            self._tokens[record.instance_id] = observed.scope_token
            return record
        return self.dispatch(read)

    def new_instance(self, owned_node_ids: Mapping[str, str]) -> RecipeInstance:
        """Uncommitted candidate; only a successful transaction may register it."""
        if self.observe().box_present:
            raise LifecycleUnavailable("UNAVAILABLE: BUILD requires a clean owned scope")
        return RecipeInstance(uuid4().hex, self.spec.recipe_id, self.spec.version,
                              dict(owned_node_ids), {}, 0, "", self.box_name)

    def fingerprint(self, instance: RecipeInstance) -> str:
        observed = self.observe()
        if not observed.box_present:
            raise LifecycleUnavailable("UNAVAILABLE: instance scope is absent")
        token = self._tokens.get(instance.instance_id)
        if instance.graph_revision and token is None:
            record = self.dispatch(lambda: self.store.load(observed.scope_token))
            if record is None or record.instance_id != instance.instance_id:
                raise LifecycleUnavailable("UNAVAILABLE: instance identity is not current")
            token = observed.scope_token
        if (token is not None and token != observed.scope_token) or (
                dict(observed.owned_node_ids) != instance.owned_node_ids):
            raise LifecycleUnavailable("UNAVAILABLE: instance ownership changed")
        return self._digest(observed)

    def check_revision(self, instance: RecipeInstance, expected_revision: int) -> Refusal | None:
        live = self.discover()
        revision = 0 if live is None else live.graph_revision
        if (revision != expected_revision or instance.graph_revision != expected_revision or
                (live is None and instance.graph_revision != 0) or
                (live is not None and live.instance_id != instance.instance_id)):
            return Refusal(RefusalKind.STALE, "instance identity/revision changed")
        return None

    def check_conflict(self, instance: RecipeInstance) -> Refusal | None:
        observed = self.observe()
        if not observed.box_present:
            if instance.graph_revision == 0 and not instance.authored_baseline:
                return None
            return Refusal(RefusalKind.CONFLICT, "owned scope was removed")
        digest = self._digest(observed)
        token = self._tokens.get(instance.instance_id)
        if (not instance.authored_baseline or digest != instance.authored_baseline or
                dict(observed.owned_node_ids) != instance.owned_node_ids or
                (token is not None and token != observed.scope_token)):
            return Refusal(RefusalKind.CONFLICT, "authored state diverged from committed baseline")
        return None

    def commit(self, instance: RecipeInstance, *, action: ActionId,
               slots: Mapping[str, Any], approved: bool,
               expected_revision: int) -> RecipeInstance:
        """Called inside the mutation window after independent verification.

        Store a copy before updating the caller object. BUILD never uses this
        method for an existing instance: measured no-op bypasses all defaults.
        """
        if action not in (ActionId.BUILD, ActionId.LIGHT, ActionId.MATERIAL):
            raise ValueError("not a graph action")
        if action != ActionId.BUILD and not approved:
            raise ValueError("approved field commit required")
        if action == ActionId.BUILD and instance.graph_revision:
            raise ValueError("existing BUILD must be a measured no-op")
        def save():
            observed = self.observe()
            if not observed.box_present or dict(observed.owned_node_ids) != instance.owned_node_ids:
                raise LifecycleUnavailable("UNAVAILABLE: post-build ownership does not match")
            prior = self.store.load(observed.scope_token)
            if ((prior is None and expected_revision != 0) or
                    (prior is not None and (prior.graph_revision != expected_revision or
                     prior.instance_id != instance.instance_id))):
                raise LifecycleUnavailable("STALE: metadata changed before commit")
            updated = deepcopy(instance)
            updated.graph_revision = expected_revision + 1
            updated.committed_slots.update(deepcopy(dict(slots)))
            updated.authored_baseline = self._digest(observed)
            self.store.save(observed.scope_token, updated)
            self._tokens[updated.instance_id] = observed.scope_token
            instance.__dict__.update(deepcopy(updated.__dict__))
            return updated
        return self.dispatch(save)

    def restore_metadata_after_undo(self, before: RecipeInstance):
        """Undo driver has terminated; synchronize/verify non-graph identity."""
        token = self._tokens[before.instance_id]
        prior = before if before.graph_revision else None
        self.dispatch(lambda: self.store.after_undo(token, prior))


def discover(stage_path: str, spec: RecipeSpec, *, lifecycle: InstanceLifecycle):
    return lifecycle.discover(stage_path, spec)


def fingerprint(instance: RecipeInstance, *, lifecycle: InstanceLifecycle) -> str:
    return lifecycle.fingerprint(instance)


def check_revision(instance: RecipeInstance, expected_revision: int, *, lifecycle: InstanceLifecycle):
    return lifecycle.check_revision(instance, expected_revision)


def check_conflict(instance: RecipeInstance, *, lifecycle: InstanceLifecycle):
    return lifecycle.check_conflict(instance)
