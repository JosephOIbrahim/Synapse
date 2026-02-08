# Karma Rendering Reference

## ROP Types for /out

| Type Name | Description | Key Parms |
|-----------|-------------|-----------|
| `karma` | Native Karma driver | `picture`, `camera`, `engine` |
| `usdrender` | USD-based render driver | `loppath`, `outputimage`, `override_camera` |
| `ifd` | Mantra renderer | `vm_picture`, `camera` |
| `opengl` | OpenGL flipbook | `picture`, `camera` |

## Karma ROP in /out — Setup Checklist

1. Create: `hou.node("/out").createNode("usdrender", "render")`
2. Set `loppath` to LOP display node (e.g., `/stage/karma_settings`)
3. Set `renderer` to `BRAY_HdKarma`
4. Set `override_camera` to USD prim path (e.g., `/cameras/render_cam`)
5. Set `override_res` to `"specific"` (string, not int!)
6. Set `res_user1` (width) and `res_user2` (height)
7. Set `outputimage` to output file path

## IMPORTANT: output_file kwarg

`rop.render(output_file=...)` does NOT work for usdrender ROPs.
Must set `outputimage` or `picture` parm directly on the node.

## Karma XPU File Flush

Karma XPU has a 10-15 second delay between render() returning and the
file being fully written to disk. Poll with 0.25s interval for up to 15s.

## Camera Path

Camera must be specified as USD prim path: `/cameras/render_cam`
NOT as Houdini node path: `/stage/render_cam`

## Resolution Override

The `override_res` parameter is a STRING MENU:
- `""` — None (use USD settings)
- `"scale"` — Percentage of resolution
- `"specific"` — Specific resolution (enables res_user1/res_user2)
