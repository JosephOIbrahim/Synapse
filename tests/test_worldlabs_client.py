"""No network or Houdini: exercise the read/free-export/cache boundary."""
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from synapse.worldlabs.client import (
    AssetUnavailableError, AuthenticationError, WorldLabsClient, WorldLabsError,
    _SafeRedirect, _safe_asset_url, world_id_from_ref,
)
from synapse.worldlabs.importer import ImportValidationError, inspect_ply


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


WORLD = {'world_id': 'world-abc', 'display_name': 'Canal', 'model': 'marble-1.1',
         'assets': {'splats': {'semantics_metadata': {'metric_scale_factor': 2.5, 'ground_plane_offset': .75,
                                                     'secret_url': 'https://private.invalid/secret'}}}}
EXPORT = {'done': True, 'operation_id': 'operation-123',
          'response': {'asset_type': 'splats', 'format': 'ply', 'url': 'https://cdn.worldlabs.ai/example.ply?lease=secret'}}


@pytest.mark.parametrize('value', ['world-abc', 'https://marble.worldlabs.ai/world/world-abc', 'https://marble.worldlabs.ai/worlds/world-abc?view=1'])
def test_world_ref_parsing(value):
    assert world_id_from_ref(value) == 'world-abc'


@pytest.mark.parametrize('value', ['../secret', '', 'https://evil.invalid/world/world-abc', 'https://marble.worldlabs.ai:443@evil.invalid/world/world-abc', 'https://marble.worldlabs.ai/world/world-abc/more'])
def test_world_ref_rejects_non_world_inputs(value):
    with pytest.raises(WorldLabsError):
        world_id_from_ref(value)


def test_connect_then_list_only_successful_api_worlds():
    opener = FakeOpener([{'remaining_credits': 0}, {'worlds': [WORLD, {'unexpected': True}]}])
    client = WorldLabsClient('test-key', opener=opener)
    assert client.check_connection() == {'connected': True, 'remaining_credits': 0}
    assert client.list_worlds() == [{'id': 'world-abc', 'title': 'Canal', 'model': 'marble-1.1'}]
    assert [req.full_url.rsplit('/', 1)[-1] for req in opener.requests] == ['credits', 'worlds:list']
    assert json.loads(opener.requests[1].data)['status'] == 'SUCCEEDED'


def test_prepare_import_uses_only_free_ply_and_keeps_credentials_off_download(tmp_path):
    raw = ply_bytes()
    opener = FakeOpener([WORLD, EXPORT, raw, WORLD, EXPORT, raw])
    client = WorldLabsClient('test-key-do-not-persist', opener=opener)
    first = client.prepare_import('world-abc', '500k', tmp_path)
    second = client.prepare_import('world-abc', '500k', tmp_path)
    assert first['path'] == second['path']
    assert Path(first['path']).read_bytes() == raw
    assert first['metadata']['semantics_metadata'] == {'metric_scale_factor': 2.5, 'ground_plane_offset': .75}
    assert first['metadata']['scale_status'] == 'unverified'
    for request in (opener.requests[1], opener.requests[4]):
        assert json.loads(request.data) == {'asset_type': 'splats', 'format': 'ply', 'resolution': '500k'}
    for request in (opener.requests[2], opener.requests[5]):
        assert not any(key.lower() == 'wlt-api-key' for key in request.headers)
    manifests = list(tmp_path.rglob('*.json'))
    assert len(manifests) == 1
    persisted = manifests[0].read_text()
    assert 'test-key-do-not-persist' not in persisted
    assert 'lease=secret' not in persisted
    assert 'secret_url' not in persisted
    assert not list(tmp_path.rglob('.download-*'))
    assert not list(tmp_path.rglob('.metadata-*'))


def test_pending_export_polls_read_endpoint_before_download(tmp_path):
    opener = FakeOpener([WORLD, {'done': False, 'operation_id': 'op-1'}, EXPORT, ply_bytes()])
    waits = []
    result = WorldLabsClient('key', opener=opener, sleep=waits.append).prepare_import('world-abc', '100k', tmp_path)
    assert Path(result['path']).exists()
    assert opener.requests[2].full_url.endswith('/operations/op-1')
    assert opener.requests[2].get_method() == 'GET'
    assert waits == [1.0]


def test_failed_download_does_not_promote_partial_file(tmp_path):
    opener = FakeOpener([WORLD, EXPORT, URLError('secret URL/key must not be echoed')])
    with pytest.raises(AssetUnavailableError) as error:
        WorldLabsClient('key', opener=opener).prepare_import('world-abc', '500k', tmp_path)
    assert 'secret URL' not in str(error.value)
    assert not list(tmp_path.rglob('*.ply'))


def test_ordinary_points_are_not_cached_as_splats(tmp_path):
    opener = FakeOpener([WORLD, EXPORT, ply_bytes(gaussian=False)])
    with pytest.raises(ImportValidationError, match='ordinary points'):
        WorldLabsClient('key', opener=opener).prepare_import('world-abc', '500k', tmp_path)
    assert not list(tmp_path.rglob('*.ply'))


def test_api_errors_are_public_safe_and_auth_failure_never_lists():
    opener = FakeOpener([HTTPError('https://private.invalid/?key=secret', 401, 'secret-body', {}, None)])
    with pytest.raises(AuthenticationError) as error:
        WorldLabsClient('private-key', opener=opener).check_connection()
    assert 'private-key' not in str(error.value) and 'secret' not in str(error.value)
    assert len(opener.requests) == 1


def test_paid_mesh_response_is_rejected_before_any_download(tmp_path):
    result = {'done': True, 'response': {'asset_type': 'mesh', 'format': 'glb', 'url': 'https://cdn.example/x.glb'}}
    opener = FakeOpener([WORLD, result])
    with pytest.raises(AssetUnavailableError, match='PLY splat'):
        WorldLabsClient('key', opener=opener).prepare_import('world-abc', '500k', tmp_path)
    assert len(opener.requests) == 2


@pytest.mark.parametrize('url', ['http://cdn.example/asset', 'file:///tmp/a', 'https://127.0.0.1/asset', 'https://localhost/a', 'https://user:pass@cdn.example/a'])
def test_asset_url_requires_public_https(url):
    with pytest.raises(AssetUnavailableError):
        _safe_asset_url(url)


def test_api_redirect_does_not_forward_key():
    handler = _SafeRedirect()
    request = Request('https://api.worldlabs.ai/marble/v1/credits', headers={'WLT-Api-Key': 'secret'})
    with pytest.raises(WorldLabsError, match='unexpected redirect'):
        handler.redirect_request(request, None, 302, 'moved', {}, 'https://other.example/')


@pytest.mark.parametrize('extension', ['.spz', '.glb'])
def test_local_unsupported_formats_are_explicit(tmp_path, extension):
    with pytest.raises(ImportValidationError, match='Direct SPZ import is not supported'):
        inspect_ply(tmp_path / ('asset' + extension))


def test_ply_headers_validate_gaussian_attributes_and_sh(tmp_path):
    source = tmp_path / 'tiny.ply'
    source.write_bytes(ply_bytes(sh=True))
    assert inspect_ply(source)['has_spherical_harmonics'] is True
    source.write_bytes(ply_bytes().replace(b'format ascii 1.0\n', b''))
    with pytest.raises(ImportValidationError, match='encoding declaration'):
        inspect_ply(source)
