"""BP9-RETIRE (ruling 3): one panel, one loader.

The legacy chat surface (chat_panel.py, quick_actions.py, synapse_chat.pypanel)
is deleted. This pins the two facts that keep it from creeping back:

* exactly one ``.pypanel`` lives under ``houdini/python_panels/``, and it is
  the shipped ``synapse_panel.pypanel``;
* the shelf (``houdini/scripts/python/synapse_shelf.py``, the only installer
  in the tree) finds and installs only that file - no other ``.pypanel`` name
  appears anywhere in it.

Source-only: no Qt, no host.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPANELS = ROOT / "houdini/python_panels"
SHELF = ROOT / "houdini/scripts/python/synapse_shelf.py"
SHIPPED = "synapse_panel.pypanel"


def test_exactly_one_pypanel_under_python_panels():
    files = sorted(p.name for p in PYPANELS.glob("*.pypanel"))
    assert files == [SHIPPED], files


def test_no_pypanel_anywhere_else_in_the_shipped_tree():
    """The legacy loader lived OUTSIDE python_panels (python/synapse/panel/);
    a .pypanel anywhere under python/ or houdini/ other than the shipped one
    is a second surface coming back."""
    stray = sorted(
        str(p.relative_to(ROOT)).replace("\\", "/")
        for base in (ROOT / "python", ROOT / "houdini")
        for p in base.rglob("*.pypanel")
        if p.resolve() != (PYPANELS / SHIPPED).resolve()
    )
    assert stray == [], stray


def test_shelf_installs_only_the_shipped_pypanel():
    source = SHELF.read_text(encoding="utf-8")
    names = set(re.findall(r"[\w/-]+\.pypanel(?![\w.])", source))
    assert names == {"python_panels/" + SHIPPED}, names
    # Both the lookup and the install path point at the shipped loader.
    assert 'hou.findFile("python_panels/%s")' % SHIPPED in source
    assert "hou.pypanel.installFile(pypanel_path)" in source
    assert "synapse_chat" not in source
