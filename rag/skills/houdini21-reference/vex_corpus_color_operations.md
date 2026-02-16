# VEX Corpus: Color Operations

> 79 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Beginner (43 examples)

### Customise the UI elements â

```vex
v@colour1 = chv('col1');
v@colour2 = chv('col2');
v@colour3 = chv('col3');
v@colour4 = chv('col4');
```

The plug button is a convenience function, it just scans for any channel references, and creates the default type, with a default value.

### Get values from other points, other geo â

```vex
float otherCd = point(0, "Cd", 5);
```

Groundwork for the next step (and probably mentioned above in passing).

If you want the colour of the current point, you use @Cd.

### Colour â

```vex
@Cd = @N;
```

One of the easiest things you can do with vex is to set the colour of your geometry based on attributes.

### Attribute components â

```vex
@Cd = @P.x;
```

@Cd is a vector, so is @P and @N, so its easy to assign them to each other, as the types are compatible.

You can also refer to sub-components, so just the x component of @P for example, with the f....

### More on code style â

```vex
foo = foo * 5;
```

Something I glossed over is a subtle C-style thing that can be easy to miss if you're not used to it.

If you had a variable and wanted to multiply it by 5, you could do this:

But there's a shorth....

### Joy of Vex Day 5 â

```vex
@P.y = @ptnum % 5;
```

Modulo, more arithmetic tricks (quantising), but show that often a chramp is easier (eg stepped chramp);

Everyone understands + - * /, but % usually surprises people who haven't done much coding b....

### Setting Color from Position

```vex
@Cd = @P;

@Cd = @P;

@Cd = @P.x;
```

Demonstrates setting the color attribute (@Cd) equal to position (@P).

### Color from Normal and Position

```vex
@Cd = @N;

@Cd = @P;

@Cd = @P.x;
```

Demonstrates assigning vector attributes to color by setting @Cd equal to @N (normal), @P (position), or individual components like @P.x.

### Vectors as Color Components

```vex
@Cd = @P;

@Cd = @N;

@Cd = @P.x;
```

Demonstrates how vectors can be assigned to color attributes since both are three-component values.

### Visualizing vectors as color

```vex
@Cd = @P;

@Cd = @N;

@Cd = @N.x;
```

Demonstrates how vector attributes like position (@P) and normal (@N) can be assigned to color (@Cd) for visualization, since both are three-component values.

### Position to Color Mapping

```vex
@Cd = @P;

@Cd = @P.x;
```

Demonstrates mapping position (@P) directly to color (@Cd), which visualizes spatial coordinates as RGB values.

### Position to Color Mapping Components

```vex
@Cd = @P;

@Cd = @P;

@Cd = @P.x;

@Cd = @N.y;
```

Demonstrates assigning position and normal components to color attributes.

### Position vs Normal-Based Color

```vex
@Cd = @P;

@Cd = @P.x;

@Cd = @N.y;
```

Demonstrates the difference between position-based and normal-based color assignment.

### Color from Normals vs Position

```vex
@Cd = @N;

@Cd = @P;

@Cd = @P.x;

@Cd = @N.y;
```

Demonstrates the visual difference between coloring geometry by normal direction (@N) versus world position (@P).

### Accessing Vector Components

```vex
@Cd = @P.x;
```

Assigns the X component of the position attribute to the color attribute, resulting in all three RGB channels being set to the same value (the X coordinate).

### Vector component access with normals

```vex
@Cd = @N.y;
```

Sets the color attribute to the Y component of the normal vector.

### Vector Component Access

```vex
@Cd = @P.x;

@Cd = @N.y;
```

Individual components of vector attributes can be accessed using dot notation (.x, .y, .z).

### Normal Component to Color

```vex
@Cd = @N;

@Cd = @P;

@Cd = @N.x;

@Cd = @N.y;
```

Demonstrates assigning individual normal vector components to color.

### Component-Based Color Assignment

```vex
@Cd = @N.y;

@Cd = @P.y;

@Cd = @P.x;

@Cd = @N.y;
```

Demonstrates assigning color based on individual vector components (x or y) from position or normal attributes.

### Extracting Normal Components to Color

```vex
@Cd = @N.y;

@Cd = @P.x;

@Cd = @N.y;
```

Demonstrates extracting individual vector components from attributes like normals and positions and assigning them to color.

### Color from Position Math

```vex
@Cd = @N.y;

@Cd = @P.x + 1;

@Cd = @P.x - 0;

@Cd = @P.x * 0 * 0.1;
```

Demonstrates basic mathematical operations on position and normal attributes to set color values.

### Single Component Math Operations

```vex
@Cd = @P.x + 1;

@Cd = @P.x - 0;

@Cd = @P.x * 0 * 0.1;

@Cd = (@P.x - 0) * 0.1;
```

Demonstrates performing basic mathematical operations on a single component of an attribute (the x component of @P) and assigning the result to color.

### Offsetting Color Values

```vex
@Cd = @P.x + 3;
```

Adding a constant value of 3 to the position's x-component shifts the color visualization, moving the zero-point (where color transitions from black to white) to the left into negative space.

### Scaling color with subtraction

```vex
@Cd = (@P.x - 6) * 0.1;
```

Demonstrates subtracting an offset value from position before scaling to control the color gradient range.

### Offsetting color values with subtraction

```vex
@Cd = (@P.x - 6) * 0.3;
```

Subtracts 6 from the X position before multiplying by 0.3 to calculate color values.

### Component-wise color assignment

```vex
@Cd.x = (@P.x - 3) * 1.2;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.x + 1;
@Cd.z = @P.y;

@Cd = @ptnum;
```

Demonstrates how to assign values to individual color components (x, y, z) separately rather than assigning the entire vector at once.

### Mapping Position to Color Channels

```vex
@Cd.x = @P.x * 1.2;
@Cd.y = @P.z + 2;
@Cd.z = @P.y;
```

Demonstrates mapping position components to color channels with transformations.

### Color Assignment Variations

```vex
@Cd = (@P.x - 0) * 0.1;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.x + 1;
@Cd.z = @P.y;

@Cd = @ptnum;
```

Demonstrates different approaches to assigning color values by mapping position components and point numbers to RGB channels.

### Remapping Position Components to Color

```vex
@Cd = (@P.x-0) * 0.;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;

@Cd = @ptnum;
```

Demonstrates remapping position components to color channels in non-standard ways.

### Point Number Color Assignment

```vex
@Cd = @ptnum;
```

Demonstrates assigning the point number attribute (@ptnum) directly to color (@Cd).

### Color from Point Number

```vex
@Cd = @ptnum;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z + 2;
@Cd.z = @P.y;

@Cd = @ptnum;
```

Sets color attribute to the point number value, demonstrating that point numbers go from 0 to 899 in this grid.

### Point Number to Color Ramp

```vex
@Cd = @ptnum/@numpt;
```

Attempts to create a color ramp by dividing point number by total number of points.

### Normalizing Values with fit()

```vex
@Cd = fit(@P.y, -1, 1, 0, 1);
```

Demonstrates using the fit() function to normalize values from one range to another, specifically converting position Y values from -1 to 1 into the 0 to 1 range.

### Color from Normal Y Component

```vex
@Cd = @N.y;

@Cd = -@N.y;
```

Sets the color attribute (@Cd) based on the Y component of the normal vector (@N.y).

### Normal-based Color Lighting

```vex
@Cd = -@N.y;
```

Sets the color attribute to the negated Y component of the point normal, creating a lighting effect where upward-facing surfaces are darker and downward-facing surfaces are lighter.

### Dot Product Lighting

```vex
@Cd = dot(@N, {0,1,0});
```

Uses the dot product to calculate lighting by comparing each point's normal vector against an upward-facing light direction vector {0,1,0}.

### Bounding Box Color Thresholding

```vex
vector bbox = relpointbbox(0, @P);
@Cd = {1,0,0};
if(bbox.y < 0.5){
    @Cd = {0,1,0};
}
```

Uses relpointbbox to get the normalized bounding box coordinates of each point, then conditionally colors points based on their vertical position.

### Dot Product for Conditional Coloring

```vex
float d = dot(@N, {0,1,0});
@Cd = {1,0,0};
if(d > 0.3){
    @Cd = {1,1,1};
}
if(bbox.y < 0.5){
    @Cd = {0,1,0};
}
```

Creates a float variable to store the dot product between the point normal and an up vector {0,1,0}, then uses this value to conditionally set color to white when the dot product exceeds 0.3.

### Handling Negative Color Values

```vex
@Cd = @N;
if (min(@Cd)<0) {
    @Cd = 0.1;
}
```

Assigns normal vectors to color attributes, then checks if any color component is negative using min().

### Conditional Color Assignment

```vex
@Cd = @N.z;
if (sin(@Cd.x) > 0) {
    @Cd = 0.1;
}
```

Sets the color attribute to the Z component of the normal, then conditionally overrides it to a dark gray value (0.1) when the sine of the red channel is positive.

### Modulo on Color Attributes

```vex
@Cd.r = @ptnum % 5;
@P.y = @ptnum % 5;
@Cd.r = @Time % 0.7;
```

Demonstrates using the modulo operator (%) to create repeating patterns in point attributes.

### Reading Second Input Attributes

```vex
vector p1 = @opinput1_P;
vector cd1 = @opinput1_Cd;

@P = p1;
@Cd = cd1;
```

This demonstrates reading attributes from the second input geometry using the @opinput1_ prefix.

### Reading Attributes from Second Input

```vex
vector pi = @opinput1_P;
vector cd1 = @opinput1_Cd;

@P = pi;
@Cd = cd1;
```

Demonstrates how to read attributes from the second input (input 1) of a wrangle node using the @opinput1_ prefix syntax.

## Intermediate (32 examples)

### Get existing attribute values â

```vex
v@myvector=@P;
```

You want myvector to get its values from the point position?

The @ symbol is used to get attributes as well as set them.

### opinput â

```vex
@P = point(1, 'P', @ptnum);
```

Say you had 2 identical grids, and one has been deformed by a mountain sop.

### Multiple tests, other tests â

```vex
if (@ptnum > 50) {
     if (@P.x < 2) {
          @Cd = {1,0,0};
     }
 }
```

Say you wanted to do a thing if @ptnum is greater than 50, and @P.x is less than 2.

### Color from Point Number

```vex
@Cd = @ptnum;

@Cd = (@P.x - 0) * 0.3;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;

// ...
```

Setting color (@Cd) equal to point number (@ptnum) assigns each point a color value based on its index.

### Color from Point Number

```vex
@Cd = (@P.x-0) * 0.1;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z+2;
@Cd.z = @P.y;

@Cd.x = @P.x-1 * 1.2;
@Cd.y = @P.z+2;
// ...
```

Demonstrates assigning point color directly from point number using @ptnum.

### Point Number to Color Mapping

```vex
@Cd = @ptnum;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z + 2;
@Cd.z = @P.y;

@Cd = (@P.x * 0.0) * 0.3;

// ...
```

Setting color (@Cd) directly to point number (@ptnum) creates undesirable results because point numbers on a grid from 0 to 899 exceed the valid color range of 0 to 1, resulting in nearly all white....

### Normalizing Point Number Colors

```vex
@Cd = @ptnum;

@Cd = (@P.x - 0) * 0.1;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.x + 2;
@Cd.z = @P.y;

// ...
```

Demonstrates the problem of directly assigning point numbers to color without normalization.

### Channel Operator Input Syntax

```vex
vector p1 = OWInput1.P1;
vector cd1 = OWInput1.Cd;

@P = p1;
@Cd = cd1;
```

Demonstrates reading position and color attributes from a Channel Operator input using the OWInput syntax.

### Dot Product for Color Masking

```vex
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);
```

Retrieves the position of the first point from input 1 and uses the dot product between the current point's normal and that position to create a color value.

### Normalized Direction for Surface Masking

```vex
@Cd = dot(@N, {0,1,0});

vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);

pos = normalize(pos);
@Cd = dot(@N, pos);
```

Demonstrates creating a surface mask by calculating the dot product between surface normals and a direction vector from another input.

### Normalizing Position for Dot Product Mask

```vex
vector pos = point(1, "P", 0);
pos = normalize(pos);
@Cd = dot(@N, pos);
```

Demonstrates normalizing a position vector before using it in a dot product calculation to create a directional mask.

### Floating Point Comparison and Multiple Conditionals

```vex
if ( abs(foo - bar) < 0.00001 ) {
    @Cd = {1,0,0};
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
// ...
```

Demonstrates epsilon testing for floating point comparison using absolute value to avoid precision errors, and shows multiple ways to combine conditional tests including nested if statements, AND (....

### Matrix Translation Component Visualization

```vex
@P.x = @id == 1;
@P.y = 0.0;
@P.z = 0.5;
@Cd.x = 1;
@Cd.y = 0.0;
@Cd.z = 0.0;
@Cd.w = 1.0;
```

Demonstrates setting point position and color attributes to visualize matrix components.

### xyzdist Function Introduction

```vex
@P = primuv;
@Cd = v;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

The xyzdist() function finds the closest point on a geometry and returns the distance, while also writing the primitive ID and UV coordinates to output variables.

### XYZ Distance with Prim UV Sampling

```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

vector gp = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```

Uses xyzdist() to find the nearest point on geometry (input 1) and returns the distance along with primitive ID and UV coordinates.

### Transferring Attributes with primuv

```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```

Uses xyzdist to find the closest primitive and UV coordinates on input 1, then uses primuv to snap the point position to the surface and transfer the color attribute from that surface location.

### Query Attributes with primuv

```vex
i@primid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```

Demonstrates using primuv to query any attribute (not just position) from a surface.

### Querying Attributes with primuv

```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);

// ...
```

Using primuv() to query multiple attributes from a surface using parametric UV coordinates found by xyzdist().

### primuv color attribute lookup

```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);

// ...
```

Demonstrates that primuv can query any attribute from a surface using parametric coordinates, not just position.

### Sample Color with primuv

```vex
int @primid;
vector @uv;
float @dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```

After using xyzdist() to find the closest point on a geometry and get its primitive ID and UV coordinates, primuv() can be used to sample not just position but also other attributes like color.

### Transferring Color with primuv

```vex
int primid;
v@uv;
float dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```

This code finds the nearest point on a reference geometry using xyzdist() to get the primitive ID and UV coordinates, then uses primuv() to both relocate the point position and transfer the color a....

### Reading color with primuv

```vex
int primid;
v@uv;
float dist;

@dist = xyzdist(1, @P, @primid, @uv);
@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```

After using xyzdist to find the closest point on a grid and obtaining the primitive ID and UV coordinates, primuv is used to sample both the position and color attributes from that primitive location.

### Reading Color from Closest Surface Point

```vex
i@prim1id;
v@uv;
@dist;

@dist = xyzdist(1, @P, @prim1id, @uv);

@P = primuv(1, 'P', @prim1id, @uv);

// ...
```

Uses xyzdist to find the closest primitive and UV coordinates on a grid surface from a point in space, then uses primuv to sample both the position and color attributes at that UV location.

### Reading Primitive Color with primuv

```vex
i@primId;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primId, @uv);

@P = primuv(1, 'P', @primId, @uv);
@Cd = primuv(1, 'Cd', @primId, @uv);
```

Uses xyzdist() to find the closest primitive on input 1 (a grid) and stores the primitive ID and UV coordinates.

### Reading Color Attributes via UV Lookup

```vex
i@primid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', i@primid, @uv);

// ...
```

Using xyzdist to find the closest primitive and UV coordinates on a grid, then using primuv to read both position and color attributes from that location.

### Proximity Attribute Sampling

```vex
@dist = xyzdist(1, @P, @ptid, @uv);

v@c = primuv(1, "P", @ptid, @uv);
@Cd = primuv(1, "Cd", @ptid, @uv);
```

Uses xyzdist() to find the closest point on a primitive surface, capturing both the primitive ID and UV coordinates.

### create_cdf

```vex
// Iterate over all lights, sampling their powerint[]li=getlights();floatvalues[];resize(values,len(li));intnsamples=256;intsid=israytrace?SID:newsampler();vectors,pos,clr;floatscale;for(inti=0;i<len(li);i++){for(intj=0;j<nsamples;j++){nextsample(sid,s.x,s.y,"mode","nextpixel");sample_light(li[i],P,s,Time,pos,clr,scale);values[i] +=luminance(clr);}values[i] /=nsamples;}// Create a CDF of the power distributionfloatcdf[] =create_cdf(values);// Randomly select a light based on power distributionnextsample(sid,s.x,s.y,"mode","nextpixel");intindex=0;sample_cdf(cdf,s.x,index);// Do something with the selected light// li[index] ...
```

Signature: // Iterate over all lights, sampling their powerint[]li=getlights();floatvalues[];resize(values,len(li));intnsamples=256;intsid=israytrace?SID:newsampler();vectors,pos,clr;floatscale;for....

### file_stat

```vex
#include <file.h>v@Cd={1,0,0};stats=file_stat("$HH/pic/Mandril.pic");if(s->isValid())v@Cd={0,1,0};
```

Overwrites an integer array with data representing the file system
    information for the given file.

Do not use this function.

### illuminance

```vex
illuminance(position, [axis], [angle], [light_typemask], [lightmask]){// Here, Cl and L will be set to the value/direction for the// current light source.// To force the shadow shader to be called, use:// shadow(Cl);}
```

Signature: illuminance(position, [axis], [angle], [light_typemask], [lightmask]){// Here, Cl and L will be set to the value/direction for the// current light source.// To force the shadow shader to....

### specularBRDF

```vex
vectornn=normalize(frontface(N,I));vectorii=normalize(-I);Cf=0;illuminance(P,nn){vectorll=normalize(L);Cf+=Cl* (specularBRDF(ll,nn,ii,rough) +diffuseBRDF(ll,nn));}
```

Signature: vectornn=normalize(frontface(N,I));vectorii=normalize(-I);Cf=0;illuminance(P,nn){vectorll=normalize(L);Cf+=Cl* (specularBRDF(ll,nn,ii,rough) +diffuseBRDF(ll,nn));}

Adds an item to an ar....

### split_bsdf

```vex
// Split BSDF into component lobesfloatweights[];bsdflobes[];split_bsdf(lobes,hitF,weights);// Get albedos of lobesfloatalbedos[];resize(albedos,len(lobes));for(inti=0;i<len(lobes);i++){albedos[i] =luminance(albedo(lobes[i], -hitnI)) *weights[i];}// Compute CDFfloatcdf[] =compute_cdf(albedos);// Randomly select a BSDF based on albedo distributionintindex=0;sample_cdf(cdf,s.x,index);// Do something with the selected BSDF// lobes[index] ...
```

Signature: // Split BSDF into component lobesfloatweights[];bsdflobes[];split_bsdf(lobes,hitF,weights);// Get albedos of lobesfloatalbedos[];resize(albedos,len(lobes));for(inti=0;i<len(lobes);i++){....

### Attribute Syntax

```vex
// Reading attributes (@ prefix)
vector pos = @P;           // Built-in position
float scale = @pscale;     // Custom float attribute
int id = @id;              // Custom integer attribute

// Writing attributes
@Cd = {1, 0, 0};          // Set color to red
@N = normalize(@N);        // Modify normal
// ...
```

// Reading attributes (@ prefix)
vector pos = @P;           // Built-in position
float scale = @pscale;     // Custom float attribute
int id = @id;              // Custom integer attribute

// Writing.

## Advanced (3 examples)

### Random colour groups with vex â

```vex
string groups[]  = detailintrinsic(0, 'primitivegroups');

foreach (string g; groups) {
    if (inprimgroup(0,g,@primnum)==1) {
        @Cd = rand(random_shash(g));
    }
}
```

An extension of the above snippet:.

### xyzdist to get info about the closest prim to a position â

```vex
float distance;
int myprim;
vector myuv;
distance = xyzdist(1,@P, myprim, myuv);
```

Download scene: Download file: xyzdist_example.hipnc

If you've used a ray sop, this is a similar thing.

### xyzdist â

```vex
i@primid;
 v@uv;
 @dist;

 @dist = xyzdist(1, @P, @primid, @uv);
```

minpos gives you the closest @P on geometry when you feed it some arbitrary position.

## Expert (1 examples)

### Dot Product with Normal and Up Vector

```vex
@Cd = dot(@N, {0, 1, 0});
```

Uses the dot product between the surface normal (@N) and an up vector (0,1,0) to generate a color value.
