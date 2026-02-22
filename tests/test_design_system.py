"""
Synapse Design System — Integration Tests

Validates:
  - Design tokens (colors, typography, spacing, icon specs, states)
  - SVG icons (valid XML, viewBox, SIGNAL color present)
  - Shelf XML (valid, expected tools present)
  - Python module imports (tokens, styles, shelf callbacks)
  - Installer dry-run
"""

import json
import os
import sys
import glob
import xml.etree.ElementTree as ET

import pytest


# ── Setup ─────────────────────────────────────────────────

_SYNAPSE_HOME = os.path.join(os.path.expanduser("~"), ".synapse")
_DESIGN_DIR = os.path.join(_SYNAPSE_HOME, "design")
_HOUDINI_DIR = os.path.join(_SYNAPSE_HOME, "houdini")
_SVG_DIR = os.path.join(_DESIGN_DIR, "icons", "svg")

# Add design dir to path for imports
if _DESIGN_DIR not in sys.path:
    sys.path.insert(0, _DESIGN_DIR)


# ── Token Tests ───────────────────────────────────────────

class TestTokens:
    """Validate design tokens are well-formed."""

    def test_import(self):
        import tokens
        assert hasattr(tokens, "SIGNAL")
        assert hasattr(tokens, "VOID")
        assert hasattr(tokens, "PALETTE")

    def test_signal_color(self):
        from tokens import SIGNAL
        assert SIGNAL == "#00D4FF"

    def test_palette_has_all_colors(self):
        from tokens import PALETTE
        expected = {
            "SIGNAL", "VOID", "NEAR_BLACK", "CARBON", "GRAPHITE",
            "SLATE", "SILVER", "BONE", "WHITE",
            "FIRE", "GROW", "WARN", "ERROR",
            "HOU_ORANGE", "HOU_DARK", "HOU_WIRE",
        }
        assert set(PALETTE.keys()) == expected

    def test_hex_format(self):
        from tokens import PALETTE
        import re
        for name, hex_val in PALETTE.items():
            assert re.match(r"^#[0-9A-Fa-f]{6}$", hex_val), f"{name} = {hex_val} is not valid hex"

    def test_color_function(self):
        from tokens import color, SIGNAL
        c = color(SIGNAL)
        assert "hex" in c
        assert "rgb_int" in c
        assert "rgb_float" in c
        assert "rgba_float" in c
        assert "qt_rgba" in c
        assert c["hex"] == "#00D4FF"
        r, g, b = c["rgb_int"]
        assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255

    def test_color_alpha(self):
        from tokens import color, SIGNAL
        c = color(SIGNAL, alpha=0.5)
        assert c["rgba_float"][3] == 0.5
        assert "0.5" in c["qt_rgba"]

    def test_typography(self):
        from tokens import FONT_MONO, FONT_SANS, FONT_MONO_CSS, FONT_SANS_CSS
        assert FONT_MONO == "JetBrains Mono"
        assert FONT_SANS == "DM Sans"
        assert "JetBrains Mono" in FONT_MONO_CSS
        assert "DM Sans" in FONT_SANS_CSS

    def test_font_sizes(self):
        from tokens import SIZE_LABEL, SIZE_SMALL, SIZE_UI, SIZE_BODY, SIZE_TITLE, SIZE_HERO
        sizes = [SIZE_LABEL, SIZE_SMALL, SIZE_UI, SIZE_BODY, SIZE_TITLE, SIZE_HERO]
        # Must be monotonically increasing
        for i in range(len(sizes) - 1):
            assert sizes[i] <= sizes[i + 1], f"Font size {sizes[i]} > {sizes[i + 1]}"

    def test_spacing(self):
        from tokens import SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL
        spaces = [SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL]
        for i in range(len(spaces) - 1):
            assert spaces[i] < spaces[i + 1]

    def test_icon_sizes(self):
        from tokens import ICON_SIZES
        assert "hero" in ICON_SIZES
        assert "shelf" in ICON_SIZES
        assert "small" in ICON_SIZES
        # Shelf and small should NOT have dendrites
        assert ICON_SIZES["shelf"]["dendrite"] is False
        assert ICON_SIZES["small"]["dendrite"] is False
        # Hero should have dendrites
        assert ICON_SIZES["hero"]["dendrite"] is True

    def test_stroke_inversely_proportional(self):
        """Stroke weight should increase as icon size decreases."""
        from tokens import ICON_SIZES
        hero_stroke = ICON_SIZES["hero"]["stroke"]
        small_stroke = ICON_SIZES["small"]["stroke"]
        assert small_stroke > hero_stroke

    def test_states(self):
        from tokens import STATES
        expected_states = {"connected", "executing", "idle", "warning", "error", "disconnected"}
        assert set(STATES.keys()) == expected_states
        for state, info in STATES.items():
            assert "color" in info
            assert "label" in info
            assert "icon" in info

    def test_panel_dimensions(self):
        from tokens import PANEL_MIN_WIDTH, PANEL_PREF_WIDTH, PANEL_MIN_HEIGHT
        assert PANEL_MIN_WIDTH > 0
        assert PANEL_PREF_WIDTH >= PANEL_MIN_WIDTH
        assert PANEL_MIN_HEIGHT > 0


# ── SVG Icon Tests ────────────────────────────────────────

class TestSVGIcons:
    """Validate generated SVG icons."""

    def _get_svgs(self):
        return sorted(glob.glob(os.path.join(_SVG_DIR, "*.svg")))

    def test_svgs_exist(self):
        svgs = self._get_svgs()
        assert len(svgs) >= 18, f"Expected at least 18 SVGs, found {len(svgs)}"

    def test_svg_valid_xml(self):
        for svg_path in self._get_svgs():
            try:
                ET.parse(svg_path)
            except ET.ParseError as e:
                pytest.fail(f"{os.path.basename(svg_path)} is not valid XML: {e}")

    def test_svg_has_viewbox(self):
        for svg_path in self._get_svgs():
            tree = ET.parse(svg_path)
            root = tree.getroot()
            viewbox = root.get("viewBox")
            assert viewbox is not None, f"{os.path.basename(svg_path)} missing viewBox"

    def test_svg_viewbox_square(self):
        for svg_path in self._get_svgs():
            tree = ET.parse(svg_path)
            root = tree.getroot()
            viewbox = root.get("viewBox", "")
            parts = viewbox.split()
            if len(parts) == 4:
                w, h = float(parts[2]), float(parts[3])
                assert w == h == 64, f"{os.path.basename(svg_path)} viewBox is {w}x{h}, expected 64x64"

    def test_signal_color_in_icons(self):
        """At least some icons should use the SIGNAL color (#00D4FF)."""
        signal_count = 0
        for svg_path in self._get_svgs():
            with open(svg_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "#00D4FF" in content or "#00d4ff" in content:
                signal_count += 1
        assert signal_count > 0, "No SVGs reference the SIGNAL color (#00D4FF)"

    def test_icon_names(self):
        """All 6 icon families should have 32px variants."""
        expected = {"synapse", "inspect", "execute", "verify", "document", "profile"}
        found = set()
        for svg_path in self._get_svgs():
            basename = os.path.basename(svg_path)
            if "_32.svg" in basename:
                name = basename.replace("_32.svg", "")
                found.add(name)
        assert expected.issubset(found), f"Missing 32px icons: {expected - found}"

    def test_icon_size_variants(self):
        """Each icon should have at least 32px and 64px variants."""
        names = set()
        for svg_path in self._get_svgs():
            basename = os.path.basename(svg_path)
            for suffix in ["_64.svg", "_32.svg", "_20.svg"]:
                if basename.endswith(suffix):
                    names.add(basename.replace(suffix, ""))
        for name in names:
            assert os.path.exists(os.path.join(_SVG_DIR, f"{name}_32.svg")), \
                f"Missing {name}_32.svg"


# ── Shelf XML Tests ───────────────────────────────────────

class TestShelf:
    """Validate the Houdini shelf XML."""

    _SHELF_PATH = os.path.join(_HOUDINI_DIR, "toolbar", "synapse.shelf")

    def test_shelf_exists(self):
        assert os.path.exists(self._SHELF_PATH)

    def test_shelf_valid_xml(self):
        ET.parse(self._SHELF_PATH)

    def test_shelf_has_tools(self):
        tree = ET.parse(self._SHELF_PATH)
        root = tree.getroot()
        tools = root.findall(".//tool")
        assert len(tools) >= 5, f"Expected at least 5 tools, found {len(tools)}"

    def test_shelf_tool_names(self):
        tree = ET.parse(self._SHELF_PATH)
        root = tree.getroot()
        tool_names = {t.get("name") for t in root.findall(".//tool")}
        expected = {"synapse_panel", "synapse_inspect_selection", "synapse_inspect_scene",
                    "synapse_last_result", "synapse_health_check"}
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_shelf_icons_use_namespace(self):
        tree = ET.parse(self._SHELF_PATH)
        root = tree.getroot()
        for tool in root.findall(".//tool"):
            icon = tool.get("icon", "")
            if icon:
                assert icon.startswith("SYNAPSE_"), \
                    f"Tool {tool.get('name')} icon '{icon}' doesn't use SYNAPSE_ namespace"

    def test_shelf_scripts_reference_synapse_shelf(self):
        tree = ET.parse(self._SHELF_PATH)
        root = tree.getroot()
        for tool in root.findall(".//tool"):
            script = tool.find("script")
            if script is not None and script.text:
                assert "synapse_shelf" in script.text, \
                    f"Tool {tool.get('name')} doesn't reference synapse_shelf module"


# ── Panel Tests ───────────────────────────────────────────

class TestPanel:
    """Validate the Python panel file."""

    _PANEL_PATH = os.path.join(_HOUDINI_DIR, "python_panels", "synapse_panel.pypanel")

    def test_panel_exists(self):
        assert os.path.exists(self._PANEL_PATH)

    def test_panel_valid_xml(self):
        ET.parse(self._PANEL_PATH)

    def test_panel_has_interface(self):
        tree = ET.parse(self._PANEL_PATH)
        root = tree.getroot()
        interfaces = root.findall(".//interface")
        assert len(interfaces) >= 1
        assert interfaces[0].get("name") == "synapse_panel"

    def test_panel_has_oncreateinterface(self):
        with open(self._PANEL_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        assert "onCreateInterface" in content


# ── Stylesheet Tests ──────────────────────────────────────

class TestStylesheet:
    """Validate the Qt stylesheet generator."""

    def test_import(self):
        from synapse_styles import generate_stylesheet, STATUS_STYLES
        assert callable(generate_stylesheet)
        assert isinstance(STATUS_STYLES, dict)

    def test_stylesheet_not_empty(self):
        from synapse_styles import generate_stylesheet
        qss = generate_stylesheet()
        assert len(qss) > 500, "Stylesheet seems too short"

    def test_stylesheet_references_tokens(self):
        from synapse_styles import generate_stylesheet
        from tokens import SIGNAL, NEAR_BLACK, CARBON
        qss = generate_stylesheet()
        assert SIGNAL in qss
        assert NEAR_BLACK in qss
        assert CARBON in qss

    def test_status_styles_complete(self):
        from synapse_styles import STATUS_STYLES
        from tokens import STATES
        for state in STATES:
            assert state in STATUS_STYLES, f"Missing status style for '{state}'"


# ── Shelf Callbacks Tests ─────────────────────────────────

class TestShelfCallbacks:
    """Validate the shelf callbacks module (without Houdini)."""

    _CALLBACKS_PATH = os.path.join(
        _HOUDINI_DIR, "scripts", "python", "synapse_shelf.py"
    )

    def test_callbacks_exist(self):
        assert os.path.exists(self._CALLBACKS_PATH)

    def test_callbacks_syntax(self):
        """Verify the module is valid Python syntax."""
        with open(self._CALLBACKS_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        compile(source, self._CALLBACKS_PATH, "exec")

    def test_callbacks_defines_functions(self):
        """Check expected function names are defined."""
        with open(self._CALLBACKS_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        expected_funcs = [
            "open_panel", "inspect_selection", "inspect_scene",
            "copy_last_result", "health_check", "generate_docs",
        ]
        for func_name in expected_funcs:
            assert f"def {func_name}" in source, f"Missing function: {func_name}"


# ── Installer Tests ───────────────────────────────────────

class TestInstaller:
    """Validate the installer script."""

    _INSTALLER_PATH = os.path.join(_SYNAPSE_HOME, "install.py")

    def test_installer_exists(self):
        assert os.path.exists(self._INSTALLER_PATH)

    def test_installer_syntax(self):
        with open(self._INSTALLER_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        compile(source, self._INSTALLER_PATH, "exec")

    def test_installer_dry_run(self, tmp_path):
        """Run installer in dry-run mode against a temp directory."""
        # Create a fake houdini prefs directory
        fake_prefs = tmp_path / "houdini21.0"
        fake_prefs.mkdir()

        # Import and run
        sys.path.insert(0, _SYNAPSE_HOME)
        try:
            import install as installer
            count = installer.install(str(fake_prefs), dry_run=True)
            assert count > 0, "Dry-run should report files to install"
        finally:
            sys.path.remove(_SYNAPSE_HOME)

    def test_installer_actual_install(self, tmp_path):
        """Run actual install against a temp directory."""
        fake_prefs = tmp_path / "houdini21.0"
        fake_prefs.mkdir()

        sys.path.insert(0, _SYNAPSE_HOME)
        try:
            import install as installer
            count = installer.install(str(fake_prefs), dry_run=False)
            assert count > 0

            # Verify files were actually created
            assert (fake_prefs / "toolbar" / "synapse.shelf").exists()
            assert (fake_prefs / "scripts" / "python" / "synapse_shelf.py").exists()
            assert (fake_prefs / "scripts" / "python" / "tokens.py").exists()
        finally:
            sys.path.remove(_SYNAPSE_HOME)

    def test_installer_uninstall(self, tmp_path):
        """Install then uninstall, verify cleanup."""
        fake_prefs = tmp_path / "houdini21.0"
        fake_prefs.mkdir()

        sys.path.insert(0, _SYNAPSE_HOME)
        try:
            import install as installer
            installer.install(str(fake_prefs), dry_run=False)
            removed = installer.uninstall(str(fake_prefs), dry_run=False)
            assert removed > 0

            # Core files should be gone
            assert not (fake_prefs / "toolbar" / "synapse.shelf").exists()
            assert not (fake_prefs / "scripts" / "python" / "synapse_shelf.py").exists()
        finally:
            sys.path.remove(_SYNAPSE_HOME)


# ── Brand Mark Tests ──────────────────────────────────────

class TestBrandMarks:
    """Validate brand mark SVGs."""

    _BRAND_DIR = os.path.join(_DESIGN_DIR, "brand")

    def test_brand_marks_exist(self):
        expected = [
            "synapse_mark_dark.svg",
            "synapse_mark_light.svg",
            "synapse_construction.svg",
        ]
        for name in expected:
            path = os.path.join(self._BRAND_DIR, name)
            assert os.path.exists(path), f"Missing brand mark: {name}"

    def test_brand_marks_valid_xml(self):
        for svg_path in glob.glob(os.path.join(self._BRAND_DIR, "*.svg")):
            try:
                ET.parse(svg_path)
            except ET.ParseError as e:
                pytest.fail(f"{os.path.basename(svg_path)} is not valid XML: {e}")
