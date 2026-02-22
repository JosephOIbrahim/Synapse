"""Tests for the Synapse exception hierarchy."""

import sys
import os

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.errors import (
    SynapseError,
    SynapseUserError,
    SynapseServiceError,
    NodeNotFoundError,
    ParameterError,
    ExecutionError,
    HoudiniUnavailableError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Verify the two-branch inheritance tree."""

    def test_base_class_is_exception(self):
        assert issubclass(SynapseError, Exception)

    def test_user_errors_inherit_from_base(self):
        assert issubclass(SynapseUserError, SynapseError)

    def test_service_errors_inherit_from_base(self):
        assert issubclass(SynapseServiceError, SynapseError)

    def test_node_not_found_is_user_error(self):
        assert issubclass(NodeNotFoundError, SynapseUserError)

    def test_parameter_error_is_user_error(self):
        assert issubclass(ParameterError, SynapseUserError)

    def test_validation_error_is_user_error(self):
        assert issubclass(ValidationError, SynapseUserError)

    def test_execution_error_is_service_error(self):
        assert issubclass(ExecutionError, SynapseServiceError)

    def test_houdini_unavailable_is_service_error(self):
        assert issubclass(HoudiniUnavailableError, SynapseServiceError)


class TestErrorMessages:
    """Coaching-tone message conventions."""

    def test_node_not_found_has_path(self):
        err = NodeNotFoundError("/stage/missing_light")
        assert "/stage/missing_light" in str(err)
        assert err.node_path == "/stage/missing_light"

    def test_node_not_found_with_suggestion(self):
        err = NodeNotFoundError("/stage/key", suggestion="key_light")
        assert "key_light" in str(err)

    def test_parameter_error_has_node_and_parm(self):
        err = ParameterError("/stage/light", "intensity")
        assert err.node_path == "/stage/light"
        assert err.parm_name == "intensity"

    def test_parameter_error_with_suggestion(self):
        err = ParameterError("/stage/light", "intensity", suggestion="xn__inputsintensity_i0a")
        assert "xn__inputsintensity_i0a" in str(err)

    def test_houdini_unavailable_default_message(self):
        err = HoudiniUnavailableError()
        msg = str(err)
        assert "Houdini" in msg
        # Coaching tone: not "Error" or "Failed"
        assert "Error" not in msg

    def test_validation_error_preserves_field(self):
        err = ValidationError("code", "Required field missing")
        assert err.field == "code"

    def test_execution_error_preserves_partial(self):
        err = ExecutionError("Script crashed", partial_result="/stage/node1")
        assert err.partial_result == "/stage/node1"


class TestErrorCategorization:
    """Verify errors sort into user vs service correctly."""

    def test_user_errors_not_service(self):
        for cls in (NodeNotFoundError, ParameterError, ValidationError):
            err = cls.__new__(cls)
            assert isinstance(err, SynapseUserError)
            assert not isinstance(err, SynapseServiceError)

    def test_service_errors_not_user(self):
        for cls in (ExecutionError, HoudiniUnavailableError):
            err = cls.__new__(cls)
            assert isinstance(err, SynapseServiceError)
            assert not isinstance(err, SynapseUserError)


class TestHandlerDispatchIntegration:
    """Verify exception classification for handler routing."""

    def test_user_error_classification(self):
        """SynapseUserError -> success=False, no circuit breaker trip."""
        err = NodeNotFoundError("/stage/missing")
        assert isinstance(err, SynapseUserError)
        assert "Couldn't find" in str(err)

    def test_service_error_classification(self):
        """SynapseServiceError is catchable separately."""
        err = HoudiniUnavailableError()
        assert isinstance(err, SynapseServiceError)
        assert isinstance(err, SynapseError)
        assert not isinstance(err, SynapseUserError)
