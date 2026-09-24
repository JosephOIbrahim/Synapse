import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

import pytest

from rag.ingest import sidefx_library as lib


def fixture_help(tmp_path):
    hfs = tmp_path / 'hfs'
    header = hfs / 'toolkit/include/SYS/SYS_Version.h'
    header.parent.mkdir(parents=True)
    header.write_text('#define SYS_VERSION_FULL "22.0.400"')
    help_dir = hfs / 'houdini/help'
    help_dir.mkdir(parents=True)
    (help_dir / 'index.txt').write_text('= Welcome =\nNetwork creation help')
    (help_dir / 'licensing').mkdir()
    (help_dir / 'licensing/index.txt').write_text('= Licensing =\nLicense server setup')
    with zipfile.ZipFile(help_dir / 'nodes.zip', 'w') as stream:
        stream.writestr('sop/scatter.txt', '= Scatter =\nDistribute points.\n== Density ==\nControl points with density.\n')
        stream.writestr('apex/Callback.txt', '= Callback =\nFederated callback secret test token')
    return hfs


def test_complete_installed_inventory_and_search(tmp_path):
    root = tmp_path / 'corpus'
    manifest = lib.snapshot_installed(root, fixture_help(tmp_path))
    assert set(manifest['pages']) == {'index.txt', 'licensing/index.txt', 'nodes/sop/scatter.txt', 'nodes/apex/Callback.txt'}
    pointer = lib.build_library(root, runtime_build='22.0.400')
    assert pointer['coverage']['apex_archived_not_indexed'] == 1
    with sqlite3.connect(root / pointer['database']) as con:
        rows = con.execute("SELECT id FROM chunks_fts WHERE chunks_fts MATCH 'density'").fetchall()
        assert rows and all('scatter' in r[0] for r in rows)
        assert con.execute("SELECT COUNT(*) FROM chunks WHERE source_url LIKE '%nodes/apex/%'").fetchone()[0] == 0
        meta = json.loads(con.execute('SELECT metadata FROM chunks WHERE id=?', (rows[0][0],)).fetchone()[0])
        assert meta['docs_build'] == '22.0.400'
        assert meta['evidence_level'] == 'document_only'
        assert meta['source_sha256'] == manifest['pages']['nodes/sop/scatter.txt']['sha256']


def test_corrupt_input_preserves_published_generation(tmp_path):
    root = tmp_path / 'corpus'
    manifest = lib.snapshot_installed(root, fixture_help(tmp_path))
    lib.build_library(root)
    prior = (root / 'current.json').read_bytes()
    (root / manifest['pages']['index.txt']['path']).write_text('corrupt')
    with pytest.raises(ValueError, match='verification failed'):
        lib.build_library(root)
    assert (root / 'current.json').read_bytes() == prior


def test_incomplete_web_does_not_replace_active(tmp_path):
    root = tmp_path / 'corpus'
    lib.snapshot_installed(root, fixture_help(tmp_path))
    lib.build_library(root)
    prior = (root / 'current.json').read_bytes()
    lib.atomic_json(root / 'web_manifest.json', {'schema': 'sidefx_web_manifest/v1', 'pages': {}, 'closure_complete': False})
    with pytest.raises(ValueError, match='incomplete'):
        lib.build_library(root, include_web=True)
    assert (root / 'current.json').read_bytes() == prior


def test_web_provenance_stays_separate_from_installed_build(tmp_path):
    root = tmp_path / 'corpus'
    lib.snapshot_installed(root, fixture_help(tmp_path))
    data = b'# New tool\n## Usage\nNew geometry feature.'
    (root / 'web.md').write_bytes(data)
    lib.atomic_json(root / 'web_manifest.json', {'schema': 'sidefx_web_manifest/v1', 'closure_complete': True, 'pages': {'nodes/sop/new.md': {
        'status': 'ok', 'path': 'web.md', 'sha256': hashlib.sha256(data).hexdigest(),
        'source_url': lib.BASE + 'nodes/sop/new.md', 'docs_build': '22.0.452', 'build_source': 'index_inferred',
    }}})
    result = lib.build_library(root, include_web=True, runtime_build='22.0.400')
    with sqlite3.connect(root / result['database']) as con:
        row = json.loads(con.execute("SELECT metadata FROM chunks WHERE id LIKE 'sidefx_library:web:%' LIMIT 1").fetchone()[0])
    assert row['docs_build'] == '22.0.452'
    assert row['docs_build_basis'] == 'index_inferred'
    assert row['runtime_build_at_import'] == '22.0.400'
    manifest = json.loads((root / 'web_manifest.json').read_text())
    manifest['pages']['nodes/sop/new.md'].update(validated_at='later', etag='same-content-validator')
    lib.atomic_json(root / 'web_manifest.json', manifest)
    repeated = lib.build_library(root, include_web=True, runtime_build='22.0.400')
    assert repeated['generation'] == result['generation']


@pytest.mark.parametrize('relative', ['../escape.txt', '/absolute.txt', 'folder/../../escape.txt', 'folder\\escape.txt'])
def test_confined_paths(tmp_path, relative):
    with pytest.raises(ValueError):
        lib.confined(tmp_path, relative)


def test_chunks_cover_long_text_without_truncation():
    original = '# Heading\n' + '\n'.join(f'line_{i:05}: Important description.' for i in range(600))
    result = list(lib.chunks(original))
    joined = '\n'.join(r[2] for r in result)
    assert len(result) > 2
    assert all(len(r[2]) <= lib.MAX_CHUNK for r in result)
    for line in original.splitlines():
        assert line in joined


def test_loose_override_is_recorded(tmp_path):
    hfs = fixture_help(tmp_path)
    loose = hfs / 'houdini/help/nodes/sop/scatter.txt'
    loose.parent.mkdir(parents=True)
    loose.write_text('= Scatter =\nA newer loose override')
    manifest = lib.snapshot_installed(tmp_path / 'corpus', hfs)
    assert len(manifest['overrides']) == 1
    assert manifest['pages']['nodes/sop/scatter.txt']['origin'] == str(loose)


def test_lock_blocks_second_writer(tmp_path):
    with lib.writer_lock(tmp_path):
        with pytest.raises(FileExistsError):
            with lib.writer_lock(tmp_path):
                pytest.fail('second writer acquired the lock')
    assert not (tmp_path / '.ingest.lock').exists()


def test_unchanged_snapshot_reuses_generation(tmp_path):
    root = tmp_path / 'corpus'
    hfs = fixture_help(tmp_path)
    lib.snapshot_installed(root, hfs)
    first = lib.build_library(root)
    stat = (root / first['database']).stat().st_mtime_ns
    lib.snapshot_installed(root, hfs)
    second = lib.build_library(root)
    assert first['generation'] == second['generation']
    assert (root / second['database']).stat().st_mtime_ns == stat


def test_same_body_provenance_correction_changes_generation(tmp_path):
    root = tmp_path / 'corpus'
    manifest = lib.snapshot_installed(root, fixture_help(tmp_path))
    before = lib.build_library(root)
    manifest['pages']['index.txt']['source_url'] = lib.BASE + 'new/index.md'
    lib.atomic_json(root / 'installed_manifest.json', manifest)
    after = lib.build_library(root)
    assert before['generation'] != after['generation']


def test_wiki_directives_and_fidelity_label_survive(tmp_path):
    root = tmp_path / 'corpus'
    hfs = fixture_help(tmp_path)
    (hfs / 'houdini/help/index.txt').write_text('= Welcome =\n#contentfrom: /shared#description\n#id: signature\n:include /shared#mask/:')
    lib.snapshot_installed(root, hfs)
    pointer = lib.build_library(root)
    with sqlite3.connect(root / pointer['database']) as con:
        rows = con.execute("SELECT body,metadata FROM chunks WHERE id LIKE '%:index.txt#%'").fetchall()
    assert any('#contentfrom: /shared#description' in r[0] for r in rows)
    assert all(json.loads(r[1])['source_format'] == 'sidefx_wiki_unexpanded' for r in rows)


def test_closed_graph_with_failed_fetch_preserves_generation(tmp_path):
    root = tmp_path / 'corpus'
    lib.snapshot_installed(root, fixture_help(tmp_path))
    lib.build_library(root)
    before = (root / 'current.json').read_bytes()
    lib.atomic_json(root / 'web_manifest.json', {
        'schema': 'sidefx_web_manifest/v1', 'closure_complete': True,
        'pages': {'missing.md': {'status': 'error', 'error': 'HTTP 404'}}})
    with pytest.raises(ValueError, match='incomplete'):
        lib.build_library(root, include_web=True)
    assert (root / 'current.json').read_bytes() == before


def test_offline_update_connects_without_downloader(tmp_path, monkeypatch):
    from scripts import update_sidefx_library as update
    monkeypatch.setattr(update, 'REPO', tmp_path / 'checkout')
    monkeypatch.setattr(update, 'Downloader', lambda *a, **k: pytest.fail('offline update attempted HTTP'))
    root = tmp_path / 'corpus'
    assert update.main(['--root', str(root), '--hfs', str(fixture_help(tmp_path)), '--installed-only', '--connect']) == 0
    config = json.loads((tmp_path / 'checkout/.synapse/sidefx_library.json').read_text())
    assert Path(config['root']) == root
    assert (root / 'current.json').exists()
