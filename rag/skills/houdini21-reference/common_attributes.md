# Common Houdini Geometry Attributes

## Point Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `P` | vector3 | Position (x, y, z) |
| `N` | vector3 | Normal vector |
| `Cd` | vector3 | Color (r, g, b) in 0-1 range |
| `Alpha` | float | Opacity (0=transparent, 1=opaque) |
| `v` | vector3 | Velocity (units/second) |
| `w` | vector4 | Angular velocity (quaternion) |
| `orient` | vector4 | Orientation quaternion |
| `pscale` | float | Point scale (uniform) |
| `scale` | vector3 | Non-uniform scale |
| `up` | vector3 | Up vector (for copy-to-points) |
| `id` | int | Stable particle ID (survives death/birth) |
| `age` | float | Particle age in seconds |
| `life` | float | Particle lifespan in seconds |
| `rest` | vector3 | Rest position (for texturing deforming geo) |
| `uv` | vector3 | UV texture coordinates |
| `shop_materialpath` | string | Material assignment path |

## Primitive Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | string | Prim group name (used by Solaris for USD paths) |
| `shop_materialpath` | string | Per-prim material assignment |
| `path` | string | USD/Alembic hierarchy path |

## Detail Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `varmap` | string | Variable mapping for shaders |

## Vertex Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `uv` | vector3 | Per-vertex UV (overrides point UV) |
| `N` | vector3 | Per-vertex normal (overrides point normal) |
| `Cd` | vector3 | Per-vertex color |

## Special Attributes for Copy-to-Points
The `copytopoints` SOP reads these from target points:
- `P` - Position (required)
- `orient` - Quaternion rotation (highest priority)
- `N` + `up` - Rotation from normal+up (if no orient)
- `pscale` - Uniform scale
- `scale` - Non-uniform scale (vector3)
- `v` - Velocity (for motion blur)

## Pyro/Volume Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `density` | float | Smoke/fire density (0-1+) |
| `temperature` | float | Heat for buoyancy |
| `flame` | float | Visible flame (0-1) |
| `fuel` | float | Combustible fuel |
| `vel` | vector3 | Volume velocity field |

## FLIP Fluid Attributes
| Attribute | Type | Description |
|-----------|------|-------------|
| `viscosity` | float | Per-particle viscosity override |
| `surface` | float | Surface distance (from particlefluidsurface) |
| `vorticity` | vector3 | Curl of velocity field |
| `droplet` | float | Isolated particle flag (for spray meshing) |

## Constraints (RBD)
| Attribute | Type | Description |
|-----------|------|-------------|
| `constraint_name` | string | Constraint type identifier |
| `constraint_type` | int | 0=position, 1=rotation |
| `strength` | float | Breaking threshold |
| `anchor_name` | string | Connected piece name |

## Intrinsic Attributes (read via primintrinsic())
| Attribute | Description |
|-----------|-------------|
| `measuredarea` | Surface area of prim |
| `measuredperimeter` | Perimeter of prim |
| `measuredvolume` | Volume of closed mesh |
| `typename` | Prim type ("Poly", "BezierCurve", etc.) |
| `packedfulltransform` | Full transform of packed prim |
