# TOPs/PDG Wedging Reference

## What is Wedging?

Wedging generates parameter variations automatically. Use it for:
- Material lookdev (roughness sweeps)
- Lighting variations (intensity ranges)
- Render quality presets
- Simulation parameter exploration

## Network Structure

Create a `topnet` at `/obj` level. Inside:

```
wedge → ropfetch (or other processor)
```

## Wedge Node Key Parameters

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| Wedge Count | `wedgecount` | int | Number of variations |
| Wedge Attributes | `wedgeattribs` | string | Attribute name to create |
| Type | `type` | menu | Random, Range, or Specific values |
| Range Start | `range1` | float | Start of range |
| Range End | `range2` | float | End of range |

## MCP Tool: houdini_wedge

```json
{
  "node": "/obj/topnet1/wedge1",
  "parm": "roughness",
  "values": [0.1, 0.3, 0.5, 0.7, 0.9]
}
```

The handler creates work items for each value and cooks the network.

## ropfetch Node

Fetches a ROP and renders for each wedge variation:
- `roppath`: Path to the render ROP (e.g., `/out/karma1`)
- `pdg_workitemindex`: Auto-set per work item

## Channel References

To use wedge values in your scene, use:
```
`@wedge_roughness`
```
in any parameter expression. TOPs injects the attribute at cook time.

## Typical Workflows

### Roughness Sweep
```
wedge(roughness: 0.0 → 1.0, 10 steps) → ropfetch → imagemagick_montage
```

### Light Intensity Sweep
```
wedge(intensity: 1.0 → 10.0, 5 steps) → ropfetch
```

### Multi-Parameter Wedge
Stack multiple wedge nodes for combinatorial exploration:
```
wedge1(color: red,green,blue) → wedge2(roughness: 0.2,0.5,0.8) → ropfetch
```
Generates 3 x 3 = 9 variations.
