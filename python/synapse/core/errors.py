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

Circuit breaker: only SynapseServiceError trips it.
Handler.handle(): SynapseUserError -> success=False (don't trip CB).
                  SynapseServiceError -> success=False + trip CB.
"""


class SynapseError(Exception):
    """Base class for all Synapse errors."""


class SynapseUserError(SynapseError):
    """User-caused errors (bad input, missing resources).

    These do NOT trip the circuit breaker.
    """


class SynapseServiceError(SynapseError):
    """Service-level errors (Houdini down, crashes, timeouts).

    These DO trip the circuit breaker.
    """


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


class ExecutionError(SynapseServiceError):
    """Python/VEX execution failed inside Houdini."""

    def __init__(self, message: str, partial_result=None):
        self.partial_result = partial_result
        super().__init__(message)


class HoudiniUnavailableError(SynapseServiceError):
    """Houdini is not reachable or hou module is not available."""

    def __init__(self, message: str = ""):
        if not message:
            message = (
                "Houdini isn't reachable right now -- make sure it's running "
                "and Synapse is started from the Python Panel"
            )
        super().__init__(message)
