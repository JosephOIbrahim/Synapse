"""No network or Houdini: the read-only Atlas v2 client, its route allowlist, key handling and cache.

World Labs serves Atlas only (2026-11-22). Every Atlas task costs credits, so the client must never be able to start
one. These tests pin that it can only list operations, read one operation and mint an asset read URL.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest

from synapse.worldlabs import client as wl
from synapse.worldlabs.client import (
    API_BASE, AssetUnavailableError, AtlasClient, AuthenticationError, WorldLabsClient, WorldLabsError,
    _SafeRedirect, _safe_asset_url, cli_saved_key, operation_id_from_ref, resolve_key, splat_outputs,
)
from synapse.worldlabs.importer import ImportValidationError, inspect_ply, prepare_local_asset

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "spz_fixture.py"
_spec = importlib.util.spec_from_file_location("spz_fixture_for_client_tests", _FIXTURE)
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

NO_SAVED = dict(saved_key=lambda: None)   # never read the real worldlabs CLI sign-in from a test


def ply_bytes(points=1, gaussian=True, sh=False):
    properties = ['x', 'y', 'z']
    if gaussian:
        properties += ['opacity'] + ['f_dc_%d' % i for i in range(3)] + ['scale_%d' % i for i in range(3)] + ['rot_%d' % i for i in range(4)]
    if sh:
        properties += ['f_rest_%d' % i for i in range(45)]
    header = ['ply', 'format ascii 1.0', 'element vertex %d' % points]
    header += ['property float ' + p for p in properties]
    header += ['end_header']
    rows = [' '.join('1' if p == 'rot_0' else '0' for p in properties)] * points
    return ('\n'.join(header + rows) + '\n').encode('ascii')


class FakeOpener:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def open(self, req, timeout):
        self.requests.append(req)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply if isinstance(reply, bytes) else json.dumps(reply).encode())


SPZ = fx.legacy_spz(fx.sample_splats(5), version=3)
OPERATION = {
    'id': 'op123abc', 'ownerId': 'acct_SECRET_OWNER', 'done': True, 'error': None,
    'metadata': {'task': 'posedImages2Splats', 'state': 'SUCCEEDED'},
    'response': {'refinedSplats': {
        '500000': {'assetId': 'asset_big', 'url': 'https://storage.example/big.spz?X-Goog-Signature=SECRET'},
        '100000': {'assetId': 'asset_small', 'url': 'https://storage.example/small.spz?X-Goog-Signature=SECRET'}}},
}


def _client(replies, key='test-key'):
    opener = FakeOpener(replies)
    return AtlasClient(key, opener=opener, **NO_SAVED), opener


# ---------------------------------------------------------------------------
# Route allowlist: no task can ever be started
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('method,route', [
    ('POST', '/tasks:posedImages2Splats'), ('POST', '/tasks:atlasGenerate'), ('POST', '/tasks:images2PosedRGBD'),
    ('POST', '/assets'), ('POST', '/assets/asset_x:createUploadUrl'), ('DELETE', '/assets/asset_x'),
    ('POST', '/operations/op123:cancel'), ('GET', '/../marble/v1/credits'), ('GET', '/operations/op/../../tasks'),
])
def test_routes_outside_the_read_allowlist_are_refused_before_any_request(method, route):
    client, opener = _client([])
    with pytest.raises(WorldLabsError, match='only reads'):
        client._request(method, route)
    assert opener.requests == []


def test_base_url_is_pinned_to_the_atlas_v2_origin(monkeypatch):
    monkeypatch.setenv('WLT_API_BASE', 'https://evil.invalid')
    client, opener = _client([{'operations': []}])
    client.list_operations()
    assert opener.requests[0].full_url.startswith('https://api.atlas.worldlabs.ai/api/v2/operations?')
    assert API_BASE == 'https://api.atlas.worldlabs.ai/api/v2'


def test_list_operations_filters_finished_splat_tasks_and_sends_key_only_to_the_api():
    client, opener = _client([{'operations': [
        {'id': 'op1', 'metadata': {'task': 'posedImages2Splats'}, 'createdAtSecs': 1795371733},
        {'id': '../bad', 'metadata': {}}, 'not-a-row']}])
    rows = client.list_operations(page_size=500)
    assert rows == [{'id': 'op1', 'task': 'posedImages2Splats', 'created': 1795371733}]
    query = parse_qs(urlsplit(opener.requests[0].full_url).query)
    assert query == {'task': ['posedImages2Splats'], 'status': ['SUCCEEDED'], 'pageSize': ['50']}
    assert opener.requests[0].get_header('Wlt-api-key') == 'test-key'
    assert opener.requests[0].get_method() == 'GET'


# ---------------------------------------------------------------------------
# Keys: typed > $WLT_API_KEY > the worldlabs CLI sign-in for this origin
# ---------------------------------------------------------------------------

def test_key_resolution_order(monkeypatch):
    monkeypatch.setenv('WLT_API_KEY', 'env-key')
    assert resolve_key('typed', saved=lambda: 'cli-key') == ('typed', 'typed')
    assert resolve_key('', saved=lambda: 'cli-key') == ('env-key', 'environment')
    monkeypatch.delenv('WLT_API_KEY')
    assert resolve_key('', saved=lambda: 'cli-key') == ('cli-key', 'worldlabs CLI sign-in')
    assert resolve_key('', saved=lambda: None) == ('', None)


def test_cli_saved_key_reads_only_the_file_named_for_the_pinned_origin(tmp_path):
    credentials = tmp_path / 'credentials'
    credentials.mkdir()
    name = hashlib.sha256(b'https://api.atlas.worldlabs.ai').hexdigest()
    (credentials / ('0' * 64 + '.key')).write_text('other-origin-key\n')
    assert cli_saved_key(tmp_path) is None
    (credentials / (name + '.key')).write_text('  saved-key-123\n')
    assert cli_saved_key(tmp_path) == 'saved-key-123'
    (credentials / (name + '.key')).write_text('bad key with spaces\n')
    assert cli_saved_key(tmp_path) is None
    (credentials / (name + '.key')).write_text('x' * 5000)
    assert cli_saved_key(tmp_path) is None


def test_missing_key_refuses_without_a_request(monkeypatch):
    monkeypatch.delenv('WLT_API_KEY', raising=False)
    opener = FakeOpener([])
    with pytest.raises(AuthenticationError, match='worldlabs auth login'):
        AtlasClient('', opener=opener, **NO_SAVED).list_operations()
    assert opener.requests == []


def test_auth_failure_is_public_safe():
    client, opener = _client([HTTPError('https://private.invalid/?key=secret', 401, 'secret-body', {}, None)],
                             key='private-key')
    with pytest.raises(AuthenticationError) as error:
        client.check_connection()
    assert 'private-key' not in str(error.value) and 'secret' not in str(error.value)


@pytest.mark.parametrize('code,kind', [(404, AssetUnavailableError), (429, WorldLabsError), (500, WorldLabsError)])
def test_http_errors_map_to_public_messages(code, kind):
    client, _ = _client([HTTPError('https://x.invalid', code, 'm', {}, None)])
    with pytest.raises(kind):
        client.get_operation('op123abc')


def test_transport_failure_is_public_safe():
    client, _ = _client([URLError('host https://secret.invalid down')])
    with pytest.raises(WorldLabsError) as error:
        client.get_operation('op123abc')
    assert 'secret' not in str(error.value)


# ---------------------------------------------------------------------------
# Operations and outputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('value,expected', [
    ('op123abc', 'op123abc'),
    ('accounts/acct_1/projects/p/operations/op123abc', 'op123abc'),
    (' 0123456789abcdef0123456789abcdef ', '0123456789abcdef0123456789abcdef'),
])
def test_operation_refs(value, expected):
    assert operation_id_from_ref(value) == expected


@pytest.mark.parametrize('value', ['', '../secret', 'https://marble.worldlabs.ai/world/abc', 'op id', 'x' * 200])
def test_bad_operation_refs_are_refused(value):
    with pytest.raises(WorldLabsError):
        operation_id_from_ref(value)


def test_splat_outputs_orders_refined_by_count_then_draft():
    op = {'response': {'refinedSplats': {'100': {'assetId': 'a'}, '2000': {'assetId': 'b'}, 'x': {'assetId': 'c'}},
                       'draftSplat': {'assetId': 'd'}}}
    assert [(r['label'], r['count']) for r in splat_outputs(op)] == [('refined', 2000), ('refined', 100), ('draft', None)]
    assert splat_outputs({'response': {'frames': []}}) == []
    assert splat_outputs({'response': None}) == []


def test_get_operation_must_return_the_requested_id():
    client, _ = _client([dict(OPERATION, id='someone-else')])
    with pytest.raises(WorldLabsError, match='different operation'):
        client.get_operation('op123abc')


# ---------------------------------------------------------------------------
# prepare_import: read URL -> credential-free download -> SPZ decode -> cached PLY
# ---------------------------------------------------------------------------

def test_prepare_import_downloads_the_largest_refined_splat_without_the_key(tmp_path):
    client, opener = _client([OPERATION, {'readUrl': 'https://storage.example/fresh.spz?sig=SECRET'}, SPZ])
    prepared = client.prepare_import('op123abc', tmp_path)
    get_op, read_url, download = opener.requests
    assert get_op.get_method() == 'GET' and get_op.full_url.endswith('/operations/op123abc')
    assert read_url.get_method() == 'POST' and read_url.full_url.endswith('/assets/asset_big:createReadUrl')
    assert download.full_url == 'https://storage.example/fresh.spz?sig=SECRET'
    assert download.get_header('Wlt-api-key') is None
    assert inspect_ply(prepared['path'])['point_count'] == 5
    meta = prepared['metadata']
    assert meta['operation_id'] == 'op123abc' and meta['splat_count'] == 500000 and meta['axis'] == 'y_up'
    assert meta['source'] == 'atlas_operation' and meta['api_version'] == 'atlas_v2'
    blob = json.dumps(meta)
    for forbidden in ('SECRET', 'acct_', 'sig=', 'X-Goog', 'test-key'):
        assert forbidden not in blob
    cached = list((tmp_path / 'atlas' / 'op123abc').glob('*.spz'))
    assert len(cached) == 1 and cached[0].name == hashlib.sha256(SPZ).hexdigest() + '.spz'


def test_prepare_import_fewest_takes_the_smallest_refined_count(tmp_path):
    client, opener = _client([OPERATION, {'readUrl': 'https://storage.example/s.spz'}, SPZ])
    assert client.prepare_import('op123abc', tmp_path, choice='fewest')['metadata']['splat_count'] == 100000
    assert opener.requests[1].full_url.endswith('/assets/asset_small:createReadUrl')


@pytest.mark.parametrize('operation,match', [
    (dict(OPERATION, done=False), 'not finished'),
    (dict(OPERATION, error={'code': 3, 'message': 'SECRET'}), 'failed'),
    (dict(OPERATION, response={'frames': []}), 'no splat output'),
])
def test_unusable_operations_stop_before_any_download(tmp_path, operation, match):
    client, opener = _client([operation])
    with pytest.raises(AssetUnavailableError, match=match) as error:
        client.prepare_import('op123abc', tmp_path)
    assert 'SECRET' not in str(error.value)
    assert len(opener.requests) == 1


def test_oversized_download_is_refused_and_leaves_no_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(wl, 'MAX_ASSET_BYTES', 10)
    client, _ = _client([OPERATION, {'readUrl': 'https://storage.example/s.spz'}, SPZ])
    with pytest.raises(AssetUnavailableError, match='import limit'):
        client.prepare_import('op123abc', tmp_path)
    assert not [p for p in (tmp_path / 'atlas' / 'op123abc').iterdir()]


@pytest.mark.parametrize('url', ['http://cdn.example/asset', 'file:///tmp/a', 'https://127.0.0.1/asset', 'https://localhost/a', 'https://user:pass@cdn.example/a'])
def test_asset_url_requires_public_https(url):
    with pytest.raises(AssetUnavailableError):
        _safe_asset_url(url)


def test_api_redirect_does_not_forward_key():
    handler = _SafeRedirect()
    request = Request(API_BASE + '/operations', headers={'WLT-Api-Key': 'secret'})
    with pytest.raises(WorldLabsError, match='unexpected redirect'):
        handler.redirect_request(request, None, 302, 'moved', {}, 'https://other.example/')


def test_old_name_still_points_at_the_atlas_client():
    assert WorldLabsClient is AtlasClient


# ---------------------------------------------------------------------------
# Local preparation: .spz, .ply and a `worldlabs operations download` folder
# ---------------------------------------------------------------------------

def test_prepare_local_spz_converts_to_a_y_up_ply(tmp_path):
    source = tmp_path / 'scene.spz'
    source.write_bytes(SPZ)
    prepared = prepare_local_asset(source, tmp_path / 'cache')
    assert inspect_ply(prepared['path'])['point_count'] == 5
    assert prepared['metadata']['axis'] == 'y_up' and prepared['metadata']['display_name'] == 'scene'


def test_prepare_local_operation_folder_uses_its_spz_and_operation_id(tmp_path):
    folder = tmp_path / 'scene'
    folder.mkdir()
    (folder / 'refinedSplats_100000.spz').write_bytes(fx.legacy_spz(fx.sample_splats(3), version=3))
    (folder / 'refinedSplats_500000.spz').write_bytes(SPZ)
    (folder / 'operation.json').write_text(json.dumps({'operationId': 'op123abc', 'metadata': {'task': 'posedImages2Splats'},
                                                       'url': 'https://secret.example/?sig=SECRET'}))
    prepared = prepare_local_asset(folder, tmp_path / 'cache')
    meta = prepared['metadata']
    assert meta['operation_id'] == 'op123abc' and meta['task'] == 'posedImages2Splats'
    assert meta['point_count'] == 5 and meta['display_name'] == 'atlas_op123abc'
    assert 'SECRET' not in json.dumps(meta)


def test_prepare_local_ply_keeps_the_historical_y_down_default(tmp_path):
    source = tmp_path / 'export.ply'
    source.write_bytes(ply_bytes())
    prepared = prepare_local_asset(source, tmp_path / 'cache')
    assert prepared == {'path': str(source.resolve()), 'metadata': {}}


@pytest.mark.parametrize('name', ['mesh.glb', 'missing.spz'])
def test_prepare_local_refuses_meshes_and_missing_files(tmp_path, name):
    if name.endswith('.glb'):
        (tmp_path / name).write_bytes(b'glTF')
    with pytest.raises(ImportValidationError):
        prepare_local_asset(tmp_path / name, tmp_path / 'cache')


def test_inspect_ply_points_spz_at_the_converter(tmp_path):
    with pytest.raises(ImportValidationError, match='converted first'):
        inspect_ply(tmp_path / 'asset.spz')


def test_ply_headers_validate_gaussian_attributes_and_sh(tmp_path):
    source = tmp_path / 'tiny.ply'
    source.write_bytes(ply_bytes(sh=True))
    assert inspect_ply(source)['has_spherical_harmonics'] is True
    source.write_bytes(ply_bytes().replace(b'format ascii 1.0\n', b''))
    with pytest.raises(ImportValidationError, match='encoding declaration'):
        inspect_ply(source)
    source.write_bytes(ply_bytes(gaussian=False))
    with pytest.raises(ImportValidationError, match='ordinary points'):
        inspect_ply(source)
