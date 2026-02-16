# VEX Corpus: Edge & Topology

> 88 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (2 examples)

### Linear vertex or find the starting point on every curve â

```vex
i@a = @vtxnum;
```

I did this a while ago, forgot, Remi and Legomyrstan and Swalsch and Ulyssesp gave me the answers I needed.

Say you have lots of curves, and want to identify the first point in each curve.

### Ensure unique names â

```vex
@name += '_' + itoa(@primnum);
```

Good question from lovely friend and coworker Ben Skinner .

## Intermediate (80 examples)

### Cross product â

```vex
@N = cross(@N, {0,1,0});
```

Switch to the sphere now (or if you're not using my hip, create a sphere in polygon mode, frequency around 5, append a normal sop in point mode).

### Cross Product Introduction

```vex
@N = cross(@N, {0,1,0});
```

Computing the cross product between the point normal and the up vector {0,1,0}, which produces a new vector perpendicular to both input vectors.

### Cross Product Right Hand Rule

```vex
vector tmp = cross(@N, {0,1,0});
@N = cross(@N, tmp);
```

Demonstrates the right-hand rule for cross products by first computing a perpendicular vector from the normal and up vector, then using that temporary vector to compute a second perpendicular direc....

### Cross product vector orientation

```vex
@N = cross(@N, {1,1,0});
```

Uses the cross product to compute a new normal direction perpendicular to both the original normal and the vector {1,1,0}.

### Cross Product for Normal Calculation

```vex
@N = cross(@v, {1,1,0});

vector tmp = cross(@v, {0,1,0});
@N = cross(tmp, @v);
```

Demonstrates using the cross product to compute normals by crossing velocity vectors with arbitrary axis vectors.

### Double Cross Product

```vex
vector tmp = cross(@N, {0, -1, 0});
@N = cross(@N, tmp);
```

Demonstrates a double cross product operation where the normal is first crossed with a vector, stored in a temporary variable, then crossed again with the original normal.

### Cross product for hair combing

```vex
vector tmp = cross(@N, {0, 1, 0});
@N = cross(@N, tmp);
```

Creates a temporary vector by crossing the point normal with the up vector, then crosses the normal with this temp vector to produce a combed-down effect.

### Cross Product for Gravity Combing

```vex
vector tmp = cross(@N, {0, 1, 0});
@N = cross(@v, tmp);
```

Creates a temporary vector by crossing the normal with the up vector, then recalculates the normal by crossing velocity with that temporary vector.

### Gravity-Based Vector Combing

```vex
vector tmp = cross(@N, {0,1,0});
@N = cross(tmp, @N);
```

Creates a gravity-based combing effect by computing two successive cross products to align normals downward.

### Double Cross Product for Grooming

```vex
vector tmp = cross(@N, {0,1,0});
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
@N = cross(@N, tmp);
```

Demonstrates a double cross product technique commonly used in grooming operations to orient all normals downward, creating a gravity-based directional flow.

### Iterative Cross Product Rotations

```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

Demonstrates iterative application of the cross product to rotate normals around an axis.

### Sequential Cross Products for Vector Rotation

```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

Demonstrates sequential cross product operations to rotate normals around an axis.

### Iterative Cross Product Application

```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

Demonstrates iterative application of the cross product, repeatedly computing perpendicular vectors from the point normal.

### Normalizing Points and Relative Bounding Box

```vex
@P = normalize(@P);

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;
```

Normalizes point positions to create a spherical distribution, then uses relpointbbox() to get the relative position of each point within the geometry's bounding box.

### Using chramp with relpointbbox

```vex
vector bbox = relpointbbox(0,@P);
@Cd = relpointbbox(0, @P);

vector bbox = relpointbbox(0,@P);
@Cd = bbox;

vector bbox = relpointbbox(0,@P);
@P += @N*bbox.y*ch('scale');
// ...
```

Demonstrates progressive refinement of a bounding box-based displacement effect, culminating in using chramp() to create a custom remapping curve.

### Creating polylines with noise-driven endpoints

```vex
int pt = addpoint(0, @P + 0);
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, {0,3,0});
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, @P - @N);
addprim(0, 'polyline', @ptnum, pt);
// ...
```

Demonstrates creating polylines between existing points and newly generated points using addpoint() and addprim().

### Procedural Fur Using Polylines

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates procedural fur-like polylines by generating a series of points along the normal direction from each input point.

### Procedural Grass with Animated Curvature

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.1;

for(int i=0; i<@i; i++) {
// ...
```

Creates procedural grass blades by generating polylines that extend from each point along its normal direction.

### Creating Polylines with Different Primitive Types

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline primitive and adds six points to it, where each point position is offset by curl noise and stepped along the normal direction.

### Removing Primitives Conditionally

```vex
removepoint(0, @ptnum);

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) * ch('cutoff')) {
    removeprim(0, @primnum, 1);
// ...
```

Demonstrates various ways to remove geometry elements using removepoint() and removeprim() functions.

### Identity Quaternion for Orient Attribute

```vex
@orient = {0, 0, 0, 1};
```

Sets the @orient attribute to the identity quaternion {0,0,0,1}, which represents no rotation and aligns geometry to world space axes.

### Animating Primitive Closed State

```vex
int openLove = int(rand(@primnum * @Frame * 7));
setprimintrinsic(0, "closed", @primnum, openLove);
```

Uses random values driven by primitive number and frame to animate whether primitives are open or closed via the 'closed' intrinsic attribute.

### Setting closed intrinsic randomly

```vex
int openclose = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

Randomly sets the 'closed' primitive intrinsic to convert polygons between closed faces and open polyline outlines.

### Setting Primitive Closed Intrinsic

```vex
int openclose = int(rand(@primnum * @Frame) ** 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

Creates a random open/close state for each primitive using the primitive number and frame number as random seed, then uses setprimintrinsic() to set the "closed" intrinsic attribute.

### Random Open/Closed Primitives

```vex
int openlook = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openlook);
```

This code randomly sets primitives to be open or closed using a random value based on primitive number and frame.

### Randomizing Primitive Closed State

```vex
int openClose = int(rand(@primnum*frame)*2);
setprimintrinsic(0, 'closed', @primnum, openClose);

int openClose = int(rand(@primnum+frame)*2);
setprimintrinsic(0, 'closed', @primnum, openClose);
```

Uses random values to toggle the 'closed' intrinsic attribute on primitives, controlling whether curves or polygons are open or closed.

### Transferring Attributes from Second Input

```vex
int pt = nearpoint(0, v@P);
@Cd = point(0, 'Cd', pt);
```

This demonstrates transferring attributes from a second input geometry by finding the nearest point on the reference geometry and copying its color attribute.

### Rotating Normals with Cross Products

```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

Demonstrates iterative rotation of normals by 90 degrees using repeated cross products.

### Cross Product Rotation

```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
```

Demonstrates repeated application of the cross product between a normal vector and the up axis, then progressively crossing the result with itself to create progressive rotational transformations.

### Conditional Point Creation with addpoint

```vex
int pt = addpoint(0, (0,3,0));

int pt = addpoint(0, (0,3,0));

if (@ptnum==0) {
    addpoint(0, (0,5,0));
}

// ...
```

Demonstrates the problem of adding points in a point wrangle without conditional logic, where each input point creates a new point resulting in double the geometry.

### Creating Lines Between Points

```vex
int pt = addpoint(0, (0,1,0));
addprim(0, 'polyline', @ptnum, pt);
```

Creates a new point at position (0,1,0) and stores its point number in the variable pt.

### Creating polylines from points

```vex
int pt = addpoint(0, {0,0,0});
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, {0,1,0});
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, @P+@N);
addprim(0, 'polyline', @ptnum, pt);
```

Creates a new point at a specific position using addpoint(), then connects it to the current point with addprim() to form a polyline primitive.

### Polyline with Curl Noise Offset

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addpoint(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < @i+1; i++) {
// ...
```

Creates a polyline primitive by iterating and adding points along the normal direction with curl noise displacement.

### Creating polylines with curl noise

```vex
vector offset, pos;
int pr, pt;
float stepSize;

pr = addpoint(0, "polyline");
stepSize = 0.5;

for (int i = 0; i < 6; i++) {
// ...
```

Creates a polyline primitive for each point, then iteratively generates new points along the normal direction modified by curl noise, appending them to the polyline.

### Creating polyline with for loop

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < @numpt; i++) {
// ...
```

Creates a new polyline primitive for each input point and uses a for loop to generate vertices along that polyline.

### Growing Polylines with Curvoise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a 6-point polyline growing from each input point along its normal direction with curvoise-based randomization.

### Animated Fur Using Curlnoise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i = 0; i < 1; i++) {
// ...
```

Creates animated grass-like fur strands by generating polyline primitives that extend from surface normals, with curlnoise-based displacement animated by @Time.

### Dynamic polyline growth with loop

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<@i; i++) {
// ...
```

Creates a polyline primitive that grows dynamically by adding points in a loop, with each point positioned using a stepped offset plus curl noise displacement.

### Loop-based Polyline Creation

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<10; i++) {
// ...
```

Demonstrates building a polyline procedurally using a loop to add vertices incrementally.

### Creating polylines with for loops

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<61; i++) {
// ...
```

Demonstrates creating a polyline primitive using a for loop that generates points along the surface normal direction, with curlnoise-based offset for variation.

### For Loop Geometry Creation

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline primitive with 6 points using a for loop, where each point is offset along the normal direction with curl noise distortion animated by time.

### For Loop Geometry Creation

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline primitive with multiple points using a for loop that iterates 6 times.

### Noise vs Rand for Deletion

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

int pt = addpoint(0, (0,3,0));
addprim(0, 'polyline', @primnum, pt);

int pt = addpoint(0, @P + @N);
// ...
```

Demonstrates the difference between rand() and noise() for procedural deletion of primitives.

### Random Curve Open/Close with setprimintrinsic

```vex
int openclose = int(rand(@primnum*@Frame)**2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

Creates a random integer (0 or 1) per primitive per frame using a scaled random function, then uses setprimintrinsic to toggle the 'closed' intrinsic attribute on curves.

### Randomly Toggle Primitive Closed Intrinsic

```vex
int openclose = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

Creates a random integer (0 or 1) per primitive based on primitive number and frame, then sets the primitive's 'closed' intrinsic attribute to randomly open or close curves over time.

### Randomizing Primitive Open/Closed State

```vex
int open_loop = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, open_loop);
```

Uses animated random values based on primitive number and frame to toggle primitives between open and closed states.

### Random Polygon Open/Closed Animation

```vex
int openCase = int(rand(@primnum+@Frame)*2);
setprimintrinsic(0, "closed", @primnum, openCase);
```

Randomly animates polygons between open and closed states by converting a random value (0-2) to an integer and setting the 'closed' primitive intrinsic attribute.

### Random Open/Closed Polygon Animation

```vex
int openCase = int(rand(@primuv[0]*rand)*2);
setprimintrinsic(0, 'closed', @primnum, openCase);

int openClose = int(rand(@primnum+@Frame)*2);
setprimintrinsic(0, 'closed', @primnum, openClose);
```

Randomly animates polygons between open and closed states using the 'closed' primitive intrinsic.

### nearpoints point cloud query

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
v@N = {0,0,0};
foreach (pt; pts) {
    vector pos = point(1, "P", pt);
    addpoint(0, pos);
}
```

Uses nearpoints() to find up to 25 points within a specified distance from the current point, then iterates through the found points and creates new geometry at their positions using addpoint().

### agentlayerbindings

```vex
stringlayer=agentcollisionlayer(0,@primnum);int[]bindings=agentlayerbindings(0,@primnum,layer,"static");matrixxforms[] =agentworldtransforms(0,@primnum);foreach(intidx;bindings){matrixxform=xforms[idx];}
```

Signature: stringlayer=agentcollisionlayer(0,@primnum);int[]bindings=agentlayerbindings(0,@primnum,layer,"static");matrixxforms[] =agentworldtransforms(0,@primnum);foreach(intidx;bindings){matrixxf....

### agentrigfind

```vex
intidx=agentrigfind(0,@primnum,"Hips");if(idx>=0){matrixlocal_xforms[] =agentlocaltransforms(0,@primnum);matrixxform=local_xforms[idx];}
```

Signature: intidx=agentrigfind(0,@primnum,"Hips");if(idx>=0){matrixlocal_xforms[] =agentlocaltransforms(0,@primnum);matrixxform=local_xforms[idx];}

When running in the context of a node (such as a....

### bouncemask

```vex
reflect_or_refract=bouncemask("reflect refract")
```

Signature: reflect_or_refract=bouncemask("reflect refract")

A label or space-separated list of labels.

### hedge_dstpoint

```vex
intdstpt;// Get vertex number of half-edge number 3.dstpt=hedge_dstpoint("defgeo.bgeo",3);
```

Signature: intdstpt;// Get vertex number of half-edge number 3.dstpt=hedge_dstpoint("defgeo.bgeo",3);

The name of the geometry file to reference.

### hedge_equivcount

```vex
intis_boundary=0;intis_interior=0;intis_nonmanifold=0;// Determine the type of edge represented by half-edge number 3:intnumeq;numeq=hedge_equivcount("defgeo.bgeo",3);if(numeq==1)is_boundary=1;elseif(numeq>=3)is_nonmanifold=1;elseis_interior=1;
```

Signature: intis_boundary=0;intis_interior=0;intis_nonmanifold=0;// Determine the type of edge represented by half-edge number 3:intnumeq;numeq=hedge_equivcount("defgeo.bgeo",3);if(numeq==1)is_boun....

### hedge_isequiv

```vex
intopposite=0;// test if hedges 2 and 3 are oppositely oriented equivalent half-edgesif(hedge_isequiv("defgeo.bgeo",2,3)){if(hedge_srcpoint("defgeo.bgeo",2) ==hedge_dstpoint("defgeo.bgeo",3))opposite=1;}
```

Signature: intopposite=0;// test if hedges 2 and 3 are oppositely oriented equivalent half-edgesif(hedge_isequiv("defgeo.bgeo",2,3)){if(hedge_srcpoint("defgeo.bgeo",2) ==hedge_dstpoint("defgeo.bgeo....

### hedge_isprimary

```vex
intnumedges;// Count the number of edgesif(hedge_isprimary("defgeo.bgeo",3))numedges++;
```

Signature: intnumedges;// Count the number of edgesif(hedge_isprimary("defgeo.bgeo",3))numedges++;

The name of the geometry file to reference.

### hedge_isvalid

```vex
intsrcpt;// find the source point of a half-edge number 3 if it is validif(hedge_isvalid("defgeo.bgeo",3))srcpt=hedge_srcpoint("defgeo.bgeo",3);
```

Signature: intsrcpt;// find the source point of a half-edge number 3 if it is validif(hedge_isvalid("defgeo.bgeo",3))srcpt=hedge_srcpoint("defgeo.bgeo",3);

When running in the context of a node (s....

### hedge_next

```vex
intnexthedge;// Get the next half-edge of half-edge number 3.nexthedge=hedge_next("defgeo.bgeo",3);
```

Signature: intnexthedge;// Get the next half-edge of half-edge number 3.nexthedge=hedge_next("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be a....

### hedge_nextequiv

```vex
// Determine the number of half-edges equivalent to half-edge number 3 (including itself)intnum_equiv=0;inth=3;do{h=hedge_nextequiv("defgeo.bgeo",h);num_equiv++;}while(h!=3);
```

Signature: // Determine the number of half-edges equivalent to half-edge number 3 (including itself)intnum_equiv=0;inth=3;do{h=hedge_nextequiv("defgeo.bgeo",h);num_equiv++;}while(h!=3);

When runni....

### hedge_presrcpoint

```vex
intpresrcpt;// Get the pre-source point of half-edge number 3.presrcpt=hedge_presrcpoint("defgeo.bgeo",3);
```

Signature: intpresrcpt;// Get the pre-source point of half-edge number 3.presrcpt=hedge_presrcpoint("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument c....

### hedge_presrcvertex

```vex
intpresrcvtx;// Get the pre-source vertex of half-edge number 3.presrcvtx=hedge_presrcvertex("defgeo.bgeo",3);
```

Signature: intpresrcvtx;// Get the pre-source vertex of half-edge number 3.presrcvtx=hedge_presrcvertex("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argume....

### hedge_prev

```vex
intprev;// Get the previous half-edge of half-edge number 3.prevhedge=hedge_prev("defgeo.bgeo",3);
```

Signature: intprev;// Get the previous half-edge of half-edge number 3.prevhedge=hedge_prev("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an....

### hedge_primary

```vex
intprimhedge;// Get the primary half-edge equivalent  to half-edge number 3.primhedge=hedge_primary("defgeo.bgeo",3);
```

Signature: intprimhedge;// Get the primary half-edge equivalent  to half-edge number 3.primhedge=hedge_primary("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this....

### hedge_srcpoint

```vex
intsrcpt;// Get the source point of half-edge number 3.srcpt=hedge_srcpoint("defgeo.bgeo",3);
```

Signature: intsrcpt;// Get the source point of half-edge number 3.srcpt=hedge_srcpoint("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an inte....

### neighbours

```vex
int[]neighbours(intopinput,intptnum){inti,n;intresult[];n=neighbourcount(input,ptnum);resize(result,n);for(i=0;i<n;i++)result[i] =neighbour(input,ptnum,i);}
```

Signature: int[]neighbours(intopinput,intptnum){inti,n;intresult[];n=neighbourcount(input,ptnum);resize(result,n);for(i=0;i<n;i++)result[i] =neighbour(input,ptnum,i);}

When running in the context ....

### osd_limitsurface

```vex
intnpatches=osd_patchcount(file);for(intpatch=0;patch<npatches;patch++){for(intv=0;v<100;v++){vectorP;if(osd_limitsurface(file,"P",patch,nrandom(),nrandom(),P)){intptid=addpoint(geohandle,P);}}}
```

Signature: intnpatches=osd_patchcount(file);for(intpatch=0;patch<npatches;patch++){for(intv=0;v<100;v++){vectorP;if(osd_limitsurface(file,"P",patch,nrandom(),nrandom(),P)){intptid=addpoint(geohandl....

### pointedge

```vex
intedge_count=0;// Determine if there is an edge between points 23 and 25:inth0=pointedge("defgeo.bgeo",23,25);if(h0!= -1){// Edge exists!}
```

Signature: intedge_count=0;// Determine if there is an edge between points 23 and 25:inth0=pointedge("defgeo.bgeo",23,25);if(h0!= -1){// Edge exists!}

When running in the context of a node (such a....

### pointhedge

```vex
intedge_count=0;// Count number of *edges* (not half-edges) incident to point number 23.inthout=pointhedge("defgeo.bgeo",23);while(hout!= -1){if(hedge_isprimary("defgeo.bgeo",hout))edge_count++;inthin=hedge_prev("defgeo.bgeo",hout);if(hedge_isprimary("defgeo.bgeo",hin))edge_count++;hout=pointhedgenext("defgeo",hout);};
```

Signature: intedge_count=0;// Count number of *edges* (not half-edges) incident to point number 23.inthout=pointhedge("defgeo.bgeo",23);while(hout!= -1){if(hedge_isprimary("defgeo.bgeo",hout))edge_....

### pointhedgenext

```vex
intedge_count=0;// Count number of *edges* (not half-edges) incident to point number 23.inthout=pointhedge("defgeo.bgeo",23);while(hout!= -1){if(hedge_isprimary("defgeo.bgeo",hout))edge_count++;inthin=hedge_prev("defgeo.bgeo",hout);if(hedge_isprimary("defgeo.bgeo",hin))edge_count++;hout=pointhedgenext("defgeo",hout);}
```

Signature: intedge_count=0;// Count number of *edges* (not half-edges) incident to point number 23.inthout=pointhedge("defgeo.bgeo",23);while(hout!= -1){if(hedge_isprimary("defgeo.bgeo",hout))edge_....

### polyneighbours

```vex
int[]polyneighbours(conststringopname;constintprimnum){intresult[] ={};intstart=primhedge(opname,primnum);for(inthedge=start;hedge!= -1; ){for(intnh=hedge_nextequiv(opname,hedge);nh!=hedge;nh=hedge_nextequiv(opname,nh)){intprim=hedge_prim(opname,nh);if(prim!= -1&&prim!=primnum){append(result,prim);}}hedge=hedge_next(opname,hedge);if(hedge==start)break;}returnresult;}
```

Signature: int[]polyneighbours(conststringopname;constintprimnum){intresult[] ={};intstart=primhedge(opname,primnum);for(inthedge=start;hedge!= -1; ){for(intnh=hedge_nextequiv(opname,hedge);nh!=hed....

### primvertexcount

```vex
intnvtx;// Get the number of vertices of primitive 3nvtx=primvertexcount("defgeo.bgeo",3);
```

Signature: intnvtx;// Get the number of vertices of primitive 3nvtx=primvertexcount("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an integer....

### usd_addrelationshiptarget

```vex
// Add the sphere to cube's relationship.usd_addrelationshiptarget(0,"/geo/cube","relationship_name","/geo/sphere");
```

Signature: // Add the sphere to cube's relationship.usd_addrelationshiptarget(0,"/geo/cube","relationship_name","/geo/sphere");

A handle to the stage to write to.

### usd_blockprimvar

```vex
// Block the primvar.usd_blockprimvar(0,"/geo/sphere","primvar_name");
```

Signature: // Block the primvar.usd_blockprimvar(0,"/geo/sphere","primvar_name");

A handle to the stage to write to.

### usd_isrelationship

```vex
// Check if the cube has a relationship "some_relationship".intis_valid_relationship=usd_isrelationship(0,"/geo/cube","some_relationship");
```

Signature: // Check if the cube has a relationship "some_relationship".intis_valid_relationship=usd_isrelationship(0,"/geo/cube","some_relationship");

When running in the context of a node (such a....

### usd_setrelationshiptargets

```vex
// Set the cube's relationship.usd_setrelationshiptargets(0,"/geo/cube","new_relation",array("/geo/sphere6","/geo/sphere7"));
```

Signature: // Set the cube's relationship.usd_setrelationshiptargets(0,"/geo/cube","new_relation",array("/geo/sphere6","/geo/sphere7"));

A handle to the stage to write to.

### usd_settransformreset

```vex
// Ignore parent's transform.usd_settransformreset(0,"/geo/cone",1);
```

Signature: // Ignore parent's transform.usd_settransformreset(0,"/geo/cone",1);

A handle to the stage to write to.

### vertexcurveparam

```vex
// Find the curve parameter of the current vertex and use it// to look up a ramp parameter.// Note that @vtxnum also works when iterating over points.floatu=vertexcurveparam(0,@vtxnum);// convert to unitlen space, to correct for points unevenly distributed along// the curveu=primuvconvert(0,u,@primnum,PRIMUV_UNIT_TO_UNITLEN);@width=chramp("width",u);
```

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing the input number (starting at 0) to read the geometry from.

Alternatively, the argument ....

### vertexhedge

```vex
intvtxhedge;// Get the hedge out of vertex vertex number 2.vtxhedge=vertexhedge("defgeo.bgeo",2);
```

Signature: intvtxhedge;// Get the hedge out of vertex vertex number 2.vtxhedge=vertexhedge("defgeo.bgeo",2);

When running in the context of a node (such as a wrangle SOP), this argument can be an ....

### vertexprev

```vex
intvtx;// Get the previous vertex of vertex 3vtx=vertexprev("defgeo.bgeo",3);
```

Signature: intvtx;// Get the previous vertex of vertex 3vtx=vertexprev("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing....

### vertexprimindex

```vex
intprim,vtx;// Find the primitive and vertex offset of the linear vertex 6.prim=vertexprim("defgeo.bgeo",6);vtx=vertexprimindex("defgeo.bgeo",6);
```

Signature: intprim,vtx;// Find the primitive and vertex offset of the linear vertex 6.prim=vertexprim("defgeo.bgeo",6);vtx=vertexprimindex("defgeo.bgeo",6);

To convert the linear index into a prim....

## Advanced (5 examples)

### Remove Geometry â

```vex
removepoint(0,@ptnum);
```

To add a point you use the addpoint function.

### Orient basics â

```vex
@orient = {0,0,0,1};
```

On the instance attributes page you'll see that orient is at the top of the list.

### Quaternion Interpolation with Slerp

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(0,v@up,chf('PI/2'));
float blend = chramp('blendramp',@Time % 1);
@orient = slerp(a, b, blend);

vector4 a = {0,0,0,1};
vector4 b = quaternion(1,0,1,0) * PI/2;
float blend = chramp('blendwramp', @Time % 1);
// ...
```

Demonstrates smooth interpolation between quaternion rotations using slerp() instead of hard switching between orientations.

### For loops with iteration-based spacing

```vex
for(int i = 0; i < 10; i++){
    addpoint(0, @P + (i * @N * 4));
}

for(int i = 0; i < 10; i++){
    addpoint(0, @P, @N * (i * 0.1));
}

// ...
```

Demonstrates using the loop counter variable to create progressively spaced points along the normal direction.

### Removing Points and Primitives

```vex
removepoint(0, @ptnum);

removeprim(0, @primnum, 1);
```

Demonstrates basic geometry deletion using removepoint() to delete a point by its number and removeprim() to delete a primitive by its number.

## Expert (1 examples)

### Solver sop and wrangles for simulation â

```vex
int left = prim(0,'Cd',@primnum-1);
int right = prim(0,'Cd',@primnum+1);
int top = prim(0,'Cd',@primnum+30);
int bottom = prim(0,'Cd',@primnum-30);

int total = left+right+top+bottom;

if (total==1 && @Cd ==1 ){
// ...
```

Download scene: Download file: game_of_life_solver.hip

A whole other level of fun opens up when you drop a wrangle into a solver.
