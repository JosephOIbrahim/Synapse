# VEX Corpus: Field Analysis

## Triggers
attribtype, expand_udim, getattribute, hasattrib, mask_bsdf, printf,
spline, usd vex, usd_clearmetadata, usd_drawmode, usd_getbbox,
usd_isstage, usd_relationshiptargets, usd_setkind, field analysis

## Context
VEX functions for attribute inspection, USD stage queries, BSDF manipulation,
and string formatting. Reference examples from SideFX documentation.

## Code

```vex
// attribtype: get the type of an attribute
// Returns: -1=doesn't exist, 0=int, 1=float, 2=string
int type_p = attribtype(0, "point", "P");          // 1 (float/vector)
int type_id = attribtype(0, "point", "id");         // 0 (int)
int type_name = attribtype(0, "prim", "name");      // 2 (string)
int type_missing = attribtype(0, "point", "foo");   // -1 (not found)
```

```vex
// hasattrib: check if attribute or group exists
if (hasattrib(0, "point", "density")) {
    f@density = point(0, "density", @ptnum);
}
if (hasattrib(0, "pointgroup", "selected")) {
    // Group "selected" exists
    if (inpointgroup(0, "selected", @ptnum)) {
        @Cd = {1, 0, 0};
    }
}
```

```vex
// getattribute: read attribute from file or SOP path
vector pos, uv, clr;

// Read position of point 3 from a file
getattribute("defgeo.bgeo", pos, "point", "P", 3, 0);

// Read UV of vertex 2 on primitive 3
getattribute("defgeo.bgeo", uv, "vertex", "uv", 3, 2);

// Read Cd from a SOP path (Houdini only)
getattribute("op:/obj/geo1/color1", clr, "primitive", "Cd", 7);
```

```vex
// printf / sprintf: string formatting
printf("P = %g, dot(N,P) = %g, pt %d = 0x%x\n",
       @P, dot(@N, @P), @ptnum, @ptnum);
printf("RGB = {%g, %g, %g}\n", @Cd.r, @Cd.g, @Cd.b);
printf("%-20s\n", "Left justified");
printf("%+08.3g\n", length(@v));

// sprintf returns a string (useful for paths)
string map_path = sprintf("/maps/map%04d.rat", @ptnum);
s@label = sprintf("pt_%d_frame_%d", @ptnum, int(@Frame));
```

```vex
// expand_udim: resolve UDIM texture path from UV coordinates
string base_map = sprintf("%s/%s_%%(UDIM)d.rat", chs("texture_path"), chs("texture_base"));
string resolved = expand_udim(@uv.x, @uv.y, base_map);
if (resolved != "") {
    // Texture exists for this UDIM tile
    vector clr = texture(resolved, @uv.x, @uv.y);
    @Cd = clr;
}
```

```vex
// spline: interpolate through key values
// Basis types: "linear", "catrom", "bezier", "bspline"
float t = float(@ptnum) / float(@numpt - 1);

// Linear interpolation through 4 values
float val = spline("linear", t, 0.0, 0.5, 0.8, 1.0);

// Catmull-Rom (smooth) through control points
vector pos = spline("catrom", t,
    {0,0,0}, {1,1,0}, {2,0,0}, {3,1,0});
@P = pos;
```

```vex
// USD VEX functions (LOP wrangles)
// usd_isstage: check if input has a valid stage
int valid = usd_isstage(0);

// usd_drawmode: get/set prim draw mode
string mode = usd_drawmode(0, "/geo/cube");  // "default", "bounds", etc.

// usd_getbbox_center: bounding box center of a prim
vector center = usd_getbbox_center(0, "/src/sphere", "render");

// usd_relationshiptargets: get relationship targets
string targets[] = usd_relationshiptargets(0, "/geo/cube", "some_relationship");

// usd_setkind: set prim kind metadata
usd_setkind(0, "/geo/sphere", "assembly");

// usd_clearmetadata: remove custom metadata
usd_clearmetadata(0, "/geo/sphere", "customData:some_name");
```

```vex
// usd_pointinstance: query instanced geometry bounds
vector inst_min = usd_pointinstance_getbbox_min(0,
    "/src/instanced_spheres", 0, "render");
vector inst_max = usd_pointinstance_getbbox_max(0,
    "/src/instanced_spheres", 0, "render");
vector inst_size = inst_max - inst_min;
```

```vex
// mask_bsdf: filter BSDF components for LPE
// Remove refraction component from a BSDF
bsdf filtered = mask_bsdf(inF, PBR_ALL_MASK & ~PBR_REFRACT_MASK);

// Keep only diffuse
bsdf diffuse_only = mask_bsdf(inF, PBR_DIFFUSE_MASK);

// Keep only specular reflection
bsdf spec_only = mask_bsdf(inF, PBR_REFLECT_MASK);
```

## Common Mistakes
- Using getattribute with wrong class name -- must be "point", "prim", "vertex", or "detail"
- Forgetting to check expand_udim result -- returns "" if UDIM tile texture doesn't exist
- Using printf in production -- creates massive output; use only for debugging
- Wrong spline basis for smooth curves -- "linear" is piecewise linear; use "catrom" for smooth
