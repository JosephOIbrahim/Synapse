"""Fenced Jev adapter -- invariant 5 of the Jev README (amended 2026-09-21).

``judge(state, questions, *, lane, mode="shadow")`` asks the TypeSafe System One model
(Jev) a set of typed questions about ``state`` and returns the raw answers as a dict,
or ``None``. It has NO callers in the product yet; it exists so that a product-path
judgment, if one ever ships, goes through one fenced door. The adapter never decides
anything -- policy code that consumes the answers is responsible for the decision.

The six conditions, each pinned by ``tests/test_jev_adapter.py``:

(a) **Hard timeout.** The network call runs on a daemon thread; ``future.result(
    timeout=TIMEOUT_S)`` (0.8 s wall clock) bounds the wait. Timeout returns ``None``.
    Every exception on every path returns ``None``. ``judge`` never raises.
(b) **``SYNAPSE_JEV`` env.** Unset, or ``off``/``0``/``false``, means disabled -- the
    default in-product is OFF. Disabled short-circuits before any I/O, any ledger
    write, and before the SDK is imported.
(c) **Key resolution.** ``TYPESAFE_API_KEY`` is resolved once per call through
    :func:`resolve_key` (env first, then the Windows user-scope registry), modelled on
    the panel providers' ``resolve_key``. The key is never written to any log or
    ledger row.
(d) **Ledger.** One JSONL row per call under ``~/.synapse/jev/<lane>.jsonl``
    (directories created; ``SYNAPSE_JEV_LEDGER_DIR`` overrides the root for tests).
    Rows carry request hash, question ids, raw answers, latency ms, and ``mode``.
    Never ``synapse.log``; never the build-time ledger directory.
(e) **Main-thread refusal.** If ``hou`` is loaded, ``hou.isUIAvailable()`` is true,
    and the caller is the main thread, return ``None`` and ledger
    ``main_thread_refused`` without calling out -- a blocking wait on the GUI thread
    is the known Houdini freeze class.
(f) **Shadow-first.** ``mode`` defaults to ``"shadow"`` (``{"shadow", "on"}``) and is
    recorded on every row. The adapter returns answers or ``None``; it decides nothing.

Question spec shape (mirrors the build-time question builder)::

    {qid: {"type": "choice" | "noul" | "score", "instructions": str, "criteria": ...}}

The SDK (``typesafe_sdk``) is imported lazily inside the call, never at module import.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import Future
from concurrent.futures import TimeoutError as _FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

__all__ = ["judge", "resolve_key", "ledger_path", "enabled", "TIMEOUT_S", "MODES"]

TIMEOUT_S: float = 0.8
MODES = frozenset({"shadow", "on"})
_ENV_FLAG = "SYNAPSE_JEV"
_ENV_KEY = "TYPESAFE_API_KEY"
_ENV_LEDGER_DIR = "SYNAPSE_JEV_LEDGER_DIR"
_DISABLED_VALUES = frozenset({"", "off", "0", "false"})
_DEFAULT_MODEL = "jev-latest"


# --------------------------------------------------------------------------- (b)
def enabled() -> bool:
    """True only when ``SYNAPSE_JEV`` is set to something other than off/0/false."""
    return os.environ.get(_ENV_FLAG, "").strip().lower() not in _DISABLED_VALUES


# --------------------------------------------------------------------------- (c)
def resolve_key() -> Optional[str]:
    """``TYPESAFE_API_KEY``: env first, then the Windows user-scope registry.

    ``None`` means unconfigured. Never raises. The value must never be logged.
    """
    k = os.environ.get(_ENV_KEY, "").strip()
    if k:
        return k
    if sys.platform == "win32":
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as hk:
                v, _ = winreg.QueryValueEx(hk, _ENV_KEY)
                v = str(v or "").strip()
                if v:
                    return v
        except Exception:  # noqa: BLE001 - registry absent/unreadable is "unconfigured"
            pass
    return None


# --------------------------------------------------------------------------- (d)
def ledger_path(lane: str) -> Path:
    root = os.environ.get(_ENV_LEDGER_DIR, "").strip()
    base = Path(root) if root else Path.home() / ".synapse" / "jev"
    safe = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in str(lane)) or "default"
    return base / f"{safe}.jsonl"


def _ledger(lane: str, row: dict) -> None:
    """Append one row. Swallows every error: the ledger is evidence, not a gate."""
    try:
        p = ledger_path(lane)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- (e)
def _on_houdini_main_thread() -> bool:
    hou = sys.modules.get("hou")
    if hou is None:
        return False
    try:
        ui = bool(hou.isUIAvailable())
    except Exception:  # noqa: BLE001
        return False
    return ui and threading.current_thread() is threading.main_thread()


# --------------------------------------------------------------------------- SDK seam
def _load_sdk():
    """Lazy SDK import. Returns ``(TypeSafeClient, Choice, Score, Noul)``.

    Kept as a module-level seam so tests substitute fakes without any network.
    """
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient  # type: ignore

    return TypeSafeClient, Choice, Score, Noul


def _build_questions(spec: dict, Choice, Score, Noul) -> dict:
    out = {}
    for qid, q in spec.items():
        t = q["type"]
        if t == "choice":
            out[qid] = Choice(instructions=q["instructions"], criteria=q["criteria"])
        elif t == "score":
            out[qid] = Score(instructions=q["instructions"], criteria=q["criteria"])
        elif t == "noul":
            out[qid] = Noul(instructions=q["instructions"])
        else:
            raise ValueError(f"unknown question type {t!r} for {qid}")
    return out


def _get(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _answers_to_dict(resp: Any) -> dict:
    """Flatten an SDK response into plain JSON. Unknown shapes are stringified, not dropped."""
    if isinstance(resp, dict):
        return resp
    out: dict = {"choices": {}, "scores": {}, "nouls": {}}
    for qid, a in (_get(resp, "choices") or {}).items():
        probs = _get(a, "probabilities") or {}
        out["choices"][qid] = {
            "probabilities": dict(probs) if probs else {},
            "confidence": _get(a, "confidence"),
        }
    for qid, a in (_get(resp, "scores") or {}).items():
        out["scores"][qid] = {"score": _get(a, "score"), "confidence": _get(a, "confidence")}
    for qid, a in (_get(resp, "nouls") or {}).items():
        out["nouls"][qid] = {"probability": _get(a, "probability"), "confidence": _get(a, "confidence")}
    if not any(out.values()):
        out["raw"] = repr(resp)[:2000]
    return out


def _request_hash(state: Any, questions: dict, model: str) -> str:
    payload = json.dumps({"state": state, "questions": questions, "model": model}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _run_on_daemon(fn: Callable[[], Any], timeout: float) -> Any:
    """Run ``fn`` on a daemon thread; wait at most ``timeout`` seconds (wall clock)."""
    fut: Future = Future()

    def _target():
        try:
            fut.set_result(fn())
        except BaseException as e:  # noqa: BLE001 - surfaced via future, never lost
            fut.set_exception(e)

    threading.Thread(target=_target, name="synapse-jev-judge", daemon=True).start()
    return fut.result(timeout=timeout)  # raises TimeoutError past the bound


# --------------------------------------------------------------------------- entry
def judge(
    state: Any,
    questions: dict,
    *,
    lane: str,
    mode: str = "shadow",
    model: Optional[str] = None,
) -> Optional[dict]:
    """Ask Jev; return raw answers as a dict, or ``None``. Never raises. Decides nothing.

    See the module docstring for conditions (a)-(f).
    """
    try:
        # (b) disabled: before any I/O, before any SDK import, before the ledger.
        if not enabled():
            return None

        base = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lane": lane,
            "mode": mode,  # (f) recorded on every row
            "question_ids": sorted(questions.keys()) if isinstance(questions, dict) else [],
            "thread": threading.current_thread().name,
        }

        if mode not in MODES:
            _ledger(lane, {**base, "result": "fallback", "reason": f"invalid mode {mode!r}"})
            return None

        # (e) never block the Houdini GUI thread.
        if _on_houdini_main_thread():
            _ledger(lane, {**base, "result": "main_thread_refused"})
            return None

        # (c) resolved once; the value never reaches a row.
        key = resolve_key()
        if not key:
            _ledger(lane, {**base, "result": "fallback", "reason": "no_key"})
            return None

        model_name = model or _DEFAULT_MODEL
        base["request_hash"] = _request_hash(state, questions, model_name)
        base["model"] = model_name

        def _call():
            TypeSafeClient, Choice, Score, Noul = _load_sdk()
            qs = _build_questions(questions, Choice, Score, Noul)
            with TypeSafeClient(api_key=key, timeout=TIMEOUT_S) as client:
                try:
                    resp = client.system_one(state=state, questions=qs, model=model_name)
                except TypeError:  # older SDK: model is set on the client, not the call
                    resp = client.system_one(state=state, questions=qs)
            return _answers_to_dict(resp)

        t0 = time.perf_counter()
        try:
            answers = _run_on_daemon(_call, TIMEOUT_S)  # (a)
        except (TimeoutError, _FuturesTimeout):
            _ledger(lane, {**base, "result": "timeout", "latency_ms": int((time.perf_counter() - t0) * 1000)})
            return None
        except Exception as e:  # noqa: BLE001 - fail closed on anything
            reason = f"{type(e).__name__}: {e}"[:400].replace(key, "<redacted>")
            _ledger(lane, {**base, "result": "fallback",
                           "latency_ms": int((time.perf_counter() - t0) * 1000), "reason": reason})
            return None

        _ledger(lane, {**base, "result": "ok", "latency_ms": int((time.perf_counter() - t0) * 1000),
                       "answers": answers})
        return answers
    except Exception:  # noqa: BLE001 - (a): no code path raises out of judge()
        return None
