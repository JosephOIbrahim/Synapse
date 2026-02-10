# VEX Functions Reference

## Attribute Access

### Built-in Attributes (read/write with @)
- `@P` - Point position (vector)
- `@N` - Normal vector
- `@Cd` - Color (vector)
- `@v` - Velocity (vector)
- `@pscale` - Point scale (float)
- `@id` - Particle ID (int)
- `@orient` - Orientation quaternion (vector4)
- `@up` - Up vector for orientation (vector)
- `@rest` - Rest position for noise (vector)
- `@uv` - UV coordinates (vector)
- `@Alpha` - Point opacity (float)
- `@width` - Curve width (float)
- `@age` - Particle age in seconds (float)
- `@life` - Particle life expectancy (float)

### Context Variables (read-only)
- `@ptnum` - Current point number
- `@numpt` - Total point count
- `@primnum` - Current primitive number
- `@numprim` - Total primitive count
- `@vtxnum` - Current vertex number
- `@Frame` - Current frame number (float)
- `@Time` - Current time in seconds (float)
- `@TimeInc` - Time increment per frame
- `@OpInput1` - Path to first input (string)

### Type Prefixes
```vex
f@density = 1.0;        // float
i@id = 42;              // integer
v@velocity = {0,1,0};   // vector (3 floats)
p@orient = {0,0,0,1};   // vector4 (quaternion)
s@name = "piece1";      // string
2@xform = ident();      // matrix2
3@transform = ident();  // matrix3
4@xform4 = ident();     // matrix (4x4)
```

## Geometry Functions

### Read Attributes
- `point(input, "attr", ptnum)` - Read point attribute
- `prim(input, "attr", primnum)` - Read prim attribute
- `vertex(input, "attr", linearidx)` - Read vertex attribute
- `detail(input, "attr")` - Read detail attribute (single value for whole geo)

### Write Attributes
- `setpointattrib(geohandle, "attr", ptnum, value)` - Write point attribute
- `setprimattrib(geohandle, "attr", primnum, value)` - Write prim attribute
- `setdetailattrib(geohandle, "attr", value)` - Write detail attribute

### Create/Delete Geometry
- `addpoint(geohandle, position)` - Create new point, returns ptnum
- `addprim(geohandle, "poly")` - Create new primitive, returns primnum
- `addvertex(geohandle, primnum, ptnum)` - Add vertex to prim
- `removepoint(geohandle, ptnum)` - Delete point
- `removeprim(geohandle, primnum, andpoints)` - Delete prim (andpoints=1 to also delete points)

### Query Geometry
- `npoints(input)` - Count points on input
- `nprims(input)` - Count prims on input
- `nvertices(input)` - Count vertices on input
- `primpoints(input, primnum)` - Get point numbers of a prim
- `pointprims(input, ptnum)` - Get prim numbers connected to a point
- `primintrinsic(input, "measuredarea", primnum)` - Read intrinsic attribute

### Spatial Queries
- `nearpoint(input, pos)` - Find nearest point (returns ptnum)
- `nearpoints(input, pos, radius, maxpts)` - Find multiple nearest points
- `pcfind(input, "P", pos, radius, maxpts)` - Point cloud search (fast)
- `pcopen(input, "P", pos, radius, maxpts)` - Open point cloud handle
- `pcfilter(handle, "attr")` - Filter point cloud attribute (smooth/average)
- `pcclose(handle)` - Close point cloud handle
- `intersect(input, origin, dir, pos, u, v)` - Ray-geometry intersection
- `xyzdist(input, pos, primnum, primuv)` - Distance to nearest surface

## Math Functions

### Vector Operations
- `length(v)` - Vector length (magnitude)
- `length2(v)` - Squared length (faster, no sqrt)
- `normalize(v)` - Unit vector
- `dot(a, b)` - Dot product (alignment: 1=same, 0=perpendicular, -1=opposite)
- `cross(a, b)` - Cross product (perpendicular vector)
- `distance(a, b)` - Distance between points
- `reflect(dir, normal)` - Reflect direction off normal
- `refract(dir, normal, ior)` - Refract through surface

### Interpolation
- `lerp(a, b, t)` - Linear interpolation
- `slerp(a, b, t)` - Spherical interpolation (for quaternions/normals)
- `fit(val, omin, omax, nmin, nmax)` - Remap value range
- `fit01(val, nmin, nmax)` - Remap 0-1 to new range
- `efit(val, omin, omax, nmin, nmax)` - Remap with clamping
- `clamp(val, min, max)` - Clamp value
- `smooth(min, max, val)` - Smooth step (hermite)
- `chramp("ramp", pos)` - Evaluate ramp parameter (0-1 in, float out)

### Basic Math
- `abs(v)` - Absolute value
- `floor(v)` / `ceil(v)` / `round(v)` - Rounding
- `sign(v)` - Sign (-1, 0, or 1)
- `min(a, b)` / `max(a, b)` - Min/max
- `pow(base, exp)` - Power
- `sqrt(v)` - Square root
- `log(v)` / `log10(v)` - Logarithms
- `exp(v)` - e^v
- `sin(a)` / `cos(a)` / `tan(a)` - Trigonometry (radians)
- `asin(v)` / `acos(v)` / `atan(v)` - Inverse trig
- `atan2(y, x)` - Two-argument arctangent
- `radians(deg)` / `degrees(rad)` - Angle conversion

## Noise Functions

- `noise(pos)` - Perlin noise (0 to 1)
- `snoise(pos)` - Signed Perlin noise (-1 to 1)
- `onoise(pos)` - Original noise (Houdini classic)
- `curlnoise(pos)` - Curl noise (divergence-free -- ideal for smoke/fluid advection)
- `anoise(pos)` - Alligator noise (cellular, sharp)
- `vnoise(pos, jitter)` - Voronoi noise (returns cell distances)
- `flownoise(pos, flow)` - Flow noise (animated without sliding)
- `xnoise(pos)` - Simplex noise (faster than Perlin, fewer artifacts)

### Noise Tips
- Add `@Time` or `@Frame` to position for animated noise: `noise(@P + @Time * 0.5)`
- Multiply position to change frequency: `noise(@P * 5.0)` = higher frequency
- Layer octaves for detail: `noise(@P) * 0.5 + noise(@P*2) * 0.25 + noise(@P*4) * 0.125`
- `curlnoise` is mass-conserving -- use for velocity fields, smoke turbulence

## String Functions

- `sprintf(fmt, ...)` - Format string (like C printf)
- `concat(a, b)` - Concatenate strings
- `strlen(s)` - String length
- `substr(s, start, len)` - Substring
- `match(pattern, s)` - Glob pattern match (returns 1 or 0)
- `re_match(pattern, s)` - Regex match
- `split(s, sep)` - Split string into array
- `join(sep, array)` - Join array into string
- `strip(s)` - Trim whitespace
- `replace(s, old, new)` - Replace substring

## Channel Functions

- `ch("parm")` - Read float channel (from node parameters)
- `chs("parm")` - Read string channel
- `chv("parm")` - Read vector channel
- `chi("parm")` - Read integer channel
- `chramp("ramp", pos)` - Evaluate ramp parameter
- `chf("../other_node/parm")` - Read from another node (relative path)

## Matrix Functions

- `maketransform(order, xyz, t, r, s)` - Build transform matrix
- `invert(m)` - Invert matrix
- `transpose(m)` - Transpose matrix
- `determinant(m)` - Matrix determinant
- `identity()` - Identity matrix 4x4
- `lookat(from, to, up)` - Build look-at rotation matrix
- `dihedral(a, b)` - Rotation matrix from vector a to vector b
- `quaternion(angle, axis)` - Create quaternion from angle-axis
- `qrotate(quat, vector)` - Rotate vector by quaternion
- `eulertoquaternion(r, order)` - Euler angles to quaternion

## Utility

- `printf("msg %g\\n", val)` - Debug print to Houdini console
- `warning("msg")` - Raise node warning
- `error("msg")` - Raise node error (stops cooking)
- `assert(condition)` - Assert condition
- `rand(@ptnum)` - Random float 0-1 per point (deterministic from seed)
- `random(seed)` - Random vector from seed
- `set(x, y, z)` - Create vector from components
- `getcomp(v, idx)` - Get vector component by index
- `setcomp(v, val, idx)` - Set vector component by index
- `array(a, b, c)` - Create array

## Common VEX Patterns

### Scatter with Constraints
```vex
// Remove points below a height threshold
if (@P.y < ch("min_height")) removepoint(0, @ptnum);
```

### Orient from Normal
```vex
// Set orient quaternion from N and up for copy-to-points
v@up = set(0, 1, 0);
p@orient = dihedral(set(0, 0, 1), @N);
```

### Color by Attribute
```vex
// Color by height with ramp
float height = fit(@P.y, ch("min_y"), ch("max_y"), 0, 1);
v@Cd = chramp("color_ramp", height);
```

### Custom Deformer
```vex
// Sine wave deformation
float amp = ch("amplitude");
float freq = ch("frequency");
@P.y += sin(@P.x * freq + @Time * 2) * amp;
```

### Group by Expression
```vex
// Add to group based on condition
if (@P.y > ch("threshold")) i@group_top = 1;
```

### Point Cloud Averaging
```vex
// Smooth positions using neighbors
int handle = pcopen(0, "P", @P, ch("radius"), chi("maxpts"));
@P = pcfilter(handle, "P");
pcclose(handle);
```

### Random Attribute from ID
```vex
// Stable random value per piece (survives point reorder)
f@rand_val = rand(i@id * 12345 + 67890);
v@Cd = set(rand(i@id), rand(i@id+1), rand(i@id+2));
```
