"""Owned headless installer probe: actual primary Moneta and native operations."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import types
import traceback


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_config(config):
    c = json.loads(config.read_text(encoding="utf-8"))
    root = Path(c["sandbox"]).resolve()
    output = Path(c["output"]).resolve()
    if (c.get("schema") != "synapse-native-install-check-1" or not root.name.startswith("synapse-native-check-")
            or output.parent != root or config.parent != root):
        raise RuntimeError("Unowned native qualification configuration")
    return c


def main(config):
    c = checked_config(config)
    root = Path(c["sandbox"]).resolve()
    runtime = Path(c["runtime"]).resolve()
    if sys.flags.optimize or c["phase"] not in {"write", "reopen"}:
        raise RuntimeError("Native qualification requires active assertions and a known phase")
    for key in ("HOME", "USERPROFILE", "HOUDINI_USER_PREF_DIR", "HOUDINI_PACKAGE_DIR", "TEMP", "TMP"):
        if not Path(os.environ[key]).resolve().is_relative_to(root):
            raise RuntimeError("Native qualification environment escaped the disposable root")
    manifest = json.loads((runtime / "payload-manifest.json").read_text())
    assert hashlib.sha256((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()).hexdigest() == c["manifest_sha256"]
    assert sys.platform == c["target"]["platform"]
    assert struct.calcsize("P") * 8 == c["target"]["bits"]
    assert ".".join(map(str, sys.version_info[:3])) == c["target"]["python_full"]
    assert os.environ.get("MONETA_NATIVE") == c["native_value"]
    import synapse
    from synapse.server.main_thread import run_on_main
    import hou
    assert Path(synapse.__file__).resolve() == runtime / "python/synapse/__init__.py"
    assert synapse.__version__ == manifest["version"]
    assert run_on_main(lambda: not hou.isUIAvailable() and hou.applicationVersionString() == c["target"]["houdini"], label="setup-native:headless-build")
    assert run_on_main(lambda: Path(hou.getenv("HOUDINI_USER_PREF_DIR")).resolve() == Path(c["preference"]).resolve(), label="setup-native:isolated-preferences")
    project = root / "project"
    scene = project / "disposable.hip"
    if c["phase"] == "write":
        run_on_main(lambda: hou.hipFile.save(str(scene)), label="setup-native:save-disposable")
    else:
        run_on_main(lambda: hou.hipFile.load(str(scene), suppress_save_prompt=True), label="setup-native:reopen-disposable")
    from synapse.memory import store as st
    from synapse.memory.models import Memory
    from synapse.core.crypto import ENCRYPTION_AVAILABLE
    assert ENCRYPTION_AVAILABLE and st._global_synapse is None
    memory = run_on_main(st.get_synapse_memory, label="setup-native:one-primary-owner")
    try:
        assert run_on_main(st.get_synapse_memory, label="setup-native:same-owner") is memory
        assert Path(memory.storage_dir).resolve() == project / ".synapse"
        assert type(memory.store).__name__ == "MonetaBackedStore" and memory.store._handle is not None
        health = st.backend_health(memory.store)
        assert health["status"] == "SUCCESS" and health["active_backend"] == "moneta"
        import moneta
        from moneta import _native
        assert Path(moneta.__file__).resolve().is_relative_to(runtime / "dependencies/moneta/src")
        native = sys.modules.get("moneta_native.moneta_native")
        assert native is not None, "AUTO did not load the native extension"
        native_site = Path(c["native_site"]).resolve()
        for name, expected in c["native_files"].items():
            assert sha(native_site / name) == expected
        assert Path(native.__file__).resolve() == native_site / "moneta_native/moneta_native.pyd"
        before = _native.counters()
        expected = [{"id": "installer-native-%d" % i, "content": "disposable native qualification record %d" % i} for i in range(3)]
        def rows(store):
            return sorted([{"id": r.id, "content": r.content} for r in store.all()], key=lambda r: r["id"])
        if c["phase"] == "write":
            assert rows(memory.store) == []
            for row in expected:
                memory.store.add(Memory(**row), require_durable=True)
        assert rows(memory.store) == expected
        witnessed = {}
        def native_type(t):
            return getattr(native, getattr(t, "__name__", ""), None) is t or "moneta_native" in (getattr(t, "__module__", "") or "")
        def profile(frame, event, arg):
            if event != "c_call":
                return
            owner = getattr(arg, "__self__", None)
            module = getattr(arg, "__module__", "") or ""
            if "moneta_native" in module or (owner is not None and (native_type(type(owner)) or isinstance(owner, types.ModuleType) and "moneta_native" in owner.__name__)):
                name = getattr(arg, "__name__", "unknown")
                witnessed[name] = witnessed.get(name, 0) + 1
        sys.setprofile(profile)
        try:
            for text in ("native qualification", "record 1", "record 2"):
                assert memory.search(text, limit=3)
        finally:
            sys.setprofile(None)
        after = _native.counters()
        delta = {}
        for seam in ("scan", "decay"):
            assert after[seam]["native_calls"] > before[seam]["native_calls"]
            assert not any(after[seam]["fallbacks"].values())
            status = getattr(memory.store._handle.native_status, seam)
            assert status.active == "native" and status.demoted is False and not status.fallbacks
            delta[seam] = after[seam]["native_calls"] - before[seam]["native_calls"]
        assert witnessed and "decay_batch" in witnessed, "No independent Rust callable witness"
        memory.store.save(require_durable=True)
        net = memory.store._jsonl_net
        assert net is not None and rows(net) == expected
        mirror_health = net.health()
        assert mirror_health["degraded"] is False and mirror_health["writable"] is True
        assert mirror_health["rejected_writes"] == mirror_health["overwrote_prior"] == 0
        mirror = project / ".synapse/memory.jsonl"
        lines = [line for line in mirror.read_text(encoding="utf-8").splitlines() if line]
        assert len(lines) == 3 and all(line.startswith("SYNAPSE_ENC_V1:") for line in lines)
        crypto = st._get_crypto()
        decoded = [json.loads(crypto.decrypt_line(line)) for line in lines]
        assert sorted([{"id": r["id"], "content": r["content"]} for r in decoded], key=lambda r: r["id"]) == expected
        assert st.backend_health(memory.store)["active_backend"] == "moneta"
        return {"status": "PASS", "phase": c["phase"], "primary_backend": "moneta",
                "native_value": os.environ["MONETA_NATIVE"],
                "source_commit": manifest["source_revision"], "native_pyd_sha256": sha(native.__file__),
                "native_calls_delta": delta, "native_fallbacks": {}, "native_c_call_witness": witnessed,
                "encrypted_records": 3, "scene_save_or_reopen": True, "preference_isolated": True, "source_or_backend_injected": False}
    finally:
        run_on_main(st.reset_synapse_memory, label="setup-native:close-primary-owner")


if __name__ == "__main__":
    config = Path(sys.argv[1]).resolve()
    c = checked_config(config)  # Refuse unsafe output before even writing a failure.
    try:
        report = main(config)
    except BaseException as exc:
        traceback.print_exc()  # Owned private log: producer line, never locals/key values.
        report = {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)}
    Path(c["output"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"error"}}, sort_keys=True))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
