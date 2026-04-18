"""SYNAPSE 2.0 Inspector — Exception hierarchy.

Custom exceptions let consumers catch specific failure modes instead of
inspecting string messages:

    from synapse.inspector import (
        synapse_inspect_stage,
        InspectorError,
        StageNotFoundError,
        TransportTimeoutError,
        HoudiniExtractionError,
        SchemaVersionMismatchError,
    )

    try:
        ast = synapse_inspect_stage()
    except StageNotFoundError as e:
        log.warning("Context unreachable: %s", e.path)
    except TransportTimeoutError:
        log.error("Houdini unresponsive")
    except HoudiniExtractionError as e:
        log.error("Houdini extraction failed: %s", e, extra={"tb": e.traceback})
    except SchemaVersionMismatchError as e:
        log.critical("Schema drift: expected %s got %s", e.expected, e.received)
    except InspectorError:
        log.exception("Inspector failed")

All exception classes store structured attributes (not just messages) so
downstream consumers can route on typed data.
"""

from __future__ import annotations

from typing import Optional


class InspectorError(Exception):
    """Base class for all Inspector failures.

    Catch this to handle any Inspector-originated error.
    """


class TransportNotConfiguredError(InspectorError):
    """The transport function has not been registered.

    Fix: call ``synapse.inspector.configure_transport(fn)`` at application
    startup, or pass ``execute_python_fn`` explicitly per call.
    """


class TransportError(InspectorError):
    """WebSocket transport layer failed.

    The message either never reached Houdini or the response never came
    back. Distinct from HoudiniExtractionError, which means Houdini
    received the message, executed it, and reported a failure itself.

    Attributes:
        underlying: The original transport exception, if available.
    """

    def __init__(self, message: str, *, underlying: Optional[BaseException] = None):
        super().__init__(message)
        self.underlying = underlying


class TransportTimeoutError(TransportError):
    """Transport operation exceeded the timeout."""


class InvalidTargetPathError(InspectorError):
    """Target path failed validation before being sent to Houdini.

    Attributes:
        target_path: The offending value.
    """

    def __init__(self, message: str, *, target_path: object = None):
        super().__init__(message)
        self.target_path = target_path


class StageNotFoundError(InspectorError):
    """The target Houdini context path doesn't exist.

    Usually means Houdini is running but the context name is wrong, or
    Houdini is between scene loads and the context hasn't been created yet.

    Attributes:
        path: The target path that was not found.
    """

    def __init__(self, path: str):
        super().__init__(f"Stage context not found in Houdini: {path!r}")
        self.path = path


class HoudiniExtractionError(InspectorError):
    """The Houdini-side extraction script raised during execution.

    Attributes:
        traceback: The Houdini-side Python traceback, if captured.
        detail: Short detail string from the extraction script.
    """

    def __init__(
        self,
        message: str,
        *,
        detail: Optional[str] = None,
        traceback: Optional[str] = None,
    ):
        super().__init__(message)
        self.detail = detail
        self.traceback = traceback


class SchemaValidationError(InspectorError):
    """Response from Houdini didn't match the expected AST schema.

    Usually means the extraction script was modified without updating the
    Pydantic models, or Houdini API behavior changed between versions.
    """


class SchemaVersionMismatchError(InspectorError):
    """Response schema version is incompatible with this Inspector build.

    Attributes:
        expected: The schema version this Inspector was built for.
        received: The schema version in the response payload.
    """

    def __init__(self, *, expected: str, received: str):
        super().__init__(
            f"Schema version mismatch: expected {expected!r}, "
            f"received {received!r}. Inspector and extraction script are "
            f"out of sync — regenerate the payload or pin matching versions."
        )
        self.expected = expected
        self.received = received
