"""F04: hip_crawler resolves $HFS through hou.text.expandString, not the deprecated hou.expandString."""

import inspect
import sys
import types

from forge.extractors import hip_crawler


def test_crawl_examples_uses_hou_text_expandstring(tmp_path, monkeypatch):
    fake_hou = types.SimpleNamespace(
        text=types.SimpleNamespace(expandString=lambda s: str(tmp_path)),
    )
    monkeypatch.setitem(sys.modules, "hou", fake_hou)

    manifest = hip_crawler.crawl_examples(output_path=str(tmp_path / "m.json"))

    assert manifest.hfs_path == str(tmp_path)
    assert manifest.total_scanned == 0


def test_source_has_no_deprecated_expandstring():
    assert "hou.expandString(" not in inspect.getsource(hip_crawler)
