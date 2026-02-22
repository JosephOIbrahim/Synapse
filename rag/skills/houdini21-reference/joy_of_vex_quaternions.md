# Joy of VEX: Quaternions

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
@orient = slerp(base, target, blend);  // Spherical Interpolation with Orient
float angle = ch('angle');  // Quaternion from Angle and Axis
@N = normalize(@P);  // Quaternion Extra Rotation
```

## Orient Attribute

### Quaternion Extra Rotation [[Ep7, 100:40](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6040s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(PI/2, {1,0,0});
```
Creates a quaternion representing a 90-degree rotation around the x-axis using the quaternion() function with PI/2 as the angle and (1,0,0) as the axis. This extra rotation quaternion will be combined with the existing @orient attribute to allow blending between different orientations, similar to manually rotating by 90 degrees in X in a transform node.

### Combining Quaternion Rotations [[Ep7, 101:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6074s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N,@up));

vector4 extrarot = quaternion($PI/2, {1,0,0});

@orient = qmultiply(@orient, extrarot);
```
Creates an orientation quaternion from normalized position and up vector, then applies an additional 90-degree rotation around the X-axis using quaternion multiplication. This allows for blending multiple rotational transformations together, rotating geometry (likely instanced geometry) to point outward from the origin and then tilting it 90 degrees.

### Quaternion Rotation Composition [[Ep7, 101:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6078s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));

vector4 extrarot = quaternion($PI/2, {1,0,0});

@orient = qmultiply(@orient, extrarot);

// Alternative with channel reference:
vector N, up;
N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
vector4 extrarot = quaternion(radians(ch('angle')), {1,0,0});

@orient = qmultiply(@orient, extrarot);
```
Demonstrates composing quaternion rotations by creating an initial orientation from a normal and up vector, then applying an additional 90-degree rotation around the X-axis using qmultiply. The second version shows how to parameterize the extra rotation angle with a channel reference, allowing interactive control of the final orientation.

### Parametric Rotation with Quaternions [[Ep7, 103:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6200s)]
```vex
@N = normalize(@P);
vector up = {0,1,0};
@orient = quaternion(maketransform(@N, up));
vector4 extrarot = quaternion(radians(ch("angle")), {1,0,0});
@orient = qmultiply(@orient, extrarot);
```
Creates an orientation quaternion from a transform matrix built from normalized position and up vector, then applies an additional rotation around the X-axis controlled by an angle parameter slider. The channel reference allows interactive adjustment of the rotation angle at the parameter level, replacing the hardcoded 90-degree rotation with a user-controllable value.

### Quaternion Rotation with UI Parameter [[Ep7, 103:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6228s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(radians(ch("angle")), {1,0,0});

@orient = qmultiply(@orient, extrarot);
```
Creates an orientation quaternion from normalized position and up vector, then applies an additional rotation around the X-axis controlled by a user-adjustable parameter. The channel reference allows interactive control of the rotation angle through a slider in the parameter interface, enabling dynamic adjustment of the orientation (e.g., a 90-degree rotation or animated head shake).

### Quaternion Rotation with Channel Parameter [[Ep7, 103:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6230s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extratrot = quaternion(radians(ch("angle")), {1,0,0});

@orient = qmultiply(@orient, extratrot);
```
Creates an orientation quaternion using normalized point position as normal vector and an up vector, then applies an additional rotation controlled by a channel parameter. The extra rotation is constructed as a quaternion from a user-adjustable angle parameter (converted to radians) rotating around the X-axis, and multiplied with the base orientation to allow dynamic rotation control (e.g., 90-degree adjustments or animated head shakes).

### Quaternion multiplication for head rotation [[Ep7, 106:10](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6370s)]
```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@D), {1,0,0});
headshake = quaternion(radians(20) * sin(@Frame*3), {0,1,0});

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
```
This code creates complex rotations by multiplying quaternions together. After establishing a base orientation from the point position, it applies additional rotations: one based on a custom @D attribute around the X-axis, and an animated head shake rotation (20 degrees oscillating at 3 times per frame) around the Y-axis. Each rotation is combined using qmultiply to build up the final @orient attribute.

### Combining Multiple Quaternion Rotations [[Ep7, 106:44](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6404s)]
```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@P.x), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
```
Demonstrates chaining multiple quaternion rotations together using qmultiply. The code creates a base orientation from the normalized position, then applies additional rotations for pitch variation (extrarot) and animated head shake movement, accumulating all transformations into the @orient attribute by repeatedly reassigning the result of qmultiply operations.

### Combining Quaternion Rotations [Needs Review] [[Ep7, 106:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6408s)]
```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(20), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
```
Demonstrates how to combine multiple quaternion rotations using qmultiply to create complex orientation effects. The code chains multiple quaternion operations together by repeatedly multiplying the @orient attribute with additional rotation quaternions, first applying a static extrarot rotation, then a time-based headshake oscillation. This technique allows accumulating rotations in sequence to create compound orientation behaviors.

### Quaternion Rotations with Wobble [[Ep7, 107:40](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6460s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@D), {1,0,0});
headshake = quaternion(radians(20) * sin(chf("Time")*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P + chf("Time")));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```
Creates a quaternion-based orientation system for points by establishing a local transform from normalized position and up vector, then applies multiple rotation layers: a pitch rotation based on @D attribute, a sine-wave headshake around Y, and a curl noise-driven wobble around Z. All rotations are multiplied together using qmultiply to compound the transformations on the @orient attribute.

### Quaternion Rotations with Wobble [Needs Review] [[Ep7, 107:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6468s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@Frame), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P + @Time));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```
Combines multiple quaternion rotations to create complex animated orientation on points. The base orientation is created from the normalized position vector, then additional rotations are applied: a frame-based rotation around X, an animated headshake around Y using sine, and a curl noise-driven wobble around Z that varies per point and over time. All rotations are accumulated using quaternion multiplication.

### Quaternion Wobble with Curl Noise [[Ep7, 108:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6510s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(v@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(chf("time")*2), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P*0.2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```
Creates a compound orientation using multiple quaternion rotations: a base orientation from normalized position, a 90-degree X-axis rotation, an animated sine-based headshake on Y-axis, and a position-dependent curl noise wobble on Z-axis. Each rotation is multiplied sequentially using qmultiply to create the final orientation stored in @orient.

### Per-Point Time Offset for Quaternion Animation [Needs Review] [[Ep7, 109:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6564s)]
```vex
vector h, up;
vector4 extrarot, headshake, wobble;

h = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(h, up));
extrarot = quaternion(radians(@N.x), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time + @ptnum) * chv("us") * 3), {0,1,0});
// wobble = quaternion({0,0,1} * curlnoise(@P*ies + t));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
// @orient = qmultiply(@orient, wobble);
```
Demonstrates using point number (@ptnum) as a per-point time offset to create varied animation timing across copied instances. By adding @ptnum to @Time in the headshake quaternion calculation, each point's rotation animates with a unique phase offset, creating organic variation that would be difficult to achieve with standard copy-to-points workflows.

### Layered Quaternion Rotations [Needs Review] [[Ep7, 110:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6614s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(@Frame), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time*chf("freq"))*3), {0,1,0});
// wobble = quaternion({0,0,1} * curlnoise(@P*freq));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
// @orient = qmultiply(@orient, wobble);
```
Demonstrates building complex rotations by layering multiple quaternions through qmultiply. Creates base orientation from point normal, then applies additional rotations for extra rotation, animated headshake based on time and frequency, and optional wobble from curl noise. This compositing approach allows independent control of each rotation layer while maintaining good performance.

### Quaternion Composition for Complex Orientations [Needs Review] [[Ep7, 110:16](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6616s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(@N), {1,0,0});
headshake = quaternion(radians(2*@P.y + sin(@TimeInc+@ptnum)*3), {0,1,0});
// wobble = quaternion({0,0,1} * curlnoise(@P*@Time*2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
// @orient = qmultiply(@orient, wobble);
```
Demonstrates building complex orientations by composing multiple quaternions together using qmultiply. Creates a base orientation from normalized position, then adds extra rotation, animated headshake, and optional wobble effects by multiplying quaternions sequentially, showing how quaternions can be layered to create sophisticated rotation behaviors.

### Quaternion Composition and Rotation [[Ep7, 111:06](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6666s)]
```vex
vector N, up;
vector@ extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), {0,1,0});
headshake = quaternion(radians(20) * sin((@Time+chsraw(0))*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P+@Time*0.1));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```
Demonstrates composing multiple quaternion rotations by creating separate quaternions for base orientation, extra rotation from normals, animated headshake, and curl noise wobble, then combining them sequentially using qmultiply. The final @orient attribute represents the compound rotation applied in order, showcasing how quaternions can be chained to build complex rotational animations.

### Converting Quaternions to Matrices [[Ep7, 111:12](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6672s)]
```vex
vector R, up;
vector4 extrarot, headshake, wobble;

R = normalize(@P);
N = {0,1,0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(90), {1,0,0});

headshake = quaternion(radians(20) * sin(@Time*ch("freq")), {0,1,0});
wobble = quaternion({0,0,1} * qntnoise(@P*chf("wfreq")));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix m = qconvert(@orient);
```
Demonstrates building complex quaternion rotations through multiplication (base orientation, 90-degree rotation, time-based headshake, and noise-based wobble), then converting the final quaternion to a matrix using qconvert() for visualization or further manipulation. The conversion allows the four-dimensional quaternion rotation to be represented as a more familiar 3x3 matrix.

### Converting quaternions to matrix [Needs Review] [[Ep7, 114:02](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6842s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin((@TimeInc * @chs("speed")) * 3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P + @TimeInc * @z));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix m = qconvert(@orient);
```
Demonstrates converting a quaternion orientation (built from multiple rotation layers) into a matrix representation using qconvert(). The code chains together base orientation, extra rotation, animated headshake, and curl noise wobble via quaternion multiplication before converting to a matrix for visualization or further manipulation.

### Quaternion Orientation with Multiple Rotations [Needs Review] [[Ep7, 114:06](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6846s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N.x), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time + @ptnum) * 3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P + @Time * 0.2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix m = qconvert(@orient);
```
Creates complex orientation behavior by building a base quaternion from normalized position and up vector, then applies three additional rotations (extra rotation, animated headshake, and curl noise wobble) by multiplying them sequentially. The final quaternion is converted to a matrix form for visualization or further transformation operations.

### Converting Quaternions to Matrix [Needs Review] [[Ep7, 114:10](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6850s)]
```vex
vector N, up;
vector4 extract, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(M), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time+@ptnum)*3), {0,1,0});
wobble = quaternion({0,0,1} * sin(@Time*0.2));

@orient = qmultiply(@orient, extract);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix m = qconvert(@orient);
```
Demonstrates converting a compound quaternion rotation (built from multiple quaternion multiplications) into a matrix using qconvert(). The code creates a base orientation from normalized position, then applies extract, headshake, and wobble rotations as quaternions before converting the final orientation to a 4x4 matrix for visualization or further transformation operations.

### Converting Quaternion to Normal Vectors [Needs Review] [[Ep7, 115:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6920s)]
```vex
H = normalize(@P);
N = {0,1,0};
@orient = quaternion(maketransform(N, up));
@xtrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(@TimeInc*chf("mus")*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P*@Time*0.2));

@orient = qmultiply(@orient, @xtrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
@N = {0,0,1} * m;
@up = {0,1,0} * m;
```
Converts a quaternion orientation to normal and up vectors by first converting the quaternion to a matrix3 using qconvert(), then multiplying basis vectors by that matrix. Multiplying a vector by a matrix applies the transformation encoded in the matrix, allowing extraction of directional vectors from the combined quaternion rotations.

### Converting Quaternion to Normal and Up Vectors [Needs Review] [[Ep7, 115:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6924s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time*chv("us"))*3), {0,1,0});
wobble = quaternion({0,0,1} * curvature(@P*ch("wobble"), 2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
@N = {0,0,1} * m;
@up = {0,1,0} * m;
```
Demonstrates converting a quaternion orientation back into explicit normal and up vectors by first converting the quaternion to a 3x3 matrix using qconvert(), then multiplying basis vectors by that matrix. Multiplying a vector by a matrix applies the transformation baked into that matrix, allowing extraction of transformed axis directions from the accumulated quaternion rotations.

### Quaternion Transformations with Matrix Extraction [[Ep7, 115:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6950s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(90*@Time), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P) * 45);

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
@N = {0,0,1} * m;
@up = {0,1,0} * m;
```
Builds a complex orientation quaternion by composing multiple rotations (base orientation, 90-degree rotation, time-based headshake, and curl noise wobble), then converts the final quaternion to a matrix3 to extract transformed normal and up vectors. The matrix multiplication extracts the Z and Y axes from the transformed orientation matrix to set @N and @up attributes for visualization.

### Converting Orient to N and Up Vectors [[Ep7, 115:58](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6958s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
@N = (0,1,0);
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), (1,0,0));
headshake = quaternion(radians(20) * sin((@TimeInc*chs("speed"))*3), (0,1,0));
wobble = quaternion((0,0,1) * curlnoise(@P+@TimeInc*2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
@N = (0,0,1) * m;
@up = (0,1,0) * m;
```
Converts a quaternion orientation back into N and up vector attributes by converting the quaternion to a matrix3, then multiplying basis vectors by that matrix. The N vector is extracted by multiplying the Z-axis (0,0,1) by the matrix, and the up vector by multiplying the Y-axis (0,1,0), allowing visualization of the orientation as two colored vectors in the viewport.

### Orientation with Multiple Quaternion Rotations [Needs Review] [[Ep7, 116:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6978s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(chf("n")), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*chf("n")*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P*chf("m")*0.2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
@N = {0,0,1} * m;
@up = {0,1,0} * m;
```
Creates a complex orientation system by composing multiple quaternion rotations through qmultiply, starting with a base orientation from maketransform, then adding extrarot, headshake (time-based sine wave), and wobble (curl noise). The final orientation is converted to a matrix and used to compute @N and @up vectors for visualization.

### Quaternion Animation with Multiple Rotations [Needs Review] [[Ep7, 116:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6980s)]
```vex
vector N, up;
vector@ extract, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(@N), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P*chf("freq")));

@orient = qmultiply(@orient, extract);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
@N = {0,0,1} * m;
@up = {0,1,0} * m;
```
Creates a compound quaternion rotation by building a base orientation from point position, then multiplying it with three separate rotation quaternions: one extracted from point normal, one for a time-based sinusoidal headshake motion, and one for curl noise-driven wobble. The final quaternion is converted to a matrix and used to calculate N and up vector attributes for visualization, demonstrating how multiple quaternion rotations can be combined through sequential multiplication to create complex animated orientations.

### Extracting Axes from Quaternion Orientation [[Ep7, 116:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6990s)]
```vex
matrix3 m = qconvert(@orient);
vector n = normalize(v@orient);
@N = normalize(m[2]); // z axis
@up = normalize(m[1]); // y axis
```
Demonstrates extracting directional vectors from a quaternion orientation by converting to a matrix3 and accessing its rows directly. The matrix rows represent the transformed basis vectors, with row 2 being the z-axis (used for @N) and row 1 being the y-axis (used for @up). These can be visualized in the viewport to show how the orientation affects directional vectors.

### Extracting Axes from Quaternion Matrix [[Ep7, 117:32](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7052s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@R), {1,0,0});
headshake = quaternion(radians(2.0) * sin((@TimeInc+chv("hs"))*3), {0,1,0});
wobble = quaternion({0,0,1} * sin(1.5*@TimeInc)*0.2);

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
@N = {0,0,1} * m;
@up = {0,1,0} * m;
```
Converts the final quaternion orientation to a matrix3 and extracts directional axes by multiplying canonical basis vectors with the rotation matrix. The z-axis {0,0,1} multiplied by the matrix becomes the @N normal attribute, and the y-axis {0,1,0} becomes the @up attribute, effectively extracting the rotated coordinate frame from the accumulated quaternion transforms.

### Complex Orientation with Multiple Quaternion Rotations [[Ep7, 120:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7204s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(1), 0, 0);
headshake = quaternion(radians(20) * sin(@Time*chv("us")*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P+@Time, 2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
vector axes[] = set(m);
@up = normalize(axes[1]);
```
Creates a complex animated orientation for eyeball geometry by combining multiple quaternion rotations: a base orientation aligned to the point normal, a small tilt, an animated headshake using sine waves, and organic wobble from curl noise. The quaternions are multiplied together to create the final @orient, and the @up vector is extracted from the resulting transformation matrix.

### Quaternion Orientation with Dynamic Rotations [[Ep7, 122:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7324s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@O), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time+chv("s"))*3), {0,1,0});
wobble = quaternion({0,0,1} * noise(@P+@Time)*0.1);

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
vector Axes[] = set(0);
Axes = m_to_axes(m);
@up = normalize(Axes[1]);
```
Creates an orient quaternion from a transformation matrix aligned to normalized point position and up vector, then applies multiple rotational modifications including a channel-driven parameter, time-based sine wave animation for headshake, and noise-driven wobble. The final quaternion is converted to a matrix to extract the up vector from the transformed coordinate system.

### Quaternion Rotations with Multiple Transforms [Needs Review] [[Ep7, 122:42](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7362s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@X), {1,0,0});
headshake = quaternion(radians(2*@Z) * sin((@Time+ch("offset"))*3), {0,1,0});
wobble = quaternion({0,0,1} * chramp("wobble", @Time*2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
vector axes[] = set(m);
@up = normalize(axes[1]);
```
Creates a base orientation using maketransform from normalized position and up vector, then applies three additional rotations via quaternion multiplication: extrarot based on X position, headshake as animated Y-axis rotation using Time and a sine wave, and wobble from a ramp. Finally converts the quaternion to a matrix to extract the up axis vector from the transformation.

### Quaternion Orientation with Curl Noise [[Ep7, 122:46](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7366s)]
```vex
vector N, up;
vector4 extract, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(@0), {1,0,0});
headshake = quaternion(radians(20) * sin((f@timeinput)*3), {0,1,0});
wobble = quaternion(0,0,1) * curlnoise(@P*f@wfreq)*3;

@orient = qmultiply(@orient, extract);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);

matrix3 m = qconvert(@orient);
vector Axes[] = {};
Axes = vectomatrix(m);
@up = normalize(Axes[1]);
```
Creates complex orientation by combining multiple quaternion rotations: a base orientation aligned to the point normal, an extract rotation from a parameter, an animated headshake sine wave, and curl noise-based wobble. The final orientation is converted to a matrix to extract the up vector, demonstrating how to decompose rotations after quaternion multiplication.

## Quaternion Basics

### Matrix casting and primitive transforms [[Ep7, 141:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8464s)]
```vex
qorient = quaternion({0,1,0} * @Time);
vscale = {1, 0.5, 2};

matrix m = ident();
scale(m, vscale);
m *= qconvert(qorient);

setprimintrinsic(0, "transform", @ptnum, m);
```
Creates a rotation quaternion based on time, applies non-uniform scaling to an identity matrix, then converts and multiplies the quaternion rotation into the matrix. The final matrix is applied to a primitive's transform intrinsic, demonstrating how to build compound transforms and cast between matrix types (matrix4 to matrix3) when needed.

## Orient Attribute

### Quaternion from Angle and Axis [[Ep7, 33:58](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2038s)]
```vex
float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);
```
Creates a quaternion orientation from an angle parameter and axis vector parameter using the quaternion() function. The resulting quaternion is stored in the @orient attribute, which is used by Houdini to rotate instances and packed geometry. The speaker demonstrates how the quaternion values update as parameters change, and suggests using @Time instead of a slider for the angle to create animated rotation.

### Quaternion Rotation with Parameters [[Ep7, 35:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2118s)]
```vex
float angle = @Time;
vector axis = chv('axis');

angle = ch('angle');
angle = @Time*ch('speed');

axis = chv('axis');

@orient = quaternion(angle, axis);
```
Creates a quaternion-based rotation by combining time with a speed parameter and a user-defined axis. The angle is calculated as time multiplied by speed, and the axis is read from a vector parameter, with the result stored in the orient attribute. This demonstrates how to parameterize rotation using channel references for interactive control.

### Quaternion Rotation with Per-Point Offsets [[Ep7, 35:26](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2126s)]
```vex
// Compact version:
@orient = quaternion(@Time, chv("axis"));

// Expanded version with offsets:
float angle;
vector axis;

angle = ch("angle");
angle += @ptnum * ch("offset");
angle += @Time * ch("speed");

axis = chv("axis");

@orient = quaternion(angle, axis);
```
Demonstrates two approaches to creating quaternion rotations: a compact one-line version using @Time directly, and an expanded version that builds the rotation angle from multiple components including a base angle, per-point offset based on @ptnum, and time-based animation. The expanded version shows how to layer multiple influences on the rotation angle for more complex per-point animation effects.

### Quaternion orientation with point offset [[Ep7, 36:56](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2216s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum * ch('offset');
axis = chv('axis');

@orient = quaternion(angle, axis);
```
Creates per-point rotation orientations using quaternions, where each point's rotation angle is offset based on its point number multiplied by an offset parameter. The base angle is taken from a channel parameter, incremented by the point number times an offset value, then converted to a quaternion orientation around a specified axis vector.

### Quaternion Rotation with Offset [[Ep7, 38:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2294s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += (@Time * ch('offset'));
angle += @Time * ch('speed');

axis = chv('axis');

@orient = quaternion(angle, axis);

// Simplified version:
// @orient = quaternion(@Time, chv('axis'));
```
Demonstrates how to create per-point quaternion rotations by combining a base angle from a channel with time-based offsets and speed multipliers. The offset parameter creates variation between points while speed controls the overall rotation rate, allowing for sweeping patterns where points rotate at slightly different phases along a global axis.

### Quaternion Rotation with Frame Offset [[Ep7, 38:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2304s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += @Frame * ch('offset');
angle = @Time * ch('speed');

axis = chv('axis');

@orient = quaternion(angle, axis);
```
Creates a rotation using quaternions where the angle is controlled by channel parameters and modified by frame offset and time-based speed. The axis parameter controls the rotation direction, creating a sweeping effect across geometry rows where higher frame numbers produce increasingly different rotations along the specified global axis.

### Quaternion rotation with axis variation [[Ep7, 38:26](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2306s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum*ch('offset');
angle += @Time*ch('speed');
axis = chv('axis');

@orient = quaternion(angle, axis);
```
Demonstrates quaternion rotation with customizable axis parameter, creating progressive rotation variations across points by accumulating angle contributions from base angle, point-number offset, and time-based animation. The axis can be adjusted via channel reference to control the global rotation direction, creating sweeping motion patterns that vary more dramatically at higher offset values.

### Quaternion Axis Magnitude Issues [Needs Review] [[Ep7, 39:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2388s)]
```vex
float angle1;
vector axis1;

angle = ch('angle');
axis1 = chv('axis1')-chv('offset');
angle += 2*(int * ch('speed'));
axis = chv('axis');

@orient = quaternion(angle, axis);
```
Demonstrates how the magnitude of the axis vector affects quaternion rotation behavior, causing non-uniform rotational speed. When the axis vector has a magnitude other than 1 (in this case, a 2-unit long vector), the rotation speeds up and down instead of maintaining constant velocity, illustrating the importance of normalizing axis vectors for quaternion rotations.

### Normalizing Rotation Axis for Orient [[Ep7, 41:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2488s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum*ch('offset');
angle *= @Time * ch('speed');

axis = chv('axis');
axis = normalize(axis);

@orient = quaternion(angle, axis);
```
Demonstrates normalizing a rotation axis vector before using it to create an orient quaternion attribute. The normalize() function converts the axis vector from chv() into a unit vector, ensuring smooth and predictable rotation regardless of the input axis magnitude. This approach combines per-point angle variation (@ptnum offset) with time-based animation to create dynamic rotation effects.

### Quaternion Orientation Variations [[Ep7, 42:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2534s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += @Time*ch('offset');
angle *= @Time*ch('speed');

axis = chv('axis');
axis = normalize(axis);

@orient = quaternion(angle, axis);

// Second variation
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum*ch('offset');
angle *= @Time*ch('speed');

axis = chv('axis');
axis = normalize(axis);

@orient = quaternion(angle, axis);

// Third variation
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= 0;

@orient = quaternion(axis);
```
Three variations of quaternion-based orientation transformations demonstrating different approaches: the first uses @Time for both offset and speed, the second uses @ptnum for offset to vary per point, and the third creates a zero-scaled axis for a neutral orientation. Normalizing the axis vector ensures smooth orientation transformations that update the @orient attribute dynamically.

### Quaternion Rotation with Multiple Time Offsets [Needs Review] [[Ep7, 42:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2538s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum * ch('offset');
angle += @Time * ch('speed');

axis = chv('axis');
axis = normalize(axis);

@orient = quaternion(angle, axis);
```
Creates quaternion-based rotation using three angle components: a base angle from a channel, an offset multiplied by point number for per-point variation, and a time-based component for animation. The axis is normalized before constructing the quaternion and storing it in the @orient attribute, which produces complex rotational motion that appears as non-human-readable values in the geometry spreadsheet.

### Quaternion Axis-Angle Rotation [Needs Review] [[Ep7, 45:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2728s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis = {1,0,0};

@orient = quaternion(axis);
```
Demonstrates creating a quaternion orientation from an axis vector using the quaternion() constructor. The example shows that when you scale the axis vector (magnitude), it creates rotation around that axis, with the vector's length determining rotation amount - conceptually similar to a spinning top where pushing up/down causes rotation.

### Vector to Quaternion Conversion [Needs Review] [[Ep7, 45:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2750s)]
```vex
vector axis1;
axis1 = chv('axis');
axis1 = normalize(axis1);
axis1 = @P * me;

@orient = quaternion(axis1);
```
Demonstrates creating a quaternion orientation from a normalized vector axis. The vector is retrieved from a channel parameter, normalized, then scaled by position and a 'me' variable before being converted to a quaternion for the @orient attribute. This shows how vectors can encode rotational information beyond simple directional data.

### Vector-Driven Quaternion Rotation [[Ep7, 45:52](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2752s)]
```vex
vector axis;

axis = chv('axis');
axis = normalize(axis);
axis *= @Time;

@orient = quaternion(axis);
```
Creates a quaternion rotation from a normalized vector axis scaled by @Time. This demonstrates how vectors can encode both direction and magnitude information, where the axis direction determines the rotation axis and the magnitude (scaled by time) determines the rotation angle. As time progresses, the rotation continuously updates, creating animated spinning around the specified axis.

### Quaternion from Normalized Axis [[Ep7, 45:54](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2754s)]
```vex
vector axis;

axis = chv('axis');
axis = normalize(axis);
axis = @Cd;

@orient = quaternion(axis);
```
Creates a quaternion orientation from a normalized vector axis. The axis is first retrieved from a channel parameter, normalized, then reassigned to the point color attribute before converting to a quaternion stored in @orient. This demonstrates how a vector can encode rotation information, where changing the vector's scale or direction causes the geometry to spin around that axis.

### Quaternion angle issue with degrees [Needs Review] [[Ep7, 46:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2780s)]
```vex
vector axis;

axis = chv("axis");
axis = normalize(axis);
axis = 45;

@orient = quaternion(axis);
```
This code demonstrates a common mistake when creating quaternions where the angle parameter is set to 45, expecting degrees, but the quaternion() function actually expects radians. The axis is first retrieved from a channel parameter, normalized, then incorrectly overwritten with a scalar value of 45 before being passed to quaternion(), which would cause unexpected rotation results.

### Quaternions with Radians Issue [[Ep7, 46:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2790s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis = {0, 1, 0};

@orient = quaternion(axis);
```
Creates an orientation quaternion from an axis vector, demonstrating a common pitfall where the quaternion() function expects rotation angles in radians, not degrees. The axis is normalized and set to Y-axis (0,1,0), but rotation values passed to quaternion functions must be converted from degrees to radians (180 degrees = PI radians, 90 degrees = PI/2 radians).

### Quaternion Rotation with Radians [Needs Review] [[Ep7, 47:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2848s)]
```vex
vector axis;

axis = chv("axis");
axis = normalize(axis);
axis = 1.570795;

@orient = quaternion(axis);
```
Demonstrates creating a quaternion rotation using a hardcoded radian value (1.570795, approximately π/2) for a 90-degree rotation. The code sets up an axis vector from a channel parameter, normalizes it, then overrides it with the radian value before constructing the quaternion. This example shows the manual conversion approach before introducing the radians() function.

### Quaternion Rotation Progressions [[Ep7, 49:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2964s)]
```vex
vector axis1;

axis1 = normalize(axis1);
axis1 = $PI/2;

@orient = quaternion(axis1);

vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= $PI/2;

@orient = quaternion(axis);

vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= trunc(rand(@ptnum)*4)*$PI/2;

@orient = quaternion(axis);

vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= trunc(noise(@P*@Time)*4)*$PI/2;

@orient = quaternion(axis);
```
A progression of quaternion rotation examples showing evolution from basic axis rotation to randomized and animated variations. The examples demonstrate using $PI constant (which can be written without the $ in modern Houdini), creating rotations from channel-referenced axes, randomizing rotations per point, and finally creating animated rotations using noise and time.

### Quaternion Rotation from Noise [[Ep7, 60:00](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3600s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@ptnum);
@a = fit(@a, 0, 1, 0, 1);
axis *= trunc(@a*5)*$PI/2;

@orient = quaternion(axis);
```
Creates quaternion-based rotations by generating noise per point, fitting it to a range, then quantizing it to discrete rotation angles (multiples of PI/2). The axis vector is scaled by the quantized noise value and converted to a quaternion orientation attribute, allowing rotation variation across points while maintaining control through the axis parameter.

### Quaternion Orientation from Axis [[Ep7, 62:32](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3752s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P * @Time);
@a = chramp('noise_rearrange', @a);
axis *= trunc(@a * 8) * $PI / 2;
@P.y = @a;

@orient = quaternion(axis);

@N = {0, 1, 0};
float s = sin(@Time);
float c = cos(@Time);
vector @up = {s, @N.y, c};

@orient = quaternion(maketransform(@N, @up));
```
Creates point orientation using quaternions derived from noise-driven axis rotation and time-based up vector animation. The code demonstrates two approaches: first using a truncated noise value to create discrete rotation angles, then using maketransform with animated up vectors to generate quaternions. A ramp parameter allows remapping noise values to control the threshold for discrete rotation steps.

### Quaternion from Matrix Transform [Needs Review] [[Ep7, 63:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3828s)]
```vex
vector axis = trunc(@P * @P.y);
vector @N = @P;

@orient = quaternion(axis);

float s = sin(@Time);
float c = cos(@Time);
vector @up = set(s, 0, c);

@orient = quaternion(maketransform(@N, @up));

matrix m = ident();
@orient = quaternion(m);
```
Demonstrates multiple approaches to creating quaternion orientations, including building them from axis vectors, constructing them from custom transform matrices using maketransform() with normal and up vectors, and converting identity matrices to quaternions. Shows the transition from manual axis manipulation to using dynamic time-based up vectors for animation.

### Quaternion Rotation with Animated Up Vector [Needs Review] [[Ep7, 66:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3980s)]
```vex
@N = {0,1,0};
float s = sin(@Time);
float c = cos(@Time);
@up = set(s, 0, c);

@orient = quaternion(maketransform(@N, @up));
```
Creates a rotating orientation by computing an animated up vector that circles around using sine and cosine of time. The up vector is constructed with set(s, 0, c) where s and c are sine and cosine values, creating circular motion in the XZ plane while @N remains fixed at {0,1,0}. This pair of vectors is then converted into a quaternion orientation using maketransform().

### Matrix to Quaternion Conversion [[Ep7, 70:34](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4234s)]
```vex
matrix3 m = ident();
@orient = quaternion(m);

@orient = {0,0,0,1};

vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);
```
Demonstrates three methods of setting orientation: converting an identity matrix3 to a quaternion, directly assigning quaternion values, and converting Euler angles from a channel parameter. The matrix3 type handles rotation and scale (unlike matrix which also includes translation, skew, and perspective), and an identity matrix converts to the same default quaternion orientation as {0,0,0,1}.

## Interpolation (slerp)

### Quaternion Interpolation with SLERP [Needs Review] [[Ep7, 73:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4430s)]
```vex
vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);

vector4 a = {0,0,0,1};
vector4 b = quaternion(0,1,0)*$PI/2);
@orient = slerp(a, b, ch('blend'));

vector4 a = {0,0,0,1};
vector4 b = quaternion(0,1,0)*$PI/2);
float blend = @Time*1;
@orient = slerp(a, b, blend);
```
Demonstrates converting Euler angles to quaternions using eulertoquaternion() with rotation order parameter (0=XYZ, 1=YZX, 2=ZXY), then shows how to interpolate between two quaternions using the slerp() function with both static channel-driven blending and time-based animation. The slerp function performs spherical linear interpolation between two quaternion orientations.

### Quaternion blending with slerp [[Ep7, 75:32](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4532s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(radians({0,1,0} * $F/2));
@orient = slerp(a, b, ch('blend'));

// Advanced version with ramp:
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = chramp('blendcap', @ptnum/1);
@orient = slerp(a, b, blend);
```
Uses slerp() to smoothly interpolate between two quaternions (identity and a rotation) based on a blend parameter. The quaternion rotation is created from frame number and Y-axis rotation, while slerp provides spherical linear interpolation for smooth orientation blending. An advanced variation uses chramp() to control per-point blending via a ramp parameter.

### Quaternion Blending with Slerp [[Ep7, 75:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4548s)]
```vex
// Basic slerp between identity and rotation
vector4 a = {0,0,0,1};
vector4 b = quaternion(radians({0,1,0} * $F/2));
@orient = slerp(a, b, ch('blend'));

// Using PI for 90-degree rotation
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * $PI/2);
@orient = slerp(a, b, ch('blend'));

// Using @Time01 for automatic animation
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * $PI/2);
float blend = @Time01;
@orient = slerp(a, b, blend);

// Using ramp parameter for blend control
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * $PI/2);
float blend = chramp('blend_ramp', @Time01);
@orient = slerp(a, b, blend);
```
Demonstrates spherical linear interpolation (slerp) to smoothly blend between two quaternion rotations on the @orient attribute. The progression shows different approaches: using a channel slider for manual control, frame-based rotation with $F, fixed 90-degree rotation with $PI/2, time-based animation with @Time01, and finally ramp-driven interpolation for custom animation curves.

### Quaternion slerp animation with noise-driven rotation [Needs Review] [[Ep7, 79:56](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4796s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(radians(0),{0}*$PI/2);
float blend = chramp('blendramp',@ptnum%1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis /= length(axis);
seed = noise(@P*@Time);
seed = chramp('noise_remap',seed);
axis *= trunc(seed*seed)*$PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim',@Time%1);

@orient = slerp(base, target, blend);
```
Creates animated quaternion rotations using slerp interpolation between a base identity quaternion and a target rotation. The target rotation is driven by noise sampled from point position and time, remapped through a ramp, then quantized with trunc to create discrete rotation snapping effects. The animation blend is controlled by a time-based ramp with modulo wrapping for looping.

### Quaternion Slerp with Ramps [Needs Review] [[Ep7, 79:58](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4798s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = chramp('blend_map',@ptnum*1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = fit(@P.x, @ptnum);
seed = chramp('noise_forrange', seed);
axis *= trunc(seed)*2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('animal', @ptnum*1);

@orient = slerp(base, target, blend);
```
Demonstrates spherical linear interpolation (slerp) between quaternions using ramp parameters for blend control. Two examples show: first, interpolating from identity quaternion to a time-animated rotation; second, using per-point noise and ramps to drive randomized axis rotations with normalized vectors and truncation for discrete rotation values.

### Quaternion SLERP Animation [[Ep7, 80:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4804s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
float blend = chramp('blendRamp',@Time);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@P, @Time);
seed = chramp('noise_remap', seed);
axis *= trunc(seed*2)*$PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim', @Time);

@orient = slerp(base, target, blend);
```
Demonstrates spherical linear interpolation (slerp) between quaternions to smoothly animate rotation orientations. The first block shows a basic slerp from identity quaternion to a 90-degree Y-axis rotation, while the second block uses noise-driven axis selection with channel ramps to create varied per-point rotational animations controlled by a blend parameter.

### Quaternion Slerp with Ramps [Needs Review] [[Ep7, 80:06](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4806s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = chramp('blendmap',@Time);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = chi('seed');
seed = chramp('noise_forangle',seed);
axis *= 1-rand(seed)*2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('angle',@Time);

@orient = slerp(base, target, blend);
```
Demonstrates spherical linear interpolation (slerp) between quaternions using ramp parameters for blend control. The first example interpolates from an identity quaternion to a frame-based rotation, while the second creates a randomized axis rotation controlled by channel references and ramps. Both use @orient to apply the rotation to points.

### Quaternion SLERP interpolation with noise [[Ep7, 80:36](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4836s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * PI/2);
float blend = chramp('blendRamp',@Time*1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_forrange',seed);
axis *= trunc(seed*4)*PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim',@Time*1);

@orient = slerp(base, target, blend);
```
Demonstrates spherical linear interpolation (SLERP) between quaternions for smooth rotation animation. The first example shows simple interpolation between identity and a 90-degree Y-axis rotation. The second example uses noise-driven random axis selection (snapped to 90-degree increments) to interpolate between identity and varied target orientations, creating animated random rotations that smoothly transition rather than snap between states.

### Quaternion Interpolation with Slerp [[Ep7, 80:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4848s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(0,v@up,chf('PI/2'));
float blend = chramp('blendramp',@Time % 1);
@orient = slerp(a, b, blend);

vector4 a = {0,0,0,1};
vector4 b = quaternion(1,0,1,0) * PI/2;
float blend = chramp('blendwramp', @Time % 1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_rerange',seed);
axis *= trunc(seed^2)*4*PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim',@Time%1);

@orient = slerp(base, target, blend);
```
Demonstrates smooth interpolation between quaternion rotations using slerp() instead of hard switching between orientations. The technique combines random per-point rotation targets (using noise and axis manipulation) with time-based blending to create smoothly animated rotations rather than the abrupt flipping seen in earlier examples.

### Smooth Quaternion Rotation Interpolation [[Ep7, 80:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4850s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = normalize(vector4(0,1,0) * PI/2);
float blend = chramp('blendramp', @Time % 1);
@orient = slerp(a, b, blend);

vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = dot(@P, @Time);
@a = chramp('noise_rerange', @a);
axis *= trunc(@a*4)*PI/2;
@P.y = @a;

@orient = quaternion(axis);
```
Demonstrates smooth rotation interpolation using quaternions by blending between two orientations with slerp() based on a time-driven ramp. The code calculates rotation axes dynamically using dot products with @P and @Time, then discretizes the rotation into 90-degree increments using trunc() before converting to quaternion form for the @orient attribute.

### Quaternion Slerp with Noise Animation [[Ep7, 80:58](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4858s)]
```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_remap', seed);
axis *= (seed * 2 - 1) * PI / 2;

target = quaternion(axis);
base = {0, 0, 0, 1};
blend = chramp('anim', @Time % 1);

@orient = slerp(base, target, blend);
```
Creates smooth animated rotation by using slerp to interpolate between identity orientation and a per-point random target rotation. The target rotation axis is derived from noise applied to point numbers, remapped through a ramp, then scaled to a range suitable for rotation angles. A separate animation ramp controls the blend factor over time for smooth transitions.

### Quaternion Slerp with Noise Remap [Needs Review] [[Ep7, 83:44](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5024s)]
```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = chramp('noise_remap', seed);
axis = trunc(seed) * $PI / 2;

target = quaternion(axis);
base = {0, 0, 0, 1};
blend = chramp('blend', @Frame);

@orient = slerp(base, target, blend);
```
Creates a quaternion orientation by normalizing an axis vector from a channel parameter, remapping a seed value through a ramp, and using spherical linear interpolation (slerp) to blend between a base identity quaternion and a target quaternion based on frame-driven blend values. The axis rotation is quantized using trunc() to create stepped rotations at PI/2 intervals.

### Quaternion Rotation with Noise-Driven Slerp [[Ep7, 83:52](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5032s)]
```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_remap', seed);
axis *= trunc(seed*2)*@PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim', @Time%1);

@orient = slerp(base, target, blend);
```
Creates randomized rotation orientations using quaternions by generating noise-based rotation angles per point, converting them to quaternion representations, then using spherical linear interpolation (slerp) to smoothly blend between an identity quaternion and the target rotation. The blend is controlled by an animated ramp that cycles every second, while the rotation angles are quantized to 90-degree increments based on remapped noise values.

### Quaternion rotation with noise seed [Needs Review] [[Ep7, 84:22](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5062s)]
```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@P + @Time);
seed = chramp('noise_rerange', seed);
axis *= lerp(seed * 2) * @PI / 2;

target = quaternion(axis);
base = {0, 0, 0, 1};
blend = chramp('angle', @Time);

@orient = slerp(base, target, blend);
```
Creates animated orientation by building a quaternion from an axis-angle representation where the angle is driven by noise remapped through a ramp. The noise is seeded by position plus time, then remapped through a 'noise_rerange' ramp and scaled to rotate the axis vector, which is converted to a quaternion and interpolated using slerp with a time-based blend ramp.

### Quaternion Rotation with Slerp [[Ep7, 85:52](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5152s)]
```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@P + @Time);
seed = chramp('noise_remap', seed);
axis *= trunc(seed * 4) * (@PI / 2);

target = quaternion(axis);
base = {0, 0, 0, 1};
blend = chramp('blendramp', @Time % 1);

@orient = slerp(base, target, blend);

vector4 a = {0, 0, 0, 1};
vector4 b = quaternion({0, 1, 0} * PI / 2);
float blend_demo = chramp('blendramp', @Time % 1);

@orient = slerp(a, b, blend_demo);
```
Uses noise to randomly select one of four 90-degree rotation angles around a user-defined axis, creates a target quaternion from the scaled axis, then smoothly interpolates between an identity quaternion and the target using slerp. The blend factor is driven by a ramp parameter animated over time, creating smooth transitional rotations.

### Quaternion slerp animation with ramps [Needs Review] [[Ep7, 87:26](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5246s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(0,1,0,$PI/2);
float blend = chramp('blendRamp',@Time%1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;

axis = set(1,0,0);
axis = normalize(axis);
seed = rand(@ptnum);
seed = chramp('noise_remap',seed);
axis = trunc(seed*3)*$PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim',@Time%1);

@orient = slerp(base, target, blend);
```
Demonstrates quaternion interpolation using slerp() to animate orientation between base and target rotations. Uses chramp() to control blend factor with modulated time (@Time%1) for looping animation, and applies per-point randomization via rand() and ramp remapping to create variation in axis angles. The trunc() function quantizes random values to discrete rotation steps.

### Quaternion Slerp Animation with Noise [[Ep7, 89:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5354s)]
```vex
float blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum, @Time);
seed = chramp('noise_remap', seed);
axis *= trunc(seed*2)*$PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim', @Time%1);

@orient = slerp(base, target, blend);
```
Creates animated quaternion rotations using slerp interpolation between a base identity quaternion and a target orientation. The target rotation axis is determined by noise evaluated per-point and time, then remapped and quantized to discrete angles. A ramp controls the blend factor over a one-second loop, creating smoothly interpolated rotations that can be filtered through different sections of geometry.

### Quaternion Interpolation with Noise [[Ep7, 89:16](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5356s)]
```vex
i[]@attribute0;
s[]@attribute1;

axis = normalize(axis);
seed = noise(@Frame);
seed = chramp('noise_range', seed);
axis = trunc(seed*3)*axis;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim', @Time%1);

@orient = slerp(base, target, blend);
```
Uses noise and ramps to create animated quaternion rotations by generating random axis selections through truncated noise values. The noise seed is remapped through a ramp, then truncated and multiplied by 3 to select discrete axis directions, which are converted to quaternions and interpolated using slerp with time-based animation control.

### Quaternion Slerp Animation [[Ep7, 89:42](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5382s)]
```vex
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_remap', seed);
axis *= trunc(seed * 4) * @P[2];

target = quaternion(axis);
base = {0, 0, 0, 1};
blend = chramp('anim', @Time % 1);

@orient = slerp(base, target, blend);
```
Uses slerp (spherical linear interpolation) to smoothly blend between a base quaternion and a target quaternion over time. The target rotation is derived from a normalized axis scaled by noise-remapped seeds and point height, while the blend parameter is driven by a ramp keyed to looping time. This creates animated orientation transformations that respect quaternion interpolation rather than Euler angles.

### Quaternion Orientation with Transform Order [[Ep7, 90:08](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5408s)]
```vex
@vis = normalize(@vis);
seed = chf("seed");
seed = chramp("noise_orange", seed);
@vis = trunc(@vis) * @P[2];

target = quaternion(@vis);
base = {0, 0, 0, 1};
blend = chramp("anim", @Frame % 1);

@orient = slerp(base, target, blend);
```
Demonstrates how the order of transform nodes affects orientation attribute behavior. When transforming geometry, placing the transform before the wrangle preserves original orientations, while placing it after allows the orientations to update with the geometry rotation. The code creates animated quaternion orientations using slerp interpolation between a base identity quaternion and a target derived from a normalized vector.

### Spherical Interpolation with Orient [Needs Review] [[Ep7, 90:10](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5410s)]
```vex
@orient = slerp(base, target, blend);
```
Uses spherical linear interpolation (slerp) to smoothly blend between two quaternion orientations stored in 'base' and 'target' variables, with the blend factor controlling the interpolation amount, and assigns the result to the @orient attribute. This allows for smooth rotation transitions that preserve the shortest path between orientations, commonly used when transforming geometry while maintaining proper orientation control.

## Orient Attribute

### Quaternion Orient Setup with Extra Rotation [[Ep7, 98:52](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5932s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N,@up));

vector4 extrarot = quaternion($PI/2, {1,0,0});
```
Creates an orientation quaternion for each point by building a transform matrix from normalized position as normal and world up vector, then stores it in @orient attribute. An additional rotation quaternion is prepared using axis-angle notation (90 degrees around X-axis) to demonstrate how multiple quaternions can be combined for layered transformations.

### Quaternion Rotation Composition [[Ep7, 99:42](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5982s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));

vector4 extrarot = quaternion($PI/2, {1,0,0});

@orient = qmultiply(@orient, extrarot);
```
Creates an orientation quaternion from normalized position vectors using maketransform, then applies an additional 90-degree rotation around the X-axis using qmultiply. This technique demonstrates composing multiple quaternion rotations by multiplying them together, with the extra rotation rotating each point's orientation by PI/2 radians.

## See Also
- **VEX Data Types** (`vex_types.md`) -- quaternion and vector4 type reference
