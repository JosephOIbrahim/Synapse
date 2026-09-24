"""Small World API client limited to reads and the documented FREE PLY export.

No generation or mesh export endpoint is exposed. API keys stay on the API
origin; asset requests never receive them. Run network methods off the Qt thread.
Sources: docs.worldlabs.ai/api/{pricing,reference/worlds/export,reference/credits/get}.
"""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_BASE = 'https://api.worldlabs.ai/marble/v1'
RESOLUTIONS = ('100k', '150k', '500k', 'full_res')
MAX_ASSET_BYTES = 1024 * 1024 * 1024
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')


class WorldLabsError(RuntimeError):
    """A public-safe error suitable for displaying without credentials or URLs."""


class AuthenticationError(WorldLabsError):
    pass


class AssetUnavailableError(WorldLabsError):
    pass


def world_id_from_ref(value: str) -> str:
    value = str(value).strip()
    if '://' in value:
        parts = urlsplit(value)
        if parts.scheme != 'https' or parts.hostname != 'marble.worldlabs.ai' or parts.username or parts.password:
            raise WorldLabsError('Use a World Labs world ID or a Marble world URL.')
        path = parts.path.strip('/').split('/')
        if len(path) != 2 or path[0] not in ('world', 'worlds'):
            raise WorldLabsError('This Marble URL does not identify a world.')
        value = path[1]
    if not _ID.fullmatch(value):
        raise WorldLabsError('Enter a valid World Labs world ID.')
    return value


def _safe_asset_url(value: str) -> str:
    parts = urlsplit(str(value))
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise AssetUnavailableError('The export did not provide a secure download URL.')
    host = parts.hostname.lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local')):
        raise AssetUnavailableError('The export download host is not supported.')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise AssetUnavailableError('The export download host is not supported.')
    except ValueError:
        pass
    return str(value)


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # API redirects are unexpected; do not forward the key to another host.
        if any(k.lower() == 'wlt-api-key' for k in req.headers):
            raise WorldLabsError('The World API returned an unexpected redirect.')
        _safe_asset_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class WorldLabsClient:
    def __init__(self, api_key: str = '', *, opener=None, timeout: float = 30.0, sleep=None):
        self._api_key = str(api_key or os.environ.get('WLT_API_KEY', '')).strip()
        self._opener = opener if opener is not None else build_opener(_SafeRedirect())
        self._timeout = timeout
        self._sleep = sleep if sleep is not None else time.sleep

    def _request(self, method: str, route: str, payload=None) -> dict:
        if not self._api_key:
            raise AuthenticationError('Add your World Labs API key to connect.')
        if any(ord(c) < 32 or ord(c) > 126 for c in self._api_key):
            raise AuthenticationError('The World Labs API key contains invalid characters.')
        data = None if payload is None else json.dumps(payload, sort_keys=True).encode('utf-8')
        req = Request(API_BASE + route, data=data, method=method,
                      headers={'WLT-Api-Key': self._api_key, 'Accept': 'application/json',
                               'Content-Type': 'application/json'})
        try:
            with self._opener.open(req, timeout=self._timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise WorldLabsError('The World API response was too large.')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError('object required')
            return result
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthenticationError('World Labs rejected this API key or access to this world.') from None
            if exc.code == 404:
                raise AssetUnavailableError('World Labs could not find this world or API account. For a Marble app world, try a local PLY export.') from None
            if exc.code == 429:
                raise WorldLabsError('World Labs is rate limiting requests. Try again shortly.') from None
            raise WorldLabsError('World Labs request failed (HTTP %d).' % exc.code) from None
        except (URLError, OSError, ValueError, UnicodeError, HTTPException):
            raise WorldLabsError('Could not read the World Labs response. Check the connection and try again.') from None

    def check_connection(self) -> dict:
        data = self._request('GET', '/credits')
        balance = data.get('remaining_credits')
        if isinstance(balance, bool) or not isinstance(balance, (float, int)) or not math.isfinite(balance) or balance < 0:
            raise WorldLabsError('World Labs returned an invalid credit balance.')
        return {'connected': True, 'remaining_credits': balance}

    def list_worlds(self) -> list[dict]:
        """Recent successful API-created worlds; Marble app history is separate."""
        data = self._request('POST', '/worlds:list', {'page_size': 50, 'status': 'SUCCEEDED', 'sort_by': 'created_at'})
        rows = data.get('worlds')
        if not isinstance(rows, list):
            raise WorldLabsError('World Labs returned an invalid world list.')
        result = []
        for row in rows:
            if isinstance(row, dict) and _ID.fullmatch(str(row.get('world_id', ''))):
                result.append({'id': row['world_id'], 'title': str(row.get('display_name') or row['world_id']),
                               'model': str(row.get('model') or '')})
        return result

    def get_world(self, world_ref: str) -> dict:
        world_id = world_id_from_ref(world_ref)
        world = self._request('GET', '/worlds/' + world_id)
        if world.get('world_id') != world_id:
            raise WorldLabsError('World Labs returned a different world than requested.')
        return world

    def prepare_import(self, world_ref: str, resolution: str, cache_dir) -> dict:
        """Fetch the free PLY export into an atomic, content-addressed local cache.

        The sole export payload is fixed to splats/ply. Pricing documents this as
        free; changing to mesh/glb would create a paid operation and is forbidden.
        """
        from .importer import inspect_ply

        if resolution not in RESOLUTIONS:
            raise WorldLabsError('Choose a supported splat resolution.')
        world = self.get_world(world_ref)
        world_id = world['world_id']
        operation = self._request('POST', '/worlds/' + world_id + ':export',
                                  {'asset_type': 'splats', 'format': 'ply', 'resolution': resolution})
        for attempt in range(31):
            if operation.get('error'):
                raise AssetUnavailableError('World Labs could not prepare this PLY export. Try again or import a local export.')
            if operation.get('done') is True:
                break
            op_id = operation.get('operation_id', '')
            if not _ID.fullmatch(str(op_id)) or attempt == 30:
                raise AssetUnavailableError('The PLY export is still unavailable. Try again shortly.')
            self._sleep(1.0)
            operation = self._request('GET', '/operations/' + str(op_id))
        export = operation.get('response') or {}
        if not isinstance(export, dict) or export.get('asset_type') != 'splats' or export.get('format') != 'ply':
            raise AssetUnavailableError('World Labs did not return a PLY splat export.')
        url = _safe_asset_url(export.get('url', ''))
        metadata = {'world_id': world_id, 'display_name': str(world.get('display_name') or world_id),
                    'model': str(world.get('model') or ''), 'resolution': resolution,
                    'api_version': 'v1', 'source': 'worldlabs_free_ply_export',
                    'coordinate_normalization': 'preserved_export_coordinates',
                    'scale_status': 'unverified'}
        assets = world.get('assets') or {}
        if not isinstance(assets, dict):
            raise AssetUnavailableError('World Labs returned invalid asset metadata.')
        splats = assets.get('splats') or {}
        if not isinstance(splats, dict):
            raise AssetUnavailableError('World Labs returned invalid splat metadata.')
        semantics = splats.get('semantics_metadata') or {}
        if not isinstance(semantics, dict):
            raise AssetUnavailableError('World Labs returned invalid scale metadata.')
        metadata['semantics_metadata'] = {
            name: value for name in ('metric_scale_factor', 'ground_plane_offset')
            if isinstance((value := semantics.get(name)), (float, int))
            and not isinstance(value, bool) and math.isfinite(value)
        }
        directory = Path(cache_dir).expanduser().resolve() / world_id / resolution
        temporary = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(dir=directory, prefix='.download-', suffix='.ply', delete=False) as target:
                temporary = Path(target.name)
                # Deliberately no API credentials on the signed asset request.
                with self._opener.open(Request(url, headers={'Accept': 'application/octet-stream'}), timeout=self._timeout) as source:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_ASSET_BYTES:
                            raise AssetUnavailableError('This PLY export exceeds the 1 GB import limit.')
                        digest.update(chunk)
                        target.write(chunk)
            inspect_ply(temporary)
            metadata['sha256'] = digest.hexdigest()
            metadata['bytes'] = size
            destination = directory / (digest.hexdigest() + '.ply')
            os.replace(temporary, destination)
            temporary = None
            # Provenance is allowlisted above: no key or signed asset URL.
            with tempfile.NamedTemporaryFile(dir=directory, prefix='.metadata-', suffix='.json', mode='w', encoding='utf-8', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(metadata, stream, indent=2, allow_nan=False, sort_keys=True)
            os.replace(temporary, destination.with_suffix('.json'))
            temporary = None
            return {'path': str(destination), 'metadata': metadata, 'world_id': world_id, 'resolution': resolution}
        except (HTTPError, URLError, OSError, HTTPException):
            raise AssetUnavailableError('The PLY export could not be downloaded or cached. Check the connection and cache folder.') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
