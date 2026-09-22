"""Single fenced product-side Jev transport, using the documented v1 HTTP API.

No SDK dependency, redirects, retries, environment-selected endpoint or model
fallback. One process-wide transport slot remains held until the actual request
ends, even after the caller's .8 second wait expires. Shadow policy belongs to
the caller. Model permissions are independent of the generation model's grant.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import ssl
import sys
import threading
import time
import types
from concurrent.futures import Future, TimeoutError as _FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path

TIMEOUT_S = .8
MODES = frozenset({"shadow", "on"})
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
MAX_RESPONSE_BYTES = 65536
_DISABLED_VALUES = frozenset({"", "off", "0", "false"})
_MODEL_ID = re.compile(r"jev-(?:latest|preview|[0-9]+\.[0-9]+(?:\.[0-9]+)?)\Z")
_REPORTED_MODEL = re.compile(r"jev-[0-9]+\.[0-9]+\.[0-9]+\Z")
# Module reload must not create capacity beside an abandoned live request.
_candidate = types.ModuleType("_synapse_jev_transport_v1")
_candidate.slot = threading.BoundedSemaphore(1)
_CAPACITY = sys.modules.setdefault(_candidate.__name__, _candidate)
del _candidate


def enabled(*, opt_in=False):
    """Explicit Off is a kill switch; a saved Measure routing pick can opt in."""
    value = os.environ.get("SYNAPSE_JEV")
    return bool(opt_in) if value is None else value.strip().lower() not in _DISABLED_VALUES


def resolve_key():
    """Environment first, then Windows user registry. Never log the value."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
                value, _ = winreg.QueryValueEx(handle, "TYPESAFE_API_KEY")
                return str(value or "").strip() or None
        except Exception:
            pass
    return None


def connection_spec(model=DEFAULT_MODEL):
    from synapse.panel.connections import ConnectionSpec
    return ConnectionSpec("typesafe", model, ENDPOINT)


def ledger_path(lane):
    root = os.environ.get("SYNAPSE_JEV_LEDGER_DIR", "").strip()
    base = Path(root) if root else Path.home() / ".synapse/jev"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(lane)) or "default"
    return base / (safe + ".jsonl")


def _ledger(lane, row):
    try:
        path = ledger_path(lane)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    except Exception:
        pass


def _on_houdini_main_thread():
    hou = sys.modules.get("hou")
    if hou is None or threading.current_thread() is not threading.main_thread():
        return False
    try:
        return bool(hou.isUIAvailable())
    except Exception:
        return True


def _get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _answers_to_dict(response):
    """Normalize current HTTP and SDK aliases, including Noul's ``noul`` field."""
    answers = _get(response, "answers")
    if answers is None:
        answers = {}
        for group, kind in (("choices", "choice"), ("scores", "score"), ("nouls", "noul")):
            for qid, value in (_get(response, group, {}) or {}).items():
                fields = {"choice": ("choice", "probabilities", "confidence"),
                          "score": ("score", "probabilities", "confidence", "legend"),
                          "noul": ("noul",)}[kind]
                answers[qid] = {"type": kind, **{field: _get(value, field) for field in fields}}
    if not isinstance(answers, dict):
        return {}
    return {"answers": answers, "model": _get(response, "model"), "usage": _get(response, "usage")}


def _number(value, minimum=0., maximum=1.):
    return type(value) in (float, int) and math.isfinite(value) and minimum <= value <= maximum


def _model_id(value):
    return isinstance(value, str) and len(value) <= 64 and bool(_MODEL_ID.fullmatch(value))


def _validated(response, questions):
    """Only typed fields survive. Never ledger arbitrary service text or bodies."""
    normalized = _answers_to_dict(response)
    source = normalized.get("answers")
    if not isinstance(source, dict) or set(source) != set(questions):
        raise ValueError("answer_set")
    answers = {}
    for qid, question in questions.items():
        value = source[qid]
        kind = question["type"]
        if not isinstance(value, dict) or value.get("type") != kind:
            raise ValueError("answer_type")
        if kind == "noul":
            if not _number(value.get("noul")):
                raise ValueError("noul")
            answers[qid] = {"type": kind, "noul": value["noul"]}
            continue
        options = question["criteria"] if kind == "choice" else {
            str(i): text for i, text in enumerate(question["criteria"])}
        probabilities = value.get("probabilities")
        if (not isinstance(probabilities, dict) or set(probabilities) != set(options)
                or not all(_number(p) for p in probabilities.values())
                or not math.isclose(sum(probabilities.values()), 1., abs_tol=.001)
                or not _number(value.get("confidence"))):
            raise ValueError("distribution")
        item = {"type": kind, "probabilities": dict(probabilities), "confidence": value["confidence"]}
        if kind == "choice":
            choice = value.get("choice")
            if choice not in options or probabilities[choice] != max(probabilities.values()):
                raise ValueError("choice")
            item["choice"] = choice
        else:
            if not _number(value.get("score"), maximum=len(options) - 1):
                raise ValueError("score")
            expected = sum(int(level) * p for level, p in probabilities.items())
            # Match the API's weighted value, allowing the same rounded
            # distribution tolerance scaled to the rubric's numeric range.
            if not math.isclose(value["score"], expected, rel_tol=0.,
                                abs_tol=.001 * (len(options) - 1)):
                raise ValueError("weighted_score")
            item["score"] = value["score"]
        answers[qid] = item
    reported = normalized.get("model")
    if (not isinstance(reported, str) or len(reported) > 64
            or not _REPORTED_MODEL.fullmatch(reported)):
        raise ValueError("reported_model")
    usage = normalized.get("usage")
    usage = {key: n for key, n in (usage.items() if isinstance(usage, dict) else ())
             if key in ("input_tokens", "output_tokens") and type(n) is int and n >= 0}
    return {"answers": answers, "model": reported, "usage": usage or None}


def _questions_valid(questions):
    if not isinstance(questions, dict) or not 0 < len(questions) <= 32:
        return False
    for qid, value in questions.items():
        if (not isinstance(qid, str) or not qid or len(qid) > 128
                or not isinstance(value, dict)
                or not isinstance(value.get("instructions"), (str, dict, list))):
            return False
        kind, criteria = value.get("type"), value.get("criteria")
        if kind == "choice" and (not isinstance(criteria, dict) or not 1 < len(criteria) <= 255):
            return False
        if kind == "score" and (not isinstance(criteria, list) or not 2 <= len(criteria) <= 10):
            return False
        if kind not in ("choice", "score", "noul"):
            return False
    return True


class _Busy(Exception):
    pass


def _run_on_daemon(function, timeout):
    if not _CAPACITY.slot.acquire(blocking=False):
        raise _Busy()
    future = Future()

    def run():
        try:
            future.set_result(function())
        except BaseException as exc:
            future.set_exception(exc)
        finally:
            _CAPACITY.slot.release()

    try:
        threading.Thread(target=run, name="synapse-jev-judge", daemon=True).start()
    except BaseException:
        _CAPACITY.slot.release()
        raise
    return future.result(timeout=timeout)


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate_response_field")
        out[key] = value
    return out


def _post(payload, key, before_send):
    """One verified-TLS POST. No redirect/retry path; bounded response bytes."""
    connection = http.client.HTTPSConnection("api.typesafe.ai", timeout=TIMEOUT_S,
                                             context=ssl.create_default_context())
    try:
        before_send()
        connection.request("POST", "/v1/systemone", body=payload,
                           headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError("http_" + str(response.status))
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("response_too_large")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite")))
    finally:
        connection.close()


def judge(state, questions, *, lane, mode="shadow", model=None, scope=None,
          grant=None, should_abort=None, opt_in=False, receipt=None):
    """Typed answers or None. Permission, cancellation and capacity fail closed.

    ``receipt`` gets input-free evidence before return; a late transport never
    mutates it. Explicitly pass the scope captured when the task was accepted.
    """
    base = {"ts": datetime.now(timezone.utc).isoformat(), "lane": lane, "mode": mode}
    key = None

    def redact(value):
        # Typed answers can still contain caller-supplied labels. Never persist
        # the resolved credential, even if an upstream service echoes it.
        if isinstance(value, str):
            return value.replace(key, "[redacted]") if key else value
        if isinstance(value, dict):
            return {redact(k): redact(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [redact(item) for item in value]
        return value

    def finish(result, reason=None, **fields):
        row = {**base, "result": result, **fields}
        if reason:
            row["reason"] = reason
        row = redact(row)
        if isinstance(receipt, dict):
            receipt.update(row)
        _ledger(redact(lane), row)

    try:
        if not enabled(opt_in=opt_in):
            if isinstance(receipt, dict):
                receipt.update(result="disabled", reason="off")
            return None  # No I/O, including no ledger.
        if mode not in MODES or (model is not None and not _model_id(model)) or not _questions_valid(questions):
            finish("fallback", "invalid_request")
            return None
        base["question_ids"] = sorted(questions)
        if _on_houdini_main_thread():
            finish("main_thread_refused")
            return None
        key = resolve_key()
        if not key:
            finish("fallback", "no_key")
            return None
        from synapse import model_access as access
        accepted_scope = scope if scope is not None else access.capture_scope()
        base["task_id"] = accepted_scope.task_id
        spec = connection_spec(model if model is not None else DEFAULT_MODEL)
        if key in spec.model:
            finish("fallback", "invalid_request")
            return None
        base.update(requested_model=spec.model, endpoint=spec.endpoint)
        payload = json.dumps({"state": state, "questions": questions, "model": spec.model},
                             sort_keys=True, allow_nan=False).encode("utf-8")
        if len(payload) > 131072:
            finish("fallback", "request_too_large")
            return None
        base["request_hash"] = hashlib.sha256(payload).hexdigest()[:16]
        abort = should_abort or (lambda: False)

        def call():
            task_grant = grant
            record = None
            result = "failed"
            answers = None
            try:
                if abort():
                    raise access.ModelAccessDenied("Task stopped")
                if task_grant is None:
                    access.require_access(spec, key=key, scope=accepted_scope)
                    task_grant = access.issue_task_grant(spec, key=key, approved=True, scope=accepted_scope)

                def before_send():
                    nonlocal record
                    if abort() or not enabled(opt_in=opt_in):
                        raise access.ModelAccessDenied("Task stopped")
                    record = access.begin_attempt(spec, lane="jev_" + redact(lane), key=key,
                                                  grant=task_grant, scope=accepted_scope)

                checked = _validated(_post(payload, key, before_send), questions)
                if checked != redact(checked):
                    raise ValueError("credential_echo")
                answers = checked
                if abort() or not enabled(opt_in=opt_in):
                    raise access.ModelAccessDenied("Task stopped")
                access.require_access(spec, key=key, grant=task_grant, scope=accepted_scope)
                result = "completed"
                return answers
            except access.ModelAccessDenied:
                result = "blocked"
                raise
            finally:
                if record is not None:
                    access.finish_attempt(record, result=result,
                                          reported_model=answers.get("model") if answers else None,
                                          usage=answers.get("usage") if answers else None)
                if task_grant is not None and task_grant is not grant:
                    task_grant.release()

        started = time.perf_counter()
        try:
            answers = _run_on_daemon(call, TIMEOUT_S)
        except _Busy:
            finish("fallback", "busy")
            return None
        except (TimeoutError, _FuturesTimeout):
            finish("timeout", "deadline", latency_ms=round((time.perf_counter() - started) * 1000, 3))
            return None
        except access.ModelAccessDenied:
            finish("fallback", "permission_or_scope", latency_ms=round((time.perf_counter() - started) * 1000, 3))
            return None
        except Exception as exc:
            finish("fallback", type(exc).__name__, latency_ms=round((time.perf_counter() - started) * 1000, 3))
            return None
        finish("ok", latency_ms=round((time.perf_counter() - started) * 1000, 3),
               reported_model=answers["model"], usage=answers["usage"], answers=answers["answers"])
        return answers
    except Exception:
        finish("fallback", "invalid_request")
        return None
