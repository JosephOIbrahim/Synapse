"""Rope L4-2a — Ollama discovery + cached catalog. Mocked HTTP, no live Ollama.

Model names are GENERATED per run — zero hardcoded names, because a name typed
into a test is the same claim-shape the catalog exists to refuse (R74).
"""
import json
import random
import urllib.error
import urllib.request
import uuid

from synapse.panel.providers import catalog

ENDPOINT = "http://127.0.0.1:11434"


def _gen_models(n, remote_every=3):
    """n /api/tags rows with runtime-generated names; every ``remote_every``-th
    one carries a remote_host (the :cloud shape) so ``local`` gets both values."""
    rows = []
    for i in range(n):
        row = {"name": "m-%s:latest" % uuid.uuid4().hex[:10]}
        if remote_every and i % remote_every == 0:
            row["remote_host"] = "https://ollama.example.invalid"
        rows.append(row)
    return rows


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = 200

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(monkeypatch, models):
    def fake_urlopen(req, timeout=None):
        return _FakeResponse({"models": models})
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def _kill_endpoint(monkeypatch):
    def dead(req, timeout=None):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", dead)


def test_discovery_lists_n_models_zero_hardcoded(monkeypatch, tmp_path):
    n = random.randint(3, 9)
    models = _gen_models(n)
    _serve(monkeypatch, models)
    path = tmp_path / "model_catalog.json"

    res = catalog.refresh(path=path, endpoint=ENDPOINT, now=1000.0)

    assert res.stale is False and res.reason is None
    assert len(res.entries) == n
    generated = {m["name"] for m in models}
    assert {e.id for e in res.entries} == generated
    assert set(res.new) == generated          # cold cache: everything is new
    assert res.removed == ()

    by_id = {e.id: e for e in res.entries}
    for m in models:
        e = by_id[m["name"]]
        assert e.provider == "ollama"
        assert e.endpoint == ENDPOINT
        assert e.local == ("remote_host" not in m)
        assert e.first_seen == e.last_seen == 1000.0
        assert e.latency_ms is not None and e.latency_ms >= 0.0
        assert e.auth_ok is True

    # Persisted, and the round trip is lossless.
    assert catalog.load_catalog(path) == res.entries


def test_refresh_diffs_new_and_removed(monkeypatch, tmp_path):
    first = _gen_models(random.randint(4, 8))
    path = tmp_path / "model_catalog.json"
    _serve(monkeypatch, first)
    catalog.refresh(path=path, endpoint=ENDPOINT, now=1000.0)

    dropped = first[0]["name"]
    added = {"name": "m-%s:latest" % uuid.uuid4().hex[:10]}
    second = first[1:] + [added]
    _serve(monkeypatch, second)

    res = catalog.refresh(path=path, endpoint=ENDPOINT, now=2000.0)

    assert res.stale is False
    assert set(res.new) == {added["name"]}
    assert set(res.removed) == {dropped}
    ids = {e.id for e in res.entries}
    assert dropped not in ids and added["name"] in ids

    by_id = {e.id: e for e in res.entries}
    for m in first[1:]:                       # survivors keep first_seen
        assert by_id[m["name"]].first_seen == 1000.0
        assert by_id[m["name"]].last_seen == 2000.0
    assert by_id[added["name"]].first_seen == 2000.0

    # A third refresh with the same set fires no events — removal reported once.
    res3 = catalog.refresh(path=path, endpoint=ENDPOINT, now=3000.0)
    assert res3.new == () and res3.removed == ()


def test_dead_endpoint_degrades_to_cache_plus_stale(monkeypatch, tmp_path):
    models = _gen_models(random.randint(3, 6))
    path = tmp_path / "model_catalog.json"
    _serve(monkeypatch, models)
    seeded = catalog.refresh(path=path, endpoint=ENDPOINT, now=1000.0)

    _kill_endpoint(monkeypatch)
    res = catalog.refresh(path=path, endpoint=ENDPOINT, now=2000.0)

    assert res.stale is True
    assert res.reason == "unreachable"
    assert res.entries == seeded.entries      # cache served, not emptied
    assert res.new == () and res.removed == ()
    # The file was not clobbered by the failure; last_seen still says 1000.
    on_disk = catalog.load_catalog(path)
    assert on_disk == seeded.entries
    assert all(e.last_seen == 1000.0 for e in on_disk)


def test_cold_start_dead_endpoint_never_raises(monkeypatch, tmp_path):
    _kill_endpoint(monkeypatch)
    path = tmp_path / "model_catalog.json"

    res = catalog.refresh(path=path, endpoint=ENDPOINT, now=1000.0)

    assert res.stale is True
    assert res.entries == ()
    assert not path.exists()                  # a failure writes nothing
    assert catalog.load_catalog(path) == ()   # and the start read is determinate


def test_panel_start_reads_cache_without_network(monkeypatch, tmp_path):
    models = _gen_models(4)
    path = tmp_path / "model_catalog.json"
    _serve(monkeypatch, models)
    catalog.refresh(path=path, endpoint=ENDPOINT, now=1000.0)

    def boom(*args, **kwargs):
        raise AssertionError("panel start must not touch the network")
    monkeypatch.setattr(urllib.request, "urlopen", boom)

    entries = catalog.load_catalog(path)      # the panel-start path
    assert len(entries) == len(models)


def test_corrupt_cache_degrades_to_empty(monkeypatch, tmp_path):
    path = tmp_path / "model_catalog.json"
    path.write_text("{this is not json", encoding="utf-8")
    assert catalog.load_catalog(path) == ()

    _kill_endpoint(monkeypatch)
    res = catalog.refresh(path=path, endpoint=ENDPOINT, now=1000.0)
    assert res.stale is True and res.entries == ()
