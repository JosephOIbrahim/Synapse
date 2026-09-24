"""Offline, adversarial HTTP fixtures for the resumable public-docs archive."""
import hashlib
import io
import json
from pathlib import Path
import threading
from urllib.error import URLError

import pytest

from rag.ingest import sidefx_download as d


INDEX = b'# Houdini\n| <p> HOUDINI help </p> | <p>22.0.452</p> |\n'


class Response(io.BytesIO):
    def __init__(self, url, raw=b'', status=200, headers=None):
        super().__init__(raw)
        self.status = status
        self.url = url
        self.headers = {'Content-Length': str(len(raw)), **(headers or {})}

    def geturl(self):
        return self.url


class Server:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
        self.lock = threading.Lock()

    def open(self, request, timeout):
        url = request.full_url
        with self.lock:
            self.calls.append((url, dict(request.header_items())))
            value = self.pages[url]
            if isinstance(value, list):
                value = value.pop(0)
        if callable(value):
            return value(request)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            status, raw, headers = value
            return Response(url, raw, status, headers)
        return Response(url, value)


def supplied(tmp_path, links='[A](a.md)\n'):
    path = tmp_path / 'source-index.txt'
    path.write_bytes(INDEX + links.encode())
    return path


def downloader(root, server, **kwargs):
    return d.Downloader(root, opener_factory=lambda: server, sleep=lambda _: None,
                        checkpoint_every=1, **kwargs)


def test_crawl_preserves_raw_builds_html_links_and_archive_only_apex(tmp_path):
    raw_a = b'# A\r\n[Next](folder/b.html?view=1#details)\n<a href="nodes/apex/c.md">Callback</a>\n'
    raw_b = b'# B\nHOUDINI help | 22.0.499\n[Back](../a.md#top)\n'
    server = Server({d.BASE_URL + 'a.md': raw_a, d.BASE_URL + 'folder/b.md': raw_b,
                     d.BASE_URL + 'nodes/apex/c.md': b'# Callback\nPublic archive only.\n'})
    root = tmp_path / 'archive'
    result = downloader(root, server).run(index_file=supplied(tmp_path))
    assert result['closure_complete'] and result['fetch_complete']
    assert result['counts']['discovered'] == 3
    assert set(result['pages']) == {'a.md', 'folder/b.md', 'nodes/apex/c.md'}
    assert (root / result['pages']['a.md']['path']).read_bytes() == raw_a
    assert result['pages']['a.md']['sha256'] == hashlib.sha256(raw_a).hexdigest()
    assert result['pages']['a.md']['docs_build'] == '22.0.452'
    assert result['pages']['a.md']['build_source'] == 'index_inferred'
    assert result['pages']['folder/b.md']['docs_build'] == '22.0.499'
    assert result['pages']['folder/b.md']['build_source'] == 'page'
    assert result['index']['fetched_at'] is None
    assert json.loads((root / 'web_manifest.json').read_text()) == result
    assert len(server.calls) == 3


def test_scope_canonicalization_rejects_escapes_and_deduplicates_variants():
    assert d.canonical_url('../a.html?q=1#x', d.BASE_URL + 'nested/b.md') == d.BASE_URL + 'a.md'
    for ref in ('../../../outside.md', 'https://other.invalid/docs/houdini/a.md',
                'https://www.sidefx.com.evil.invalid/docs/houdini/a.md',
                'https://user@www.sidefx.com/docs/houdini/a.md',
                '//www.sidefx.com:999/docs/houdini/a.md', '/docs/houdini/%2e%2e/escape.md',
                '/docs/houdini/%252e%252e/escape.md', '/docs/houdini/a%5cb.md', '#local',
                'file:///docs/houdini/a.md', '/docs/houdini/a.png'):
        assert d.canonical_url(ref) is None, ref
    links = b'[one](a.html?x=1) [two](a.md#z) <a href="a.md?q=2">Three</a>\n[x]: <b.md>\n'
    assert d.discover_links(links, d.INDEX_URL) == ['a.md', 'b.md']


def test_resume_checks_hashes_and_repairs_corruption_without_refetching_good_cache(tmp_path):
    index = supplied(tmp_path, '[A](a.md) [B](b.md)')
    root = tmp_path / 'archive'
    server = Server({d.BASE_URL + 'a.md': b'# A\n', d.BASE_URL + 'b.md': b'# B\n'})
    first = downloader(root, server).run(index_file=index)
    server.calls.clear()
    second = downloader(root, server).run(resume=True)
    assert second['fetch_complete'] and server.calls == []
    (root / first['pages']['a.md']['path']).write_bytes(b'# corrupted\n')
    third = downloader(root, server).run(resume=True)
    assert third['fetch_complete']
    assert [url for url, _ in server.calls] == [d.BASE_URL + 'a.md']
    assert (root / first['pages']['a.md']['path']).read_bytes() == b'# A\n'


def test_conditional_refresh_304_keeps_verified_bytes_and_fetched_time(tmp_path):
    index = supplied(tmp_path)
    root = tmp_path / 'archive'
    server = Server({d.BASE_URL + 'a.md': (200, b'# A\n', {'ETag': '"first"', 'Last-Modified': 'Mon, 01 Jun 2026 00:00:00 GMT'})})
    first = downloader(root, server).run(index_file=index)
    server.pages[d.INDEX_URL] = index.read_bytes()
    server.pages[d.BASE_URL + 'a.md'] = (304, b'', {})
    result = downloader(root, server).run(refresh=True)
    assert result['fetch_complete']
    assert result['pages']['a.md']['sha256'] == first['pages']['a.md']['sha256']
    assert result['pages']['a.md']['fetched_at'] == first['pages']['a.md']['fetched_at']
    headers = dict((k.lower(), v) for k, v in server.calls[-1][1].items())
    assert headers['if-none-match'] == '"first"'
    assert 'if-modified-since' in headers


def test_redirect_scope_is_checked_before_any_second_request(tmp_path):
    server = Server({d.BASE_URL + 'a.md': (302, b'', {'Location': 'https://outside.invalid/a.md'})})
    result = downloader(tmp_path / 'archive', server).run(index_file=supplied(tmp_path))
    assert result['closure_complete'] and not result['fetch_complete']
    assert result['pages']['a.md']['status'] == 'error'
    assert 'redirect' in result['pages']['a.md']['error']
    assert [url for url, _ in server.calls] == [d.BASE_URL + 'a.md']


def test_redirected_page_links_resume_from_final_url(tmp_path):
    index = supplied(tmp_path)
    root = tmp_path / 'archive'
    server = Server({d.BASE_URL + 'a.md': (302, b'', {'Location': 'moved/a.md'}),
                     d.BASE_URL + 'moved/a.md': b'# A\n[B](b.md)\n',
                     d.BASE_URL + 'moved/b.md': b'# B\n'})
    result = downloader(root, server).run(index_file=index)
    assert result['fetch_complete'] and set(result['pages']) == {'a.md', 'moved/b.md'}
    server.calls.clear()
    resumed = downloader(root, server).run(resume=True)
    assert resumed['fetch_complete'] and server.calls == []
    assert set(resumed['pages']) == {'a.md', 'moved/b.md'}


def test_retry_after_and_transient_network_failure_are_bounded(tmp_path):
    waits = []
    server = Server({d.BASE_URL + 'a.md': [(429, b'', {'Retry-After': '2'}), URLError('temporary'), b'# A\n']})
    fetch = d.Downloader(tmp_path / 'archive', opener_factory=lambda: server, sleep=waits.append)
    result = fetch.run(index_file=supplied(tmp_path))
    assert result['fetch_complete'] and len(server.calls) == 3
    assert waits == [2.0, 1.0]


def test_errors_are_explicit_and_resume_retries_them(tmp_path):
    index = supplied(tmp_path, '[Missing](missing.md) [Busy](busy.md)')
    root = tmp_path / 'archive'
    server = Server({d.BASE_URL + 'missing.md': (404, b'', {}), d.BASE_URL + 'busy.md': (503, b'', {})})
    first = downloader(root, server, retries=0).run(index_file=index)
    assert first['closure_complete'] and not first['fetch_complete']
    assert first['status_counts'] == {'ok': 0, 'error': 2}
    assert set(first['errors'].values()) == {'HTTP 404', 'HTTP 503'}
    server.pages = {d.BASE_URL + key: b'# Recovered\n' for key in ('missing.md', 'busy.md')}
    assert downloader(root, server).run(resume=True)['fetch_complete']


@pytest.mark.parametrize('limit,options', [
    ('max_pages', {'max_pages': 1}), ('max_requests', {'max_requests': 1}),
    ('max_bytes', {'max_bytes': 4}),
])
def test_limits_preserve_pending_and_never_claim_closure(tmp_path, limit, options):
    root = tmp_path / 'archive'
    server = Server({d.BASE_URL + 'a.md': b'# A\n[B](b.md)\n', d.BASE_URL + 'b.md': b'# B\n'})
    result = downloader(root, server, workers=1, **options).run(index_file=supplied(tmp_path))
    assert not result['closure_complete'] and not result['fetch_complete']
    assert result['pending'] and limit in result['limit_reasons']
    if limit == 'max_requests':
        assert len(server.calls) == 1
    if limit == 'max_bytes':
        assert result['counts']['bytes_received'] <= 4
    assert downloader(root, server, workers=1).run(resume=True)['fetch_complete']


def test_windows_reserved_unicode_case_and_cache_escape_are_safe(tmp_path):
    root = tmp_path / 'archive'
    keys = ['con.md', 'foo/aux.txt.md', 'Foo.md', 'foo.md', 'apex/Array<Geometry>.md']
    local = [d.cache_relative(key, root) for key in keys]
    assert len({path.lower() for path in local}) == len(keys)
    assert all(path.startswith('cache/web/') for path in local)
    assert local[3] == 'cache/web/foo.md'
    fetch = downloader(root, Server({}))
    with pytest.raises(ValueError, match='escapes'):
        fetch._path('../outside.md')


def test_worker_limit_allows_parallel_fetch_without_exceeding_bound(tmp_path):
    barrier = threading.Barrier(3)
    lock = threading.Lock()
    active, maximum = 0, 0
    def reply(request):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        barrier.wait(timeout=3)
        with lock:
            active -= 1
        return Response(request.full_url, b'# Page\n')
    server = Server({d.BASE_URL + str(n) + '.md': reply for n in range(3)})
    result = downloader(tmp_path / 'archive', server, workers=3).run(
        index_file=supplied(tmp_path, ' '.join(f'[P]({n}.md)' for n in range(3))))
    assert result['fetch_complete'] and maximum == 3
    with pytest.raises(ValueError, match='1..16'):
        downloader(tmp_path / 'other', server, workers=17)


def test_atomic_checkpoint_survives_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / 'web_manifest.json'
    target.write_bytes(b'{"old":true}')
    def fail_replace(*args):
        raise OSError('disk full')
    monkeypatch.setattr(d.os, 'replace', fail_replace)
    with pytest.raises(OSError, match='disk full'):
        d._atomic(target, b'{"new":true}')
    assert target.read_bytes() == b'{"old":true}'
    assert not list(tmp_path.glob('.sidefx-*.tmp'))


def test_invalid_index_and_oversized_page_are_incomplete(tmp_path):
    index = supplied(tmp_path)
    root = tmp_path / 'archive'
    server = Server({d.BASE_URL + 'a.md': b'# A\n' + b'x' * 150})
    result = downloader(root, server, max_page_bytes=100).run(index_file=index)
    assert result['closure_complete'] and not result['fetch_complete']
    assert result['errors'] == {'a.md': 'max_page_bytes'}
    index.write_bytes(b'# Empty index\n')
    result = downloader(tmp_path / 'empty', Server({})).run(index_file=index)
    assert not result['closure_complete'] and 'index_unavailable' in result['limit_reasons'][0]


def test_archive_has_one_writer_and_existing_manifest_requires_resume(tmp_path):
    root = tmp_path / 'archive'
    with d._archive_lock(root):
        with pytest.raises(RuntimeError, match='owns'):
            with d._archive_lock(root):
                pass
    server = Server({d.BASE_URL + 'a.md': b'# A\n'})
    downloader(root, server).run(index_file=supplied(tmp_path))
    with pytest.raises(ValueError, match='resume'):
        downloader(root, server).run()


def test_changed_refresh_discovers_new_links_and_drops_removed_validators(tmp_path):
    root = tmp_path / 'archive'
    index = supplied(tmp_path)
    server = Server({d.BASE_URL + 'a.md': (200, b'# Old\n', {'ETag': '"old"'})})
    original = downloader(root, server).run(index_file=index)
    server.pages.update({d.INDEX_URL: index.read_bytes(),
                         d.BASE_URL + 'a.md': b'# New\n[More](b.md)\n',
                         d.BASE_URL + 'b.md': b'# More\n'})
    refreshed = downloader(root, server).run(refresh=True)
    assert refreshed['fetch_complete'] and set(refreshed['pages']) == {'a.md', 'b.md'}
    assert refreshed['pages']['a.md']['sha256'] != original['pages']['a.md']['sha256']
    assert refreshed['pages']['a.md']['etag'] is None
    assert (root / refreshed['pages']['a.md']['path']).read_bytes() == b'# New\n[More](b.md)\n'


def test_corrupt_cache_cannot_accept_304_or_send_validators(tmp_path):
    root = tmp_path / 'archive'
    server = Server({d.BASE_URL + 'a.md': (200, b'# A\n', {'ETag': '"old"'})})
    first = downloader(root, server).run(index_file=supplied(tmp_path))
    (root / first['pages']['a.md']['path']).write_bytes(b'# corrupt\n')
    server.pages[d.BASE_URL + 'a.md'] = (304, b'', {})
    result = downloader(root, server).run(resume=True)
    assert result['closure_complete'] and not result['fetch_complete']
    assert 'SHA256-verified' in result['errors']['a.md']
    assert 'if-none-match' not in {k.lower() for k in server.calls[-1][1]}


def test_request_budget_counts_redirects_and_retries(tmp_path):
    server = Server({d.BASE_URL + 'a.md': (302, b'', {'Location': 'b.md'}),
                     d.BASE_URL + 'b.md': [(503, b'', {}), b'# Done\n']})
    result = downloader(tmp_path / 'archive', server, max_requests=2).run(index_file=supplied(tmp_path))
    assert len(server.calls) == result['counts']['requests'] == 2
    assert result['pending'] == ['a.md'] and not result['closure_complete']
    assert result['limit_reasons'] == ['max_requests']


def test_long_retry_after_defers_and_non_markdown_response_is_rejected(tmp_path):
    server = Server({d.BASE_URL + 'a.md': (429, b'', {'Retry-After': '3600'}),
                     d.BASE_URL + 'b.md': b'<html>Bad gateway</html>'})
    result = downloader(tmp_path / 'archive', server).run(index_file=supplied(tmp_path, '[A](a.md) [B](b.md)'))
    assert len(server.calls) == 2
    assert result['closure_complete'] and not result['fetch_complete']
    assert 'resume later' in result['errors']['a.md']
    assert 'instead of Markdown' in result['errors']['b.md']


def test_repeated_separators_share_url_and_cache_identity():
    assert d.canonical_url(d.BASE_URL + 'foo//bar.md') == d.BASE_URL + 'foo/bar.md'
    assert d.discover_links(b'[A](foo/bar.md) [Alias](https://www.sidefx.com/docs/houdini/foo//bar.md)', d.INDEX_URL) == ['foo/bar.md']


def test_official_heading_free_and_summary_before_title_shapes_are_archived(tmp_path):
    # Observed official responses on 2026-09-24: includes have no heading;
    # expression aliases and crowd-procedural docs put a summary before it.
    fragments = {
        'nodes/sop/_onnx_dtype_common.md': b'The tensor element data type.\n',
        'nodes/dop/standard_embedding_parms.md': b'**Enable Embedding**\nTurns on/off the use of embedded geometry.\n',
        'expressions/strlen.md': b'Returns the number of characters in a string.\n\n# strlen\n',
        'nodes/lop/houdinicrowdprocedural.md': b'Houdini Crowd Procedural for Solaris.\n\n# Houdini Procedural: Crowd\n',
        'licenses/core-math.md': b'The CORE-MATH code is distributed under the following license (MIT license).\n',
    }
    server = Server({d.BASE_URL + key: (200, raw, {'Content-Type': 'text/plain'}) for key, raw in fragments.items()})
    result = downloader(tmp_path / 'archive', server).run(index_file=supplied(tmp_path, '\n'.join(f'[P]({key})' for key in fragments)))
    assert result['fetch_complete'] and len(result['pages']) == len(fragments)
    for key, raw in fragments.items():
        assert (tmp_path / 'archive' / result['pages'][key]['path']).read_bytes() == raw
        assert result['pages'][key]['build_source'] == 'index_inferred'


@pytest.mark.parametrize('raw,headers', [
    (b'<!-- cache error -->\n<!DOCTYPE html><html>Bad gateway</html>', {}),
    (b'# Looks like Markdown', {'Content-Type': 'text/html; charset=utf-8'}),
    (b'{"error":"upstream unavailable"}', {'Content-Type': 'text/plain'}),
    (b'502 Bad Gateway\n', {}), (b'', {}), (b'binary\x00text', {}),
])
def test_error_envelopes_cannot_be_accepted_as_heading_free_markdown(tmp_path, raw, headers):
    server = Server({d.BASE_URL + 'a.md': (200, raw, headers)})
    result = downloader(tmp_path / 'archive', server).run(index_file=supplied(tmp_path))
    assert not result['fetch_complete'] and result['pages']['a.md']['status'] == 'error'


def test_redirected_index_uses_final_base_and_resumes_without_network(tmp_path):
    root = tmp_path / 'archive'
    server = Server({d.INDEX_URL: (302, b'', {'Location': 'current/index.md'}),
                     d.BASE_URL + 'current/index.md': INDEX + b'[A](a.md)\n',
                     d.BASE_URL + 'current/a.md': b'# A\n'})
    first = downloader(root, server).run()
    assert first['fetch_complete'] and set(first['pages']) == {'current/a.md'}
    server.calls.clear()
    assert downloader(root, server).run(resume=True)['fetch_complete']
    assert server.calls == []


def test_cli_returns_incomplete_status_then_resume_success(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'archive'
    index = supplied(tmp_path)
    server = Server({d.BASE_URL + 'a.md': (404, b'', {})})
    implementation = d.Downloader
    monkeypatch.setattr(d, 'Downloader', lambda **options: implementation(**options, opener_factory=lambda: server))
    assert d.main(['--root', str(root), '--index-file', str(index)]) == 2
    assert json.loads(capsys.readouterr().out)['fetch_complete'] is False
    server.pages[d.BASE_URL + 'a.md'] = b'# Recovered\n'
    assert d.main(['--root', str(root), '--resume']) == 0
    assert json.loads(capsys.readouterr().out)['fetch_complete'] is True


def test_partial_then_complete_refresh_preserves_each_generations_raw_bytes(tmp_path):
    root = tmp_path / 'archive'
    index = supplied(tmp_path, '[A](a.md) [B](b.md)')
    server = Server({d.BASE_URL + 'a.md': b'# Original A\n', d.BASE_URL + 'b.md': b'# Original B\n'})
    first = downloader(root, server, workers=1).run(index_file=index)
    first_paths = {key: root / row['path'] for key, row in first['pages'].items()}
    server.pages.update({d.INDEX_URL: index.read_bytes(),
                         d.BASE_URL + 'a.md': b'# Changed A\n', d.BASE_URL + 'b.md': (503, b'', {})})
    partial = downloader(root, server, workers=1, retries=0).run(refresh=True)
    assert not partial['fetch_complete'] and partial['errors'] == {'b.md': 'HTTP 503'}
    for key, path in first_paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == first['pages'][key]['sha256']
    assert partial['pages']['a.md']['path'] != first['pages']['a.md']['path']
    assert first_paths['a.md'].read_bytes() == b'# Original A\n'
    changed_path = root / partial['pages']['a.md']['path']
    server.pages.update({d.BASE_URL + 'a.md': b'# Newest A\n', d.BASE_URL + 'b.md': b'# Original B\n'})
    complete = downloader(root, server, workers=1).run(refresh=True)
    assert complete['fetch_complete']
    assert len({state['pages']['a.md']['path'] for state in (first, partial, complete)}) == 3
    assert changed_path.read_bytes() == b'# Changed A\n'
    assert first_paths['a.md'].read_bytes() == b'# Original A\n'
    assert complete['pages']['b.md']['path'] == first['pages']['b.md']['path']


def test_legacy_url_cache_is_retained_on_resume_and_304(tmp_path):
    root = tmp_path / 'archive'
    index = supplied(tmp_path)
    server = Server({d.BASE_URL + 'a.md': (200, b'# Legacy\n', {'ETag': '"legacy"'})})
    first = downloader(root, server).run(index_file=index)
    legacy = root / 'cache/web/a.md'
    legacy.write_bytes(b'# Legacy\n')
    first['pages']['a.md']['path'] = 'cache/web/a.md'
    (root / 'web_manifest.json').write_text(json.dumps(first), encoding='utf-8')
    server.calls.clear()
    resumed = downloader(root, server).run(resume=True)
    assert server.calls == [] and resumed['pages']['a.md']['path'] == 'cache/web/a.md'
    server.pages.update({d.INDEX_URL: index.read_bytes(), d.BASE_URL + 'a.md': (304, b'', {})})
    refreshed = downloader(root, server).run(refresh=True)
    assert refreshed['fetch_complete'] and refreshed['pages']['a.md']['path'] == 'cache/web/a.md'
    server.pages[d.BASE_URL + 'a.md'] = b'# Changed legacy\n'
    changed = downloader(root, server).run(refresh=True)
    assert changed['fetch_complete'] and changed['pages']['a.md']['path'].startswith('cache/web/objects/')
    assert legacy.read_bytes() == b'# Legacy\n'


def test_changed_index_build_preserves_legacy_index_bytes_and_provenance(tmp_path):
    root = tmp_path / 'archive'
    index = supplied(tmp_path)
    original_index = index.read_bytes()
    server = Server({d.BASE_URL + 'a.md': b'# A\n'})
    first = downloader(root, server).run(index_file=index)
    original_index_record = dict(first['index'])
    assert first['index']['path'] == f"cache/web/objects/{first['index']['sha256']}.txt"
    # Simulate an archive from the first downloader: index pointed to llms.txt.
    first['index']['path'] = 'llms.txt'
    (root / original_index_record['path']).unlink()
    (root / 'web_manifest.json').write_text(json.dumps(first), encoding='utf-8')
    new_index = original_index.replace(b'22.0.452', b'22.0.499')
    server.pages[d.INDEX_URL] = new_index
    refreshed = downloader(root, server).run(refresh=True)
    assert refreshed['fetch_complete']
    assert refreshed['pages']['a.md']['docs_build'] == refreshed['index']['docs_build'] == '22.0.499'
    assert refreshed['index']['path'] != original_index_record['path']
    assert (root / original_index_record['path']).read_bytes() == original_index
    assert (root / refreshed['index']['path']).read_bytes() == new_index
    assert (root / 'llms.txt').read_bytes() == new_index
    captured = refreshed['index_history'][original_index_record['sha256']]
    assert captured['path'] == original_index_record['path'] and captured['migrated_from'] == 'llms.txt'
    assert captured['docs_build'] == '22.0.452'
    assert hashlib.sha256((root / captured['path']).read_bytes()).hexdigest() == captured['sha256']


def test_index_migration_is_durable_before_alias_overwrite_crash(tmp_path, monkeypatch):
    root = tmp_path / 'archive'
    index = supplied(tmp_path)
    original_index = index.read_bytes()
    server = Server({d.BASE_URL + 'a.md': b'# A\n'})
    first = downloader(root, server).run(index_file=index)
    (root / first['index']['path']).unlink()
    first['index']['path'] = 'llms.txt'
    (root / 'web_manifest.json').write_text(json.dumps(first), encoding='utf-8')
    new_index = original_index.replace(b'22.0.452', b'22.0.499')
    server.pages[d.INDEX_URL] = new_index
    atomic = d._atomic
    def crash_after_alias(path, raw):
        atomic(path, raw)
        if path == root / 'llms.txt' and raw == new_index:
            raise SystemExit('simulated process death after alias replacement')
    monkeypatch.setattr(d, '_atomic', crash_after_alias)
    with pytest.raises(SystemExit, match='process death'):
        downloader(root, server).run(refresh=True)
    persisted = json.loads((root / 'web_manifest.json').read_text(encoding='utf-8'))
    assert (root / 'llms.txt').read_bytes() == new_index
    assert (root / persisted['index']['path']).read_bytes() == original_index
    assert persisted['index_history'][first['index']['sha256']]['migrated_from'] == 'llms.txt'
