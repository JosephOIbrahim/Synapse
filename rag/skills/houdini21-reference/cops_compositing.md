# COPs (Compositing) Node Reference

## Overview
COPs = Composite Operators. Houdini's built-in 2D image compositing context.
Located at `/img` or inside `cop2net` SOPs/LOPs.

## Common COP Node Types

### Generators
| Node | Description |
|------|-------------|
| `file` | Load image/sequence from disk |
| `color` | Solid color plane |
| `ramp` | Gradient ramp (linear, radial, etc.) |
| `noise` | Procedural noise pattern |
| `font` | Text rendering |
| `constant` | Constant value (all pixels same) |

### Color Correction
| Node | Description |
|------|-------------|
| `colorcorrect` | Gamma, gain, offset per channel |
| `grade` | Lift/gamma/gain (film grading) |
| `bright` | Simple brightness/contrast |
| `hueshift` | Hue rotation |
| `hsv` | HSV adjustment |
| `lut` | LUT application |
| `tonemap` | HDR tonemapping |

### Compositing
| Node | Description |
|------|-------------|
| `over` | A over B (alpha composite) |
| `multiply` | Multiply blend |
| `add` | Additive blend |
| `subtract` | Subtractive blend |
| `screen` | Screen blend |
| `switch` | Switch between inputs |
| `blend` | Blend with controllable mix |

### Transform
| Node | Description |
|------|-------------|
| `xform` | 2D translate/rotate/scale |
| `crop` | Crop image bounds |
| `scale` | Resize resolution |
| `flip` | Flip horizontal/vertical |
| `corner_pin` | Four-corner pin warp |

### Filters
| Node | Description |
|------|-------------|
| `blur` | Gaussian blur |
| `defocus` | Lens defocus (bokeh) |
| `sharpen` | Sharpen filter |
| `edge` | Edge detection |
| `median` | Median noise reduction |

### Channels
| Node | Description |
|------|-------------|
| `channelcopy` | Copy channels between planes |
| `shuffle` | Rearrange channels |
| `premultiply` | Premultiply alpha |
| `unpremultiply` | Remove premultiplication |
| `rename` | Rename image planes |

### Output
| Node | Description |
|------|-------------|
| `rop_comp` | Render/write to disk |
| `null` | Output marker (like SOP null) |

## Key Parameters

### File COP
- `filename` - Path to image/sequence (use `$F4` for frame padding)
- `overridesize` - Override resolution
- `linearize` - Apply sRGB to linear conversion

### Color Correct
- `gamma` / `gammar/g/b` - Per-channel gamma
- `gain` / `gainr/g/b` - Per-channel gain
- `offset` / `offsetr/g/b` - Per-channel offset
- `saturation` - Saturation (1=unchanged)

### Grade
- `lift` - Shadow adjustment (lift)
- `gamma` - Midtone adjustment
- `gain` - Highlight adjustment
- `whitepoint` / `blackpoint` - Range mapping

## Tips
- COPs process per-scanline (memory efficient for large images)
- Use `null` nodes as output markers
- Chain: `file` -> `colorcorrect` -> `grade` -> `null` for basic correction
- COPs can be used inline in SOPs via `cop2net` for texture baking
