# Joy of VEX: Surface Sampling

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
@P = minpos(1, @P);  // Snapping Points to Geometry
vector uv = chv('uv');  // UV-based Position Lookup
vector up = chv('up');  // primuv function introduction
```

## Distance Queries

### Distance to Secondary Input Geometry [Needs Review] [[Ep3, 32:48](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1968s)]
```vex
vector pos = minpos(1, @P);
float dist = distance(@P, pos);
@Cd = chramp("calc", dist);
@Cd.r = sin(dist);
```
Calculates the distance from each point to the closest point on a secondary input geometry using minpos(). The distance value is used to drive color through a ramp parameter and sine function, demonstrating how distances can respect the shape of the input geometry rather than using simple spatial calculations.

## primuv Sampling

### primuv function introduction [Needs Review] [[Ep8, 22:12](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1332s)]
```vex
vector up = chv('up');

@P = primuv(0, "N", @ptnum, u);
```
Introduces the primuv() function which samples an attribute value from a primitive surface at a given parametric UV coordinate. The code sets up a vector parameter 'up' and uses primuv to set point positions based on sampling the Normal attribute, though the parameters appear incomplete or示範性的 for introduction purposes.

### Sample Position and Normal with primuv [[Ep8, 22:14](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1334s)]
```vex
vector uv = chv('uv');

@P = primuv(0, 'P', @ptnum, uv);
@N = primuv(1, 'N', @ptnum, uv);
// This code samples position and normal attributes from primitives using UV coordinates. The primuv() function interpolates attributes at a UV location on a primitive, reading @P from input 0 and @N from input 1, with the UV coordinates controlled by a channel vector parameter.
```

### Sample Surface with primuv [[Ep8, 24:12](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1452s)]
```vex
vector uv = chv('uv');

@P = primuv(1, "P", 0, uv);
@N = primuv(1, "N", 0, uv);
```
Uses primuv() to sample position and normal attributes from a surface geometry (input 1) at UV coordinates specified by a channel reference parameter. This allows positioning a point on a surface by evaluating primitive attributes at specific UV coordinates, with the rubber toy being copied to points sampled from a grid.

### Sampling Attributes with primuv [[Ep8, 25:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1524s)]
```vex
vector uv = chv('uv');

@P = primuv(1, 'P', @v, uv);
@N = primuv(1, 'N', @v, uv);
// Uses primuv() to sample position and normal attributes from a second input geometry at specific UV coordinates. The UV coordinates are driven by a channel parameter, allowing interactive control over the sampling position on the primitive.
```

### Sampling Geometry with primuv [[Ep8, 25:40](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1540s)]
```vex
vector uv = chv('uv');

@P = primuv(1, 'P', @u, @v);
@N = primuv(1, 'N', @u, @v);
// Uses primuv() to sample position and normal attributes from a second input geometry based on UV coordinates. The UV parameter is exposed as a channel reference allowing interactive control, while @u and @v intrinsic attributes specify the parametric location on the primitive.
```

### UV-based Position Lookup [[Ep8, 26:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1584s)]
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
// Uses a channel parameter to define a UV coordinate, then looks up the position attribute at that UV location on primitive 0 of the first input geometry. This allows interactive sampling of positions across a primitive's surface using UV coordinates.
```

### primuv sampling position and normal [[Ep8, 27:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1658s)]
```vex
vector uv = chv('uv');

@P = primuv(1, "P", v, uv);
@N = primuv(1, "N", v, uv);
```
Uses primuv() to sample both position and normal attributes from a primitive at UV coordinates specified by a channel parameter. The sampled position and normal are assigned to the current point's @P and @N attributes, effectively moving and orienting the point to match the sampled surface location.

### Sampling UV Position and Normal [[Ep8, 27:52](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1672s)]
```vex
vector uv = chv('uv');

vector gx = primuv(1, 'P', 0, uv);
vector gN = primuv(1, 'N', 1, uv);
// Retrieves a UV coordinate from a channel parameter and uses it to sample both position (P) and normal (N) attributes from a grid primitive. The primuv function samples attributes at parametric UV coordinates on a primitive surface, with the second call sampling from primitive 1.
```

### UV primitive attribute sampling [Needs Review] [[Ep8, 27:56](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1676s)]
```vex
vector uv = chv('uv');

v@P = primuv(1, 'P', 0, uv);
v@N = primuv(1, 'N', 0, uv);
```
Uses primuv() to sample position and normal attributes from a primitive on input 1 at UV coordinates specified by a channel parameter. The UV parameter controls which location on the primitive surface to sample, allowing interactive exploration of attribute values across the primitive's parametric space.

### Sampling Position and Normal with primuv [Needs Review] [[Ep8, 28:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1714s)]
```vex
vector uv = chv('uv');

@P = primuv(0, '', 'P', 0, uv);
@N = primuv(0, '', 'N', 0, uv);
// Uses primuv() to sample both position and normal attributes from a primitive using UV coordinates. The UV coordinates are controlled via a channel reference parameter, allowing interactive exploration of different UV positions on the primitive surface.
```

### primuv for UV lookup [[Ep8, 29:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1778s)]
```vex
vector uv = chv('uv');

@P = primuv(1, 'P', @ptnum, uv);
@N = primuv(1, 'N', 0, uv);
```
Uses primuv() to sample position and normal attributes from the second input geometry at UV coordinates. The position lookup uses @ptnum to sample different primitives per point, while the normal lookup samples only primitive 0, demonstrating two different primitive sampling patterns with the same UV coordinates from a channel parameter.

### primuv function introduction [[Ep8, 29:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1794s)]
```vex
vector uv = chv('uv');

primuv(1, 'P', 0, uv);
primuv(1, 'N', 0, uv);

vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
// The primuv() function samples attribute values from a primitive at a specific UV coordinate. It takes the input geometry index (1 = second input), attribute name to read, primitive number, and a UV vector position to sample from.
```

### Sample Surface with primuv [[Ep8, 30:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1858s)]
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Uses primuv() to sample position and normal from a surface at UV coordinates controlled by a parameter. The UV coordinates are read from a channel parameter and used to extract interpolated P and N attributes from primitive 0 on the second input. The resulting point is positioned and oriented according to the sampled surface data.

### Circular Motion with primuv [Needs Review] [[Ep8, 33:06](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1986s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.5, 2);
@P += {0, 3, uv.x};

@P = primuv(0, 'P', 0, uv);
// Creates circular motion by using sin/cos with @Time to generate UV coordinates, then uses primuv() to sample a position from the first input geometry. The UV coordinates are animated in a circle and remapped from [-1,1] to [0.5,2] range before sampling the primitive surface.
```

### Circular Motion via primuv [[Ep8, 33:08](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1988s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0, 2);

uv *= {0.5, 0.5};

@P = primuv('p', 'P', 0, uv);
// Creates circular motion by using sine and cosine of time to generate UV coordinates, then samples a position on a primitive using primuv(). The sine/cosine values are fitted from [-1,1] to [0,2] range and scaled by 0.5 to keep the motion within primitive bounds.
```

### Circular Motion with primuv [[Ep8, 33:12](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1992s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0, 0.2);
uv += {0.5, 0.5};

@P = primuv(1, 'P', 0, uv);
```
Creates circular motion by generating UV coordinates using sin/cos of time, then remapping the values to a small range centered at (0.5, 0.5) to sample positions from the primitive on input 1. The primuv function samples the position attribute at the calculated UV coordinate on primitive 0 of input 1.

### Circular Motion with primuv [[Ep8, 33:14](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1994s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.5);
uv += {0.5, 0.5};

@P = primuv(0, 'P', u, uv);
@N = primuv(1, 'N', u, uv);
```
Creates circular motion by using sine and cosine of time to generate UV coordinates that move in a circle. The UV values are fitted from the sine/cosine range (-1 to 1) into a smaller range (0.2 to 0.5) and offset to center, then used with primuv to sample position and normal from input geometries, causing an object to orbit in a circular path on a surface.

### Circular UV Motion Sampling [Needs Review] [[Ep8, 33:16](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1996s)]
```vex
vector uv;

uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += set(0.5, 0.5, 0);

@P = primuv(0, 'P', uv);
@N = primuv(1, 'N', uv);
```
Animates a point in circular motion by using sine and cosine of the frame number to generate UV coordinates, then samples position and normal attributes from input geometries using primuv(). The UV coordinates are fitted from the -1 to 1 range into a smaller 0.2 to 0.2 range and offset by 0.5 to center the motion in UV space.

### Circular Motion with primuv [Needs Review] [[Ep8, 33:18](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1998s)]
```vex
vector uv;

uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += {0.5, 0.5};

@P = primuv(0, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates circular motion by using sine and cosine of the frame number to generate UV coordinates, then samples position and normal attributes from primitives using primuv(). The UV values are fitted from the -1 to 1 range into 0.2 to 0.2 (likely meant to be a smaller range) and offset by 0.5 to center them, allowing an object to move in a circular path on a surface while sampling normals for orientation.

### Animating UV sampling with trigonometry [[Ep8, 33:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2004s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += {0.5, 0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates circular motion by computing UV coordinates using sine and cosine functions driven by @Time, then samples position and normal attributes from input 1 at those animated UV coordinates. The fit() function remaps the -1 to 1 range of trig functions to 0.2 to 0.8, then offsets by 0.5 to center the circular path in UV space.

### Circular UV Animation with Primuv [[Ep8, 35:08](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2108s)]
```vex
vector uv;

uv.x = sin(6*@Time*2);
uv.y = cos(6*@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += set(0.5, 0.5, 0);

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates circular motion by using sine and cosine functions with the same time-based input on different UV axes. The UV coordinates are generated in a circular path, scaled down using fit() to a smaller range (-0.2 to 0.2), then offset to center (0.5, 0.5) before sampling position and normal attributes from a surface primitive using primuv().

### Circular UV Animation with Fit [[Ep8, 35:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2138s)]
```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates circular motion by combining sin and cos functions with @Time for UV coordinates, then remaps the range from [-1,1] to [-0.2,0.2] using fit() to scale down the motion. The resulting UV coordinates are used with primuv() to sample position and normal attributes from input 1, creating an animated point that moves in a small circle on a surface.

### Circular UV Animation with primuv [Needs Review] [[Ep8, 36:46](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2206s)]
```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates circular animation by calculating UV coordinates using sine and cosine of time, fitting the range from -1,1 to -0.2,0.2, then offsetting by 0.5 to center. Uses primuv to sample position and normal from input geometry at the animated UV coordinates, causing the point to orbit around the primitive surface.

### Circular UV animation with primuv [[Ep8, 36:48](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2208s)]
```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates a circular motion path by using sin and cos of time to generate UV coordinates that animate in a circle. The UV values are fitted to a smaller range (-0.2 to 0.2) then offset to center (0.5, 0.5), and primuv samples both position and normal from input 1 at those animated UV coordinates, causing geometry to rotate around in a circle while maintaining orientation based on the surface normal.

### Circular UV Animation with primuv [[Ep8, 37:00](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2220s)]
```vex
vector uv;

uv.x = sin($T*$TPI*2);
uv.y = cos($T*$TPI*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

@P = primuv(1, "P", 0, uv);
@N = primuv(1, "N", 0, uv);
```
Creates circular motion by calculating UV coordinates using sin and cos functions, then uses primuv to sample both position and normal from a surface geometry (input 1). The UV values are animated with $T, fitted to a small range around the center (0.3-0.7), and used to position and orient a point on a NURBS or polygon surface.

### Circular UV Animation with primuv [[Ep8, 37:02](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2222s)]
```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

@P = primuv(1, "P", 0, uv);
@N = primuv(1, "N", 0, uv);
```
Creates circular motion by using sine and cosine of time to generate UV coordinates, fitting them to a constrained range around the center (0.5, 0.5), then sampling position and normal attributes from input 1 at those UV coordinates using primuv. The object moves in a circular path on a surface (grid or NURBS) while maintaining orientation based on the surface normal.

### Animated UV Sampling on NURBS [Needs Review] [[Ep8, 37:08](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2228s)]
```vex
vector uv;

uv.x = sin(@Time * 10);
uv.y = cos(@Time * 10);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += {0.5, 0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates animated UV coordinates using sine and cosine of time, fits them to a specific range, then samples position and normal attributes from a NURBS surface at those UV coordinates. The circular motion causes an object to orbit on the surface while maintaining orientation based on the surface normal, though orientation can fluctuate as the frame of reference shifts.

### Animating Points on NURBS Surface with UV [Needs Review] [[Ep8, 37:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2244s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

vector UV = fit(uv, -1, 1, 0.2, 0.8);
UV += {0.5, 0.5, 0};

@P = primuv(1, 'P', 0, UV);
@N = primuv(1, 'N', 0, UV);
```
Creates animated circular motion on a surface by calculating UV coordinates using sine and cosine of time, fitting them to a specific range, then sampling position and normal attributes from a NURBS surface at those UV coordinates. The technique works on both polygon and NURBS surfaces, demonstrating primuv's versatility for surface-based animation.

### Animating Point on NURBS Surface [[Ep8, 37:30](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2250s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += {0.5, 0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates a circular animation path on a NURBS surface by generating UV coordinates using sine and cosine of time. The UV coordinates are fitted to a smaller range (0.2 to 0.2) and centered at 0.5 to create circular motion within the surface's parametric space. The primuv function samples both position and normal from the surface at the calculated UV coordinates.

### UV Sampling Animated NURBS Surface [Needs Review] [[Ep8, 37:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2258s)]
```vex
vector uv;

uv.x = sin(@Time*u);
uv.y = cos(@Time*u);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += set(0.5, 0.5, 0.0);

@P = primuv(1, 'P', u, uv);
@N = primuv(1, 'N', u, uv);
```
Samples position and normal attributes from a NURBS surface (input 1) using dynamically calculated UV coordinates that animate in a circular pattern over time. The UV coordinates are generated using sine and cosine functions, remapped from -1,1 to 0.2,0.8 range, then offset to center the sampling region, with primuv() extracting both position and normal at those coordinates.

### Animated UV Surface Sampling [Needs Review] [[Ep8, 38:02](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2282s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

v@UV = fit(uv, -1, 1, 0.2, 0.2);
v@UV += {0.5, 0.5};

@P = primuv(1, 'P', @primnum, v@UV);
@N = primuv(1, 'N', @primnum, v@UV);
// Creates animated UV coordinates using sine and cosine of time, fits them to a normalized range centered at 0.5, then samples position and normal attributes from a reference geometry's surface using those UV coordinates. This creates points that ride along an animated path on a deforming surface.
```

### Animated UV sampling on surface [Needs Review] [[Ep8, 38:04](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2284s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

UV = fit(uv, -1, 1, 0.2, 0.8);
UV += {0.5, 0.5};

@P = primuv(1, 'P', 0, UV);
@N = primuv(1, 'N', 0, UV);
// Creates animated UV coordinates using sine and cosine functions driven by @Time, remaps them from -1:1 range to 0.2:0.8, offsets by 0.5 to center, then samples position and normal attributes from a surface using primuv. This allows points to ride along an animated deforming surface.
```

### Animating Point on Surface with UV [Needs Review] [[Ep8, 38:08](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2288s)]
```vex
vector uv;

uv.x = sin(@Time*4);
uv.y = cos(@Time*4);

vector UV = fit(uv, -1, 1, 0.2, 0.8);
UV += {0.5, 0.5, 0};

@P = primuv(1, 'P', 0, UV);
@N = primuv(1, 'N', 0, UV);
// Creates an animated UV coordinate using sine and cosine of time, fits the range to (0.2-0.8), offsets to center, then samples position and normal from a surface geometry at input 1 using primuv. This produces a point that rides along an animated path on the surface.
```

### Animated UV Surface Sampling [Needs Review] [[Ep8, 38:10](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2290s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

UV = fit(uv, -1, 1, 0.2, 0.8);
UV += (0.5, 0.5);

@P = primuv(1, 'P', 0, UV);
@N = primuv(1, 'N', 0, UV);
// Creates animated UV coordinates using sine and cosine of @Time multiplied by 10, fits them to a range, then uses primuv() to sample position and normal attributes from input 1 at those UV coordinates. This causes a point to ride along an animated deformed surface.
```

### Animating Points on Surface with primuv [Needs Review] [[Ep8, 38:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2300s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

@P = primuv(1, 'P', @primnum, uv);
@N = primuv(1, 'N', @primnum, uv);
```
Animates a point riding along a surface by computing UV coordinates using sine and cosine of @Time, fitting them to a small range around (0.5, 0.5), then sampling position and normal from a reference surface using primuv(). This creates smooth surface-following motion useful for effects like boats on water or objects attached to animated geometry.

### Animating Point on Surface with UV [Needs Review] [[Ep8, 38:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2304s)]
```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += {0.5, 0.5};

@P = primuv(0, "P", 0, uv);
@N = primuv(0, "N", 0, uv);
```
Animates a point's position and normal by sampling UV coordinates that move in a circular pattern on a surface. The UV coordinates are driven by sine and cosine of time, fitted to a range, then used with primuv to extract position and normal from the first input geometry, demonstrating how to attach objects to animated surfaces like boats on an ocean.

### Animated UV Surface Sampling [[Ep8, 38:26](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2306s)]
```vex
vector uv;

uv.x = sin(@Time*u);
uv.y = cos(@Time*u);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += set(0.5, 0.5, 0);

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates animated UV coordinates using sine and cosine functions driven by time, then samples position and normal data from a reference surface at those coordinates. The UV values oscillate smoothly over time and are fitted to a range centered at (0.5, 0.5), allowing a point to ride along the surface of another geometry, useful for effects like boats on ocean surfaces.

### Animating Point on Surface with primuv [[Ep8, 38:36](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2316s)]
```vex
uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += {0.2, 0.5};

@P = primuv(1, 'P', uv);
@N = primuv(1, 'N', uv);
```
This code animates a point riding along a surface by calculating UV coordinates that vary with the frame number using sine and cosine functions. The UV values are remapped using fit() and offset, then used with primuv() to sample both position and normal from a reference geometry (input 1), causing the point to stick to and follow the surface topology.

### Animating Point on Surface with primuv [Needs Review] [[Ep8, 39:06](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2346s)]
```vex
uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

UV = fit(uv, -1, 1, 0.2, 0.2);
UV += {0.2, 0.5};

@P = primuv(1, 'P', v.uv);
@N = primuv(1, 'N', v.uv);
```
Demonstrates attaching a point to an animated surface position using primuv(). UV coordinates are calculated using sine and cosine of the frame number to create circular motion, fitted to a range, then used to sample both position and normal from a primitive surface. This technique can be used for practical scenarios like attaching a boat to an ocean surface.

### Attaching Object to Surface Using primuv [[Ep8, 39:08](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2348s)]
```vex
vector uv;

uv.x = sin($T*2);
uv.y = cos($T*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Demonstrates attaching a point to an animated surface position using primuv() lookups. The UV coordinates are animated using sine and cosine functions, fitted to a constrained range, then offset to center around 0.5. Both position and normal are sampled from the surface to properly orient the attached point.

### Parametric UV Sampling with Primuv [Needs Review] [[Ep8, 39:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2378s)]
```vex
vector uv;

uv.x = sin(PI*ue**2);
uv.y = cos(PI*ue**2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
// Creates animated UV coordinates using sine and cosine functions based on a time variable, fits them to a smaller range centered at 0.5, then samples position and normal attributes from a primitive using primuv. This moves a point around on a surface by sampling different UV locations over time.
```

### Animated UV Sampling with Primuv [[Ep8, 39:40](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2380s)]
```vex
vector uv;

uv.x = sin(@id*@Time*2);
uv.y = cos(@id*@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
Creates animated UV coordinates using sine and cosine functions driven by point id and time, then uses primuv() to sample both position and normal attributes from a NURBS surface, causing points to move around in 3D space based on the animated UV lookup. The UV coordinates are fitted to a narrow range around the center (0.5, 0.5) of the surface parametric space.

### Parametric UV Lookup per Primitive [[Ep8, 42:26](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2546s)]
```vex
vector uv;

uv.x = sin(6*Time*2);
uv.y = cos(6*Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
This code demonstrates parametric UV lookups on a specific primitive (primitive 0) using animated sine and cosine values. The UV coordinates are calculated per-primitive, not globally across the entire surface, which means changing the grid resolution affects which primitive is being sampled. The Time-based animation creates a circular motion pattern that samples position and normal attributes from the primitive's parametric space.

### Primitive UV Lookup Animation [[Ep8, 42:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2558s)]
```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

@P = primuv(1, "P", 0, uv);
@N = primuv(1, "N", 0, uv);
```
Animates a point's position and normal by using sine and cosine functions to generate circular UV coordinates over time, then uses primuv() to look up position and normal attributes from primitive 0 of the second input at those parametric coordinates. The UV values are fit from the sine/cosine range (-1 to 1) to a smaller range (-0.2 to 0.2) and offset to center around (0.5, 0.5).

## Distance Queries

### xyzdist with UV and prim attributes [[Ep8, 45:00](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2700s)]
```vex
i@prim1d;
v@uv;
@dist;

@dist = xyzdist(1, @P, @prim1d, @uv);
```
Uses xyzdist() to find the closest point on geometry from input 1, storing the resulting primitive ID in @prim1d and UV coordinates in @uv. The function returns the distance which is stored in @dist. Note that UV sampling requires a separate function (uvsample), and this demonstrates how primitive-based geometry like tubes, spheres, and discs have their own UV space calculations.

### xyzdist on Primitive Surfaces [[Ep8, 45:04](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2704s)]
```vex
i@grid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```
Demonstrates using xyzdist() on non-polygonal primitive surfaces like tubes, spheres, and discs to compute UV coordinates. When geometry lacks explicit UVs, Houdini renderers use per-face UV coordinates calculated through primitive intrinsics, which is why default grids show tiled textures per face.

## primuv Sampling

### xyzdist Function Introduction [Needs Review] [[Ep8, 45:30](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2730s)]
```vex
@P = primuv;
@Cd = v;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```
The xyzdist() function finds the closest point on a geometry and returns the distance, while also writing the primitive ID and UV coordinates to output variables. This is a powerful complement to primuv() - where primuv() retrieves attributes given a UV location, xyzdist() finds the UV location of the nearest surface point.

## Distance Queries

### xyzdist Introduction [[Ep8, 46:36](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2796s)]
```vex
@grid;
v@v;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
// The xyzdist function finds the minimum distance from a point to a surface geometry and outputs the primitive ID and UV coordinates of the closest point on that surface. This allows you to bridge the concept of finding the closest point on geometry with looking up attributes at that location.
```

## primuv Sampling

### XYZ Distance Setup with UV Sampling [Needs Review] [[Ep8, 47:32](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2852s)]
```vex
int prim = 0;
vector uv;
f@dist;

uv = fit(uv, -1, 1, -0.2, 0.2);
uv *= {0.5, 0.5};

@P = primuv(1, "P", 0, uv);
@N = primuv(1, "N", 0, uv);
// Initializes variables for distance calculations and UV-based primitive sampling. The code prepares a UV coordinate system that is fitted and scaled, then uses primuv to sample position and normal attributes from a primitive surface at the calculated UV coordinates.
```

## Distance Queries

### xyzdist primitive distance query [[Ep8, 48:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2934s)]
```vex
i@ptnum1;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```
Uses xyzdist() to find the closest point on input geometry (input 1) to the current point position. The function returns the distance and writes the primitive ID and parametric UV coordinates of the closest location into the specified variables, demonstrating how xyzdist provides multiple outputs through parameter references.

### xyzdist Multi-Output Pattern [[Ep8, 49:36](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2976s)]
```vex
i@grid;
v@uv;
@ui1;

@ui1 = xyzdist(1, @P, @grid, @uv);
```
The xyzdist() function returns the distance to the closest point on a geometry surface while simultaneously writing additional data (primitive ID and UV coordinates) to referenced variables. This multi-output pattern allows a single function call to populate multiple attributes: the return value becomes the distance (@ui1), while the primitive ID is written to @grid and the parametric UV position is written to @uv.

### xyzdist multi-value return [[Ep8, 49:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2998s)]
```vex
i@primid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```
The xyzdist() function demonstrates VEX's ability to return multiple values from a single function call. While the function returns the distance value explicitly, it also writes the closest primitive ID and UV coordinates into the variables passed by reference (indicated by the ampersand & in the function signature). This allows you to retrieve three pieces of information - distance, primitive ID, and UV coordinates - from one function call.

### xyzdist Distance and UV Calculation [[Ep8, 51:40](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3100s)]
```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```
The xyzdist function calculates the distance from the current point to the closest point on a surface (input 1), while simultaneously returning the closest primitive ID and UV coordinates via reference arguments. This provides three pieces of information in a single operation: distance stored in @dist, primitive ID in @primid, and parametric UV coordinates in @uv.

## primuv Sampling

### xyzdist and primuv combined lookup [[Ep8, 52:00](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3120s)]
```vex
int @primid;
vector @uv;
float @dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, "P", @primid, @uv);
// Uses xyzdist() to find the closest point on a surface (input 1), which returns the distance, primitive ID, and UV coordinates. Then uses primuv() to look up the actual position at those UV coordinates, effectively snapping points to the closest location on the target surface.
```

### Transferring Attributes with primuv [[Ep8, 53:00](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3180s)]
```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```
Uses xyzdist to find the closest primitive and UV coordinates on input 1, then uses primuv to snap the point position to the surface and transfer the color attribute from that surface location. The primuv function allows querying any attribute (not just position) from a specific primitive at UV coordinates, making it more versatile than minpos for attribute transfer.

### Sample Color with primuv [[Ep8, 53:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3214s)]
```vex
int @primid;
vector @uv;
float @dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```
After using xyzdist() to find the closest point on a geometry and get its primitive ID and UV coordinates, primuv() can be used to sample not just position but also other attributes like color. This demonstrates how to transfer color (@Cd) from a source geometry to points by sampling at the closest UV location.

### Transferring Color with primuv [[Ep8, 53:46](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3226s)]
```vex
int primid;
v@uv;
float dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```
This code finds the nearest point on a reference geometry using xyzdist() to get the primitive ID and UV coordinates, then uses primuv() to both relocate the point position and transfer the color attribute from the reference geometry. This technique allows points to inherit both position and color from a surface while maintaining parametric UV relationships.

### Reading Color from Closest Surface Point [[Ep8, 54:12](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3252s)]
```vex
i@prim1id;
v@uv;
@dist;

@dist = xyzdist(1, @P, @prim1id, @uv);

@P = primuv(1, 'P', @prim1id, @uv);

@Cd = primuv(1, 'Cd', @prim1id, @uv);
// Uses xyzdist to find the closest primitive and UV coordinates on a grid surface from a point in space, then uses primuv to sample both the position and color attributes at that UV location. This allows a point to snap to the grid surface while also inheriting the color from that surface location.
```

### Reading Primitive Color with primuv [[Ep8, 54:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3278s)]
```vex
i@primId;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primId, @uv);

@P = primuv(1, 'P', @primId, @uv);
@Cd = primuv(1, 'Cd', @primId, @uv);
```
Uses xyzdist() to find the closest primitive on input 1 (a grid) and stores the primitive ID and UV coordinates. Then uses primuv() to read both the position and color (Cd) attributes from that primitive at those UV coordinates, effectively sampling color data from the closest point on the grid geometry.

### Attribute Interpolation with primuv [[Ep8, 56:30](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3390s)]
```vex
@dist = xyzdist(1, @P, @primid, @uv);

v@c = primuv(1, 'P', @primid, @uv);
v@cd = primuv(1, 'Cd', @primid, @uv);
```
Uses xyzdist to find the closest primitive and UV coordinates on a source geometry, then uses primuv to interpolate position and color attributes from that source primitive at the found UV location. This technique allows you to sample and transfer attributes from one geometry to another based on proximity, which can also be achieved using the Attribute Interpolate SOP.

## Distance Queries

### Snapping Points to Geometry [[Ep8, 71:04](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4264s)]
```vex
@P = minpos(1, @P);
```
Uses minpos() to snap each point to the nearest position on the geometry connected to the second input, causing points to track to the closest surface position as they move. As animated points rotate around the target geometry, they continuously snap to the nearest point on its surface rather than smoothly sliding across it.

## See Also
- **VEX Functions Reference** (`vex_functions.md`) -- primuv, xyzdist function signatures
