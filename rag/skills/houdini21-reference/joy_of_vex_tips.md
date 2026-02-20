# Joy of VEX: Tips & Misc

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
int pts[];  // Point Array Variable Declaration
@Cd = (sin(length(@P)*ch('scale'))+1)*0.5;  // One-line vs multi-line code readability
vector origin = point(1, "P", 0);  // Setting velocity from origin point
```

## Debugging

### Multi-line operations for readability [[Ep1, 102:06](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=6126s)]
```vex
float foo = 1;
foo *= 3;          // set range
foo += 1;          // make sure values never get below 0
foo /= @Cd.x;      // reduce range to within red value
foo += @N.y;       // addition normal on y
// Each line performs a single operation -- easier to debug than one compound expression
```

### Code Review and Debugging Practices [Needs Review] [[Ep1, 104:58](https://www.youtube.com/watch?v=9gB1zB9aLg4&t=6298s)]
```vex
float foo = 1;

vector pos = v@P - vector(centroid);
vector center = chv('center');
float r = distance(pos, center);
r *= ch('scale');
@Cd = fit(sin(r+chf('time')), -1, 1, 0, 3);
// Debug: check for typos like using 'd' instead of 'r' -- errors manifest visually
```

### Debugging Visual Results in VEX [Needs Review] [[Ep1, 105:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=6302s)]
```vex
vector pos = @P * chv('anyscale');
vector center = chv('center');
vector d = normalize(pos - center);
d *= ch('scaleb');
@Cd = fit(sin(d.x), -1, 1, 0, 1);
// When output looks wrong: review each step -- common mistake is missing normalize or scale
```

## Optimization

### One-line vs multi-line code readability [[Ep1, 76:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4562s)]
```vex
@Cd = (sin(length(@P)*ch('scale'))+1)*0.5;
// Compact but hard to debug -- prefer multi-line with intermediate variables in production
```

### Code Style and Readability [[Ep1, 76:04](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4564s)]
```vex
@Cd = (sin(length(@P) * ch('scale')) * 1) * 0.5;
// Studio best practice: prefer intermediate variables over brevity -- your future self will thank you
```

### Code Readability Best Practices [[Ep1, 76:08](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4568s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

float d = length(@P) * ch('scale');
@Cd = (sin(d)+1)*0.5;

@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;

vector center = chv('center');
float d = distance(@P, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
// All four variants produce the same result -- choose clarity over cleverness
```

## Debugging

### Code Readability and Variable Extraction [Needs Review] [[Ep1, 76:10](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4570s)]
```vex
// Complex one-liner
@Cd = (sin(length(@P)*ch('scale'))%1)*0.5;

// Extracted to variable for clarity
float d = length(@P) * ch('scale');
@Cd = (sin(d)%1)*0.5;

// Using distance to fixed point
float d = distance(@P, {1,0,3});
d *= ch('scale');
@Cd = (sin(d)%1)*0.5;

// Using channel reference for center point
vector center = chv('center');
float d = distance(@P, center);
d *= ch('scale');
@Cd = (sin(d)%1)*0.5;
// Extract to named variables -- same result, far easier to review and modify later
```

## Miscellaneous Tips

### Setting Velocity from Origin [Needs Review] [[Ep4, 38:30](https://www.youtube.com/watch?v=66WGmbykQhI&t=2310s)]
```vex
vector origin = point(1, 'P', 0);
@v = @origin;
// Direct assignment -- useful for RBD/particle motion toward a specific origin point
```

### Setting velocity from origin point [[Ep4, 38:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=2326s)]
```vex
vector origin = point(1, "P", 0);
@v = origin;
// Input 1 = second input node; point(1, "P", 0) reads P from point 0 of that input
```

### Explosion Velocity from Origin Point [[Ep4, 39:24](https://www.youtube.com/watch?v=66WGmbykQhI&t=2364s)]
```vex
vector origin = point(1, 'P', 0);
@v = (@P - origin) * ch('scale');
// (@P - origin) = direction away from origin; ch('scale') controls explosion force magnitude
```

### Velocity From Origin Point [[Ep4, 39:26](https://www.youtube.com/watch?v=66WGmbykQhI&t=2366s)]
```vex
f@z = ch('scale');

vector origin = point(1, 'P', 0);
@v = @P - origin;
// Store scale in f@z for inspection; velocity points away from origin
```

### Setting Velocity from Origin Point [[Ep4, 39:48](https://www.youtube.com/watch?v=66WGmbykQhI&t=2388s)]
```vex
vector origin = point(1, 'P', 0);
@v = @P - origin;
// Normalize and scale @v afterward to control the exact speed of the explosion
```

### Directional velocity from origin point [[Ep4, 39:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=2396s)]
```vex
@v *= ch("scale");

@v = -@N;             // variant: use inverted normal as velocity direction
@v *= ch("scale");

vector origin = point(1, 'P', 0);
@v = @P - origin;     // variant: direction from origin to each point
@v *= ch("scale");    // scale controls explosion force magnitude
```

### Velocity from Origin Point [[Ep4, 40:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=2412s)]
```vex
vector origin = point(1, 'P', 0);
@v = -origin;
// Negating origin creates outward blast direction -- use (@P - origin) for per-point divergence
```

### Velocity from Origin Point [[Ep4, 40:30](https://www.youtube.com/watch?v=66WGmbykQhI&t=2430s)]
```vex
vector origin = point(1, 'P', 0);
@v = (@P - origin);

@N = @v * ch('scale');  // copy scaled velocity into @N for art-directible force field
```

## Debugging

### Floating Point Precision Errors [[Ep4, 75:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=4546s)]
```vex
float foo = 0;
float bar = sin(PI);

if(foo == bar) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};  // sin(PI) returns ~-8.74228e-8, not exactly 0 -- equality fails
}
// Fix: use abs(foo - bar) < 1e-6 for float comparisons
```

### Floating Point Comparison Issues [Needs Review] [[Ep4, 76:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=4562s)]
```vex
float foo = 0;
float bar = sin(@P.y);

if(foo == bar) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};  // sin(@P.y) returns ~0.00000087, not 0 -- == comparison fails
}
// Always use epsilon comparison: if(abs(foo - bar) < 1e-6) for float equality
```

### Floating Point Precision Errors [[Ep4, 76:04](https://www.youtube.com/watch?v=66WGmbykQhI&t=4564s)]
```vex
float foo = 0;
float bar = sin(@P);

if(foo == bar) {
    @Cd = {0,1,0};
} else {
    @Cd = {1,0,0};  // will almost always be red -- sin accumulates tiny floating point errors
}
// Rule: never use == for floats; use abs(a - b) < 0.000001 (epsilon tolerance)
```

## Groups

### Random Primitive Removal [[Ep5, 145:14](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8714s)]
```vex
if(rand(@primnum, ch('seed')) < ch('chance'))
    removepoint(0, @primnum, 1);
```
Uses a random value per primitive to conditionally remove primitives based on a user-controlled chance parameter. The removepoint function is called with flag 1 to remove the entire primitive rather than just the point.

## Debugging

### Common Syntax Error: Missing Brackets [[Ep5, 148:44](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8924s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @primnum, 1);
}
```
A common syntax error occurs when forgetting to close brackets in conditional statements, especially when using channel references with the ch() function. This example demonstrates proper bracket matching in an if statement that randomly removes primitives based on a threshold value.

## Groups

### Random Primitive Removal [[Ep5, 157:04](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9424s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}
```
Conditionally removes primitives based on a random threshold comparison. Uses rand() with primitive number and seed to generate random values, then removes the primitive if the value is below the cutoff parameter.

### Random Primitive Removal [[Ep5, 157:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9426s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
```
Uses random per-primitive values to selectively delete primitives based on a threshold. The rand() function generates consistent pseudo-random values per primitive using a seed parameter, and removeprim() deletes primitives where the random value falls below the cutoff slider value.

### Random Prim Removal Setup [Needs Review] [[Ep5, 157:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9428s)]
```vex
if(rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}

// spiral() seaweed using sin and cos
vector offset, pos;
int pr, pt;
```
Uses random values per primitive to conditionally remove primitives based on a cutoff threshold. The code snippet also declares variables for an upcoming seaweed spiral generation example using trigonometric functions.

### Primitive Deletion Based on Random Threshold [[Ep5, 158:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9496s)]
```vex
if(rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}
```
Uses a random number generator seeded by primitive number to conditionally delete primitives. If the random value falls below a user-defined cutoff threshold parameter, the primitive is removed. This creates a random culling effect where the cutoff parameter controls the percentage of primitives deleted.

## Miscellaneous Tips

### Vector and Array Indexing [Needs Review] [[Ep5, 21:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1294s)]
```vex
vector myvector = {1,2,3};

v@a = {10,12,100};

float foo = @a.x; // will return 10

float foo = @a[2]; // that's asking for index 2, which will return 100

float myFloatArray[] = {1,2,3,4,5};
```
Demonstrates two methods for accessing vector components: dot notation (.x, .y, .z) and array-style indexing ([0], [1], [2]). Shows that vectors can be treated as arrays where index 0 corresponds to x, index 1 to y, and index 2 to z. Also introduces float array declaration syntax using square brackets and curly braces.

### Declaring Array Attributes [[Ep5, 29:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1790s)]
```vex
float myFloatArray[] = {1,2,3,4,5};
vector myVectorArray[] = {{1,2,3},{4,5,6},{7,8,9}};

f[]@a = {1,2,3,4,5};
v[]@vecs = {{1,2,3},{4,5,6},{7,8,9}};
```
Demonstrates two ways to declare array attributes in VEX: using local variables (float[], vector[]) and using geometry attributes (f[]@, v[]@). Vector arrays use nested curly braces, with outer braces for the array and inner braces for each vector element.

### Array Indexing and Retrieval [[Ep5, 30:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1854s)]
```vex
float myFloatArray[] = {1,2,3,4,5};
vector myVectorArray[] = {{1,2,3},{4,5,6},{7,8,9}};

f[]@a = {2,3,4,5};
v[]@vecs = {{1,2,3},{4,5,6}};

f@b = f[]@a[2];
v@c = v[]@vecs[1];
```
Demonstrates accessing individual elements from float and vector arrays using zero-based indexing. The code creates array attributes, then retrieves specific elements by index (e.g., @a[2] gets the third element, @vecs[1] gets the second vector) and stores them in scalar attributes.

### Array Syntax in VEX [[Ep5, 32:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1952s)]
```vex
float myFloatArray[] = {1, 2, 3, 4.5};
vector myVectorArray[] = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};

f[]@a = {1, 2, 3, 4.5};
v[]@vecs = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};

@P = f[]@a[2];
v@c = v[]@vecs[1];
```
Arrays in VEX can be declared using bracket notation for both local variables and attributes. For attributes, use type[]@name syntax (e.g., f[]@a for float array, v[]@vecs for vector array) to store comma-separated lists. Array elements are accessed using zero-based indexing, allowing rapid operations over multiple data values.

### set vs array for vectors and arrays [[Ep5, 36:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2210s)]
```vex
float s = 421;
v@v = set(s, s, s);
f[]@array = array(s, s, s, s, s);

int pt = nearpoint(1, @P);
vector col = point(1, "Cd", pt);
@Cd = col;

int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, chf("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
Demonstrates the difference between set() for creating vectors with variables and array() for creating longer arrays. The set() function constructs a vector from variable components, while array() creates a float array with multiple values. The code also shows how to use nearpoint() to find the closest point on another input and read its attributes (position and color) for distance-based color blending.

## Optimization

### Variable Declaration Optimization [[Ep5, 48:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2916s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

pt = pts[0];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;

pt = pts[1];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Demonstrates proper variable declaration by moving all variable definitions to the top of the code block, allowing variables to be reused across multiple operations without redeclaring them. This cleaner approach declares variables once (pos, col, pts, pt, d) and then reuses them for processing multiple nearby points, accumulating their color contributions.

## Debugging

### Debugging with Temporary Attributes [Needs Review] [[Ep5, 53:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3196s)]
```vex
vector pos, col;
int pt;
int pts[];
float d;

pts = nearpoints(1, @P, 40);

@Cd = 0;

// first point
pt = pts[0];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, 0.1, 1, 0);
@Cd += col * d;

// second point
pt = pts[1];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, 0.1, 1, 0);
@Cd += col * d;

// Debug output
i[]@pts = pts;
```
Demonstrates using temporary attributes for debugging by writing intermediate array results to a geometry attribute. The code finds nearby points and blends their colors based on distance, while storing the point numbers array to a custom attribute for inspection in the geometry spreadsheet. This pattern shows the common debugging technique of exposing internal variables as attributes to verify algorithm behavior.

### Debugging with Array Attributes [Needs Review] [[Ep5, 54:14](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3254s)]
```vex
int pts[];
pts = nearpoints(0, @P, 20);
i[]@a = pts;

// first point
int pt = pts[0];
vector col = point(0, 'Cd', pt);
vector pos = point(0, 'P', pt);
float d = distance(@P, pos);
@Cd = mix(@Cd, col, 1-d);
d = clamp(d, 0, 1);
@Cd += d;

// second point
pt = pts[1];
col = point(0, 'Cd', pt);
pos = point(0, 'P', pt);
d = distance(@P, pos);
@Cd = mix(@Cd, col, 1-d);
d = clamp(d, 0, 1);
@Cd += d;
```
Demonstrates a debugging technique by writing the nearpoints array to a detail array attribute (@a) so you can visualize which points are being found in the point cloud search. This temporary visualization attribute helps verify that the nearpoints query is working correctly before using those results in further calculations. The code then processes the first two nearest points to blend their colors based on distance.

## Miscellaneous Tips

### Point Array Variable Declaration [Needs Review] [[Ep5, 68:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4088s)]
```vex
int pts[];
int pt;
```
Declares two integer variables: an empty array 'pts' to store multiple point numbers, and a single integer 'pt' for individual point operations. These are typically used in preparation for point cloud queries or neighbor finding operations.

### Animated vertical oscillation with sine [[Ep6, 52:50](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3170s)]
```vex
float d = length(@P);
float t = @Time * @offset;
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates dancing geometry by animating the vertical position of points using a sine function. The sine output is scaled by 0.5 to constrain the oscillation range between -0.5 and 0.5, producing a controlled bouncing motion that can be adjusted for different wavelengths and speeds.

## Debugging

### Debugging Packed Transform Matrix [[Ep7, 142:38](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8558s)]
```vex
matrix pft = primintrinsic(0, "packedfullransform", @ptnum);
4@a = pft;
```
Demonstrates how to debug packed primitive transforms by reading the packedfullransform intrinsic attribute into a matrix variable, then writing it to a 4x4 matrix detail attribute for inspection. This allows visualization of the full transformation matrix applied to each packed primitive.

## Optimization

### Compacting Quaternion Code [[Ep7, 35:16](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2116s)]
```vex
float angle = @Time;
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Compact version:
@orient = quaternion(@Time, chv('axis'));
```
Demonstrates code refactoring by condensing multi-line quaternion setup into a single compact line. The angle and axis variables are eliminated by directly passing @Time and chv('axis') to the quaternion function, maintaining identical functionality while improving code brevity. This is a stylistic choice that balances readability with conciseness.

## Debugging

### Storing noise as attribute [[Ep7, 54:12](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3252s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+f@time);
axis *= trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
```
Creates a float attribute @a to store the noise value for debugging and inspection in the geometry spreadsheet. The noise function evaluates position plus time, and this intermediate value is stored before being used to calculate rotation angles. This allows inspection of the noise range to verify it stays within expected bounds (0-1).

### Visualizing Attribute Data with Position [[Ep7, 60:58](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3658s)]
```vex
@a = noise(@P * @Time);
@a = chramp('noise_ramp', @a);

vector axis;
axis = chv('axis');
axis = axis * length(@orient, @a);
axis *= trunc(@a * 4) * ($PI / 2);

@v = {0, 1, 0};
@orient = quaternion(axis);

@P.y = @a;
```
Demonstrates visualizing an attribute value by mapping it to point position, specifically setting the Y component of @P equal to a processed noise/ramp value (@a). This technique allows visual debugging of attribute data by translating numeric values into geometric displacement, making it easier to understand the distribution and variation of the attribute across points.

### Visualizing Data with Position [[Ep7, 61:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3688s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = chramp('noise_range', @Cd);
axis *= trunc(@a * 4) * @P.z;
@P.y = @a;
@orient = quaternion(axis);
```
Demonstrates visualizing attribute data by mapping a remapped color value (@a from chramp) to the Y position of points, making the data visible through vertical displacement. The code also calculates an orientation quaternion based on a scaled axis vector, with the scaling factor derived from the truncated remapped value and Z position.

### Visualizing Attributes via Position [[Ep7, 61:40](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3700s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@N = noise(@P*@Time);
@a = noise(@P*@Time*PI)*@b1/2;
@P.y = @a;

@orient = quaternion(axis);

axis *= trunc(@a*4)*(PI/2);
@P.y = 0;

@orient = quaternion(axis);
```
Demonstrates visualization technique by mapping an attribute value (@a) to point position (@P.y), causing points to jump up and down based on noise-driven values. This provides an alternative way to visualize numeric attributes spatially rather than just viewing them in the spreadsheet.

### Visualizing Data via Position [Needs Review] [[Ep7, 62:46](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3766s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+f@time);
@a = chramp('noise_range',@a);
axis *= trunc(@a*@a)*$PI/2;
@P.y = @a;

@orient = quaternion(axis);

@N = {0,1,0};
float s = sin(@P.x*@Time);
float c = cos(@P.x*@Time);
@up = s*{0,1,0};

@orient = quaternion(maketransform(@N, @up));
```
Demonstrates techniques for visually debugging VEX data by temporarily assigning computed values to @P.y to see how they vary across points. The code can be commented out (Ctrl+/) to toggle visualization on and off, allowing flexible inspection of noise-driven data and orientation computations in the viewport.

### Workflow: Commenting and Resetting [[Ep7, 63:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3804s)]
```vex
vector axis;
axis = chv("axis");
axis = normalize(axis);
@a = noise(@P*time);
@a = chramp("noise_rrange",@a);
axis *= trunc(@a*4)*(PI/2);
@P.y = @a;
@orient = quaternion(axis);

// Example 2: Using make transform
@N = {0,1,0};
float x = sin(@Frame);
float c = cos(@Frame);
@up = set(x,0,c);
@orient = quaternion(maketransform(@N, @up));
```
Demonstrates VEX workflow techniques including commenting out lines with Ctrl+/ while preserving end-of-line comments, and resetting spare parameters between examples. Shows transitioning between different orientation methods using quaternions from axis-angle and from transform matrices.

### VEX Comment Syntax Behavior [Needs Review] [[Ep7, 63:38](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3818s)]
```vex
// Example showing VEX comment behavior
// Code context appears to be demonstrating that comments can be nested
// and how control+/ (comment toggle) behaves with existing comments

vector axis;
axis = chv('axis');
axis = normalize(axis);
@N = noise(@P * chf('freq'));
@a = chramp('noise_remap', @a);
axis *= trunc(@a * 4) * (PI / 2);
@P.y = @a;

@orient = quaternion(axis);

// Expression variations
@P += @N * chf('Displace') * noise(@P);
@Cd = chramp('noise_remap', @a);

@V = {0, 1, 0};
float s = sin(chf('time'));
float c = cos(chf('time'));
@up = set(s, 0, c);

@orient = quaternion(maketransform(@N, @up));
```
Demonstrates VEX comment syntax behavior when using keyboard shortcuts like Ctrl+/ to toggle comments. Shows that when commenting out a line that already has a trailing comment, both remain commented. The code includes examples of orientation setup using quaternions, noise-based displacement, and custom up vectors for orientation.

## Miscellaneous Tips

### Day 20 Reference Resources [Needs Review] [[Ep8, 100:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=6054s)]
```vex
int list pc = pcopen(0, "P", @P, ch("maxdist"), ch("numpoints"));
vector pos = normalize(jitter(@P, 8));
vector norm = normalize(pos);
@Cd = fit01(pos, -1, 1, 0, 1);
@Cd = fit(pos, -1, 1, 0, 1);
@Cd = pcw(pos, 0, ch("seed"));
```
This code snippet demonstrates various VEX functions used throughout the Joy of Vex series, including point cloud queries, vector normalization, jittering, and color mapping with fit functions. The transcript indicates this is Day 20 content focusing on external resources and references rather than specific exercises, encouraging viewers to explore the VEX documentation and community resources like Entagma and Matt's CG Wiki.

### Velocity Smoothing via Point Cloud [[Ep8, 92:14](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5534s)]
```vex
int pc = pcopen(1, @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= (1, 0, 1);
avgp *= (1, 0, 1);
@v += avgv - avgp;
```
Uses point cloud queries on a second input geometry to calculate averaged velocity and position values from nearby points, then modifies particle velocity by the difference between these smoothed values. The vector multiplication masks out the Y-component to constrain the effect to horizontal dimensions only.

## See Also
- **VEX Performance** (`vex_performance.md`) -- optimization guidelines
