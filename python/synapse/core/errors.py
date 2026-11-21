"""
Synapse Exception Hierarchy

Two-branch tree:
  SynapseError (base)
  +-- SynapseUserError     (bad input, missing node, bad parm name)
  |   +-- NodeNotFoundError
  |   +-- ParameterError
  |   +-- ValidationError
  +-- SynapseServiceError  (Houdini down, execution crash, timeout)
      +-- ExecutionError
      +-- HoudiniUnavailableError
      +-- OperationTimeoutError
      +-- OperationFailedError

Circuit breaker: only SynapseServiceError trips it.
Handler.handle(): SynapseUserError -> success=False (don't trip CB).
                  SynapseServiceError -> success=False + trip CB.
"""


class SynapseError(Exception):
    """Base class for all Synapse errors."""


class SynapseUserError(SynapseError):
    """User-caused errors (bad input, missing resources).

    These do NOT trip the circuit breaker.

    ``suggestion`` carries the remediation the raiser already knows -- e.g. the
    LOP catalog's ``known_absent`` entry for 'grid' is "use the plane LOP".
    Several call sites (handlers_solaris_graph.py, handlers_solaris_compose.py)
    were already passing it; without an ``__init__`` accepting it, every one of
    those raises died as ``TypeError: takes no keyword arguments`` inside a bare
    ``except``, so the designed diagnostic surfaced as internal Python noise.
    Positional use (``SynapseUserError("msg")``) is unchanged.
    """

    def __init__(self, *args, suggestion: str | None = None):
        super().__init__(*args)
        self.suggestion = suggestion

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base} -- {self.suggestion}" if self.suggestion else base


class SynapseServiceError(SynapseError):
    """Service-level errors (Houdini down, crashes, timeouts).

    These DO trip the circuit breaker.

    ``outcome_code`` is what makes that true on the wire (R-015, BRAINSTEM-7):
    ``handlers._failure_receipt_data`` puts the outcome on the failed
    response's data, and every transport classifies a breaker failure by that
    code (``core.outcomes.is_service_failure``) instead of by matching words in
    the error text. A subclass that knows a more specific case overrides it
    (ExecutionAborted -> tool.internal, ExecutionDeadlineExceeded ->
    execution.deadline_exceeded).
    """

    outcome_code = "tool.failed"


class NodeNotFoundError(SynapseUserError):
    """A Houdini node path didn't resolve to an existing node."""

    def __init__(self, node_path: str, suggestion: str = ""):
        self.node_path = node_path
        self.suggestion = suggestion
        msg = f"Couldn't find a node at '{node_path}'"
        if suggestion:
            msg += f" -- did you mean '{suggestion}'?"
        super().__init__(msg)


class ParameterError(SynapseUserError):
    """A parameter name doesn't exist on the target node."""

    def __init__(self, node_path: str, parm_name: str, suggestion: str = ""):
        self.node_path = node_path
        self.parm_name = parm_name
        self.suggestion = suggestion
        msg = f"Couldn't find parameter '{parm_name}' on {node_path}"
        if suggestion:
            msg += f" -- try '{suggestion}' instead"
        super().__init__(msg)


class ValidationError(SynapseUserError):
    """A required field is missing or has an invalid value."""

    def __init__(self, field: str, message: str = ""):
        self.field = field
        msg = f"Missing or invalid field '{field}'"
        if message:
            msg += f": {message}"
        super().__init__(msg)


class HistoryScopeRefused(SynapseUserError):
    """An agent history call would step over work SYNAPSE did not record.

    R-012: the undo/redo tools read ``hou.undos`` labels and refuse unless the
    next step is a SYNAPSE group recorded in this session. The rule stops the
    call BEFORE dispatch, so the outcome is ``policy.safety_guard`` (refused,
    nothing ran) and it never trips the circuit breaker.
    """

    outcome_code = "policy.safety_guard"


class ExecutionError(SynapseServiceError):
    """Python/VEX execution failed inside Houdini."""

    def __init__(self, message: str, partial_result=None):
        self.partial_result = partial_result
        super().__init__(message)


class ExecutionAborted(ExecutionError):
    """execute_python's script raised SystemExit/KeyboardInterrupt/GeneratorExit.

    Raised at the exec boundary (BRAINSTEM-3), where provenance is known: the
    payload raised these inside its own frame, so they are that call's failure,
    not a signal to stop the server. The transport-wide re-raise in
    ``SynapseHandler.handle`` still covers genuine shutdown raised outside the
    exec frame. ``outcome_code`` is read by ``core.outcomes.for_exception`` and
    put on the failed response's data by ``handlers._failure_receipt_data``.
    """

    outcome_code = "tool.internal"


class ExecutionDeadlineExceeded(ExecutionError):
    """A main-thread deadline stopped execute_python/execute_vex (BRAINSTEM-4).

    The script ran until its budget expired, so the scene may be partial; the
    outcome says exactly that and tells the caller to check the scene.
    """

    outcome_code = "execution.deadline_exceeded"


class HoudiniUnavailableError(SynapseServiceError):
    """Houdini is not reachable or hou module is not available."""

    def __init__(self, message: str = ""):
        if not message:
            message = (
                "Houdini isn't reachable right now -- make sure it's running "
                "and Synapse is started from the Python Panel"
            )
        super().__init__(message)


class OperationTimeoutError(SynapseServiceError):
    """A Houdini operation exceeded its time limit.

    Trips the circuit breaker — repeated timeouts indicate Houdini is stalled.
    """

    def __init__(self, operation: str = "", timeout_seconds: float = 0):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        msg = "Operation timed out"
        if operation:
            msg = f"Operation '{operation}' timed out"
        if timeout_seconds > 0:
            msg += f" after {timeout_seconds:.0f}s"
        msg += " -- the scene may be unresponsive or a heavy cook is blocking"
        super().__init__(msg)


class OperationFailedError(SynapseServiceError):
    """A Houdini operation (render, cook, etc.) failed at runtime.

    Distinguished from ExecutionError (code bugs) — this is an operational
    failure (render crash, cook error, disk full, GPU OOM).
    """

    def __init__(self, operation: str, message: str = "", node_path: str = ""):
        self.operation = operation
        self.node_path = node_path
        msg = f"Operation '{operation}' failed"
        if node_path:
            msg += f" on {node_path}"
        if message:
            msg += f": {message}"
        super().__init__(msg)
