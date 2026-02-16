# VEX Corpus: Flow & Visualization

> 61 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Intermediate (54 examples)

### Wispy Curves with Curlnoise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
// ...
```

Creates wispy polyline curves by iterating along each point's normal direction, adding multiple points displaced by curlnoise.

### Curl Noise Polylines with Normals

```vex
vector offset = @nrelpe(@OpInput1)*{1,0.3,1};
int pt = addpoint(0,@P+pos);
addprim(0,"polyline",@ptnum,pt);

vector offset, pos;
int pr, pt;
float stepsize;

// ...
```

Creates polyline primitives by iterating through points and adding vertices displaced by both the point normal and curl noise.

### Polyline growth with curl noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
// ...
```

Creates a polyline primitive that grows from each point along its normal direction, with curl noise applied as offset at each step.

### Creating Polylines with Curl Noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline primitive with six points, positioning each point along a path influenced by curl noise that animates over time.

### Removing Points with Random Threshold

```vex
removepoint(0, @ptnum);

// removepoint(int geohandle, int point_number)
// removepoint(int geohandle, string pointgroup, int and_or_prims)

if (rand(@ptnum) < ch('cutoff')) {
    removepoint(0, @ptnum);
}
// ...
```

The removepoint() function deletes points from geometry by specifying a geometry handle and point number.

### Seaweed Example Setup with Random Deletion

```vex
if(rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}

// spirally seaweed using sin and cos
vector offset, pos;
int n, ps;
float stepsize;
// ...
```

Creates seaweed geometry by randomly removing primitives based on a cutoff value, then initializes variables for generating spiral seaweed patterns using sine and cosine functions.

### Near Points to New Geometry

```vex
int pt1[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;
foreach (pt; pt1) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
```

Finds up to 25 nearby points from input 1 within a radius controlled by channel 'd', then creates new points in the current geometry at each found point's position.

### Point Cloud Basics Setup

```vex
int pt[] = nearpoints(1, @P, ch('d'), 25);
int pts;
v@Cd = 1;
foreach (pt; pts) {
    vector pos = point(1, "P", pt);
    addpoint(0, pos);
}
```

This snippet finds nearby points using nearpoints() and iterates through them with a foreach loop to create new points at their positions.

### Point Cloud Creation Loop

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos = 0;
foreach (pt; pts) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
```

Finds nearby points within a distance using nearpoints() and creates new points at their positions.

### Animating Wave with Delays

```vex
v@visualize;
int npts[];
int pts[];
float d, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
// ...
```

Creates an animated wave effect with per-point delays by finding nearby points within a radius, calculating randomized time offsets using fit01 and rand, then modifying Y position with a sine funct....

### Adding Points Conditionally

```vex
// addpoint(0, {0,0,0});

if (@ptnum==0) {
    addpoint(0, @P+(0,1,0));
}

// addpoint(0, @P + (0,5,0));

// ...
```

Demonstrates using conditional statements to add points selectively based on point number, avoiding the need for post-creation fusing.

### Adding Points with Offsets

```vex
if (@ptnum==1) {
    addpoint(0, (0,1,0));
}

addpoint(0, @P + (0,1,0));

addpoint(0, @P + (0,5,0));

// ...
```

Demonstrates adding new points to geometry using addpoint() with various offset strategies.

### addpoint without assignment

```vex
addpoint(0, @P * (0,1,0));

addpoint(0, @P + (0,5,0));

addpoint(0, @P + @N * 0.1);

for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
// ...
```

The addpoint() function can be called without assigning its return value to a variable when you don't need to reference the point number later.

### Creating points along normals with loops

```vex
addpoint(0, @P * @N * 4);

addpoint(0, @P + (0, 5, 0));

addpoint(0, @P + @N * 4);

for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
// ...
```

Demonstrates creating new points at positions offset from the current point using addpoint().

### Creating Points Along Normal with For Loop

```vex
for(int i = 0; i < 10; i++){
    addpoint(0, @P + @N * 0.1 * i);
}
```

Uses a for loop to create 10 points along the surface normal, each spaced 0.1 units apart from the previous point.

### For loop with addpoint

```vex
for(int i = 0; i < len; i++){
    addpoint(0, set * BB * (i * 0.1));
}
```

A for loop iterates from 0 to len, creating points at each iteration using addpoint.

### Creating Points with addpoint

```vex
for(int i = 0; i < 4; i++){
    addpoint(0, @P * 0.8 * (1 + 0.1));
}
```

Uses a for loop to create 4 new points using addpoint() on geometry input 0.

### Multiple Points Along Normal with Noise

```vex
vector offset, pos;
int pt, pr;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
// ...
```

Creates wispy lines by generating multiple points along each input point's normal direction using a for loop.

### Curlnoise wispy hair growth

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
// ...
```

Creates wispy procedural hair-like geometry by generating polylines that grow along normals with curlnoise offset at each step.

### Implicit normals in VEX

```vex
vector pos = chv('@prim') * (1, 0.3, 1);
int pt = addpoint(0, @P * pos);
addprim(0, 'polyline', @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

// ...
```

Demonstrates that @N (normal) can be read implicitly in VEX without explicitly creating it beforehand, as Houdini automatically calculates normals for geometry primitives.

### Polyline with Curl Noise Offset

```vex
vector pos = v@P;
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

// ...
```

Creates polylines extending from each point along the normal direction with curl noise offsets.

### Implicit normals in geometry creation

```vex
vector pos, offset;
int pr, pt;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
// ...
```

Demonstrates how Houdini uses implicit point normals when generating geometry along the @N direction.

### Normals in Geometry Creation

```vex
vector pos = ch("pos") * {1,0,1};
int pt = addpoint(0,@P+pos);
addprim(0,"polyline",@ptnum,pt);

vector offset, pos;
int pr, pt;
float stepsize;

// ...
```

Demonstrates how implicit normals on grid geometry are used when creating new geometry with @N in loops.

### Curl Noise Trail Generation

```vex
vector pos = @P;
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", pt, @ptnum, pt);

vector pos = @P + noise(@P + @Time) * {1, 0, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

// ...
```

Demonstrates progressive techniques for creating polyline trails from points.

### Extruding Polylines with Normals

```vex
vector pos = chv("pos");
int pt = addpoint(0, @P);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

// ...
```

Creates extruded polyline geometry by iterating along point normals with curl noise displacement.

### Normal Calculation Methods for Displacement

```vex
vector pos = chv("pos");
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pt, pt1, pr;
float bias = 0;
float stepsize = 0.5;
// ...
```

Demonstrates how normals can be calculated implicitly by Houdini based on vertex data versus being explicitly set beforehand.

### Growing Lines with Curl Noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
// ...
```

Creates polylines that grow from each input point along the normal direction with curl noise displacement applied at each step.

### Curl Noise Trail Generator

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline trail by iterating 6 times, calculating curl noise at animated positions offset by the loop iteration, and adding points along the noise-driven path.

### Creating Polyline with Offset Points

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline primitive with six points positioned along the normal direction from the original point.

### Animated Fur Using Curlnoise

```vex
for (int i = 0; i < chi('i'); i++) {
    vector offset = curlnoise(f@Time*ch('z'))*ch('z');
    vector pos = @P + @N * i * chf('size') + offset;
    int pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

Creates animated fur strands by iterating and generating points along the normal direction, offset by curlnoise based on time.

### Curl Noise Fur Displacement

```vex
for (int i = 0; i < nprims(@opinput1); i++) {
    offset = curlnoise(@P[elem=i]) * 0.2;
    pos = @P + @N * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, prim, pt);
}
```

Creates wavy, organic-looking fur by iterating over primitives and displacing new points using curl noise combined with the normal direction and a step size.

### Curl Noise Grass Generation

```vex
for (int i = 0; i < chi(""); i++) {
    offset = curlnoise((@P+i*chf("amp1"))*chf("freq2"));
    pos = @P + @N * chf("stepsize") + offset;
    pt = addpoint(0, pos);
    addvertex(0, @primnum, pt);
}
```

Generates wavy grass-like geometry by iterating to create points displaced by curl noise.

### Creating polyline with curl noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.01;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline primitive by adding six points in a loop, positioning each point along the normal direction with a small step size, then applying curl noise offset that animates over time.

### Creating Polylines with Curl Noise Offset

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline primitive with 6 points by iterating through a loop.

### Removing Primitives with Conditions

```vex
removeprim(0, @ptnum, 1);

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
// ...
```

Demonstrates using removeprim() to delete primitives, with control over whether to keep (0) or delete (1) associated points.

### Random Prim Removal Setup

```vex
if(rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}

// spiral() seaweed using sin and cos
vector offset, pos;
int pr, pt;
```

Uses random values per primitive to conditionally remove primitives based on a cutoff threshold.

### Seaweed with random culling and spiral offset

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprims(0, @primnum, 1);
}

// spirally seaweed using sin and cos
vector offset, pos;
int pr, pt;
int nseg = 50;
// ...
```

This code randomly removes primitives based on a probability threshold, then creates spiraling seaweed geometry by generating points along a path using sine and cosine offsets.

### Random Point Deletion with Seed

```vex
v@up = set(0, 1, 0);
if(rand(@primnum, ch('seed')) < ch('cutoff')) {
    removepoint(0, @primnum, 1);
}
```

Demonstrates random point deletion using rand() with a seed parameter for reproducibility and a cutoff threshold.

### Noise vs Rand for Deletion

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
    addpoint(0, {0,1,0});
// ...
```

Comparison of rand() versus noise() for structured deletion patterns.

### Point Cloud Manual Point Iteration

```vex
int pts[] = pcfind(1, 'P', @P, ch('d'), 25);
int pt;
vector pos;
foreach (pt; pts){
    pos = point(1, 'P', pt);
    addpoint(0, pos);
}
```

This code demonstrates a manual approach to point cloud operations by finding nearby points with pcfind, then iterating through each point number to retrieve its position and create new points.

### agentrigchildren

```vex
int[]queue={transform};while(len(queue) >0){inti=removeindex(queue,0);printf("%d\n",i);foreach(intchild;agentrigchildren(0,@primnum,i))push(queue,child);}
```

Signature: int[]queue={transform};while(len(queue) >0){inti=removeindex(queue,0);printf("%d\n",i);foreach(intchild;agentrigchildren(0,@primnum,i))push(queue,child);}

When running in the context of....

### agentrigparent

```vex
introot;while(true){intparent=agentrigparent(0,@primnum,transform);if(parent<0){root=transform;break;}elsetransform=parent;}matrixroot_xform=agentworldtransform(0,@primnum,root);
```

Signature: introot;while(true){intparent=agentrigparent(0,@primnum,transform);if(parent<0){root=transform;break;}elsetransform=parent;}matrixroot_xform=agentworldtransform(0,@primnum,root);

When r....

### findattribval

```vex
intprim_num=findattribval(0,"prim","id",10);// Note: you can use idtoprim(0, 10) instead
```

Signature: intprim_num=findattribval(0,"prim","id",10);// Note: you can use idtoprim(0, 10) instead

When running in the context of a node (such as a wrangle SOP), this argument can be an integer r....

### nextsample

```vex
intnsamples=10;intsid=israytrace?SID:newsampler();for(i=0;i<nsamples;i++){if(israytrace)nextsample(sid,sx,sy,"mode","nextpixel");elsenextsample(sid,sx,sy,"mode","qstrat");// Sample something using sx/sy...}
```

Signature: intnsamples=10;intsid=israytrace?SID:newsampler();for(i=0;i<nsamples;i++){if(israytrace)nextsample(sid,sx,sy,"mode","nextpixel");elsenextsample(sid,sx,sy,"mode","qstrat");// Sample somet....

### opstart

```vex
intstarted=opstart("Performing long operation");perform_long_operation();if(started>=0)opend(started);
```

Signature: intstarted=opstart("Performing long operation");perform_long_operation();if(started>=0)opend(started);

Adds an item to an array or string.

Returns the indices of a sorted version of an....

### pcfind

```vex
intclosept[] =pcfind(filename,"P",P,maxdistance,maxpoints);P=0;foreach(intptnum;closept){vectorclosepos=point(filename,"P",ptnum);P+=closepos;}P/=len(closept);
```

Signature: intclosept[] =pcfind(filename,"P",P,maxdistance,maxpoints);P=0;foreach(intptnum;closept){vectorclosepos=point(filename,"P",ptnum);P+=closepos;}P/=len(closept);

When running in the conte....

### pcfind_radius

```vex
intclosept[] =pcfind_radius(filename,"P","pscale",1.0,P,maxdistance,maxpoints);P=0;foreach(intptnum;closept){vectorclosepos=point(filename,"P",ptnum);P+=closepos;}P/=len(closept);
```

Signature: intclosept[] =pcfind_radius(filename,"P","pscale",1.0,P,maxdistance,maxpoints);P=0;foreach(intptnum;closept){vectorclosepos=point(filename,"P",ptnum);P+=closepos;}P/=len(closept);

When ....

### print_once

```vex
// Only print "Hello world" one timefor(inti=0;i<100; ++i)print_once("Hello world\n");// Print a missing texture warning, just one time across all shadersprint_once(sprintf("Missing texture map: %s\n",texture_map),"global",1);
```

Signature: // Only print "Hello world" one timefor(inti=0;i<100; ++i)print_once("Hello world\n");// Print a missing texture warning, just one time across all shadersprint_once(sprintf("Missing text....

### rand

```vex
vectorpos=1;floatseed=0;pos*=rand(seed);
```

Signature: vectorpos=1;floatseed=0;pos*=rand(seed);

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates an array from its arguments.

### shadowmap

```vex
shadowmap(mapname,pz,spread,bias,quality,"channel",channel);
```

Signature: shadowmap(mapname,pz,spread,bias,quality,"channel",channel);

Allows you to specify your own sampling rectangle.

### usd_setcollectionincludes

```vex
// Set the exludes list on the cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_setcollectionincludes(0,collection_path,array("/geo/sphere1","/geo/sphere2"));
```

Signature: // Set the exludes list on the cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_setcollectionincludes(0,collection_path,array("/geo/sph....

### usd_setpurpose

```vex
// Set the sphere primitive to be traversable only for rendering.usd_setpurpose(0,"/geo/sphere","render");
```

Signature: // Set the sphere primitive to be traversable only for rendering.usd_setpurpose(0,"/geo/sphere","render");

A handle to the stage to write to.

### usd_setvisibility

```vex
#include <usd.h>// Make the sphere primitive visible.usd_setvisibility(0,"/geo/sphere",USD_VISIBILITY_VISIBLE);// Configure the cube primitive to inherit visibility from parent.usd_setvisibility(0,"/geo/cube",USD_VISIBILITY_INHERIT);
```

Signature: #include <usd.h>// Make the sphere primitive visible.usd_setvisibility(0,"/geo/sphere",USD_VISIBILITY_VISIBLE);// Configure the cube primitive to inherit visibility from parent.usd_setvi....

### vnoise

```vex
// 1D noisefloatfp0,fp1,p1x,p1y,p2x,p2y;vectorvp0,vp1;vnoise(s*10,0.8,seed,f1,f2,fp0,fp1);vnoise(s*10,t*10,0.8,0.8,seed,f1,f2,p1x,p1y,p2x,p2y);vnoise(P*10,{.8,.8,.8},seed,f1,f2,vp0,vp1);
```

Generates 1D noise.

## Advanced (6 examples)

### Create geometry â

```vex
int pt = addpoint(0, {0,3,0});
```

For once I promise not to do ramp falloffs or waves.

### Remove geometry, nearpoints, parallel code â

```vex
float max = ch('max');
int limit = chi('limit');
int pts[] = nearpoints(0,@P,max);
if (len(pts)>limit) {
   removepoint(0,@ptnum);
}
```

Great bonus tip courtesy of walking Vex encyclopedia Stephen Walsch.

Say you had a bunch of scattered points with no relax, and you wanted to remove points that are too close together.

The correc....

### Orient via vector length â

```vex
vector axis;
 axis = chv('axis');
 axis = normalize(axis);
 axis *= 0;

 @orient = quaternion(axis);
```

That gallop misfeature segues to another way to define a quaternion, with just an axis vector, no angle required.

### Quaternion Rotation with Slerp

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@P + @Time);
seed = chramp('noise_remap', seed);
// ...
```

Uses noise to randomly select one of four 90-degree rotation angles around a user-defined axis, creates a target quaternion from the scaled axis, then smoothly interpolates between an identity quat....

### For loops with addpoint

```vex
for(int i = 0; i<10; i++){
    addpoint(0, @P + @N * (i * 0.1));
}
```

Uses a for loop to iterate 10 times, creating points along the normal direction at incrementally increasing distances.

### Removing Geometry with VEX

```vex
removepoint(0, @ptnum);

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
// ...
```

Demonstrates how to delete points and primitives using removepoint() and removeprim() functions.

## Expert (1 examples)

### Pseudo Attributes and Compilation

```vex
// VCC compiler command (not VEX code)
// VCC -q $VOP_INCLUDEPATH -o $VOP_OBJECTFILE -e $VOP_ERRORFILE $VOP_SOURCEFILE
```

Discussion of pseudo attributes like @P, @ptnum, and @Time that are automatically generated by Houdini.
