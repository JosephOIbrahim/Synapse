"""
Synapse Design System — SVG Icon Generator

Generates all Synapse icons as individual SVG files using Pentagram
construction rules. Raw XML strings — no SVG library needed.

Usage:
    python generate_icons.py
"""

import os
import sys

# Import tokens from same directory
sys.path.insert(0, os.path.dirname(__file__))
from tokens import SIGNAL, VOID, ICON_SIZES

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "icons", "svg")
BRAND_DIR = os.path.join(os.path.dirname(__file__), "brand")

# All icons use 64x64 viewBox — scale via width/height
VIEWBOX = "0 0 64 64"


# ─────────────────────────────────────────────────────────────
# SVG helpers
# ─────────────────────────────────────────────────────────────


def _svg_wrap(content: str, size: int, icon_name: str) -> str:
    """Wrap SVG content in root element with correct attributes."""
    return (
        f'<!-- Synapse {icon_name} {size}px | Pentagram -->\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="{VIEWBOX}">\n'
        f'{content}'
        f'</svg>\n'
    )


def _circle(cx, cy, r, fill, opacity=1.0):
    op = f' opacity="{opacity}"' if opacity < 1.0 else ""
    return f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{op}/>\n'


def _line(x1, y1, x2, y2, stroke, stroke_width, opacity=1.0, cap="round"):
    op = f' opacity="{opacity}"' if opacity < 1.0 else ""
    return (
        f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}" '
        f'stroke-linecap="{cap}"{op}/>\n'
    )


def _path(d, stroke, stroke_width, fill="none", opacity=1.0,
          cap="round", join="round"):
    op = f' opacity="{opacity}"' if opacity < 1.0 else ""
    return (
        f'  <path d="{d}" stroke="{stroke}" stroke-width="{stroke_width}" '
        f'fill="{fill}" stroke-linecap="{cap}" stroke-linejoin="{join}"{op}/>\n'
    )


def _rect(x, y, w, h, stroke, stroke_width, fill="none", opacity=1.0):
    op = f' opacity="{opacity}"' if opacity < 1.0 else ""
    return (
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}" fill="{fill}"{op}/>\n'
    )


def _ellipse(cx, cy, rx, ry, stroke, stroke_width, fill="none", opacity=1.0):
    op = f' opacity="{opacity}"' if opacity < 1.0 else ""
    return (
        f'  <ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}" fill="{fill}"{op}/>\n'
    )


# ─────────────────────────────────────────────────────────────
# Icon generators
# ─────────────────────────────────────────────────────────────

# S-curve path data (64x64 viewBox)
_S_CURVE = (
    "M22 24 C22 18, 28 15, 32 15 C38 15, 42 19, 42 24 "
    "C42 30, 36 32, 32 33.5 C28 35, 22 37, 22 42 "
    "C22 48, 28 51, 32 51 C36 51, 42 47, 42 42"
)
_S_TOP = (22, 24)
_S_BOT = (42, 42)


def _gen_synapse(size_key: str) -> str:
    """Generate the Synapse primary mark (S-curve + nodes + dendrites)."""
    spec = ICON_SIZES[size_key]
    sw = spec["stroke"]
    nr = spec["node_r"]
    content = ""

    # S-curve
    content += _path(_S_CURVE, SIGNAL, sw)

    # Terminal nodes
    content += _circle(_S_TOP[0], _S_TOP[1], nr, SIGNAL)
    content += _circle(_S_BOT[0], _S_BOT[1], nr, SIGNAL)

    # Dendrites (only at large+ sizes)
    if spec["dendrite"]:
        decays = spec["opacity_decay"]
        # Top node dendrites
        if len(decays) >= 1:
            content += _line(_S_TOP[0], _S_TOP[1], 14, 16, SIGNAL, sw * 0.6, decays[0])
            content += _line(_S_TOP[0], _S_TOP[1], 14, 24, SIGNAL, sw * 0.6, decays[0])
        if len(decays) >= 2:
            content += _line(14, 16, 8, 12, SIGNAL, sw * 0.4, decays[1])
            content += _line(14, 24, 8, 24, SIGNAL, sw * 0.4, decays[1])
        if len(decays) >= 3:
            content += _line(8, 12, 4, 10, SIGNAL, sw * 0.3, decays[2])

        # Bottom node dendrites
        if len(decays) >= 1:
            content += _line(_S_BOT[0], _S_BOT[1], 50, 50, SIGNAL, sw * 0.6, decays[0])
            content += _line(_S_BOT[0], _S_BOT[1], 50, 42, SIGNAL, sw * 0.6, decays[0])
        if len(decays) >= 2:
            content += _line(50, 50, 56, 54, SIGNAL, sw * 0.4, decays[1])
            content += _line(50, 42, 56, 42, SIGNAL, sw * 0.4, decays[1])
        if len(decays) >= 3:
            content += _line(56, 54, 60, 56, SIGNAL, sw * 0.3, decays[2])

    return content


def _gen_inspect(size_key: str) -> str:
    """Generate the Inspect icon (concentric circles + crosshair)."""
    spec = ICON_SIZES[size_key]
    sw = spec["stroke"]
    content = ""
    cx, cy = 32, 32

    if size_key in ("hero", "large", "medium"):
        # Three concentric circles
        content += _circle(cx, cy, 20, "none")
        content = content.replace("/>", f' stroke="{SIGNAL}" stroke-width="{sw * 0.5}" opacity="0.2"/>')
        content += f'  <circle cx="{cx}" cy="{cy}" r="14" fill="none" stroke="{SIGNAL}" stroke-width="{sw * 0.6}" opacity="0.4"/>\n'
        content += f'  <circle cx="{cx}" cy="{cy}" r="8" fill="none" stroke="{SIGNAL}" stroke-width="{sw * 0.8}" opacity="0.7"/>\n'
        # Center dot
        content += _circle(cx, cy, 2.5, SIGNAL)
        # Crosshair lines
        content += _line(cx, 4, cx, 12, SIGNAL, sw * 0.4, 0.3)
        content += _line(cx, 52, cx, 60, SIGNAL, sw * 0.4, 0.3)
        content += _line(4, cy, 12, cy, SIGNAL, sw * 0.4, 0.3)
        content += _line(52, cy, 60, cy, SIGNAL, sw * 0.4, 0.3)
    elif size_key == "shelf":
        # Two circles + dot, no crosshairs
        content += f'  <circle cx="{cx}" cy="{cy}" r="12" fill="none" stroke="{SIGNAL}" stroke-width="{sw * 0.7}" opacity="0.4"/>\n'
        content += f'  <circle cx="{cx}" cy="{cy}" r="6" fill="none" stroke="{SIGNAL}" stroke-width="{sw * 0.9}" opacity="0.7"/>\n'
        content += _circle(cx, cy, 2.5, SIGNAL)
    else:
        # Small: single circle + dot
        content += f'  <circle cx="{cx}" cy="{cy}" r="10" fill="none" stroke="{SIGNAL}" stroke-width="{sw}" opacity="0.6"/>\n'
        content += _circle(cx, cy, 3, SIGNAL)

    return content


# Lightning bolt path (angular, Pentagram style)
_BOLT = "M35 10 L23 32 L31 32 L29 54 L41 28 L33 28 Z"


def _gen_execute(size_key: str) -> str:
    """Generate the Execute icon (lightning bolt + orbital ring)."""
    spec = ICON_SIZES[size_key]
    sw = spec["stroke"]
    content = ""

    if size_key in ("hero", "large", "medium"):
        # Faint orbital ring
        content += _ellipse(32, 32, 26, 10, SIGNAL, sw * 0.3, opacity=0.15)
        # Stroked bolt with bevel joins
        content += _path(_BOLT, SIGNAL, sw, join="bevel")
    elif size_key == "shelf":
        # Bolt only, stroked
        content += _path(_BOLT, SIGNAL, sw, join="bevel")
    else:
        # Small: bolt filled solid, no stroke
        content += f'  <path d="{_BOLT}" fill="{SIGNAL}" stroke="none"/>\n'

    return content


# Checkmark path
_CHECK = "M22 33 L29 40 L42 24"


def _gen_verify(size_key: str) -> str:
    """Generate the Verify icon (circle + checkmark)."""
    spec = ICON_SIZES[size_key]
    sw = spec["stroke"]
    content = ""

    if size_key in ("hero", "large", "medium"):
        # Outer circle
        content += f'  <circle cx="32" cy="32" r="22" fill="none" stroke="{SIGNAL}" stroke-width="{sw * 0.5}" opacity="0.3"/>\n'
        # Check
        content += _path(_CHECK, SIGNAL, sw, cap="round", join="round")
    elif size_key == "shelf":
        # Thinner circle, thicker check
        content += f'  <circle cx="32" cy="32" r="18" fill="none" stroke="{SIGNAL}" stroke-width="{sw * 0.4}" opacity="0.25"/>\n'
        content += _path(_CHECK, SIGNAL, sw * 1.1, cap="round", join="round")
    else:
        # Small: check only
        content += _path(_CHECK, SIGNAL, sw, cap="round", join="round")

    return content


def _gen_document(size_key: str) -> str:
    """Generate the Document icon (page + text lines + generation spark)."""
    spec = ICON_SIZES[size_key]
    sw = spec["stroke"]
    content = ""

    if size_key in ("hero", "large", "medium"):
        # Page rectangle (sharp corners — no rx)
        content += _rect(16, 10, 26, 36, SIGNAL, sw * 0.6)
        # Text lines with decreasing length and opacity
        content += _line(20, 20, 36, 20, SIGNAL, sw * 0.4, 0.6)
        content += _line(20, 26, 34, 26, SIGNAL, sw * 0.4, 0.45)
        content += _line(20, 32, 30, 32, SIGNAL, sw * 0.4, 0.3)
        # Generation spark: circle with + crosshair
        content += _circle(46, 16, 3, "none")
        content = content[:-1]  # Remove last newline to append attrs
        content += f'\n  <circle cx="46" cy="16" r="3" fill="none" stroke="{SIGNAL}" stroke-width="{sw * 0.4}" opacity="0.5"/>\n'
        content += _line(46, 13, 46, 19, SIGNAL, sw * 0.35, 0.5)
        content += _line(43, 16, 49, 16, SIGNAL, sw * 0.35, 0.5)
    elif size_key == "shelf":
        # Rectangle + one line, no spark
        content += _rect(18, 12, 22, 32, SIGNAL, sw * 0.7)
        content += _line(22, 22, 36, 22, SIGNAL, sw * 0.5, 0.5)
    else:
        # Small: rectangle outline only
        content += _rect(20, 14, 18, 28, SIGNAL, sw * 0.8)

    return content


def _gen_profile(size_key: str) -> str:
    """Generate the Profile icon (bar chart + trend line)."""
    spec = ICON_SIZES[size_key]
    sw = spec["stroke"]
    content = ""

    bar_x = [14, 24, 34, 44]
    bar_h = [20, 30, 16, 26]  # Heights from baseline
    bar_w = 6
    baseline_y = 52

    if size_key in ("hero", "large", "medium"):
        # Four bars
        opacities = [0.4, 0.7, 0.3, 0.6]
        for i, (bx, bh) in enumerate(zip(bar_x, bar_h)):
            by = baseline_y - bh
            content += _rect(bx, by, bar_w, bh, "none", 0, fill=SIGNAL, opacity=opacities[i])
        # Trend line connecting bar tops
        tops = [(bx + bar_w / 2, baseline_y - bh) for bx, bh in zip(bar_x, bar_h)]
        d = f"M{tops[0][0]} {tops[0][1]}"
        for tx, ty in tops[1:]:
            d += f" L{tx} {ty}"
        content += _path(d, SIGNAL, sw * 0.5, cap="round")
        # Baseline
        content += _line(10, baseline_y, 54, baseline_y, SIGNAL, sw * 0.3, 0.3)
    elif size_key == "shelf":
        # Three bars only
        for i, (bx, bh) in enumerate(zip(bar_x[:3], bar_h[:3])):
            bx_adj = bx + 5  # center 3 bars
            by = baseline_y - bh
            content += _rect(bx_adj, by, bar_w + 1, bh, "none", 0, fill=SIGNAL, opacity=0.5 + i * 0.1)
    else:
        # Small: three bars filled
        for i, (bx, bh) in enumerate(zip(bar_x[:3], bar_h[:3])):
            bx_adj = bx + 7
            by = baseline_y - bh
            content += _rect(bx_adj, by, bar_w, bh, "none", 0, fill=SIGNAL, opacity=0.6)

    return content


# ─────────────────────────────────────────────────────────────
# Generator registry
# ─────────────────────────────────────────────────────────────

ICON_GENERATORS = {
    "synapse": _gen_synapse,
    "inspect": _gen_inspect,
    "execute": _gen_execute,
    "verify": _gen_verify,
    "document": _gen_document,
    "profile": _gen_profile,
}

# Map pixel sizes to spec keys
SIZE_MAP = {64: "large", 32: "shelf", 20: "small"}


# ─────────────────────────────────────────────────────────────
# Brand marks
# ─────────────────────────────────────────────────────────────


def _gen_brand_dark() -> str:
    """Full hero-size mark with construction grid on dark background."""
    size = 120
    spec_key = "hero"
    content = _gen_synapse(spec_key)
    # Add faint construction grid
    for x in range(0, 65, 5):
        content += _line(x, 0, x, 64, SIGNAL, 0.15, 0.05)
    for y in range(0, 65, 5):
        content += _line(0, y, 64, y, SIGNAL, 0.15, 0.05)
    return _svg_wrap(content, size, "brand_dark")


def _gen_brand_light() -> str:
    """Hero mark stroked in VOID for light backgrounds."""
    size = 120
    spec = ICON_SIZES["hero"]
    sw = spec["stroke"]
    nr = spec["node_r"]
    content = ""
    content += _path(_S_CURVE, VOID, sw)
    content += _circle(_S_TOP[0], _S_TOP[1], nr, VOID)
    content += _circle(_S_BOT[0], _S_BOT[1], nr, VOID)
    # Dendrites in VOID
    decays = spec["opacity_decay"]
    if len(decays) >= 1:
        content += _line(_S_TOP[0], _S_TOP[1], 14, 16, VOID, sw * 0.6, decays[0])
        content += _line(_S_TOP[0], _S_TOP[1], 14, 24, VOID, sw * 0.6, decays[0])
        content += _line(_S_BOT[0], _S_BOT[1], 50, 50, VOID, sw * 0.6, decays[0])
        content += _line(_S_BOT[0], _S_BOT[1], 50, 42, VOID, sw * 0.6, decays[0])
    return _svg_wrap(content, size, "brand_light")


def _gen_brand_construction() -> str:
    """Full construction grid version with annotations."""
    size = 120
    content = ""
    # 12-column grid
    col_w = 64 / 12
    for i in range(13):
        x = i * col_w
        content += _line(x, 0, x, 64, SIGNAL, 0.2, 0.08)
    for i in range(13):
        y = i * col_w
        content += _line(0, y, 64, y, SIGNAL, 0.2, 0.08)
    # S-curve in low opacity
    content += _path(_S_CURVE, SIGNAL, 2.0, opacity=0.4)
    # Node positions marked
    content += _circle(_S_TOP[0], _S_TOP[1], 4, "none")
    content += f'  <circle cx="{_S_TOP[0]}" cy="{_S_TOP[1]}" r="4" fill="none" stroke="{SIGNAL}" stroke-width="0.5" opacity="0.6" stroke-dasharray="2 2"/>\n'
    content += f'  <circle cx="{_S_BOT[0]}" cy="{_S_BOT[1]}" r="4" fill="none" stroke="{SIGNAL}" stroke-width="0.5" opacity="0.6" stroke-dasharray="2 2"/>\n'
    # Annotation text
    content += f'  <text x="4" y="62" font-size="3" fill="{SIGNAL}" opacity="0.4" font-family="monospace">SYNAPSE CONSTRUCTION</text>\n'
    return _svg_wrap(content, size, "construction")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────


def generate_all():
    """Generate all SVG icons and brand marks."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(BRAND_DIR, exist_ok=True)

    count = 0

    # Generate each icon at each size
    for icon_name, gen_func in ICON_GENERATORS.items():
        for px_size, spec_key in SIZE_MAP.items():
            content = gen_func(spec_key)
            svg = _svg_wrap(content, px_size, icon_name)
            filename = f"{icon_name}_{px_size}.svg"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(svg)
            count += 1

    # Brand marks
    brands = {
        "synapse_mark_dark.svg": _gen_brand_dark(),
        "synapse_mark_light.svg": _gen_brand_light(),
        "synapse_construction.svg": _gen_brand_construction(),
    }
    for filename, svg_content in brands.items():
        filepath = os.path.join(BRAND_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(svg_content)
        count += 1

    print(f"Generated: {count} SVG files")
    print(f"Icons:     {OUTPUT_DIR}")
    print(f"Brand:     {BRAND_DIR}")
    print(f"Sizes:     64px, 32px, 20px")
    print(f"Icons:     {', '.join(ICON_GENERATORS.keys())}")
    return count


if __name__ == "__main__":
    generate_all()
