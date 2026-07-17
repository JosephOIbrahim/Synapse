"""RETINA host hook — manifest writer + .done sentinel wiring tests.

Drives ``synapse.host.retina_manifest`` with a fake ROP node (the module imports
zero ``hou`` — every Houdini touch is a duck-typed ``node`` method — so a plain
fake exercises it fully). Asserts the ADDITIVE + never-raises + honesty
contracts, and that the catalog rulings are honored (husk-level sentinel param;
space-free script path; husk_metadata fingerprint receipt).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from synapse.host import retina_manifest as rm

NOW = "2026-07-16T00:00:00+00:00"


# --------------------------------------------------------------------------
# Fakes (duck-typed hou.Parm / hou.Node)
# --------------------------------------------------------------------------

class FakeParm:
    def __init__(self, name, value=""):
        self._name = name
        self._value = value

    def name(self):
        return self._name

    def unexpandedString(self):
        return self._value

    def eval(self):
        return self._value

    def set(self, v):
        self._value = v


class FakeNode:
    def __init__(self, path="/stage/karma1", parms=None):
        self._path = path
        self._parms = parms or {}

    def path(self):
        return self._path

    def parm(self, name):
        return self._parms.get(name)


@pytest.fixture(autouse=True)
def _clean_retina_env():
    """Snapshot, CLEAR, then restore the env vars the sentinel wiring sets.

    Clearing at setup gives every test a clean slate regardless of what leaked
    in from an earlier test file — e.g. ``test_render.py``'s MagicMock-node
    renders exercise ``install_retina_hooks`` and legitimately set
    ``SYNAPSE_RETINA_MANIFEST`` process-wide. Restoring at teardown keeps this
    file from leaking outward in turn."""
    keys = (rm.MANIFEST_ENV_VAR, "SYNAPSE_RETINA_DONE_FALLBACK")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# --------------------------------------------------------------------------
# assemble_manifest + fingerprint
# --------------------------------------------------------------------------

def test_assemble_manifest_shape():
    m = rm.assemble_manifest(
        rop_path="/stage/karma1",
        products=["/renders/beauty.0001.exr"],
        frame_range=(1, 1),
        generated_at=NOW,
        engine="karma_xpu",
        resolution=(960, 540),
        aovs=["primid"],
    )
    assert m["schema"] == "retina_manifest/v1"
    assert m["products"] == ["/renders/beauty.0001.exr"]
    assert m["resolution"] == [960, 540]
    assert m["frame_range"] == [1, 1]
    assert m["renderer"] == "karma_xpu"
    assert m["fingerprint"].startswith("rm1")
    assert m["scene_fingerprint"].startswith("sf1")


def test_fingerprint_excludes_generated_at():
    base = dict(
        rop_path="/stage/karma1", products=["/r/b.exr"], frame_range=(1, 1),
        engine="karma", resolution=(960, 540),
    )
    a = rm.assemble_manifest(generated_at="2026-01-01T00:00:00+00:00", **base)
    b = rm.assemble_manifest(generated_at="2099-12-31T23:59:59+00:00", **base)
    # Different clock, same declared render -> identical content fingerprint.
    assert a["fingerprint"] == b["fingerprint"]
    assert a["scene_fingerprint"] == b["scene_fingerprint"]


def test_fingerprint_changes_with_declared_render():
    base = dict(
        rop_path="/stage/karma1", products=["/r/b.exr"], frame_range=(1, 1),
        generated_at=NOW, engine="karma",
    )
    a = rm.assemble_manifest(resolution=(960, 540), **base)
    b = rm.assemble_manifest(resolution=(1920, 1080), **base)
    assert a["fingerprint"] != b["fingerprint"]


def test_manifest_path_for_strips_exr_and_sibling():
    assert rm.manifest_path_for("/x/y/beauty.0001.exr").replace("\\", "/") == \
        "/x/y/beauty.0001.retina_manifest.json"


# --------------------------------------------------------------------------
# write_manifest_atomic
# --------------------------------------------------------------------------

def test_write_manifest_atomic_writes_when_dir_exists(tmp_path):
    m = {"schema": "retina_manifest/v1", "products": ["a.exr"]}
    dest = tmp_path / "beauty.retina_manifest.json"
    assert rm.write_manifest_atomic(m, str(dest)) is True
    assert json.loads(dest.read_text(encoding="utf-8"))["products"] == ["a.exr"]
    # no leftover tmp
    assert not (tmp_path / "beauty.retina_manifest.json.tmp").exists()


def test_write_manifest_atomic_no_dir_no_side_effect(tmp_path):
    missing = tmp_path / "does_not_exist" / "m.json"
    assert rm.write_manifest_atomic({"a": 1}, str(missing)) is False
    assert not missing.parent.exists()  # did NOT fabricate a directory


# --------------------------------------------------------------------------
# configure_husk_sentinel — catalog rulings
# --------------------------------------------------------------------------

def _sentinel_node():
    return FakeNode(parms={
        "husk_postframe": FakeParm("husk_postframe"),
        "husk_postrender": FakeParm("husk_postrender"),
        "husk_metadata_key": FakeParm("husk_metadata_key"),
        "husk_metadata_value": FakeParm("husk_metadata_value"),
    })


def test_configure_sentinel_wires_husk_postframe_and_receipt(tmp_path):
    node = _sentinel_node()
    restore = []
    honesty = {}
    script = str(tmp_path / "sentinel.py")  # space-free
    report = rm.configure_husk_sentinel(
        node, manifest_path="/r/m.json", fingerprint="rm1deadbeef",
        sentinel_script=script, restore=restore, honesty=honesty,
    )
    assert report["done_wired"] is True
    assert report["done_param"] == "husk_postframe"  # per-frame preferred
    assert report["receipt_wired"] is True
    # sentinel script landed on husk_postframe
    assert node.parm("husk_postframe").eval() == script
    # receipt landed as synapse_retina_fingerprint
    assert node.parm("husk_metadata_key").eval() == "synapse_retina_fingerprint"
    assert node.parm("husk_metadata_value").eval() == "rm1deadbeef"
    # env carrier set
    assert os.environ[rm.MANIFEST_ENV_VAR] == "/r/m.json"
    # every set was recorded for restore-in-finally (WP4): the env carrier
    # restorer + postframe + metadata key + value.
    assert len(restore) == 4


def test_configure_sentinel_rejects_spaced_script_path():
    node = _sentinel_node()
    restore = []
    honesty = {}
    report = rm.configure_husk_sentinel(
        node, manifest_path="/r/m.json", fingerprint="rm1x",
        sentinel_script="/has a space/sentinel.py", restore=restore, honesty=honesty,
    )
    assert report["done_wired"] is False
    assert "space" in honesty["done_sentinel"]
    assert restore == []  # nothing touched
    # env NOT set on the refusal path
    assert os.environ.get(rm.MANIFEST_ENV_VAR) is None


def test_configure_sentinel_falls_back_to_postrender(tmp_path):
    node = FakeNode(parms={"husk_postrender": FakeParm("husk_postrender")})
    restore, honesty = [], {}
    report = rm.configure_husk_sentinel(
        node, manifest_path="/r/m.json", fingerprint="rm1x",
        sentinel_script=str(tmp_path / "s.py"), restore=restore, honesty=honesty,
    )
    assert report["done_wired"] is True
    assert report["done_param"] == "husk_postrender"


def test_configure_sentinel_missing_params_are_honest(tmp_path):
    node = FakeNode(parms={})  # non-husk ROP
    restore, honesty = [], {}
    report = rm.configure_husk_sentinel(
        node, manifest_path="/r/m.json", fingerprint="rm1x",
        sentinel_script=str(tmp_path / "s.py"), restore=restore, honesty=honesty,
    )
    assert report["done_wired"] is False
    assert report["receipt_wired"] is False
    assert "done_sentinel" in honesty
    assert "fingerprint_receipt" in honesty


def test_configure_sentinel_env_carrier_restores_to_unset(tmp_path):
    # repair (4): the process-global SYNAPSE_RETINA_MANIFEST carrier must ride the
    # SAME restore list the ROP parms do, so applying the handler's finally returns
    # the process env byte-identical. Prior here is UNSET (autouse fixture cleared
    # it) -> restore must POP it back to unset, not leave it set.
    node = _sentinel_node()
    restore, honesty = [], {}
    assert os.environ.get(rm.MANIFEST_ENV_VAR) is None
    rm.configure_husk_sentinel(
        node, manifest_path="/r/m.json", fingerprint="rm1x",
        sentinel_script=str(tmp_path / "s.py"), restore=restore, honesty=honesty,
    )
    assert os.environ[rm.MANIFEST_ENV_VAR] == "/r/m.json"  # set during render
    # apply the restore list exactly as handlers_render's finally does
    for _p, _raw in reversed(restore):
        _p.set(_raw)
    assert os.environ.get(rm.MANIFEST_ENV_VAR) is None  # byte-identical: back to unset


def test_configure_sentinel_env_carrier_restores_prior_value(tmp_path):
    # repair (4): a non-None prior value must be restored verbatim, not popped.
    node = _sentinel_node()
    restore, honesty = [], {}
    os.environ[rm.MANIFEST_ENV_VAR] = "/prior/manifest.json"
    rm.configure_husk_sentinel(
        node, manifest_path="/r/new.json", fingerprint="rm1x",
        sentinel_script=str(tmp_path / "s.py"), restore=restore, honesty=honesty,
    )
    assert os.environ[rm.MANIFEST_ENV_VAR] == "/r/new.json"
    for _p, _raw in reversed(restore):
        _p.set(_raw)
    assert os.environ[rm.MANIFEST_ENV_VAR] == "/prior/manifest.json"


# --------------------------------------------------------------------------
# install_retina_hooks — the entry point (never raises)
# --------------------------------------------------------------------------

def test_install_hooks_end_to_end(tmp_path):
    product = str(tmp_path / "beauty.0001.exr")
    node = _sentinel_node()
    restore = []
    report = rm.install_retina_hooks(
        node,
        product_path=product,
        frame=1,
        engine="karma_xpu",
        node_type="karma",
        resolution=(960, 540),
        restore=restore,
        generated_at=NOW,
        sentinel_script=str(tmp_path / "sentinel.py"),
        houdini_build="22.0.368",
    )
    assert report["ok"] is True
    assert report["manifest_written"] is True
    manifest_path = report["manifest_path"]
    assert os.path.isfile(manifest_path)
    written = json.loads(open(manifest_path, encoding="utf-8").read())
    assert written["products"] == [product]
    assert written["resolution"] == [960, 540]
    assert written["fingerprint"] == report["fingerprint"]
    assert written["manifest_path"] == manifest_path
    # sentinel wired
    assert report["sentinel"]["done_wired"] is True
    assert report["sentinel"]["receipt_wired"] is True


def test_install_hooks_camera_and_aovs_are_honest_at_m1(tmp_path):
    node = _sentinel_node()
    report = rm.install_retina_hooks(
        node, product_path=str(tmp_path / "b.0001.exr"), frame=1, engine="karma",
        node_type="karma", resolution=(960, 540), restore=[], generated_at=NOW,
        sentinel_script=str(tmp_path / "s.py"),
    )
    honesty = report["honesty"]
    # M1 is thin: camera 4x4 + declared AOVs/targets not fabricated.
    assert "camera_matrix" in honesty
    assert "aovs" in honesty
    assert "targets" in honesty


def test_install_hooks_degrades_when_dir_absent_never_raises():
    node = _sentinel_node()
    # product in a non-existent directory -> manifest not written, but no raise.
    report = rm.install_retina_hooks(
        node, product_path="/no/such/dir/b.0001.exr", frame=1, engine="karma",
        node_type="karma", resolution=(960, 540), restore=[], generated_at=NOW,
        sentinel_script="/tmp/s.py",
    )
    assert report["ok"] is False
    assert report["manifest_written"] is False
    assert "manifest" in report["honesty"]


def test_install_hooks_accepts_declared_payload(tmp_path):
    node = _sentinel_node()
    payload = {
        "claim": "material_swap:/geo/crystal",
        "aovs": ["primid"],
        "targets": [{"prim": "/geo/crystal", "world_bbox": [0, 0, 0, 1, 1, 1]}],
        "camera_matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    }
    report = rm.install_retina_hooks(
        node, product_path=str(tmp_path / "b.0001.exr"), frame=1, engine="karma",
        node_type="karma", resolution=(960, 540), restore=[], generated_at=NOW,
        sentinel_script=str(tmp_path / "s.py"), retina_payload=payload,
    )
    manifest = json.loads(open(report["manifest_path"], encoding="utf-8").read())
    assert manifest["claim"] == "material_swap:/geo/crystal"
    assert manifest["aovs"] == ["primid"]
    assert manifest["targets"][0]["prim"] == "/geo/crystal"
    assert manifest["camera_matrix"][0] == 1
    # declared -> no camera/aov honesty flag
    assert "camera_matrix" not in report["honesty"]
    assert "aovs" not in report["honesty"]


def test_install_hooks_never_raises_on_hostile_node(tmp_path):
    class BoomNode:
        def path(self):
            raise RuntimeError("boom")

        def parm(self, name):
            raise RuntimeError("boom")

    report = rm.install_retina_hooks(
        BoomNode(), product_path=str(tmp_path / "b.exr"), frame=1, engine="karma",
        node_type="karma", resolution=None, restore=[], generated_at=NOW,
        sentinel_script=str(tmp_path / "s.py"),
    )
    # A node that raises on every access still yields a report, never an exception.
    assert report["ok"] in (True, False)
    assert "honesty" in report


# --------------------------------------------------------------------------
# The husk post-frame sentinel script (runs in husk's python; zero hou/cv2)
# --------------------------------------------------------------------------

def test_sentinel_drops_done_for_each_product(tmp_path):
    from synapse.host import retina_sentinel_postframe as sentinel

    p1 = tmp_path / "beauty.0001.exr"
    p2 = tmp_path / "beauty.0002.exr"
    p1.write_bytes(b"exr")
    p2.write_bytes(b"exr")
    manifest = tmp_path / "beauty.retina_manifest.json"
    manifest.write_text(json.dumps({
        "products": [str(p1), str(p2)], "fingerprint": "rm1abc",
    }), encoding="utf-8")

    os.environ[rm.MANIFEST_ENV_VAR] = str(manifest)
    written = sentinel.run()
    assert written == 2
    for p in (p1, p2):
        done = tmp_path / (p.name + ".done")
        assert done.exists()
        body = json.loads(done.read_text(encoding="utf-8"))
        assert body["status"] == "rendered"
        assert body["fingerprint"] == "rm1abc"


def test_sentinel_fires_under_husk_exec_namespace(tmp_path):
    """repair (1)/(2) — the dead-sentinel showstopper.

    husk execs its ``--postframe-script`` FILE (it does not import it) with a
    globals dict whose ``__name__ == "builtins"`` — NOT ``"__main__"``. This test
    reproduces husk's invocation faithfully: it exec-s the sentinel's own source
    in a fresh globals dict with ``__name__ == "builtins"`` (not a ``run()`` call,
    not an import) and asserts a ``.done`` drops. It FAILS against the old
    ``if __name__ == "__main__"`` guard (no ``.done`` ever dropped on a real
    render) and PASSES after the fix.
    """
    from synapse.host import retina_sentinel_postframe as sentinel

    product = tmp_path / "beauty.0001.exr"
    product.write_bytes(b"exr")
    manifest = tmp_path / "beauty.retina_manifest.json"
    manifest.write_text(json.dumps({
        "products": [str(product)], "fingerprint": "rm1husk",
    }), encoding="utf-8")
    os.environ[rm.MANIFEST_ENV_VAR] = str(manifest)

    # Faithful husk reproduction: run the file's OWN source in a globals dict whose
    # __name__ == "builtins" (the assayer-proved husk exec namespace).
    source = Path(sentinel.__file__).read_text(encoding="utf-8")
    husk_globals = {"__name__": "builtins", "__file__": sentinel.__file__}
    exec(compile(source, sentinel.__file__, "exec"), husk_globals)

    done = tmp_path / "beauty.0001.exr.done"
    assert done.exists(), "husk-exec surface (__name__=='builtins') must drop .done"
    body = json.loads(done.read_text(encoding="utf-8"))
    assert body["status"] == "rendered"
    assert body["fingerprint"] == "rm1husk"


def test_sentinel_plain_import_has_no_side_effect(tmp_path):
    """The flip side of repair (1): a normal ``import`` must NOT fire run() — the
    guard fires only on the ``__main__``/``builtins`` execution surfaces, so the
    module stays importable by tests with zero side effect."""
    import importlib

    # Point the carrier at a manifest with a product whose .done would be visible
    # if a mere import fired run().
    product = tmp_path / "should_not.0001.exr"
    product.write_bytes(b"exr")
    manifest = tmp_path / "should_not.retina_manifest.json"
    manifest.write_text(json.dumps({"products": [str(product)]}), encoding="utf-8")
    os.environ[rm.MANIFEST_ENV_VAR] = str(manifest)

    import synapse.host.retina_sentinel_postframe as sentinel
    importlib.reload(sentinel)  # re-exec the module body via the import machinery

    assert not (tmp_path / "should_not.0001.exr.done").exists()


def test_sentinel_no_env_is_honest_not_silent(tmp_path):
    from synapse.host import retina_sentinel_postframe as sentinel

    os.environ.pop(rm.MANIFEST_ENV_VAR, None)
    fallback = tmp_path / "unresolved"
    os.environ["SYNAPSE_RETINA_DONE_FALLBACK"] = str(fallback)
    written = sentinel.run()
    # Wrote an inconclusive marker to the fallback — visible, not silent (§7).
    assert written == 1
    body = json.loads((tmp_path / "unresolved.done").read_text(encoding="utf-8"))
    assert body["status"] == "inconclusive"


def test_sentinel_no_env_no_fallback_returns_zero():
    from synapse.host import retina_sentinel_postframe as sentinel

    os.environ.pop(rm.MANIFEST_ENV_VAR, None)
    os.environ.pop("SYNAPSE_RETINA_DONE_FALLBACK", None)
    assert sentinel.run() == 0  # no products resolvable, nothing to write, no raise


def test_sentinel_full_loop_with_host_hook(tmp_path):
    """End-to-end: host hook writes the manifest + sets the env; the sentinel
    then resolves it and drops .done — the two halves agree on the contract."""
    from synapse.host import retina_sentinel_postframe as sentinel

    product = tmp_path / "beauty.0001.exr"
    product.write_bytes(b"exr-bytes")
    node = _sentinel_node()
    report = rm.install_retina_hooks(
        node, product_path=str(product), frame=1, engine="karma",
        node_type="karma", resolution=(960, 540), restore=[], generated_at=NOW,
        sentinel_script=str(tmp_path / "sentinel.py"),
    )
    assert report["ok"] is True
    # install_retina_hooks set the env carrier; the sentinel reads it.
    assert os.environ[rm.MANIFEST_ENV_VAR] == report["manifest_path"]
    written = sentinel.run()
    assert written == 1
    assert (tmp_path / "beauty.0001.exr.done").exists()
