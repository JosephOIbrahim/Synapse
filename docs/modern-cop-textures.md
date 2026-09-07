# Modern Copernicus procedural textures

`cops_procedural_texture` targets Houdini 22's **CopNet (new)**: an editable
network whose child category is `Cop`. It refuses legacy `Cop2` parents before
creating anything. Other older COP helpers retain their existing behavior.

The helper creates two editable sibling nodes: a private **Layer** controlling
resolution, connected to **Fractal Noise** through its `size_ref` input. The
returned `path` is the noise node and `output_name` is `noise`. Its output is a
single-channel procedural signal suitable for further texture processing.

| Request | Modern configuration |
| --- | --- |
| `perlin` (default) | Fractal Noise, Perlin |
| `worley` | Fractal Noise, Worley Cellular F1 (`worleyA`) |
| `alligator` | Fractal Noise, Alligator |
| `simplex` | 3D Fractal Noise, Simplex, sampled on the canonical XY plane |
| `frequency` (default 1) | `elementsize = 1 / frequency`, in canonical image/world units; higher values produce finer features |
| `octaves` (default 4) | Sharp fractal mode, maximum octaves 1–16 |
| `resolution` (default 1024 × 1024) | Each dimension 1–8192, explicit full pixel scale, square pixels and no padding |

The 2D generator's tiling is disabled so it cannot quantize the requested element
size. There are no ramp, tiling, color-space conversion or export controls in
this helper. Simplex is a slice of a 3D field, not a claim of a native 2D Simplex
algorithm. The Layer's identity transform makes the sampling coordinates explicit.

Parameter and connection readback must match before `configured: true` is
returned. `cooked: false` means the helper has not requested or verified an image
cook. Cook or render the output separately. Requested settings, actual node type,
noise basis and the companion resolution path are included in the result.

The operation does not change parent settings, existing connections or display
flags. Existing names are preserved and Houdini assigns distinct names to new
nodes. On failure it removes only nodes created by that call; incomplete cleanup
reports the remaining paths. The undo group also supports ordinary artist undo.

The public tool name and existing argument/result keys remain available. Aliases
such as `parent_path`, `node_name` and `noise_basis` still resolve. Invalid inputs
are rejected instead of being truncated, ignored or substituted.

Implementation was grounded against the installed Houdini **22.0.400** parameter
menus and ports. Regression cases live in `tests/test_cops.py`. Bounded native
qualification checks real image dimensions, nonconstant pixels, frequency and
octave changes, repeated creation, and preservation of existing artist state.

References: [Fractal Noise](https://www.sidefx.com/docs/houdini/nodes/cop/fractalnoise.html),
[3D Fractal Noise](https://www.sidefx.com/docs/houdini/nodes/cop/fractalnoise3d.html),
[Layer](https://www.sidefx.com/docs/houdini/nodes/cop/layer.html).
