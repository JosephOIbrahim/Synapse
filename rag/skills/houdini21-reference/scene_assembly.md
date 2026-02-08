# USD Scene Assembly

## Reference vs Sublayer

| Method | LOP Node | Use Case | Composition |
|--------|----------|----------|-------------|
| Reference | `reference` | Import assets under a prim path | Stronger (overridable) |
| Sublayer | `sublayer` | Merge full layer into current | Strongest (direct edit) |

## Reference LOP

Imports USD content under a target prim path.

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| File Path | `filepath1` | string | Path to .usd/.usdc/.usda file |
| Prim Path | `primpath` | string | Target prim (e.g., `/World/building`) |
| Reference Type | `reftype` | menu | Reference or Payload |

### When to Use Reference
- Individual assets (characters, props, vehicles)
- Assets that need per-instance transforms
- Content that may be overridden by stronger layers

## Sublayer LOP

Merges an entire USD layer into the current stage.

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| File Path | `filepath1` | string | Path to USD file |
| Layer Position | `position` | menu | Strongest/weakest sublayer |

### When to Use Sublayer
- Environment layouts
- Lighting rigs
- Base layers that everything else builds on

## MCP Tool: houdini_reference_usd

```json
{
  "file": "D:/assets/building.usd",
  "prim_path": "/World/building",
  "mode": "reference",
  "parent": "/stage"
}
```

## Heavy USD Files (>50MB)

Expect slow initial cook (~5-30s depending on size).
Tips:
- Use Payloads instead of References for heavy assets
- Enable load masks to limit traversal
- Consider using `usdstitch` for pre-composed environments

## Typical Production Structure

```
/World
  /environment     ← sublayered USD (terrain, sky)
  /characters      ← referenced per-character USDs
    /hero
    /crowd
  /props           ← referenced prop USDs
  /lights          ← sublayered lighting rig
  /cameras         ← per-shot camera
```

## File Formats

| Extension | Description | Speed |
|-----------|-------------|-------|
| `.usdc` | Binary (Crate) | Fastest read/write |
| `.usda` | ASCII text | Human-readable, slow |
| `.usd` | Auto-detect | Extension is ambiguous |
| `.usdz` | Zipped package | AR/web delivery |
