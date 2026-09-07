"""Standalone agent entry points use the same installed SYNAPSE rules owner."""
from pathlib import Path
import sys

_package = Path(__file__).resolve().parents[1] / "python"
if (_package / "synapse/model_access.py").is_file() and str(_package) not in sys.path:
    sys.path.insert(0, str(_package))
try:
    from synapse.model_access import guarded_create, make_anthropic_client, scoped_request
    from synapse.request_handoff import export_scope, import_scope
except ImportError:
    raise RuntimeError("SYNAPSE model rules are unavailable. Launch the agent with the installed SYNAPSE Python package on PYTHONPATH.") from None
