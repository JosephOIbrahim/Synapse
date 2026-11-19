"""Store tests: append-only, single-writer, validate-on-read, indexes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.sim.schema import (  # noqa: E402
    AttemptRecord,
    ClusterStatus,
    EditScope,
    Observation,
    Prediction,
    ProblemCluster,
    SelectorVerdict,
    cluster_id_for,
)
from harness.sim.harness_hash import surface_tree_hash  # noqa: E402
from harness.sim.setting import SettingFingerprint  # noqa: E402
from harness.sim.store import SIMStore, StoreError, cluster_status_counts  # noqa: E402

SIG = "store test signature: guard refused unbound code read"
HASH_A = "a" * 64
HASH_B = "b" * 64


def _setting(model: str = "claude-opus-5-5") -> SettingFingerprint:
    return SettingFingerprint(model_id=model, eval_split_id="bench-12/evo", harness_hash=HASH_A)


def _cluster(signature: str = SIG) -> ProblemCluster:
    return ProblemCluster(
        cluster_id=cluster_id_for(signature),
        symptom_signature=signature,
        root_cause_diagnosis="guard refuses a read it cannot bind",
        status=ClusterStatus.OPEN,
        created_utc="2026-11-18T12:00:00+00:00",
    )


def _record(cluster: ProblemCluster, attempt: str = "att-1", **overrides) -> AttemptRecord:
    base = dict(
        attempt_id=attempt,
        cluster_id=cluster.cluster_id,
        round_id="round-1",
        parent_harness_hash=HASH_A,
        candidate_harness_hash=HASH_B,
        setting=_setting(),
        edit_scope=EditScope.INVARIANT_GATE,
        target_artifact="python/synapse/panel/worker_policy.py",
        diff_patch="--- a\n+++ b\n@@\n+ allow\n",
        edit_rationale="bind the read before the guard evaluates it",
        ex_ante_prediction=Prediction(expected_delta=0.1, target_metric="guard.false_refusals", max_regression=0.0),
        ex_post_observation=Observation(measured_delta=0.08),
        selector_verdict=SelectorVerdict.RETAIN,
        created_utc="2026-11-18T12:05:00+00:00",
    )
    base.update(overrides)
    return AttemptRecord(**base)


@pytest.fixture()
def store(tmp_path: Path) -> SIMStore:
    s = SIMStore(tmp_path / "ledger")
    s.declare_cluster(_cluster())
    return s


class TestAppendOnly:
    def test_declare_once_is_idempotent(self, store: SIMStore):
        store.declare_cluster(_cluster())
        assert len(store.clusters()) == 1

    def test_redeclare_with_different_content_is_refused(self, store: SIMStore):
        changed = ProblemCluster(
            cluster_id=cluster_id_for(SIG),
            symptom_signature=SIG,
            root_cause_diagnosis="a different diagnosis",
            status=ClusterStatus.MITIGATED,
            created_utc="2026-11-18T12:30:00+00:00",
        )
        with pytest.raises(StoreError, match="append-only"):
            store.declare_cluster(changed)

    def test_store_exposes_no_mutation_or_delete(self, store: SIMStore):
        for forbidden in ("update", "delete", "remove", "replace"):
            assert not hasattr(store, forbidden), f"SIMStore must not expose {forbidden}()"


class TestWriteRules:
    def test_append_to_unknown_cluster_is_refused(self, tmp_path: Path):
        empty = SIMStore(tmp_path / "empty")
        with pytest.raises(StoreError, match="declare it"):
            empty.append(_record(_cluster()))

    def test_second_writer_is_refused(self, store: SIMStore):
        cluster = _cluster()
        lock = store._lock_path(cluster.cluster_id)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("held", encoding="utf-8")
        with pytest.raises(StoreError, match="another writer"):
            store.append(_record(cluster))
        lock.unlink()
        store.append(_record(cluster))  # and the store works once the lock is gone

    def test_append_then_read(self, store: SIMStore):
        store.append(_record(_cluster()))
        records = store.attempts_for(_cluster().cluster_id)
        assert [r.attempt_id for r in records] == ["att-1"]

    def test_append_is_additive(self, store: SIMStore):
        cluster = _cluster()
        store.append(_record(cluster, attempt="att-1"))
        store.append(_record(cluster, attempt="att-2"))
        assert [r.attempt_id for r in store.attempts_for(cluster.cluster_id)] == ["att-1", "att-2"]


class TestValidateOnRead:
    def test_a_hand_edited_line_fails_to_load(self, store: SIMStore):
        cluster = _cluster()
        store.append(_record(cluster))
        path = store._attempts_path(cluster.cluster_id)
        payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        payload["selector_verdict"] = "NOT_A_VERDICT"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with pytest.raises(StoreError, match="does not validate"):
            store.attempts_for(cluster.cluster_id)

    def test_a_truncated_line_fails_to_load(self, store: SIMStore):
        cluster = _cluster()
        store.append(_record(cluster))
        path = store._attempts_path(cluster.cluster_id)
        path.write_text(path.read_text(encoding="utf-8")[:-12], encoding="utf-8")
        with pytest.raises(StoreError, match="does not validate"):
            store.attempts_for(cluster.cluster_id)


class TestSurfaceHash:
    """H_t identity: the hash a record names as its parent.

    A declared surface moves the hash; an undeclared file does not. That
    distinction is what lets a candidate diff be expressed at all.
    """

    SURFACES = ("bench/recipes/**/*", "bench/routing.json")

    def _tree(self, tmp_path: Path) -> Path:
        root = tmp_path / "harness_tree"
        (root / "bench" / "recipes").mkdir(parents=True)
        (root / "bench" / "recipes" / "a.yaml").write_text("x: 1\n", encoding="utf-8")
        (root / "bench" / "routing.json").write_text("{}\n", encoding="utf-8")
        return root

    def test_same_tree_same_hash(self, tmp_path: Path):
        root = self._tree(tmp_path)
        assert surface_tree_hash(root, self.SURFACES) == surface_tree_hash(root, self.SURFACES)

    def test_declared_edit_moves_the_hash(self, tmp_path: Path):
        root = self._tree(tmp_path)
        before = surface_tree_hash(root, self.SURFACES)
        (root / "bench" / "recipes" / "a.yaml").write_text("x: 2\n", encoding="utf-8")
        assert surface_tree_hash(root, self.SURFACES) != before

    def test_undeclared_file_does_not(self, tmp_path: Path):
        root = self._tree(tmp_path)
        before = surface_tree_hash(root, self.SURFACES)
        (root / "notes.txt").write_text("irrelevant\n", encoding="utf-8")
        assert surface_tree_hash(root, self.SURFACES) == before

    def test_new_declared_file_moves_the_hash(self, tmp_path: Path):
        root = self._tree(tmp_path)
        before = surface_tree_hash(root, self.SURFACES)
        (root / "bench" / "recipes" / "b.yaml").write_text("x: 3\n", encoding="utf-8")
        assert surface_tree_hash(root, self.SURFACES) != before

    def test_a_declared_pattern_that_matches_nothing_still_counts(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert surface_tree_hash(empty, ("nothing/**/*",)) != surface_tree_hash(empty, ())


class TestQueries:
    def test_query_by_signature_uses_the_cluster_id(self, store: SIMStore):
        store.append(_record(_cluster()))
        assert len(store.query_by_signature(SIG)) == 1

    def test_query_by_setting_filters(self, store: SIMStore):
        cluster = _cluster()
        store.append(_record(cluster, attempt="att-1"))
        store.append(_record(cluster, attempt="att-2", setting=_setting(model="claude-sonnet-5-5")))
        same_model = store.query_by_setting(_setting())
        assert [r.attempt_id for r in same_model] == ["att-1"]

    def test_known_negatives_excludes_retained(self, store: SIMStore):
        cluster = _cluster()
        store.append(_record(cluster, attempt="kept"))
        store.append(
            _record(cluster, attempt="killed", selector_verdict=SelectorVerdict.REMOVE)
        )
        negatives = store.known_negatives("python/synapse/panel/worker_policy.py", _setting())
        assert [r.attempt_id for r in negatives] == ["killed"]

    def test_status_counts(self, store: SIMStore):
        assert cluster_status_counts(store)["OPEN"] == 1

    def test_replace_is_a_retained_outcome_not_a_negative(self, store: SIMStore):
        """REPLACE says the edit superseded an incumbent; it did not fail."""
        cluster = _cluster()
        store.append(_record(cluster, attempt="replaced", selector_verdict=SelectorVerdict.REPLACE))
        negatives = store.known_negatives("python/synapse/panel/worker_policy.py", _setting())
        assert negatives == []

    def test_known_negatives_is_scoped_to_the_edit(self, store: SIMStore):
        cluster = _cluster()
        store.append(_record(cluster, attempt="killed", selector_verdict=SelectorVerdict.REMOVE))
        same = store.known_negatives("python/synapse/panel/worker_policy.py", _setting(),
                                     diff_patch="--- a\n+++ b\n@@\n+ allow\n")
        other = store.known_negatives("python/synapse/panel/worker_policy.py", _setting(),
                                      diff_patch="--- a\n+++ b\n@@\n- different\n")
        assert [r.attempt_id for r in same] == ["killed"]
        assert other == []


class TestClusterFiles:
    def test_a_cluster_filename_must_match_its_content_id(self, tmp_path: Path):
        """Write keys by filename, read keys by content id.

        Letting them disagree hides a cluster's attempts from every ledger-wide
        query, including the duplicate check.
        """
        s = SIMStore(tmp_path / "ledger")
        s.declare_cluster(_cluster())
        cluster = _cluster()
        right = s.root / f"{cluster.cluster_id}.cluster.json"
        wrong = s.root / f"pc-{'0' * 16}.cluster.json"
        wrong.write_bytes(right.read_bytes())
        with pytest.raises(StoreError, match="filename must equal its id"):
            s.clusters()

    def test_a_failed_cluster_write_leaves_no_cluster_and_no_temp(self, tmp_path: Path, monkeypatch):
        import harness.sim.store as store_module

        s = SIMStore(tmp_path / "ledger")

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(store_module.os, "link", boom)
        with pytest.raises(OSError):
            s.declare_cluster(_cluster())
        cluster = _cluster()
        assert not (s.root / f"{cluster.cluster_id}.cluster.json").exists()
        assert list(s.root.glob(".*.tmp")) == []
        assert s.clusters() == []

    def test_a_successful_write_leaves_no_temp_behind(self, store: SIMStore):
        assert list(store.root.glob(".*.tmp")) == []

    def test_the_store_is_usable_after_a_failed_cluster_write(self, tmp_path: Path, monkeypatch):
        import harness.sim.store as store_module

        s = SIMStore(tmp_path / "ledger")
        real_link = store_module.os.link

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(store_module.os, "link", boom)
        with pytest.raises(OSError):
            s.declare_cluster(_cluster())
        monkeypatch.setattr(store_module.os, "link", real_link)
        s.declare_cluster(_cluster())
        assert [c.cluster_id for c in s.clusters()] == [_cluster().cluster_id]

    def test_two_concurrent_declarations_publish_valid_bytes(self, tmp_path: Path):
        """Same-cluster concurrency must never leave two writers' bytes interleaved."""
        import json as _json
        import threading

        s = SIMStore(tmp_path / "ledger")
        cluster = _cluster()
        errors = []

        def declare():
            try:
                s.declare_cluster(cluster)
            except StoreError:
                pass  # one of them may lose the race; that is the refusal working
            except Exception as exc:  # pragma: no cover - a different failure
                errors.append(exc)

        threads = [threading.Thread(target=declare) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        payload = _json.loads((s.root / f"{cluster.cluster_id}.cluster.json").read_text(encoding="utf-8"))
        assert payload["cluster_id"] == cluster.cluster_id
        assert list(s.root.glob(".*.tmp")) == []


class TestTornTail:
    def test_append_refuses_a_torn_tail(self, store: SIMStore):
        """An interrupted write leaves a partial line; appending would corrupt a second record."""
        cluster = _cluster()
        store.append(_record(cluster, attempt="att-1"))
        path = store._attempts_path(cluster.cluster_id)
        torn = path.read_bytes()[:-5]
        path.write_bytes(torn)
        with pytest.raises(StoreError, match="torn tail"):
            store.append(_record(cluster, attempt="att-2"))
        # The refusal must not touch the file: a store that truncated before
        # raising would pass a test that only checked the exception.
        assert path.read_bytes() == torn
