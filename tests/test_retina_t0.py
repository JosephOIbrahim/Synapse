"""RETINA T0 — file-truth checker tests.

Drives ``retina.t0.check_manifest_against_disk`` with synthetic manifests + tiny
on-disk EXR-header fixtures, asserting the BL-007 class is caught and — the
load-bearing property — that a check which *cannot* run returns ``inconclusive``,
never a silent pass (blueprint §7).
"""

from __future__ import annotations

import json

from retina.t0 import check_manifest_against_disk, emit_verdict, verify_and_emit
from retina.tests.fixtures import exr_synth

NOW = "2026-07-16T00:00:00+00:00"


def _named_check(event, name):
    for c in event["checks"]:
        if c["name"] == name:
            return c
    return None


def _write_product(tmp_path, name="beauty.0001.exr", *, done=True, fingerprint=None,
                   width=960, height=540):
    product = tmp_path / name
    exr_synth.write_bytes(
        product, exr_synth.multipart_exr_bytes(width=width, height=height, fingerprint=fingerprint)
    )
    if done:
        exr_synth.write_done(product)
    return str(product)


def _manifest(products, **extra):
    m = {"schema": "retina_manifest/v1", "products": list(products), "claim": "material_swap:/geo/x"}
    m.update(extra)
    return m


def test_happy_path_all_present_passes(tmp_path):
    fp = "rm1abc123abc123ab"
    product = _write_product(tmp_path, fingerprint=fp)
    manifest = _manifest([product], resolution=[960, 540], aovs=["primid"], fingerprint=fp)
    event = check_manifest_against_disk(manifest, now=NOW)

    assert event["ch"] == "perception"
    assert event["v"] == 1
    assert event["tier"] == 0
    assert event["verdict"] == "pass"
    assert _named_check(event, "products_exist")["pass"] is True
    assert _named_check(event, "done_sentinels")["pass"] is True
    assert _named_check(event, "resolution")["pass"] is True
    assert _named_check(event, "aovs")["pass"] is True
    assert _named_check(event, "fingerprint_receipt")["pass"] is True


def test_missing_product_fails(tmp_path):
    manifest = _manifest([str(tmp_path / "never_rendered.exr")])
    event = check_manifest_against_disk(manifest, now=NOW)
    assert event["verdict"] == "fail"
    assert _named_check(event, "products_exist")["pass"] is False


def test_empty_product_fails(tmp_path):
    product = tmp_path / "black.0001.exr"
    product.write_bytes(b"")  # 0 bytes
    exr_synth.write_done(product)
    event = check_manifest_against_disk(_manifest([str(product)]), now=NOW)
    assert event["verdict"] == "fail"
    assert _named_check(event, "products_nonzero")["pass"] is False


def test_missing_done_sentinel_fails(tmp_path):
    product = _write_product(tmp_path, done=False)
    event = check_manifest_against_disk(_manifest([str(product)]), now=NOW)
    assert event["verdict"] == "fail"
    assert _named_check(event, "done_sentinels")["pass"] is False


def test_wrong_resolution_fails(tmp_path):
    product = _write_product(tmp_path, width=960, height=540)
    manifest = _manifest([product], resolution=[1920, 1080])
    event = check_manifest_against_disk(manifest, now=NOW)
    assert event["verdict"] == "fail"
    assert _named_check(event, "resolution")["pass"] is False


def test_missing_aov_fails(tmp_path):
    product = _write_product(tmp_path)  # has C + primid
    manifest = _manifest([product], aovs=["normal"])  # not present
    event = check_manifest_against_disk(manifest, now=NOW)
    assert event["verdict"] == "fail"
    assert _named_check(event, "aovs")["pass"] is False


def test_no_declared_resolution_is_inconclusive_not_pass(tmp_path):
    product = _write_product(tmp_path)
    manifest = _manifest([product])  # no resolution declared
    event = check_manifest_against_disk(manifest, now=NOW)
    # everything present, but resolution/aov/fingerprint were never declared ->
    # inconclusive, NOT a vacuous pass (blueprint §7 honesty).
    assert _named_check(event, "resolution")["pass"] is None
    assert _named_check(event, "aovs")["pass"] is None
    assert _named_check(event, "fingerprint_receipt")["pass"] is None
    assert event["verdict"] == "inconclusive"


def test_unreadable_product_makes_header_checks_inconclusive(tmp_path):
    # A present, non-empty, but non-EXR product: existence/size/done pass, but the
    # header-derived checks cannot run -> inconclusive, never a silent pass.
    product = tmp_path / "corrupt.0001.exr"
    product.write_bytes(exr_synth.not_an_exr_bytes())
    exr_synth.write_done(product)
    manifest = _manifest([str(product)], resolution=[960, 540], aovs=["primid"])
    event = check_manifest_against_disk(manifest, now=NOW)
    assert _named_check(event, "resolution")["pass"] is None
    assert _named_check(event, "aovs")["pass"] is None
    assert event["verdict"] == "inconclusive"


def test_no_products_declared_is_inconclusive(tmp_path):
    event = check_manifest_against_disk(_manifest([]), now=NOW)
    assert event["verdict"] == "inconclusive"
    assert _named_check(event, "products_declared")["pass"] is None


def test_fingerprint_mismatch_fails(tmp_path):
    product = _write_product(tmp_path, fingerprint="rm1_actual_stamp")
    manifest = _manifest([product], fingerprint="rm1_expected_other")
    event = check_manifest_against_disk(manifest, now=NOW)
    assert event["verdict"] == "fail"
    assert _named_check(event, "fingerprint_receipt")["pass"] is False


def test_deterministic_given_same_inputs(tmp_path):
    product = _write_product(tmp_path, fingerprint="rm1stable")
    manifest = _manifest([product], resolution=[960, 540], aovs=["primid"], fingerprint="rm1stable")
    e1 = check_manifest_against_disk(manifest, now=NOW)
    e2 = check_manifest_against_disk(manifest, now=NOW)
    assert e1 == e2  # no clock reads inside; byte-identical


def test_emit_verdict_appends_jsonl(tmp_path):
    product = _write_product(tmp_path)
    jsonl = tmp_path / "verdicts.jsonl"
    e1 = check_manifest_against_disk(_manifest([product]), now=NOW)
    emit_verdict(e1, jsonl)
    emit_verdict(e1, jsonl)
    lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert parsed["ch"] == "perception"
    assert parsed["tier"] == 0


def test_verify_and_emit_returns_event_and_persists(tmp_path):
    product = _write_product(tmp_path, fingerprint="rm1x")
    jsonl = tmp_path / "sidecar" / "verdicts.jsonl"
    manifest = _manifest([product], resolution=[960, 540], aovs=["primid"], fingerprint="rm1x")
    event = verify_and_emit(manifest, now=NOW, jsonl_path=jsonl)
    assert event["verdict"] == "pass"
    assert jsonl.exists()
    assert json.loads(jsonl.read_text(encoding="utf-8").strip())["verdict"] == "pass"
