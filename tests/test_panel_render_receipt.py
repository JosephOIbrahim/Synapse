"""FORGE Panel Mile 2 — the RETINA render-receipt compute path (pure-python).

Exercises ``synapse.panel.render_receipt.compute_receipt`` — the Qt-free seam the
worker runs on its background thread — against synthetic manifests + on-disk
fixtures. No Qt, no hou: this runs as a real CI signal under stock CPython (the
worker itself hard-imports PySide and would SKIP).

Load-bearing properties pinned here:
  * a render tool with a written manifest → the real T0 verdict flows through;
  * no manifest_path / absent manifest file / non-render tool → ``None`` (an
    honest 'no receipt'), never a faked pass;
  * missing product, zero-byte product, missing ``.done`` sentinel → ``fail``;
  * an unreadable product → ``inconclusive`` (``pass=None``), NEVER a pass;
  * the MCP nested-content extraction shape resolves;
  * the panel's hardwired BL-007 FAIL path is gone.
"""

from __future__ import annotations

import json
import os
import sys

# Portable path bootstrap (mirrors tests/panel/test_docking.py): repo root gives
# `retina`, python/ gives `synapse` — so this runs under BOTH the stock-python CI
# suite (where a .pth already provides them) and hython.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.panel.render_receipt import compute_receipt, extract_retina
from retina.tests.fixtures import exr_synth

FP = "rm1deadbeefcafe00"


def _named_check(event, name):
    for c in event["checks"]:
        if c["name"] == name:
            return c
    return None


def _write_product(tmp_path, name="beauty.0001.exr", *, done=True,
                   fingerprint=FP, width=960, height=540, data=None):
    product = tmp_path / name
    if data is None:
        data = exr_synth.multipart_exr_bytes(
            width=width, height=height, fingerprint=fingerprint)
    exr_synth.write_bytes(product, data)
    if done:
        exr_synth.write_done(product)
    return str(product)


def _write_manifest(tmp_path, products, name="beauty.0001.retina.json", **extra):
    manifest_path = str(tmp_path / name)
    manifest = {
        "schema": "retina_manifest/v1",
        "products": list(products),
        "claim": "render:file_truth",
        "manifest_path": manifest_path,
    }
    manifest.update(extra)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return manifest_path


def _retina_result(manifest_path):
    """The direct-handler result shape: ``retina`` block at the top level."""
    return {"status": "ok", "retina": {"ok": True, "manifest_path": manifest_path}}


# --------------------------------------------------------------------------
# The real verdict flows through
# --------------------------------------------------------------------------

def test_good_render_flows_pass_verdict(tmp_path):
    product = _write_product(tmp_path)
    mpath = _write_manifest(
        tmp_path, [product], resolution=[960, 540],
        aovs=["C", "primid"], fingerprint=FP)
    event = compute_receipt("houdini_render", _retina_result(mpath))
    assert event is not None
    assert event["tier"] == 0
    assert event["verdict"] == "pass", event["checks"]
    # every declared check landed True — no None masquerading as green
    assert _named_check(event, "products_exist")["pass"] is True
    assert _named_check(event, "resolution")["pass"] is True


# --------------------------------------------------------------------------
# None — an honest 'no receipt', never a faked pass
# --------------------------------------------------------------------------

def test_no_manifest_path_returns_none(tmp_path):
    # retina block present (host hook ran) but no manifest was written
    result = {"retina": {"ok": False, "honesty": {"manifest": "not written"}}}
    assert compute_receipt("houdini_render", result) is None


def test_absent_manifest_file_returns_none(tmp_path):
    ghost = str(tmp_path / "never_written.retina.json")
    assert compute_receipt("houdini_render", _retina_result(ghost)) is None


def test_non_render_tool_returns_none(tmp_path):
    product = _write_product(tmp_path)
    mpath = _write_manifest(tmp_path, [product], resolution=[960, 540])
    # a manifest exists, but this is not a render tool → do not compute
    assert compute_receipt("houdini_create_node", _retina_result(mpath)) is None


def test_no_retina_block_returns_none():
    assert compute_receipt("houdini_render", {"status": "ok"}) is None
    assert compute_receipt("houdini_render", None) is None


# --------------------------------------------------------------------------
# fail — the BL-007 blind-spot class T0 exists to kill
# --------------------------------------------------------------------------

def test_missing_product_fails(tmp_path):
    # manifest declares a product that never landed on disk
    ghost = str(tmp_path / "beauty.0001.exr")
    mpath = _write_manifest(tmp_path, [ghost], resolution=[960, 540])
    event = compute_receipt("houdini_render", _retina_result(mpath))
    assert event["verdict"] == "fail"
    assert _named_check(event, "products_exist")["pass"] is False


def test_zero_byte_product_fails(tmp_path):
    product = _write_product(tmp_path, data=b"")   # 0-byte file, .done present
    mpath = _write_manifest(tmp_path, [product])
    event = compute_receipt("houdini_render", _retina_result(mpath))
    assert event["verdict"] == "fail"
    assert _named_check(event, "products_nonzero")["pass"] is False


def test_done_sentinel_missing_fails(tmp_path):
    product = _write_product(tmp_path, done=False)  # pixels-not-landed
    mpath = _write_manifest(tmp_path, [product])
    event = compute_receipt("houdini_render", _retina_result(mpath))
    assert event["verdict"] == "fail"
    assert _named_check(event, "done_sentinels")["pass"] is False


# --------------------------------------------------------------------------
# inconclusive — a check that CANNOT run is None, never a silent pass (§7)
# --------------------------------------------------------------------------

def test_unreadable_product_inconclusive_not_pass(tmp_path):
    # a file is on disk (exists, nonzero, .done) but its bytes are not an EXR the
    # header reader understands → resolution/aov/fingerprint checks cannot run.
    product = _write_product(tmp_path, data=exr_synth.not_an_exr_bytes())
    mpath = _write_manifest(
        tmp_path, [product], resolution=[960, 540],
        aovs=["C", "primid"], fingerprint=FP)
    event = compute_receipt("houdini_render", _retina_result(mpath))
    # exists/nonzero/done/count all pass, but the header-derived checks are
    # inconclusive → the roll-up is inconclusive, and NONE of them is a pass.
    assert event["verdict"] == "inconclusive"
    assert _named_check(event, "resolution")["pass"] is None
    assert _named_check(event, "aovs")["pass"] is None
    assert _named_check(event, "fingerprint_receipt")["pass"] is None
    # honesty: an inconclusive check must never report True
    assert _named_check(event, "resolution")["pass"] is not True


# --------------------------------------------------------------------------
# extraction — both result shapes resolve
# --------------------------------------------------------------------------

def test_mcp_nested_content_extraction(tmp_path):
    product = _write_product(tmp_path)
    mpath = _write_manifest(
        tmp_path, [product], resolution=[960, 540],
        aovs=["C", "primid"], fingerprint=FP)
    # the MCP CallToolResult shape: the handler dict is JSON inside a text block
    payload = {"status": "ok", "retina": {"ok": True, "manifest_path": mpath}}
    mcp_result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    assert extract_retina(mcp_result) == {"ok": True, "manifest_path": mpath}
    event = compute_receipt("synapse_safe_render", mcp_result)
    assert event is not None and event["verdict"] == "pass"


def test_extract_retina_shapes():
    assert extract_retina({"retina": {"manifest_path": "x"}}) == {"manifest_path": "x"}
    assert extract_retina({"content": [{"text": "not json"}]}) is None
    assert extract_retina({"content": []}) is None
    assert extract_retina("not a dict") is None
    assert extract_retina(None) is None


# --------------------------------------------------------------------------
# the fake is gone — panel no longer hardwires a BL-007 FAIL
# --------------------------------------------------------------------------

def test_bl007_hardwired_fail_removed_from_panel():
    panel = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "python", "synapse", "panel", "synapse_panel.py")
    src = open(panel, encoding="utf-8").read()
    # the argless detect_render_flags() fake (and its import) are gone
    assert "detect_render_flags" not in src
    # the real receipt is wired in its place
    assert "render_receipt" in src
    assert "_on_render_receipt" in src
    assert "set_receipt" in src
