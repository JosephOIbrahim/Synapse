"""
Synapse Design System — PNG Rasterization

Converts 32px SVG icons to PNG for Houdini shelf fallback.
Tries: cairosvg → Pillow+svglib → Inkscape CLI → instruction fallback.

Usage:
    python rasterize_icons.py
"""

import os
import sys
import glob

SVG_DIR = os.path.join(os.path.dirname(__file__), "icons", "svg")
PNG_DIR = os.path.join(os.path.dirname(__file__), "icons", "png")


def _rasterize_cairosvg(svg_path: str, png_path: str, width: int, height: int) -> bool:
    """Method 1: cairosvg."""
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path,
                         output_width=width, output_height=height)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  cairosvg error: {e}")
        return False


def _rasterize_svglib(svg_path: str, png_path: str, width: int, height: int) -> bool:
    """Method 2: svglib + reportlab."""
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        drawing = svg2rlg(svg_path)
        if drawing is None:
            return False
        scale_x = width / drawing.width
        scale_y = height / drawing.height
        drawing.width = width
        drawing.height = height
        drawing.scale(scale_x, scale_y)
        renderPM.drawToFile(drawing, png_path, fmt="PNG")
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  svglib error: {e}")
        return False


def _rasterize_inkscape(svg_path: str, png_path: str, width: int) -> bool:
    """Method 3: Inkscape CLI."""
    try:
        import subprocess
        result = subprocess.run(
            ["inkscape", "--export-type=png", f"--export-width={width}",
             svg_path, "-o", png_path],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0 and os.path.exists(png_path)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"  inkscape error: {e}")
        return False


def rasterize_all():
    """Rasterize all 32px SVGs to PNG, plus @2x from 64px sources."""
    os.makedirs(PNG_DIR, exist_ok=True)

    svg_32_files = sorted(glob.glob(os.path.join(SVG_DIR, "*_32.svg")))
    svg_64_files = sorted(glob.glob(os.path.join(SVG_DIR, "*_64.svg")))

    if not svg_32_files:
        print("No 32px SVG files found. Run generate_icons.py first.")
        return

    # Detect available method
    method = None
    test_svg = svg_32_files[0]
    test_png = os.path.join(PNG_DIR, "_test.png")

    if _rasterize_cairosvg(test_svg, test_png, 32, 32):
        method = "cairosvg"
    elif _rasterize_svglib(test_svg, test_png, 32, 32):
        method = "svglib"
    elif _rasterize_inkscape(test_svg, test_png, 32):
        method = "inkscape"

    # Cleanup test
    if os.path.exists(test_png):
        os.remove(test_png)

    if method is None:
        print("No rasterization method available.")
        print("Install one of:")
        print("  pip install cairosvg          (preferred)")
        print("  pip install svglib reportlab  (alternative)")
        print("  Install Inkscape CLI          (last resort)")
        return

    print(f"Using: {method}")
    count = 0

    # 32px PNGs
    for svg_path in svg_32_files:
        name = os.path.basename(svg_path).replace(".svg", ".png")
        png_path = os.path.join(PNG_DIR, name)
        ok = False
        if method == "cairosvg":
            ok = _rasterize_cairosvg(svg_path, png_path, 32, 32)
        elif method == "svglib":
            ok = _rasterize_svglib(svg_path, png_path, 32, 32)
        elif method == "inkscape":
            ok = _rasterize_inkscape(svg_path, png_path, 32)
        if ok and os.path.exists(png_path) and os.path.getsize(png_path) > 0:
            count += 1
            print(f"  {name} ({os.path.getsize(png_path)} bytes)")
        else:
            print(f"  {name} FAILED")

    # @2x PNGs from 64px sources
    for svg_path in svg_64_files:
        base = os.path.basename(svg_path).replace("_64.svg", "")
        name = f"{base}_32@2x.png"
        png_path = os.path.join(PNG_DIR, name)
        ok = False
        if method == "cairosvg":
            ok = _rasterize_cairosvg(svg_path, png_path, 64, 64)
        elif method == "svglib":
            ok = _rasterize_svglib(svg_path, png_path, 64, 64)
        elif method == "inkscape":
            ok = _rasterize_inkscape(svg_path, png_path, 64)
        if ok and os.path.exists(png_path) and os.path.getsize(png_path) > 0:
            count += 1
            print(f"  {name} ({os.path.getsize(png_path)} bytes)")
        else:
            print(f"  {name} FAILED")

    print(f"\nGenerated: {count} PNG files in {PNG_DIR}")


if __name__ == "__main__":
    rasterize_all()
