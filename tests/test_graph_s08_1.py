"""F12: the unknown-purpose error lists purposes as a readable list, not a set literal."""

import pytest

from synapse.mcp.tool_impls.solaris import component_builder
from synapse.core.errors import ValidationError


def test_unknown_purpose_lists_purposes_readably():
    with pytest.raises(ValidationError) as exc:
        component_builder.validate({"asset_name": "chair", "purposes": ["bogus"]})
    msg = str(exc.value)
    assert "use: proxy, render, simproxy" in msg
    assert "{" not in msg and "}" not in msg
