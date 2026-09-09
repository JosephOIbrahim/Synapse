"""Scene/save/load sequences against isolated real persistent backends."""
import importlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from synapse.memory import store as module
from synapse.memory.models import Memory, MemoryTier, MemoryType


class Hip:
    def __init__(self, path):
        self.current = str(path)
        self.callbacks = []

    def path(self):
        return self.current

    def isNewFile(self):
        return not Path(self.current).is_file()

    def addEventCallback(self, callback):
        self.callbacks.append(callback)

    def removeEventCallback(self, callback):
        self.callbacks.remove(callback)

    def fire(self, event, path=None):
        if path is not None:
            self.current = str(path)
        for callback in tuple(self.callbacks):
            callback(event)


@pytest.fixture(params=["jsonl", "moneta"])
def seat(tmp_path, monkeypatch, request):
    backend = request.param
    if backend == "moneta":
        from synapse.memory import moneta_runtime as mr
        if not mr.moneta_available():
            pytest.skip("Real Moneta is unavailable")
    prior = module._global_synapse
    monkeypatch.setattr(module, "_global_synapse", None)
    hip = Hip(tmp_path / "untitled.hip")
    values = {"JOB": str(tmp_path / "default-install"),
              "HFS": str(tmp_path / "default-install"),
              "HOUDINI_TEMP_DIR": str(tmp_path / "temp")}
    events = SimpleNamespace(**{name: name for name in
        ("AfterSave", "BeforeLoad", "AfterLoad", "BeforeClear", "AfterClear")})
    fake = SimpleNamespace(hipFile=hip, hipFileEventType=events,
        getenv=lambda key, default=None: values.get(key, default),
        text=SimpleNamespace(expandString=lambda token: values.get(token.lstrip("$"), token)))
    monkeypatch.setattr(module, "HOU_AVAILABLE", True)
    monkeypatch.setattr(module, "hou", fake, raising=False)
    monkeypatch.setattr(module, "_read_on_main", lambda fn, **kwargs: fn())
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", backend)
    monkeypatch.delenv("SYNAPSE_ENCRYPTION_KEY", raising=False)
    built = []
    def make_store(self, directory):
        if backend == "jsonl":
            result = module.MemoryStore(directory, background_load=False)
        else:
            from synapse.memory.moneta_store import MonetaBackedStore
            from synapse.memory.embedding import HashEmbedder
            result = MonetaBackedStore.from_storage_dir(directory, embedder=HashEmbedder())
        built.append(result)
        return result
    monkeypatch.setattr(module.SynapseMemory, "_make_store", make_store)
    import synapse.session.tracker as tracker
    monkeypatch.setattr(tracker, "_bridge", None)
    try:
        lifecycle = importlib.import_module("synapse.host.memory_lifecycle")
        lifecycle._callback = None
        lifecycle._callback_hou = None
        lifecycle._loading = False
        lifecycle._unsaved_base = None
    except ModuleNotFoundError:
        pass
    yield SimpleNamespace(root=tmp_path, hip=hip, values=values, backend=backend, built=built)
    for store in built:
        closer = getattr(store, "close", None)
        if closer:
            closer()
        else:
            store._shutdown_flush()
    module._global_synapse = prior


def saved(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"isolated HIP address fixture")
    return path


def remember(owner, hip, text, tier=MemoryTier.SHOT):
    record = Memory(content=text, memory_type=MemoryType.DECISION,
                    hip_file=str(hip), tier=tier)
    owner.store.add(record)
    return record


def payloads(owner):
    return {m.id: m.to_json() for m in owner.store.all()}


def test_saved_scene_uses_meaningful_job_root(seat):
    job = seat.root / "show"
    hip = saved(job / "shots" / "a" / "a.hip")
    seat.values["JOB"] = str(job)
    seat.hip.current = str(hip)
    owner = module.get_synapse_memory()
    assert owner.storage_dir == job / ".synapse"


def test_first_save_rebinds_canonical_owner_and_keeps_two_records(seat):
    original = module.get_synapse_memory()
    first = remember(original, seat.hip.current, "Coral sphere")
    second = remember(original, seat.hip.current, "Copper ring")
    hip = saved(seat.root / "show" / "a.hip")
    seat.values["JOB"] = str(hip.parent)
    seat.hip.fire("AfterSave", hip)
    rebound = module.get_synapse_memory()
    assert rebound.storage_dir == hip.parent / ".synapse"
    assert payloads(rebound) == {first.id: first.to_json(), second.id: second.to_json()}
    assert original.storage_dir.exists()


def reopen(seat):
    from synapse.host.memory_lifecycle import _release
    _release(module._global_synapse)
    module._global_synapse = None
    return module.get_synapse_memory()


def test_new_process_reads_saved_records_after_nonfirst_deposit(seat):
    owner = module.get_synapse_memory()
    first = remember(owner, seat.hip.current, "Warm coral hero")
    second = remember(owner, seat.hip.current, "Copper torus")
    old_dir = owner.storage_dir
    hip = saved(seat.root / "show" / "shots" / "a.hip")
    seat.values["JOB"] = str(seat.root / "show")
    seat.hip.fire("AfterSave", hip)
    owner = module.get_synapse_memory()
    third = remember(owner, hip, "Charcoal plinth")
    seat.hip.fire("AfterSave")
    script = """
import json, sys
from pathlib import Path
from synapse.memory.store import MemoryStore
if sys.argv[2] == 'moneta':
    from synapse.memory.moneta_store import MonetaBackedStore
    from synapse.memory.embedding import HashEmbedder
    store = MonetaBackedStore.from_storage_dir(Path(sys.argv[1]), embedder=HashEmbedder())
else:
    store = MemoryStore(Path(sys.argv[1]), background_load=False)
print(json.dumps({m.id: m.to_json() for m in store.all()}, sort_keys=True))
getattr(store, 'close', lambda: store._shutdown_flush())()
"""
    env = dict(os.environ, PYTHONPATH=str(Path(module.__file__).parents[2]))
    from synapse.host.memory_lifecycle import _release
    _release(owner)
    for directory, expected in (
            (owner.storage_dir, {m.id: m.to_json() for m in (first, second, third)}),
            (old_dir, {m.id: m.to_json() for m in (first, second)})):
        result = subprocess.run([sys.executable, "-c", script, str(directory), seat.backend],
                                capture_output=True, text=True, env=env, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout.strip().splitlines()[-1]) == expected


def test_load_never_carries_previous_or_unsaved_records(seat):
    first_owner = module.get_synapse_memory()
    first = remember(first_owner, seat.hip.current, "Do not leak unsaved content")
    b = saved(seat.root / "b" / "scene.hip")
    seat.values["JOB"] = str(b.parent)
    seat.hip.fire("BeforeLoad")
    seat.hip.fire("AfterClear", seat.root / "untitled.hip")
    seat.hip.fire("AfterLoad", b)
    owner_b = module.get_synapse_memory()
    assert owner_b.storage_dir == b.parent / ".synapse"
    assert first.id not in payloads(owner_b)
    second = remember(owner_b, b, "Project B only")
    a = saved(seat.root / "a" / "scene.hip")
    seat.values["JOB"] = str(a.parent)
    seat.hip.fire("BeforeLoad")
    seat.hip.fire("AfterLoad", a)
    assert second.id not in payloads(module.get_synapse_memory())
    seat.values["JOB"] = str(b.parent)
    seat.hip.fire("BeforeLoad")
    seat.hip.fire("AfterLoad", b)
    assert payloads(module.get_synapse_memory()) == {second.id: second.to_json()}


def test_clear_starts_distinct_unsaved_context(seat):
    owner = module.get_synapse_memory()
    memory = remember(owner, seat.hip.current, "Previous unsaved session")
    seat.hip.fire("BeforeClear")
    seat.hip.fire("AfterClear")
    new = module.get_synapse_memory()
    assert new.storage_dir != owner.storage_dir
    assert memory.id not in payloads(new)


def test_save_as_lineage_survives_restart_and_second_cross_project_save(seat):
    from synapse.host.memory_lifecycle import scene_hip_paths, _key
    a = saved(seat.root / "a" / "shots" / "a.hip")
    seat.values["JOB"] = str(seat.root / "a")
    seat.hip.current = str(a)
    original = module.get_synapse_memory()
    memory = remember(original, a, "Inherited coral look")
    project_only = remember(original, a, "Project A confidential look", MemoryTier.SHOW)
    unrelated = remember(original, a.parent / "unrelated.hip", "Different shot")
    a2 = saved(a.parent / "a_v2.hip")
    seat.hip.fire("AfterSave", a2)
    assert module.get_synapse_memory() is original
    owner = reopen(seat)
    assert _key(a) in scene_hip_paths(owner)
    b = saved(seat.root / "b" / "b.hip")
    seat.values["JOB"] = str(b.parent)
    seat.hip.fire("AfterSave", b)
    inherited = module.get_synapse_memory()
    assert payloads(inherited) == {memory.id: memory.to_json()}
    assert project_only.id not in payloads(inherited)
    assert unrelated.id not in payloads(inherited)
    owner = reopen(seat)
    c = saved(seat.root / "c" / "c.hip")
    seat.values["JOB"] = str(c.parent)
    seat.hip.fire("AfterSave", c)
    assert payloads(module.get_synapse_memory()) == {memory.id: memory.to_json()}
    assert {_key(a), _key(a2), _key(b), _key(c)} <= scene_hip_paths(module.get_synapse_memory())


def test_only_records_travel_not_outbox_or_approval_files(seat):
    owner = module.get_synapse_memory()
    memory = remember(owner, seat.hip.current, "Only this decision travels")
    outbox = owner.storage_dir / "loop" / "pending"
    outbox.mkdir(parents=True)
    (outbox / "receipt.json").write_text('{"original_uri": "retained"}')
    (owner.storage_dir / "approval.json").write_text('{"grant": "retained"}')
    hip = saved(seat.root / "show" / "a.hip")
    seat.values["JOB"] = str(hip.parent)
    seat.hip.fire("AfterSave", hip)
    new = module.get_synapse_memory()
    assert memory.id in payloads(new)
    assert not (new.storage_dir / "loop").exists()
    assert not (new.storage_dir / "approval.json").exists()
    assert (outbox / "receipt.json").exists()


def test_adopt_only_current_scene_legacy_store_once(seat):
    from synapse.host import memory_lifecycle as lifecycle
    job = seat.root / "show"
    hip = saved(job / "shots" / "a" / "a.hip")
    sibling = saved(job / "shots" / "b" / "b.hip")
    legacy = module.SynapseMemory(project_path=str(hip.parent))
    wanted = remember(legacy, hip, "Legacy current scene")
    lifecycle._persist(legacy)
    lifecycle._release(legacy)
    other = module.SynapseMemory(project_path=str(sibling.parent))
    unwanted = remember(other, sibling, "Other legacy scene")
    lifecycle._persist(other)
    lifecycle._release(other)
    seat.values["JOB"] = str(job)
    seat.hip.current = str(hip)
    owner = lifecycle.ensure_current_memory()
    assert payloads(owner) == {wanted.id: wanted.to_json()}
    assert unwanted.id not in payloads(owner)
    count = len(seat.built)
    assert lifecycle.ensure_current_memory() is owner
    assert len(seat.built) == count
    assert legacy.storage_dir.exists() and other.storage_dir.exists()


def test_conflicting_destination_keeps_source_owner_and_data(seat):
    from synapse.host import memory_lifecycle as lifecycle
    owner = module.get_synapse_memory()
    memory = remember(owner, seat.hip.current, "Original immutable payload")
    destination = seat.root / "destination"
    other = module.SynapseMemory(project_path=str(destination))
    different = Memory.from_json(memory.to_json())
    different.content = "Conflicting payload"
    other.store.add(different)
    lifecycle._persist(other)
    lifecycle._release(other)
    with pytest.raises(RuntimeError, match="conflicting memory identity"):
        lifecycle.rebind_owner(destination, records=[memory])
    assert module._global_synapse is owner
    assert payloads(owner) == {memory.id: memory.to_json()}
    assert remember(owner, seat.hip.current, "Source still writable").id in payloads(owner)


def test_failed_source_save_does_not_construct_destination(seat, monkeypatch):
    from synapse.host import memory_lifecycle as lifecycle
    owner = module.get_synapse_memory()
    memory = remember(owner, seat.hip.current, "Still held here")
    built = len(seat.built)
    def failure(*args, **kwargs):
        raise OSError("disk unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(owner.store, "save", failure)
        with pytest.raises(OSError, match="disk unavailable"):
            lifecycle.rebind_owner(seat.root / "destination", records=[memory])
    assert len(seat.built) == built
    assert module._global_synapse is owner


def test_callback_failure_retries_save_carry_before_serving(seat, monkeypatch):
    from synapse.host import memory_lifecycle as lifecycle
    owner = module.get_synapse_memory()
    memory = remember(owner, seat.hip.current, "Retry this failed first save")
    hip = saved(seat.root / "saved" / "a.hip")
    seat.values["JOB"] = str(hip.parent)
    with monkeypatch.context() as patch:
        patch.setattr(lifecycle, "_open", lambda base: (_ for _ in ()).throw(OSError("disk full")))
        seat.hip.fire("AfterSave", hip)
        assert module._global_synapse is owner
        with pytest.raises(OSError, match="disk full"):
            lifecycle.ensure_current_memory()
    repaired = lifecycle.ensure_current_memory()
    assert payloads(repaired) == {memory.id: memory.to_json()}
    assert not repaired._memory_binding_error


def test_single_callback_and_tracker_refresh(seat, monkeypatch):
    from synapse.memory.markdown import MarkdownSync
    import synapse.session.tracker as tracker
    owner = module.get_synapse_memory()
    invalidations = []
    bridge = SimpleNamespace(_synapse=owner, _markdown_sync=MarkdownSync(owner.storage_dir),
        invalidate_context_cache=lambda: invalidations.append(True))
    monkeypatch.setattr(tracker, "_bridge", bridge)
    for _ in range(3):
        assert module.get_synapse_memory() is owner
    assert len(seat.hip.callbacks) == 1
    hip = saved(seat.root / "show" / "a.hip")
    seat.values["JOB"] = str(hip.parent)
    seat.hip.fire("AfterSave", hip)
    assert bridge._synapse is module._global_synapse
    assert bridge._synapse is not owner
    assert invalidations
    assert len(seat.hip.callbacks) == 1


def test_worker_initialization_is_pumped_on_main_before_authority_lock(seat, monkeypatch):
    jobs = queue.Queue()
    done = threading.Event()
    result = []
    errors = []
    construction_threads = []
    factory = module.SynapseMemory._make_store
    def construct(self, directory):
        construction_threads.append(threading.current_thread())
        return factory(self, directory)
    monkeypatch.setattr(module.SynapseMemory, "_make_store", construct)
    def dispatch(fn, **kwargs):
        if threading.current_thread() is threading.main_thread():
            return fn()
        jobs.put(fn)
        assert done.wait(10), "Main-thread pump did not finish"
        if errors:
            raise errors[0]
        return result[0]
    monkeypatch.setattr(module, "_read_on_main", dispatch)
    worker_results = []
    thread = threading.Thread(target=lambda: worker_results.append(module.get_synapse_memory()))
    thread.start()
    job = jobs.get(timeout=10)
    # The waiting worker must not own the lock needed by main's constructor.
    assert module._GLOBAL_LOCK.acquire(blocking=False)
    module._GLOBAL_LOCK.release()
    try:
        result.append(job())
    except Exception as exc:
        errors.append(exc)
    finally:
        done.set()
        thread.join(timeout=10)
    assert not thread.is_alive() and not errors
    assert worker_results == [module._global_synapse]
    assert construction_threads == [threading.main_thread()]


@pytest.mark.parametrize("bad_job", ["$MISSING/project", "different", "install"])
def test_unexpanded_unrelated_and_default_install_jobs_use_hip(seat, bad_job):
    hip = saved(seat.root / "show" / "shot.hip")
    seat.hip.current = str(hip)
    if bad_job == "different":
        (seat.root / "other").mkdir()
        seat.values["JOB"] = str(seat.root / "other")
    elif bad_job == "install":
        seat.values["HFS"] = str(seat.root)
        seat.values["JOB"] = str(seat.root)
    else:
        seat.values["JOB"] = bad_job
    assert module.get_synapse_memory().storage_dir == hip.parent / ".synapse"


@pytest.mark.parametrize("damage", ["malformed", "conflicting_id"])
def test_migration_refuses_partial_jsonl_without_rewriting_source(tmp_path, monkeypatch, damage):
    from synapse.host import memory_lifecycle as lifecycle
    directory = tmp_path / "source" / ".synapse"
    directory.mkdir(parents=True)
    record = Memory(content="Preserve this exact source")
    other = Memory.from_json(record.to_json())
    other.content = "Same identity with conflicting content"
    extra = "{broken plaintext record" if damage == "malformed" else other.to_json()
    original = (record.to_json() + "\n" + extra + "\n").encode()
    path = directory / "memory.jsonl"
    path.write_bytes(original)
    store = module.MemoryStore(directory, background_load=False)
    owner = SimpleNamespace(storage_dir=directory, store=store)
    monkeypatch.setattr(module, "_global_synapse", owner)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    try:
        with pytest.raises(RuntimeError, match="JSONL"):
            lifecycle.rebind_owner(tmp_path / "destination", records=[record])
        assert module._global_synapse is owner
        assert path.read_bytes() == original
        assert not (tmp_path / "destination").exists()
    finally:
        store._shutdown_flush()
