"""Phase 0c / SEC-0: hwebserver_adapter must import `os` if it uses `os.*`.

The hwebserver `connect()` calls ``os.environ.get("SYNAPSE_DEPLOY_MODE", ...)``
for origin validation (DNS-rebinding defense). Without ``import os`` that raises
``NameError`` at connect time -- the defense never runs and the upgrade fails.

This reads the module source by PATH (no import, no Houdini needed) so it runs in
stock CI. If a future edit reintroduces ``os.*`` usage without the import, this
fails loud. Floor: source-of-record, not a mock.
"""
import pathlib

_ADAPTER = (
    pathlib.Path(__file__).resolve().parent.parent
    / "python" / "synapse" / "server" / "hwebserver_adapter.py"
)


def test_hwebserver_adapter_imports_os_when_used():
    text = _ADAPTER.read_text(encoding="utf-8")
    if "os." in text:
        assert "import os" in text, (
            "hwebserver_adapter.py uses os.* (e.g. connect() origin validation) but "
            "does not `import os` -> NameError before validate_origin (SEC-0)."
        )
