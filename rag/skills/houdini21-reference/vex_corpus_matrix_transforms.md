# VEX Corpus: Matrix Transforms

> 17 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Intermediate (7 examples)

### set

```vex
vector4v=set(1.0,2.0,3.0,4.0);matrix3m=set(1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0);
```

Signature: vector4v=set(1.0,2.0,3.0,4.0);matrix3m=set(1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0);

When filling a matrix in Houdini, the numbers go across the first row, then across the second row, and s....

### usd_addinversetotransformorder

```vex
// Note, the USD_XFORM_TRANSLATE and USD_AXIS_Z constants used below// are defined in "usd.h" VEX header, so include it.#include <usd.h>// Construct the pivot translation operation suffix and name.stringpivot_xform_suffix="some_pivot";stringpivot_xform_name=usd_transformname(USD_XFORM_TRANSLATE,pivot_xform_suffix);// Rotate about z-axis that goes thru pivot (1,0,0).usd_addtranslate(0,"/geo/cone",pivot_xform_suffix,{1,0,0});usd_addrotate(0,"/geo/cone","some_rotation",USD_AXIS_Z, -90);usd_addinversetotransformorder(0,"/geo/cone",pivot_xform_name);
```

Signature: // Note, the USD_XFORM_TRANSLATE and USD_AXIS_Z constants used below// are defined in "usd.h" VEX header, so include it.#include <usd.h>// Construct the pivot translation operation suffi....

### usd_addrotate

```vex
// Include "usd.h" that defines axis and order constants.#include <usd.h>// Rotate the cube 30 degrees around the z-axis.usd_addrotate(0,"/geo/cube","",USD_AXIS_Z,30);// Rotate the mesh 45 degrees counter-clock wise around the y-axis.usd_addrotate(0,"/geo/mesh","geo_rotation",USD_AXIS_Y, -45);// Rotate the cone about Euler angles.usd_addrotate(0,"/geo/cone","cone_rotation",USD_ROTATE_XYZ,{0,30,45});
```

Signature: // Include "usd.h" that defines axis and order constants.#include <usd.h>// Rotate the cube 30 degrees around the z-axis.usd_addrotate(0,"/geo/cube","",USD_AXIS_Z,30);// Rotate the mesh ....

### usd_addtotransformorder

```vex
// Note, the USD_XFORM_TRANSLATE and USD_AXIS_Z constants used below// are defined in "usd.h" VEX header, so include it.#include <usd.h>// Make the first step (i.e., translate)stringstep_suffix="step";usd_addtranslate(0,"/geo/cone",step_suffix,{1,0,0});// Now repeat the same step translation by adding it to the transform orderstringstep_name=usd_transformname(USD_XFORM_TRANSLATE,step_suffix);usd_addrotate(0,"/geo/cone","first_rotation",USD_AXIS_Z, -30);usd_addtotransformorder(0,"/geo/cone",step_name);usd_addrotate(0,"/geo/cone","second_rotation",USD_AXIS_Z,45);usd_addtotransformorder(0,"/geo/cone",step_name);
```

Signature: // Note, the USD_XFORM_TRANSLATE and USD_AXIS_Z constants used below// are defined in "usd.h" VEX header, so include it.#include <usd.h>// Make the first step (i.e., translate)stringstep....

### usd_addtransform

```vex
// Transform the cube.#include <math.h>matrixxform=maketransform(XFORM_SRT,XFORM_XYZ,{1,2,3},{3,45,60},{0.5,0.25,2});usd_addtransform(0,"/geo/cube","my_xform",xform);
```

Signature: // Transform the cube.#include <math.h>matrixxform=maketransform(XFORM_SRT,XFORM_XYZ,{1,2,3},{3,45,60},{0.5,0.25,2});usd_addtransform(0,"/geo/cube","my_xform",xform);

A handle to the st....

### volumecubicsamplev

```vex
vectorP={1.0,2.0,3.0};matrix3grad,hessX,hessY,hessZ;vectorval1=volumecubicsamplev(0,"vel",P,grad,hessX,hessY,hessZ));vectoru={0.1,0.01,0.001};vectorval2=volumecubicsamplev(0,"vel",P+u);// By Taylor expansion we have:// `val1 + u * grad` is approximately equal to `val2`// And the second order approximation:// `val1 + u * grad + 0.5 * set(dot(u, u*hessX), dot(u, u*hessY), dot(u, u*hessZ))`// is appriximately equal to `val2`
```

Signature: vectorP={1.0,2.0,3.0};matrix3grad,hessX,hessY,hessZ;vectorval1=volumecubicsamplev(0,"vel",P,grad,hessX,hessY,hessZ));vectoru={0.1,0.01,0.001};vectorval2=volumecubicsamplev(0,"vel",P+u);/....

### volumesmoothsamplev

```vex
vectorP={1.0,2.0,3.0};matrix3grad,hessX,hessY,hessZ;vectorval1=volumesmoothsamplev(0,"vel",P,grad,hessX,hessY,hessZ);vectoru={0.1,0.01,0.001};vectorval2=volumesmoothsamplev(0,"vel",P+u);// By Taylor expansion we have:// `val1 + u * grad` is approximately equal to `val2`// And the second order approximation:// `val1 + u * grad + 0.5 * set(dot(u, u*hessX), dot(u, u*hessY), dot(u, u*hessZ))`// is appriximately equal to `val2`
```

Signature: vectorP={1.0,2.0,3.0};matrix3grad,hessX,hessY,hessZ;vectorval1=volumesmoothsamplev(0,"vel",P,grad,hessX,hessY,hessZ);vectoru={0.1,0.01,0.001};vectorval2=volumesmoothsamplev(0,"vel",P+u);....

## Advanced (10 examples)

### Create a new attribute â

```vex
@foo;
```

You want to define a new point float attribute 'foo'? Just type

Hit ctrl-enter, look in the geometry spreadsheet, there you go, float attribute.

### Rotate prims around an edge â

```vex
vector p0 = point(0,'P',0);
vector p1 = point(0,'P',1);

vector axis = p0-p1;
```

Based on what we know so far, it shouldn't be too hard to rotate primitives around an edge.

### Rotate prims around an edge, alternate version â

```vex
int points[] = primpoints(0,@primnum); // list of points in prim

// get @P of first and second point
vector p0 = point(0,'P',points[0]);
vector p1 = point(0,'P',points[1]);

vector axis = p0-p1;

// ...
```

Jesse reminded me of another method; I mentioned earlier that to use the rotate matrix by itself won't work because it applied rotation around the origin.

### Orient via matrix â

```vex
matrix3 m = ident();
 @orient = quaternion(m);
```

So obviously that means if we're ever in the unlikely scenario of having a matrix lying around that we've defined ourselves, that's yet another format we can directly pass to the quaternion function.

### Convert to N and up vectors â

```vex
matrix3 m = qconvert(@orient);
 @N = {0,0,1}*m;
 @up = {0,1,0}*m;
```

Well, human readable if you can read matricies, which I can't.

### Extracting Axes from Quaternion Matrix

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
@orient = quaternion(@orient);
@orient *= quaternion(radians(20) * sin((@Time*chf("m"))*3), {0,1,0});
// ...
```

Converts a quaternion orientation to a matrix3, then extracts the individual axis vectors using set() which splits the matrix into an array of three vectors.

### Transform Intrinsic from Matrix

```vex
qorient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, v@scale);
m *= dconvert(qorient);

setprimintrinsic(0, "transform", @ptnum, m);
```

Demonstrates building a matrix3 transform from orient and scale attributes, then applying it to the 'transform' intrinsic of packed primitives.

### Transform Intrinsic with Matrices

```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, @scale);
m = qconvert(@orient);

setprimintrinsic(0, "transform", @ptnum, m);
```

Creates a matrix3 transform by combining scale and orientation (from quaternion), then applies it to the transform intrinsic of primitives.

### Packed Full Transform Intrinsic

```vex
matrix3 m = matrix3(myfancyMatrix);

matrix pft = prim(0, "intrinsic:packedfulltransform", @ptnum);

@a = pft;
```

Demonstrates accessing the packedfulltransform intrinsic from packed geometry, which returns a 4x4 matrix representing the full transformation including translation.

### Packed Primitive Intrinsics and Closed Polygons

```vex
matrix pft = primintrinsic(0, "packedfullstransform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;

int open_load = int(rand(@ptnum+@Frame)*2);
setprimintrinsic(0, "closed", @primnum, open_load);
```

Demonstrates reading packed primitive transform intrinsics and extracting rotation/scale components using matrix casting.
