"""World Labs Atlas v2 client: READ-ONLY. It never submits a task.

World Labs serves Atlas only (Joe, 2026-11-22). The Marble v1 client that lived here (credits, world list, free PLY
export) is gone. Every Atlas task (``POST /tasks:<name>``) costs credits, so SYNAPSE submits none. Run tasks with the
``worldlabs`` CLI or the World Labs app. This client lists finished operations, reads one, mints a short-lived read
URL for an output asset, and downloads it. Those are free reads.

The routes this client may call are an explicit allowlist (``_ROUTES``). Anything else, a task route above all, is
refused before a request is built. The API key goes only to the pinned API origin. Asset downloads go to the signed
URL with no credentials. Run the network methods off the Qt thread.
Sources: docs.atlas.worldlabs.ai api-reference {list-operations, get-operation, create-read-url, posed-images2-splats}.
"""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_ORIGIN = 'https://api.atlas.worldlabs.ai'
API_BASE = API_ORIGIN + '/api/v2'   # pinned; never taken from the environment
API_VERSION = 'atlas_v2'
SPLAT_TASK = 'posedImages2Splats'
MAX_ASSET_BYTES = 1024 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')

# (method, route pattern). Nothing outside this list is ever sent, and no POST route can start a task.
_ROUTES = (
    ('GET', re.compile(r'/operations\Z')),
    ('GET', re.compile(r'/operations/[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')),
    ('POST', re.compile(r'/assets/[A-Za-z0-9][A-Za-z0-9_-]{0,127}:createReadUrl\Z')),
)


class WorldLabsError(RuntimeError):
    """A public-safe error suitable for displaying without credentials or URLs."""


class AuthenticationError(WorldLabsError):
    pass


class AssetUnavailableError(WorldLabsError):
    pass


def operation_id_from_ref(value: str) -> str:
    """An Atlas operation id, or a resource name ending in ``/operations/<id>``."""
    value = str(value).strip()
    if '/operations/' in value and '://' not in value:
        value = value.rsplit('/operations/', 1)[1]
    if not _ID.fullmatch(value):
        raise WorldLabsError('Enter an Atlas operation ID, such as the one `worldlabs tasks run` printed.')
    return value


def _safe_asset_url(value: str) -> str:
    parts = urlsplit(str(value))
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise AssetUnavailableError('Atlas did not provide a secure download URL.')
    host = parts.hostname.lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local')):
        raise AssetUnavailableError('The download host is not supported.')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise AssetUnavailableError('The download host is not supported.')
    except ValueError:
        pass
    return str(value)


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # API redirects are unexpected; never forward the key to another host.
        if any(k.lower() == 'wlt-api-key' for k in req.headers):
            raise WorldLabsError('The Atlas API returned an unexpected redirect.')
        _safe_asset_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cli_saved_key(config_dir=None):
    """The key ``worldlabs auth login`` saved for the pinned Atlas origin, or None.

    @worldlabsai/cli 0.6.0 keeps it as plain text in ``<config>/credentials/<sha256(origin)>.key``, where config is
    $WORLDLABS_CONFIG_DIR or ~/.config/worldlabs (dist/index.js credentialPath/readApiKey, read 2026-11-22). Only the
    file for THIS origin is read: one regular file, at most 4 KB, printable ASCII. It is never written or copied.
    """
    base = Path(config_dir or os.environ.get('WORLDLABS_CONFIG_DIR') or Path.home() / '.config' / 'worldlabs')
    target = base / 'credentials' / (hashlib.sha256(API_ORIGIN.encode('ascii')).hexdigest() + '.key')
    try:
        if not target.is_file() or target.is_symlink() or target.stat().st_size > 4096:
            return None
        key = target.read_text(encoding='ascii').strip()
    except (OSError, UnicodeError):
        return None
    if not key or any(ord(ch) < 33 or ord(ch) > 126 for ch in key):
        return None
    return key


def resolve_key(typed: str = '', *, saved=cli_saved_key):
    """(key, source): a typed key, then $WLT_API_KEY, then the worldlabs CLI sign-in. Source names where it came from."""
    typed = str(typed or '').strip()
    if typed:
        return typed, 'typed'
    env = os.environ.get('WLT_API_KEY', '').strip()
    if env:
        return env, 'environment'
    key = saved() if saved is not None else None
    return (key, 'worldlabs CLI sign-in') if key else ('', None)


def splat_outputs(operation: dict) -> list[dict]:
    """The SPZ outputs of a finished posedImages2Splats operation, refined first and most splats first.

    ``response.refinedSplats`` maps a published splat count to an asset. ``response.draftSplat`` is one asset.
    """
    response = operation.get('response') if isinstance(operation, dict) else None
    if not isinstance(response, dict):
        return []
    rows = []
    refined = response.get('refinedSplats')
    if isinstance(refined, dict):
        for key, asset in refined.items():
            if isinstance(asset, dict) and str(key).isdigit():
                rows.append({'label': 'refined', 'count': int(key), 'asset': asset})
    draft = response.get('draftSplat')
    if isinstance(draft, dict):
        rows.append({'label': 'draft', 'count': None, 'asset': draft})
    rows.sort(key=lambda r: (r['label'] != 'refined', -(r['count'] or 0)))
    return rows


class AtlasClient:
    def __init__(self, api_key: str = '', *, opener=None, timeout: float = 30.0, saved_key=cli_saved_key):
        self._api_key, self.key_source = resolve_key(api_key, saved=saved_key)
        self._opener = opener if opener is not None else build_opener(_SafeRedirect())
        self._timeout = timeout

    def _request(self, method: str, route: str, query=None) -> dict:
        if not any(method == m and pattern.fullmatch(route) for m, pattern in _ROUTES):
            raise WorldLabsError('SYNAPSE only reads from Atlas; it does not start Atlas tasks.')
        if not self._api_key:
            raise AuthenticationError('Add your Atlas API key, or sign in with `worldlabs auth login`.')
        if any(ord(c) < 32 or ord(c) > 126 for c in self._api_key):
            raise AuthenticationError('The Atlas API key contains invalid characters.')
        url = API_BASE + route + ('?' + urlencode(query) if query else '')
        req = Request(url, data=b'' if method == 'POST' else None, method=method,
                      headers={'WLT-Api-Key': self._api_key, 'Accept': 'application/json'})
        try:
            with self._opener.open(req, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise WorldLabsError('The Atlas response was too large.')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError('object required')
            return result
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthenticationError('Atlas rejected this API key, or it lacks operations.read or assets.read.') from None
            if exc.code == 404:
                raise AssetUnavailableError("Atlas could not find that operation or asset in this API key's project.") from None
            if exc.code == 429:
                raise WorldLabsError('Atlas is rate limiting requests. Try again shortly.') from None
            raise WorldLabsError('Atlas request failed (HTTP %d).' % exc.code) from None
        except (URLError, OSError, ValueError, UnicodeError, HTTPException):
            raise WorldLabsError('Could not read the Atlas response. Check the connection and try again.') from None

    # -- reads -------------------------------------------------------------------------------------------

    def list_operations(self, task: str = SPLAT_TASK, *, page_size: int = 20) -> list[dict]:
        """Recent SUCCEEDED operations of one task, newest first (no result payloads)."""
        data = self._request('GET', '/operations',
                             {'task': task, 'status': 'SUCCEEDED', 'pageSize': max(1, min(int(page_size), 50))})
        rows = data.get('operations')
        if not isinstance(rows, list):
            raise WorldLabsError('Atlas returned an invalid operation list.')
        result = []
        for row in rows:
            if isinstance(row, dict) and _ID.fullmatch(str(row.get('id', ''))):
                meta = row.get('metadata') if isinstance(row.get('metadata'), dict) else {}
                created = row.get('createdAtSecs')
                result.append({'id': row['id'], 'task': str(meta.get('task') or task),
                               'created': created if isinstance(created, int) and not isinstance(created, bool) else None})
        return result

    def check_connection(self) -> dict:
        return {'connected': True, 'operations': self.list_operations(page_size=20)}

    def get_operation(self, ref: str) -> dict:
        op_id = operation_id_from_ref(ref)
        operation = self._request('GET', '/operations/' + op_id)
        if operation.get('id') != op_id:
            raise WorldLabsError('Atlas returned a different operation than requested.')
        return operation

    def read_url(self, asset_id: str) -> str:
        if not _ID.fullmatch(str(asset_id)):
            raise AssetUnavailableError('Atlas named an invalid asset.')
        data = self._request('POST', '/assets/' + quote(str(asset_id), safe='') + ':createReadUrl')
        return _safe_asset_url(data.get('readUrl', ''))

    # -- import preparation --------------------------------------------------------------------------------

    def prepare_import(self, ref: str, cache_dir, choice: str = 'most') -> dict:
        """Download one finished operation's SPZ and convert it to a cached PLY. Reads only; no task is started.

        ``choice`` is 'most' (the largest refined count, the default) or 'fewest' (the smallest, for layout).
        """
        from . import spz

        operation = self.get_operation(ref)
        op_id = operation['id']
        meta = operation.get('metadata') if isinstance(operation.get('metadata'), dict) else {}
        task = str(meta.get('task') or '')
        if operation.get('done') is not True:
            raise AssetUnavailableError('This Atlas operation has not finished yet. Try again when it is done.')
        if operation.get('error'):
            raise AssetUnavailableError('This Atlas operation failed, so it has no splats to import.')
        outputs = splat_outputs(operation)
        if not outputs:
            raise AssetUnavailableError('This Atlas operation has no splat output. Splats come from posedImages2Splats.')
        refined = [o for o in outputs if o['label'] == 'refined'] or outputs
        chosen = refined[-1] if choice == 'fewest' else refined[0]
        asset = chosen['asset']
        asset_id = asset.get('assetId')
        url = self.read_url(asset_id) if asset_id else _safe_asset_url(asset.get('url', ''))
        directory = Path(cache_dir).expanduser().resolve() / 'atlas' / op_id
        temporary = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(dir=directory, prefix='.download-', suffix='.spz', delete=False) as target:
                temporary = Path(target.name)
                # Deliberately no API credentials on the signed asset request.
                with self._opener.open(Request(url, headers={'Accept': 'application/octet-stream'}),
                                       timeout=self._timeout) as source:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_ASSET_BYTES:
                            raise AssetUnavailableError('This splat exceeds the 1 GB import limit.')
                        digest.update(chunk)
                        target.write(chunk)
            destination = directory / (digest.hexdigest() + '.spz')
            os.replace(temporary, destination)
            temporary = None
        except (HTTPError, URLError, OSError, HTTPException):
            raise AssetUnavailableError('The splat could not be downloaded or cached. Check the connection and cache folder.') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        converted = spz.convert_to_ply(destination, cache_dir)
        # Provenance is allowlisted: no key, owner id or signed URL.
        metadata = dict(converted['metadata'])
        metadata.update({'operation_id': op_id, 'task': task[:64], 'api_version': API_VERSION,
                         'source': 'atlas_operation', 'splat_label': chosen['label'],
                         'splat_count': chosen['count'], 'display_name': 'atlas_' + op_id[:12]})
        return {'path': converted['path'], 'metadata': metadata, 'operation_id': op_id}


# Older imports keep working while callers move to AtlasClient.
WorldLabsClient = AtlasClient
