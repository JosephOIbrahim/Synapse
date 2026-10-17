"""Recognise a native (PyO3) panic without catching anything else.

PANIC-FENCE-CONSTRUCTION. PyO3 turns a Rust panic that reaches the Python
boundary into ``pyo3_runtime.PanicException``, and that class derives from
``BaseException``, not ``Exception``. Every ``except Exception`` fallback arm
lets it straight through. In ``SynapseMemory._make_store`` that meant a panic
while building the Moneta store escaped the jsonl fallback: nothing was served,
``backend_fallback()`` recorded nothing, ``_global_synapse`` was never
published, and every later ``get_synapse_memory()`` built the store again and
panicked again.

A fallback arm that should serve that case catches ``BaseException`` and
re-raises unless :func:`is_native_panic` says yes. The test is narrow on
purpose. The exception's class, or a class in its MRO, must be NAMED
``PanicException`` and come from ``pyo3_runtime`` (or carry no module at all).
Interpreter control flow -- ``KeyboardInterrupt``, ``SystemExit``,
``GeneratorExit``, ``asyncio.CancelledError`` -- never matches, whatever it is
called. The name is matched rather than a class object because there is no
``pyo3_runtime`` module to import the class from: PyO3 creates it inside the
extension.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

#: The module PyO3 gives its panic type, and the type's name. A class called
#: PanicException from any other module is somebody else's exception.
PYO3_PANIC_MODULE = "pyo3_runtime"
PYO3_PANIC_NAME = "PanicException"

#: Interpreter control flow. Never a native panic, whatever the class is named.
_NEVER_A_PANIC = (KeyboardInterrupt, SystemExit, GeneratorExit)


def _cancelled_error():
    """asyncio's ``CancelledError``, or None when asyncio is not loaded.

    Looked up, not imported. An instance cannot exist unless
    ``asyncio.exceptions`` was already imported, so a missing module means
    there is nothing to exclude, and a check that runs inside an except arm
    has no reason to import asyncio to learn that.
    """
    module = sys.modules.get("asyncio.exceptions")
    cancelled = getattr(module, "CancelledError", None)
    return cancelled if isinstance(cancelled, type) else None


def is_native_panic(exc: object) -> bool:
    """True only for a PyO3 ``PanicException`` instance. Never raises.

    False for every ``Exception`` (the ordinary fallback arms already serve
    those), for interpreter control flow, for a class named PanicException
    that some other module defined, and for anything that is not an exception
    instance. A check that cannot complete answers False, so the caller
    re-raises what it caught rather than serving something it could not
    identify.
    """
    try:
        cls = type(exc)
        if not issubclass(cls, BaseException) or issubclass(cls, Exception):
            return False
        if issubclass(cls, _NEVER_A_PANIC):
            return False
        cancelled = _cancelled_error()
        if cancelled is not None and issubclass(cls, cancelled):
            return False
        for klass in cls.__mro__:
            if klass.__name__ != PYO3_PANIC_NAME:
                continue
            module = getattr(klass, "__module__", None)
            if module is None or module == "" or module == PYO3_PANIC_MODULE:
                return True
        return False
    except Exception as err:  # noqa: BLE001 -- runs inside except arms; must never raise
        logger.debug(
            "is_native_panic could not classify an exception (%s); treating it "
            "as not a native panic", type(err).__name__,
        )
        return False
