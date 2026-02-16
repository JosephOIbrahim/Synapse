# VEX Corpus: Miscellaneous Topics

> 30 examples from vex-corpus (small topics). Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Array Ops (1 examples)

### slice

```vex
int[]nums={10,20,30,40,50,60};slice(nums,1,3) =={20,30};// nums[1:3]slice(nums,1, -1) =={20,30,30,40,50};// nums[1:-1]slice(nums,0,len(nums),2) =={20,40,60};// nums[0:len(nums):2]slice(nums,0,0,0,0,1,2) =={20,40,60};// nums[::2]
```

Signature: int[]nums={10,20,30,40,50,60};slice(nums,1,3) =={20,30};// nums[1:3]slice(nums,1, -1) =={20,30,30,40,50};// nums[1:-1]slice(nums,0,len(nums),2) =={20,40,60};// nums[0:len(nums):2]slice(n....

## Assertions (1 examples)

### assert_enabled

```vex
#define assert(EXPR)    \if (assert_enabled()) { \if (!(EXPR)) print_once(sprintf('VEX Assertion Failed %s:%d - (%s)\n', \__FILE__, __LINE__, #EXPR)); \}
```

Signature: #define assert(EXPR)    \if (assert_enabled()) { \if (!(EXPR)) print_once(sprintf('VEX Assertion Failed %s:%d - (%s)\n', \__FILE__, __LINE__, #EXPR)); \}

Returns 1 if the environment va....

## Debugging Patterns (1 examples)

### Search a string with find â

```vex
string haystack = 'mylongstring';
string needle = 'str';
if (find(haystack, needle)>=0) {
     i@found=1;
}
```

I always forget this, seems appropriate to write it here.

The vex find() function can search in strings as well as arrays:.

## Noise (3 examples)

### Noise Function Basics

```vex
noise(@P*chf('offset')+@v*chv('fancyscale')*@Time);
```

Introduction to working with noise in VEX, demonstrating how to combine position, velocity, and time with channel parameters to create animated noise patterns.

### Noise with Channel References and Time

```vex
@Cd = noise(chv('offset')+@P*chv('fancyscale')+@Time);
```

Applies animated noise to point color by combining position scaled by a vector parameter, an offset parameter, and the current time attribute.

### Animating Noise with Time

```vex
@Cd = noise(@P + chv('offset')) * @P * chv('fancyscale') + @time;
```

Creates animated noise-based color by adding a channel vector offset to position for noise sampling, multiplying the result by position and a scale vector, then adding time to animate the pattern.

## Noise Operations (1 examples)

### Visualizing Data via Position

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+f@time);
@a = chramp('noise_range',@a);
axis *= trunc(@a*@a)*$PI/2;
@P.y = @a;

// ...
```

Demonstrates techniques for visually debugging VEX data by temporarily assigning computed values to @P.y to see how they vary across points.

## Noise Remap (2 examples)

### Visualizing Data with Height and Orientation

```vex
vector axis;
axis = chv('a');
axis = normalize(axis);
axis = noise(@ptnum);
@a = chramp('noise_remap', @a);
axis *= trunc(@a*4)*(PI/2);
@P.y = @a;

// ...
```

Uses noise-driven attribute values to control both point height (@P.y) and orientation through quaternions.

### Quaternion Orientation with Dynamic Up Vector

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@N = noise(@P*1e);
@a = chramp('noise_remap', @a);
axis = trunc(@N^4) * @N / 2;
@P.y = @a;

// ...
```

Creates orientation quaternions using maketransform() with a normal vector and a dynamically animated up vector.

## Optimization Patterns (1 examples)

### volumecubicsample

```vex
vectorP={1.0,2.0,3.0};vectorgrad;matrix3hess;floatval1=volumecubicsample(0,"density",P,grad,hess);vectoru={0.1,0.01,0.001};floatval2=volumecubicsample(0,"density",P+u);// By Taylor expansion we have:// `val1 + dot(u, grad)` is approximately equal to `val2`// And the second order approximation:// `val1 + (u, grad) + 0.5 * dot(u, u*hess)`// is appriximately equal to `val2`
```

Signature: vectorP={1.0,2.0,3.0};vectorgrad;matrix3hess;floatval1=volumecubicsample(0,"density",P,grad,hess);vectoru={0.1,0.01,0.001};floatval2=volumecubicsample(0,"density",P+u);// By Taylor expan....

## Point Creation (1 examples)

### Vector Channel Parameter and Point Lookup

```vex
vector a = chv('a');
@N += a;

vector a = point(1, 'P', @i);
vector b = point(1, 'P', @i);
```

Demonstrates adding a vector channel parameter to the normal attribute and introduces the point() function for reading position attributes from input geometry.

## Point Operations (1 examples)

### Vector Subtraction Direction

```vex
vector a = point(0,"P",0);
vector b = point(1,"P",0);

@N = b - a;

// Alternative using @P for point a
vector a = @P;
vector b = point(1,"P",0);
```

When subtracting vectors, the resulting vector points in the direction of the second vector from the first.

## Primitive Ops (2 examples)

### Random Primitive and Point Deletion

```vex
// Random primitive deletion in Prim Wrangle
if(rand(@primnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

// Point deletion example
removepoint(0, @ptnum);

// ...
```

Uses rand() to generate a value between 0 and 1 for each primitive or point, comparing it against a threshold parameter to randomly delete geometry.

### usd_setactive

```vex
// Set the sphere primitive as active.usd_setactive(0,"/geo/sphere",true);
```

Signature: // Set the sphere primitive as active.usd_setactive(0,"/geo/sphere",true);

A handle to the stage to write to.

## Quaternion Operations (2 examples)

### Converting Quaternions to Matrices

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
@N = N;
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time*@ptnum)*3), {0,1,0});
// ...
```

Demonstrates converting a quaternion orientation back to a matrix representation using qconvert().

### Spherical and linear gradients â

```vex
vector p1 = point(1,'P',0);
vector p2 = point(1,'P',1);

float r = distance(p1,p2);
@Cd = (r-distance(@P, p1))/r;
```

Download scene: Download file: gradient_spherical_vs_linear.hip

Interesting question from a Patreon supporter.

## Resource Leak (3 examples)

### Random Open/Closed Primitives

```vex
int openclose = int(rand(@primnum)*rand())*2)-1;
setprimintrinsic(0, "closed", @primnum, openclose);
```

Randomly assigns primitives to be either open or closed by generating a random value that evaluates to either -1 or 1, then sets the 'closed' intrinsic attribute accordingly.

### Random Open/Closed Primitives

```vex
int openclosed = int(rand(@primnum + rand() * 2));
setprimintrinsic(0, "closed", @primnum, openclosed);
```

Randomly assigns primitives to be open or closed by generating a random integer (0 or 1) using the primitive number as a seed, then setting the 'closed' intrinsic attribute.

### opend

```vex
intop_handle=opstart("Performing long operation");perform_long_operation();if(op_handle>=0)opend(op_handle);
```

Signature: intop_handle=opstart("Performing long operation");perform_long_operation();if(op_handle>=0)opend(op_handle);

Adds an item to an array or string.

Returns the indices of a sorted version....

## Simulation Setup (3 examples)

### Setting Closed Intrinsic with Randomness

```vex
int open_loss = int(rand(@ptnum) * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, open_loss);
```

Uses randomness based on point number and frame to randomly set the 'closed' primitive intrinsic, which converts polygons to polyline outlines.

### ocean_sample

```vex
@P+=ocean_sample("spectrum.bgeo",0,1,2,0.7,@Time,0,0,@P);
```

Signature: @P+=ocean_sample("spectrum.bgeo",0,1,2,0.7,@Time,0,0,@P);

The name of the geometry file to reference.

### Other intrinsics â

```vex
int openclose = int(rand(@primnum+@Frame)*2);
 setprimintrinsic(0,'closed', @primnum, openclose);
```

There's a few that can be handy, assuming they have meaningful data.

## String Operations (6 examples)

### pluralize

```vex
stringboxes=pluralize("box");stringwomen=pluralize("woman");stringgeometries=pluralize("geometry");// Returns the string "Pluralize the last words"stringphrase=pluralize("Pluralize the last word");
```

Signature: stringboxes=pluralize("box");stringwomen=pluralize("woman");stringgeometries=pluralize("geometry");// Returns the string "Pluralize the last words"stringphrase=pluralize("Pluralize the l....

### replace

```vex
stringstr="abcdef abcdef abcdef";// Returns "abcghi abcghi abcghi"stringnew_str=replace(str,"def","ghi");// Replaces up to 2 occurrences of the string "def".// Returns "abcghi abcghi abcdef"new_str=replace(str,"def","ghi",2);
```

Signature: stringstr="abcdef abcdef abcdef";// Returns "abcghi abcghi abcghi"stringnew_str=replace(str,"def","ghi");// Replaces up to 2 occurrences of the string "def".// Returns "abcghi abcghi abc....

### replace_match

```vex
// Returns "carol is my name";strings=replace_match("bob is my name","bob*","carol*");// Returns "a-b";s=replace_match("a_to_b","*_to_*","*-*");// Swaps the matched wildcards, returning "b_to_a";s=replace_match("a_to_b","*_to_*","*(1)_to_*(0)");
```

Signature: // Returns "carol is my name";strings=replace_match("bob is my name","bob*","carol*");// Returns "a-b";s=replace_match("a_to_b","*_to_*","*-*");// Swaps the matched wildcards, returning ....

### reverse

```vex
reverse("hello") =="olleh";reverse({1,2,3,4}) =={4,3,2,1};
```

Signature: reverse("hello") =="olleh";reverse({1,2,3,4}) =={4,3,2,1};

Returns a UTF-8 encoded string with the reversedcharacters(not bytes) fromstr.

### texprintf

```vex
!vex
// Returns "map_1044.rat
texprintf(3.1, 4.15, "map_<UDIM>.rat");

// Returns "map_04_05.rat"
texprintf(3.1, 4.15, "map_%(U)02d_%(V)02d.rat");

// Returns "map_u4_v12.rat"
// ...
```

Signature: !vex
// Returns "map_1044.rat
texprintf(3.1, 4.15, "map_<UDIM>.rat");

// Returns "map_04_05.rat"
texprintf(3.1, 4.15, "map_%(U)02d_%(V)02d.rat");

// Returns "map_u4_v12.rat"
texprintf(....

### usd_iscollectionpath

```vex
// Check if string is an acceptable collection path.intis_valid_collection_path=usd_iscollectionpath(0,"/geo/cube.collection:some_collection");
```

Signature: // Check if string is an acceptable collection path.intis_valid_collection_path=usd_iscollectionpath(0,"/geo/cube.collection:some_collection");

When running in the context of a node (su....

## Subdivision Surfaces (2 examples)

### osd_lookupface

```vex
voidscatterOnLimitSurface(stringfile,texmap;intgeo_handle;intnpts){intnpatches=osd_patchcount(file);for(inti=0;i<npts; ++i){intpatch_id=nrandom() *npatches;floatpatch_s=nrandom();floatpatch_t=nrandom();intface_id;floatface_u,face_v;if(osd_lookupface(file,patch_id,patch_s,patch_t,face_id,face_u,face_v,"uv")){vectorclr=texture(texmap,face_u,face_v);vectorP;osd_limitsurface(file,"P",patch_id,patch_s,patch_t,P);intptnum=addpoint(geo_handle,P);// add a scattered point.if(ptnum>=0){addpointattrib(geo_handle,"Cd",clr);addpointattrib(geo_handle,"face_id",face_id);}}}}
```

Signature: voidscatterOnLimitSurface(stringfile,texmap;intgeo_handle;intnpts){intnpatches=osd_patchcount(file);for(inti=0;i<npts; ++i){intpatch_id=nrandom() *npatches;floatpatch_s=nrandom();floatpa....

### setpackedtransform

```vex
// matrix to transform bymatrixtf=ident();rotate(tf,radians(45),{0,1,0});translate(tf,{0,1,0});matrixtransform=getpackedtransform(0,@primnum);setpackedtransform(0,@primnum,transform*tf);
```

Signature: // matrix to transform bymatrixtf=ident();rotate(tf,radians(45),{0,1,0});translate(tf,{0,1,0});matrixtransform=getpackedtransform(0,@primnum);setpackedtransform(0,@primnum,transform*tf);....
