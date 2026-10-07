"""The installation page dates the Windows Setup's panel instead of calling it the latest.

The v5.86.0 Setup predates Spatial, the Render footer row and the scene-reading
Scatter recipe. README was corrected in 3645b2b5; docs/getting-started/installation.md
carried the same "latest panel" wording. Both pages must describe the Setup the same way.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "docs" / "getting-started" / "installation.md"
README = ROOT / "README.md"


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _setup_version(text: str) -> str:
    match = re.search(r"SYNAPSE-(\d+\.\d+\.\d+)-Setup\.exe", text)
    assert match, "no Setup download link"
    return match.group(1)


def test_installation_does_not_call_the_setup_panel_the_latest():
    assert "latest panel" not in _flat(INSTALL)


def test_installation_dates_the_panel_to_the_setup_version():
    text = _flat(INSTALL)
    assert f"panel as of v{_setup_version(text)}" in text


def test_installation_names_what_the_setup_lacks():
    text = _flat(INSTALL)
    for feature in ("Spatial", "Render footer row", "Scatter recipe"):
        assert feature in text, feature


def test_readme_and_installation_agree_on_the_setup():
    readme, install = _flat(README), _flat(INSTALL)
    assert _setup_version(readme) == _setup_version(install)
    for text in (readme, install):
        assert "latest panel" not in text
        assert f"panel as of v{_setup_version(text)}" in text
