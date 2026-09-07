"""Shared, local model-request permission. No Qt, Houdini, prompts or credentials on disk."""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from functools import wraps
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import uuid
import weakref

from synapse.panel.connections import ConnectionFacts, ConnectionSpec, is_loopback, validate_endpoint

MODES = ("ask", "local_only")
MAX_POLICY_BYTES = 65536
_AUTHORITY = object()
_SCOPE = ContextVar("synapse_model_request_scope", default=None)
_RECORDS = deque(maxlen=100)
_LOCK = threading.RLock()
_SDK_CLIENTS = weakref.WeakKeyDictionary()
_SDK_REQUEST = ContextVar("synapse_sdk_request", default=None)
_STREAM_REQUEST = ContextVar("synapse_stream_request", default=None)
_MAX_SESSION_APPROVALS = 64
_SESSION_ANCHOR = "_synapse_panel_session_consent_v1"
# The pypanel loader evicts synapse.* on ordinary reopen. One fully initialized
# process anchor keeps consent and revocation shared across those generations.
_session_candidate = types.ModuleType(_SESSION_ANCHOR)
_session_candidate.schema = 1
_session_candidate.owner_pid = os.getpid()
_session_candidate.lock = threading.RLock()
_session_candidate.approvals = {}
_session_candidate.expired = False
_SESSION_STATE = sys.modules.setdefault(_SESSION_ANCHOR, _session_candidate)
del _session_candidate


class ModelAccessDenied(RuntimeError):
    """A controlled, credential-free refusal before model payload transmission."""


class ModelRequestFailed(RuntimeError):
    """Only controlled text from SYNAPSE, never a transport response body."""


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate rules field")
        out[key] = value
    return out


def _selector():
    from synapse.panel import settings
    try:
        path = settings.settings_path()
        with path.open("rb") as stream:
            raw = stream.read(MAX_POLICY_BYTES + 1)
        if len(raw) > MAX_POLICY_BYTES:
            raise ValueError("Invalid selector")
        data = json.loads(raw, object_pairs_hook=_unique_object)
        if not isinstance(data, dict):
            raise ValueError("Invalid selector")
        chosen = data.get("model_policy_path", "")
        generation = data.get("model_policy_generation", "")
        if (not isinstance(chosen, str) or not isinstance(generation, str)
                or len(chosen) > 4096 or len(generation) > 256
                or (chosen and not Path(chosen).is_absolute())):
            raise ValueError("Invalid selector")
        return chosen, generation
    except FileNotFoundError:
        return "", ""
    except (OSError, ValueError, TypeError):
        raise ModelAccessDenied("The selected project rules could not be read. Review Connect a model settings before sending.") from None


def policy_path():
    override = os.environ.get("SYNAPSE_MODEL_POLICY", "").strip()
    if override:
        return Path(override).resolve()
    from synapse.panel import settings
    chosen, _ = _selector()
    return Path(chosen).resolve() if chosen else (settings._repo_root() / ".synapse/model_access.json").resolve()


def _selection_generation():
    if os.environ.get("SYNAPSE_MODEL_POLICY", "").strip():
        return "deployment-override"
    return _selector()[1]


def select_project_policy(path):
    if os.environ.get("SYNAPSE_MODEL_POLICY", "").strip():
        raise ModelAccessDenied("The project rules file is selected by this deployment.")
    from synapse.panel import settings
    # This explicit project-selection action can repair a corrupt selector;
    # ordinary preferences writes preserve its refusal marker.
    target = str(Path(path).resolve()) if path else ""
    current = settings.load_settings()
    if not settings.save_settings(current, _project_selection=(target, uuid.uuid4().hex)):
        raise ModelAccessDenied("The selected project could not be saved. The previous scope remains active.")
    revoke_session_approvals()
    return load_policy()


@dataclass(frozen=True)
class ModelPolicy:
    path: Path
    revision: str
    mode: str = "ask"
    approved_models: tuple = ()
    error: str | None = None


def _decode(data):
    if not isinstance(data, dict) or set(data) != {"version", "mode", "approved_models"}:
        raise ValueError("Invalid model rules")
    if type(data["version"]) is not int or data["version"] != 1 or data["mode"] not in MODES:
        raise ValueError("Invalid model rules")
    rows = data["approved_models"]
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("Invalid approved models")
    models = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"provider", "model", "endpoint"}:
            raise ValueError("Invalid approved model")
        if any(not isinstance(value, str) or not value or len(value) > 2048 for value in row.values()):
            raise ValueError("Invalid approved model")
        if row["provider"] not in ("claude", "gemini", "nemotron", "ollama", "custom"):
            raise ValueError("Unknown provider")
        models.append(ConnectionSpec(**row))
    if len(set(models)) != len(models):
        raise ValueError("Duplicate approved model")
    return data["mode"], tuple(models)


def load_policy(path=None):
    try:
        target = Path(path).resolve() if path is not None else policy_path()
    except ModelAccessDenied:
        revoke_session_approvals()
        raise
    try:
        with target.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            raw = stream.read(MAX_POLICY_BYTES + 1)
        revision = hashlib.sha256(raw).hexdigest() + ":%s:%s" % (stat.st_mtime_ns, stat.st_ino)
        if not raw or len(raw) > MAX_POLICY_BYTES:
            raise ValueError("Invalid model rules size")
        mode, approved = _decode(json.loads(raw, object_pairs_hook=_unique_object))
        return ModelPolicy(target, revision, mode, approved)
    except FileNotFoundError:
        return ModelPolicy(target, "missing")
    except (OSError, ValueError, TypeError):
        return ModelPolicy(target, "unreadable", "local_only", error="Project model rules could not be read. Open Project rules to review them.")


def save_policy(mode, approved_models=(), *, path=None, expected_revision=None):
    target = Path(path).resolve() if path is not None else policy_path()
    payload = {"version": 1, "mode": mode, "approved_models": [asdict(spec) for spec in approved_models]}
    _decode(payload)
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_POLICY_BYTES:
        raise ModelAccessDenied("Too many model permissions to save.")
    lock_path = target.with_name(target.name + ".lock")
    lock = None
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive short-lived writer; never replace another writer's staging file.
        for attempt in range(10):
            try:
                lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                if attempt == 9:
                    raise ModelAccessDenied("Project model rules are being saved elsewhere. Try again.") from None
                time.sleep(.01)
        if expected_revision is not None and load_policy(target).revision != expected_revision:
            raise ModelAccessDenied("Project model rules changed. Review the current rules before saving.")
        with tempfile.NamedTemporaryFile(prefix=".model-policy-", suffix=".tmp", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
        _expire_session_path(target)
        return load_policy(target)
    except OSError:
        raise ModelAccessDenied("Project model rules could not be saved. The previous rules remain in place.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if lock is not None:
            os.close(lock)
            lock_path.unlink(missing_ok=True)


@dataclass
class RequestScope:
    path: Path
    revision: str
    generation: str
    active: bool = True
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancelled: object = field(default=None, repr=False, compare=False)


def capture_scope():
    try:
        policy = load_policy()
        generation = _selection_generation()
        _expire_session_approvals(policy, generation)
        return RequestScope(policy.path, policy.revision, generation)
    except ModelAccessDenied:
        revoke_session_approvals()
        # Keep offline recipes usable, but never let fixing a corrupt selector
        # authorize a request accepted while its scope was unknown.
        return RequestScope(Path(), "unreadable", "unreadable", active=False)


def _check_scope(scope, policy):
    try:
        generation = _selection_generation()
    except ModelAccessDenied:
        revoke_session_approvals()
        raise
    _expire_session_approvals(policy, generation)
    if isinstance(scope, RequestScope) and callable(scope.cancelled) and scope.cancelled():
        scope.active = False
    if not isinstance(scope, RequestScope) or not scope.active:
        raise ModelAccessDenied("This task's project rules changed. Start a new task after reviewing Project rules.")
    if (scope.path != policy.path or scope.revision != policy.revision or scope.generation != generation):
        scope.active = False  # Switching back cannot revive a previously rejected task.
        raise ModelAccessDenied("This task's project rules changed. Start a new task after reviewing Project rules.")


@contextmanager
def request_scope(scope=None):
    chosen = scope if scope is not None else (_SCOPE.get() or capture_scope())
    token = _SCOPE.set(chosen)
    try:
        yield chosen
    finally:
        _SCOPE.reset(token)


def scoped_request(function):
    if inspect.iscoroutinefunction(function):
        @wraps(function)
        def run_async(*args, **kwargs):
            # Capture at acceptance, before the coroutine is queued/awaited.
            supplied = kwargs.pop("_request_scope", None)
            chosen = supplied if supplied is not None else (_SCOPE.get() or capture_scope())
            async def accepted():
                with request_scope(chosen):
                    return await function(*args, **kwargs)
            return accepted()
        return run_async
    @wraps(function)
    def run(*args, **kwargs):
        with request_scope(kwargs.pop("_request_scope", None)):
            return function(*args, **kwargs)
    return run


def _key_digest(key):
    return hashlib.sha256((key or "").encode("utf-8")).digest()


@dataclass
class TaskGrant:
    spec: ConnectionSpec
    scope: RequestScope
    local: bool
    _key: bytes = field(repr=False)
    _authority: object = field(repr=False)
    active: bool = True
    _session: object = field(default=None, repr=False, compare=False)

    def release(self):
        self.active = False


def _session_store():
    state = _SESSION_STATE
    if (sys.modules.get(_SESSION_ANCHOR) is not state or not isinstance(state, types.ModuleType)
            or getattr(state, "schema", None) != 1
            or type(getattr(state, "schema", None)) is not int
            or getattr(state, "owner_pid", None) != os.getpid()
            or type(getattr(state, "owner_pid", None)) is not int
            or getattr(state, "expired", None) is not False
            or type(getattr(state, "approvals", None)) is not dict
            or not isinstance(getattr(state, "lock", None), type(threading.RLock()))):
        # A schema/PID mismatch is a permanent expiry, even if a later reload
        # restores the old attributes. Never reinterpret or revive stale consent.
        if isinstance(state, types.ModuleType):
            state.expired = True
            approvals = getattr(state, "approvals", None)
            if type(approvals) is dict:
                for parent in approvals.values():
                    if type(parent) is dict:
                        parent["active"] = False
                approvals.clear()
        raise ModelAccessDenied("Session permissions are unavailable after a runtime change. Restart Houdini or allow one task.")
    return state


def _retire_session_approvals(predicate):
    """Caller holds the lock; retained task children see a retired parent."""
    approvals = _session_store().approvals
    retired = [identity for identity in approvals if predicate(identity)]
    for identity in retired:
        approvals.pop(identity)["active"] = False
    return len(retired)


def revoke_session_approvals():
    """Revoke all panel session approvals, including already issued task children."""
    try:
        with _session_store().lock:
            return _retire_session_approvals(lambda identity: True)
    except ModelAccessDenied:
        return 0  # An incompatible or inherited authority cannot authorize sends.


def _expire_session_path(path):
    try:
        with _session_store().lock:
            _retire_session_approvals(lambda identity: identity[0] == os.path.normcase(str(path)))
    except ModelAccessDenied:
        pass


def _expire_session_approvals(policy, generation):
    try:
        with _session_store().lock:
            context = (os.path.normcase(str(policy.path)), policy.revision, generation)
            _retire_session_approvals(lambda identity: bool(policy.error) or identity[:3] != context)
    except ModelAccessDenied:
        pass


def _session_identity(spec, key, scope):
    # Built-in immutable values survive ConnectionSpec class reloads. Never
    # retain the key itself, a task scope, a panel, a provider or scene content.
    return (os.path.normcase(str(scope.path)), scope.revision, scope.generation,
            spec.provider, spec.model, spec.endpoint, _key_digest(key))


def _session_request(spec, key, facts, scope):
    if not isinstance(spec, ConnectionSpec):
        raise ModelAccessDenied("The model connection is unavailable. Choose a model again.")
    if facts is not None and (not isinstance(facts, ConnectionFacts) or facts.spec != spec):
        raise ModelAccessDenied("The checked model connection changed. Check the selected model again.")
    chosen = scope if scope is not None else capture_scope()
    # Reuse the ordinary task and physical-send checks before publishing consent.
    # This validates local-only, credentials, HTTPS and the original project.
    child = issue_task_grant(spec, key=key, facts=facts, approved=True, scope=chosen)
    require_access(spec, key=key, facts=facts, grant=child, scope=chosen)
    return child, _session_identity(spec, key, chosen)


def _session_parent(identity):
    parent = _session_store().approvals.get(identity)
    if (type(parent) is dict and set(parent) == {"active", "local"}
            and parent["active"] is True and type(parent["local"]) is bool):
        return parent
    return None


def issue_session_grant(spec, *, key=None, facts=None, approved=False, scope=None):
    """Explicit panel consent only; return its first independently revocable task."""
    if approved is not True:
        raise ModelAccessDenied("Session permission requires an explicit choice in the panel.")
    with _session_store().lock:
        child, identity = _session_request(spec, key, facts, scope)
        parent = _session_parent(identity)
        if parent is not None and parent["local"] != child.local:
            _retire_session_approvals(lambda candidate: candidate == identity)
            parent = None
        if parent is None:
            if len(_session_store().approvals) >= _MAX_SESSION_APPROVALS:
                raise ModelAccessDenied("Too many session model permissions. End session permissions before allowing another model.")
            parent = {"local": child.local, "active": True}
            _session_store().approvals[identity] = parent
        child._session = parent
        return child


def session_task_grant(spec, *, key=None, facts=None, scope=None):
    """The panel may redeem existing consent for a fresh original task scope.

    This is never called by ambient SDK, background or process-handoff lanes.
    Missing consent returns None; invalid project/connection evidence refuses.
    """
    try:
        state = _session_store()
    except ModelAccessDenied:
        # Ordinary one-task consent remains available after session state expires.
        # Still validate the original task: an invalid scope is never a retry.
        _session_request(spec, key, facts, scope)
        return None
    with state.lock:
        child, identity = _session_request(spec, key, facts, scope)
        parent = _session_parent(identity)
        if parent is None:
            return None
        if parent["local"] and not child.local:
            _retire_session_approvals(lambda candidate: candidate == identity)
            return None
        child._session = parent
        return child


def has_session_approval(spec, *, key=None, scope=None):
    """UI observation only; it cannot mint a task grant or authorize a send."""
    try:
        with _session_store().lock:
            chosen = scope if scope is not None else capture_scope()
            policy = load_policy()
            _check_scope(chosen, policy)
            if policy.error or not isinstance(spec, ConnectionSpec):
                return False
            return _session_parent(_session_identity(spec, key, chosen)) is not None
    except (ModelAccessDenied, AttributeError, TypeError):
        return False


def issue_task_grant(spec, *, key=None, facts=None, approved=False, scope=None):
    if key is not None and (not isinstance(key, str) or any(ord(c) < 32 or ord(c) > 126 for c in key)):
        raise ModelAccessDenied("The model key contains unsupported characters. Re-enter the key.")
    policy = load_policy()
    chosen_scope = scope if scope is not None else capture_scope()
    _check_scope(chosen_scope, policy)
    if policy.error:
        raise ModelAccessDenied(policy.error)
    local = isinstance(facts, ConnectionFacts) and facts.spec == spec and facts.location == "Local"
    if not local and policy.mode == "local_only":
        raise ModelAccessDenied("Local only is active. Check a local model or review Project rules.")
    if not local and approved is not True:
        raise ModelAccessDenied("This model needs permission before any project content is sent.")
    return TaskGrant(spec, chosen_scope, local, _key_digest(key), _AUTHORITY)


def require_access(spec, *, key=None, facts=None, grant=None, scope=None):
    if key is not None and (not isinstance(key, str) or any(ord(c) < 32 or ord(c) > 126 for c in key)):
        raise ModelAccessDenied("The model key contains unsupported characters. Re-enter the key.")
    policy = load_policy()
    chosen_scope = scope if scope is not None else _SCOPE.get()
    if chosen_scope is not None:
        _check_scope(chosen_scope, policy)
    if policy.error:
        raise ModelAccessDenied(policy.error)
    p = validate_endpoint(spec.endpoint)
    if p.scheme == "http" and not is_loopback(spec.endpoint) and key not in (None, "", "not-needed"):
        raise ModelAccessDenied("Use HTTPS before sending credentials to a remote model service.")
    local = isinstance(facts, ConnectionFacts) and facts.spec == spec and facts.location == "Local"
    if grant is not None:
        if (not isinstance(grant, TaskGrant) or grant._authority is not _AUTHORITY or not grant.active
                or grant.spec != spec or grant._key != _key_digest(key)):
            raise ModelAccessDenied("This task's model permission is unavailable or changed. Start a new task.")
        _check_scope(grant.scope, policy)
        if chosen_scope is not None and chosen_scope is not grant.scope:
            raise ModelAccessDenied("This model permission belongs to another task.")
        if grant._session is not None:
            with _session_store().lock:
                identity = _session_identity(spec, key, grant.scope)
                if _session_parent(identity) is not grant._session:
                    grant.release()
                    raise ModelAccessDenied("Session permission ended. Allow this model again before sending.")
        if grant.local and not local:
            grant.release()
            raise ModelAccessDenied("Local execution could not be reverified. Check the model before starting a new task.")
    if local:
        return "local"
    if policy.mode == "local_only":
        raise ModelAccessDenied("Local only is active. This model cannot receive project content.")
    if grant is not None:
        return "session" if grant._session is not None else "task"
    if spec in policy.approved_models:
        return "project"
    raise ModelAccessDenied("This model needs permission. Open Connect a model → Project rules before running background requests.")


def _attempt_record(spec, *, lane, facts=None, scope=None):
    selected = scope if scope is not None else _SCOPE.get()
    return {"attempt_id": uuid.uuid4().hex, "at": time.time(), "lane": lane,
              "task_id": selected.task_id if isinstance(selected, RequestScope) else None,
              "policy_revision": selected.revision if isinstance(selected, RequestScope) else None,
              "provider": spec.provider, "requested_model": spec.model, "endpoint": spec.endpoint,
              "location": facts.location if isinstance(facts, ConnectionFacts) and facts.spec == spec else "Unverified",
              "reported_model": None, "usage": None, "result": "pending"}


def begin_attempt(spec, *, lane, key=None, facts=None, grant=None, scope=None):
    record = _attempt_record(spec, lane=lane, facts=facts, scope=scope)
    try:
        record["permission"] = require_access(spec, key=key, facts=facts, grant=grant, scope=scope)
    except ModelAccessDenied as exc:
        record.update(result="blocked", reason=str(exc))
        with _LOCK:
            _RECORDS.append(record)
        exc.attempt = dict(record)
        raise
    return record


def finish_attempt(record, *, result, reported_model=None, usage=None):
    if record.get("result") != "pending":
        return
    record["result"] = result
    if isinstance(reported_model, str) and 0 < len(reported_model) <= 256 and not any(ord(c) < 32 for c in reported_model):
        record["reported_model"] = reported_model
    if isinstance(usage, dict):
        values = {key: value for key, value in usage.items()
                  if key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
                  and type(value) is int and value >= 0}
        record["usage"] = values or None
    with _LOCK:
        _RECORDS.append(dict(record))


def recent_attempts():
    with _LOCK:
        return json.loads(json.dumps(list(_RECORDS), sort_keys=True))


def sdk_http_module():
    """Use the HTTPX generation required by the installed Anthropic SDK."""
    from anthropic import _base_client
    module = getattr(_base_client, "httpx2", None) or getattr(_base_client, "httpx", None)
    if module is None:
        raise ModelAccessDenied("This model SDK transport is unavailable. Configure a supported guarded SYNAPSE client.")
    return module


def _sdk_state(client):
    try:
        state = _SDK_CLIENTS.get(client)
    except TypeError:
        state = None
    if state is None:
        raise ModelAccessDenied("Configure a guarded SYNAPSE client before sending project content.")
    transport = state["http"]
    if (client._client is not transport or client.max_retries != 0
            or transport.follow_redirects or transport._trust_env or transport._mounts
            or transport._transport is not state["transport"]
            or transport.auth is not None
            or transport.event_hooks.get("request") != [state["hook"]]
            or transport.event_hooks.get("response")
            or str(client.base_url) != state["base"]
            or _key_digest(client.api_key) != state["key"]
            or getattr(client, "auth_token", None)
            or getattr(client, "credentials", None)):
        raise ModelAccessDenied("The guarded model connection changed. Start a new connection.")
    if getattr(client, "custom_auth", None) is not None or getattr(client, "_custom_auth", None) is not None:
        raise ModelAccessDenied("The guarded model connection changed. Start a new connection.")
    return state


def sdk_spec(client, model):
    state = _sdk_state(client)
    return ConnectionSpec("claude", model, state["endpoint"])


def sdk_receipt(client):
    record = _sdk_state(client).get("last_attempt")
    return json.loads(json.dumps(record, sort_keys=True)) if record else None


def guarded_create(client, *, lane, **kwargs):
    """Every owned SDK lane goes through this; opaque supplied clients refuse."""
    spec = sdk_spec(client, kwargs.get("model", ""))
    state = _sdk_state(client)
    state["last_attempt"] = None
    if kwargs.get("stream"):
        raise ModelAccessDenied("Use the guarded streaming provider for streaming requests.")
    with request_scope() as scope:
        try:
            record = begin_attempt(spec, lane=lane, key=client.api_key, scope=scope)
        except ModelAccessDenied as exc:
            state["last_attempt"] = getattr(exc, "attempt", None)
            raise
        state["last_attempt"] = record
        token = _SDK_REQUEST.set({"client": client, "spec": spec, "scope": scope, "sent": False})
        try:
            response = client.messages.create(**kwargs)
        except BaseException as exc:
            current = exc
            while current is not None:
                if isinstance(current, ModelAccessDenied):
                    finish_attempt(record, result="blocked")
                    raise ModelAccessDenied(str(current)) from None
                current = current.__cause__
            finish_attempt(record, result="failed")
            if not isinstance(exc, Exception):
                raise
            raise RuntimeError("The model request failed. Check the connection, model access, and service limits.") from None
        finally:
            _SDK_REQUEST.reset(token)
        usage = getattr(response, "usage", None)
        usage = {key: getattr(usage, key, None) for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
        finish_attempt(record, result="completed", reported_model=getattr(response, "model", None), usage=usage)
        return response


def make_anthropic_client(api_key=None, *, base_url=None, transport=None):
    """Owned transport: no environment proxy, redirects, profile auth or retries.

    ``transport`` supports offline qualification with the SDK's MockTransport.
    It is never sourced from panel input or a project rules document.
    """
    import anthropic
    if not isinstance(api_key, str) or not api_key.strip():
        raise ModelAccessDenied("Configure an API key before starting background model work.")
    http = sdk_http_module()
    fixed = {}
    def before_send(request):
        client = fixed["client"]()
        state = _sdk_state(client)
        expected = _SDK_REQUEST.get()
        try:
            payload = json.loads(request.content)
            spec = ConnectionSpec("claude", payload["model"], str(request.url))
        except (ValueError, TypeError, KeyError):
            raise ModelAccessDenied("The SDK request did not name a supported model destination.") from None
        if (not expected or expected["client"] is not client or spec != expected["spec"]
                or spec.endpoint != state["endpoint"] or request.method != "POST"
                or expected["sent"]
                or request.headers.get("host", "").lower() != request.url.netloc.decode("ascii").lower()
                or _key_digest(request.headers.get("x-api-key")) != state["key"]
                or request.headers.get("authorization")):
            raise ModelAccessDenied("The model request changed after permission was checked.")
        require_access(spec, key=client.api_key, scope=expected["scope"])
        expected["sent"] = True
    http_client = http.Client(trust_env=False, follow_redirects=False, transport=transport,
                              timeout=60.0, event_hooks={"request": [before_send]})
    try:
        selected_base = base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
        validate_endpoint(selected_base)
        client = anthropic.Anthropic(api_key=api_key.strip(), base_url=selected_base,
                                      http_client=http_client, max_retries=0)
        endpoint = str(client._prepare_url("/v1/messages"))
        validate_endpoint(endpoint)
        fixed["client"] = weakref.ref(client)
        _SDK_CLIENTS[client] = {"http": http_client, "transport": http_client._transport,
            "hook": before_send, "base": str(client.base_url), "endpoint": endpoint,
            "key": _key_digest(client.api_key)}
        _sdk_state(client)
        return client
    except BaseException:
        http_client.close()
        raise


def stream_spec(provider):
    captured = _STREAM_REQUEST.get()
    if captured is None or captured["provider"] is not provider:
        raise ModelAccessDenied("A guarded model request is required.")
    return captured["spec"]


def before_stream_send(provider, key, payload, endpoint):
    """Last check, after payload/SSL/connection preparation, before transmission."""
    from urllib.parse import quote
    spec = stream_spec(provider)
    captured = _STREAM_REQUEST.get()
    if captured["abort"]():
        raise ModelAccessDenied("This task was stopped before sending.")
    if _key_digest(key) != captured["key"]:
        raise ModelAccessDenied("The model key changed after permission was checked.")
    expected = spec.endpoint
    if spec.provider == "gemini":
        expected += "/%s:streamGenerateContent?alt=sse" % quote(spec.model, safe="")
    else:
        try:
            if json.loads(payload).get("model") != spec.model:
                raise ValueError("Changed model")
        except (ValueError, TypeError, AttributeError):
            raise ModelAccessDenied("The model request changed after permission was checked.") from None
    if endpoint != expected:
        raise ModelAccessDenied("The model request destination changed after permission was checked.")
    return require_access(spec, key=key, facts=captured["facts"],
                          grant=captured["grant"], scope=captured["scope"])


def guarded_stream(function):
    """Guard the concrete adapter, including callers outside the panel."""
    @wraps(function)
    def stream(provider, **kwargs):
        from synapse.panel.connections import provider_spec, check_connection
        provider.last_usage = None
        provider.reported_model = None
        provider._stream_complete = False
        spec = provider_spec(provider)
        grant = getattr(provider, "_model_grant", None)
        scope = getattr(provider, "_model_scope", None)
        facts = getattr(provider, "_connection_facts", None)
        key = kwargs.get("api_key")
        with request_scope(scope) as chosen:
            record = _attempt_record(spec, lane="stream", facts=facts, scope=chosen)
            token = None
            result = "failed"
            try:
                _check_scope(chosen, load_policy())
                if kwargs["should_abort"]():
                    raise ModelAccessDenied("This task was stopped before sending.")
                # Recheck local provenance on the worker thread before each payload.
                # Unknown services never become local just because their URL loops back.
                if ((isinstance(grant, TaskGrant) and grant.local)
                        or (isinstance(facts, ConnectionFacts) and facts.location == "Local")):
                    checked = check_connection(spec, key)
                    facts = checked.facts if checked.ok else None
                    provider._connection_facts = facts
                record["location"] = facts.location if isinstance(facts, ConnectionFacts) and facts.spec == spec else "Unverified"
                record["permission"] = require_access(spec, key=key, facts=facts, grant=grant, scope=chosen)
                token = _STREAM_REQUEST.set({"provider": provider, "spec": spec, "grant": grant,
                    "scope": chosen, "facts": facts, "key": _key_digest(key), "abort": kwargs["should_abort"]})
                requirements = getattr(provider, "_automatic_requirements", None)
                if requirements is not None:
                    from synapse.panel.model_routing import required_capabilities
                    required = frozenset(requirements) | required_capabilities(tools=kwargs.get("tools"), messages=kwargs.get("messages"))
                    if (not isinstance(facts, ConnectionFacts) or facts.spec != spec or not facts.fresh()
                            or facts.capabilities is None or not required.issubset(facts.capabilities)):
                        raise ModelAccessDenied("This model's checked abilities no longer cover the task. Choose a model and start a new task.")
                # Stop and scope changes can occur while the metadata check runs.
                if kwargs["should_abort"]():
                    raise ModelAccessDenied("This task was stopped before sending.")
                require_access(spec, key=key, facts=facts, grant=grant, scope=chosen)
                answer = function(provider, **kwargs)
                if not provider._stream_complete and not kwargs["should_abort"]():
                    result = "incomplete"
                    raise ModelRequestFailed("The model response ended before completion. Any reported token usage has been kept.")
                result = "cancelled" if kwargs["should_abort"]() else "completed"
                return answer
            except ModelAccessDenied as exc:
                result = "blocked"
                record["reason"] = str(exc)
                raise
            except ModelRequestFailed:
                raise
            except Exception:
                raise ModelRequestFailed("The model request failed. Check the connection, model access, and service limits.") from None
            finally:
                if token is not None:
                    _STREAM_REQUEST.reset(token)
                finish_attempt(record, result=result, reported_model=provider.reported_model, usage=provider.last_usage)
    return stream
