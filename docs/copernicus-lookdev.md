# Copernicus lookdev fixture

Use the existing `synapse_solaris_build_graph` tool with the
`copernicus_lookdev` template to create an editable Solaris fixture on
Houdini **22.0.400**:

```json
{
  "parent": "/stage",
  "template": "copernicus_lookdev",
  "layout": "vertical",
  "template_params": {
    "name": "surface_study",
    "base_color": [0.18, 0.04, 0.01],
    "noise_type": "perlin",
    "frequency": 4.0,
    "octaves": 3
  }
}
```

The new subnet contains a four-point plane and UVs in its own editable SOP
network, brought into Solaris by SOP Import. A Texture Material Library provides
modern Copernicus color and scalar roughness inputs, followed by a material
binding, camera, light and preview settings. Its textures are fixed at 256×256. Use
`layout: "horizontal"` for a left-to-right outer network, or `dry_run: true`
to inspect the planned root without building.

The result identifies `root`, `output` and the editable `controls.base_color`,
`controls.roughness` and `controls.material` nodes. Change the color layer's
RGB values or the roughness generator in Houdini to explore the material.
Those later edits are not covered by an earlier build receipt.

An existing display choice is preserved. In an empty parent, Houdini makes the
first fixture the display; the result reports `display_changed` and
`display_reason`. Creating another fixture requires a new name. Reusing a name
refuses before changing the existing graph. Node/connection overlays, display
overrides and rearranging existing nodes are outside this fixed template.

`base_color` is scene-linear RGB in 0–1. Noise choices are `perlin`, `worley`,
`alligator` and `simplex`; the last is a 3D noise sampled on an XY slice.
Frequency must be finite and positive, and octaves an integer from 1 through
16. The fixture uses the installed `QuickSurfaceMaterial` dependency and
in-session `op:` texture references. It does not package textures or qualify an
export to another scene or process.

The build verifies authored settings, material ports, composed geometry/UVs,
material binding, texture references and preview settings. That inspection
evaluates geometry and textures; it is not a render and does not measure image
pixels or establish Karma appearance. Rendering and exporting remain separate
actions with their existing permissions. No output file is selected by this
template. Failed construction removes its newly owned root; incomplete cleanup
is reported rather than silently accepted.

In studio-restricted mode, the existing builder requires the `admin` role;
`viewer`, `artist` and `lead` cannot run it. The `standard` worker profile
permits the builder, while `strict` and `demo` deny it. Local-mode permissions
are unchanged.

The native regression entry is
`scripts/live_probes/probe_copernicus_lookdev.py`. Run it only through a bounded,
isolated 22.0.400 hython harness. It refuses GUI execution and other builds,
creates and removes its own parent, and exercises the real graph handler and
main-thread dispatcher. Its checks cover first build, same-name refusal,
independent horizontal construction, preservation of existing authored state,
failure after real material wiring, and invalid UV/binding rejection using a
detached copy of the real composed USD stage. It performs no render or export.
