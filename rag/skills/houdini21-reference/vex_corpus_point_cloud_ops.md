# VEX Corpus: Point Cloud Operations

> 318 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Intermediate (304 examples)

### Exercises â

```vex
int pt = nearpoint(1,@P);
 vector pos = point(1,'P',pt);
 float d = distance(@P, pos);
 d *= ch('scale');
 d += rand(pt);
 d -= @Time;
 d %= 1;
 @P.y = chramp('pulse',d)*ch('amp');
```

Pull the following wrangle apart, set the chramp to mostly flat, with a thin triangle in the middle, lots of divisions on the grid, and feed around 8 scattered points to the second input of the wra....

### Nearpoints â

```vex
int pt = nearpoint(1,@P);
 vector col = point(1,'Cd',pt);
 @Cd = col;
```

The voronoi example using nearpoint earlier is interesting, but notice that it does a hard edge on the borders.

### More on nearpoints â

```vex
int pts[];
 pts = nearpoints(1,@P,20);
 i[]@a = pts;
```

It can be useful to see the array that nearpoints generates.

### Waves again â

```vex
int pts[];
int pt;
vector pos;
float d,w;

pts = nearpoints(1,@P,ch('radius'),chi('number_of_points'));

pt = pts[0];
// ...
```

Now you know we can't get through a chapter without waves.

Lets do the usual setup; get the distance to the closest point and store it as d, generate waves with sin(d), and add some controls so we....

### For each loops â

```vex
foreach( element; array) {
     // do things to element
 }
```

So clearly in the previous example there must be something better than copying and pasting huge chunks of code.

### For Loop â

```vex
for ( starting value; test; value increment) {

 }
```

Foreach loops as shown above are a very convenient way to process arrays, and most of the time this is the better way to go.

### Exercises â

```vex
int pts[];
int pt;
vector col,pos;
float d;

pts = nearpoints(1,@P,20);

// treat this as ink on paper, so start with white paper
// ...
```

Make ripples that are red at their peaks and green at the lowest points Make each ripple setup have the wave frequency be determined by data coming from the scatter points.

### set vs array for vectors and arrays

```vex
float s = 421;
v@v = set(s, s, s);
f[]@array = array(s, s, s, s, s);

int pt = nearpoint(1, @P);
vector col = point(1, "Cd", pt);
@Cd = col;

// ...
```

Demonstrates the difference between set() for creating vectors with variables and array() for creating longer arrays.

### Nearest Point Color Transfer with Distance Falloff

```vex
float myarray[] = array(1,2,3,4,5); // ok
float[] myarray = array(1,2,3,4,5); // ok

int pt = nearpoint(1,@P);
vector col = point(1,"Cd",pt);
@Cd = col;

int pt = nearpoint(1,@P);
// ...
```

This code demonstrates finding the nearest point from input 1 to the current point position, retrieving that point's color attribute, and applying it with a distance-based falloff.

### Distance-based color blending with nearpoint

```vex
float myarray[] = array(1,2,3,4,5);
f[]@myarray = array(1,2,3,4,5);

int pt = nearpoint(1,@P);
vector col = point(1,'Cd',pt);
@Cd = col;

int pt = nearpoint(1,@P);
// ...
```

Demonstrates finding the nearest point on a second input, retrieving its position and color, then blending the color based on distance with falloff controlled by a channel parameter.

### Reading Color from Nearest Point

```vex
int pt = nearpoint(1, v@P);
vector col = point(1, "Cd", pt);

// Extended example:
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
// ...
```

Uses nearpoint() to find the closest point on input 1 to the current point's position, then reads that point's color attribute using point().

### Point Proximity Color Transfer with Distance Falloff

```vex
int pt = nearpoint(0, @P);
vector col = point(0, "Cd", pt);
@Cd = col;

int pt = nearpoint(0, @P);
vector pos = point(0, "P", pt);
vector diff = point(0, "Cd", pt);
float d = distance(@P, pos);
// ...
```

Demonstrates finding the nearest point using nearpoint() and transferring its color attribute to the current point.

### Voronoi Pattern with Nearest Point Lookup

```vex
float myarray[] = array(x,y,x,y,5); // ok
f[]@myarray = array(x,y,x,y,5); // ok

int pt = nearpoint(1,@P);
vector col = point(1,"Cd",pt);
@Cd = col;

int pt = nearpoint(1,@P);
// ...
```

Uses nearpoint() to find the closest point from input 1, then reads that point's color attribute with point().

### Voronoi color transfer with distance falloff

```vex
int pt = nearpoints(1, @P, 1)[0];
vector col = point(1, "Cd", pt);
@Cd = col;

// Extended version with distance falloff
int pt = nearpoints(1, @P, 1)[0];
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
// ...
```

Finds the nearest point from input 1 and transfers its color to create a Voronoi pattern.

### Distance-based Color Transfer

```vex
int pt = nearpoint(1, @P);
vector pos = point(1, 'P', pt);
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```

Finds the nearest point on a second input geometry, retrieves its position and color, then calculates the distance from the current point to that nearest point.

### Distance-based color falloff

```vex
int pt = nearpoints(1, @P, 1)[0];
vector pos = point(1, 'P', pt);
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```

Calculates the distance from each point to its nearest neighbor on a second input, then uses fit() and clamp() to create a distance-based falloff value that modulates the color transfer.

### Distance-based color transfer with fit

```vex
int pt = nearpoint(1, v@P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(pos, v@P);
v@Cd = fit(d, 0, chf("radius"), col, v@Cd);
```

Finds the nearest point on input 1, calculates the distance to it, then uses fit() to blend between the nearest point's color and the current point's color based on distance within a controllable r....

### Multi-Point Blending with nearpoints

```vex
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;

// ...
```

Demonstrates the limitation of using nearpoint() for color blending, where values cannot blend across Voronoi cell boundaries.

### Expanding nearpoints search radius

```vex
int pts[] = nearpoints(1, @P, 10);
int pt = pts[0];
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 0, 1.0);
d = clamp(d, 0, 1);
@Cd = col * d;
```

Modifies the nearpoints function to search within a specified distance (10 units) rather than finding just the closest point, allowing for blending across cell boundaries.

### Extracting Point from Near Points Array

```vex
int pts[] = nearpoints(1, @P, 40);
int pt = pts[0];
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
@Cd = col;
@normal = pos;
```

Demonstrates finding nearby points within a search radius and extracting a single point from the resulting array using bracket indexing.

### Extracting Single Point from Array

```vex
int pts[] = nearpoints(1, @P, chf("radius"));
int pt = pts[0];
vector pt1 = point(1, "P", pt);
vector pt2 = point(1, "Cd", pt);
i@dir = inpointgroup(1, "phs1", pt);
float d = distance(@P, pt1);
d = fit(d, 0, chf("radius"), 1, 0);
vector v = pt2;
// ...
```

Demonstrates extracting a single point from a nearpoints array using bracket notation (pts[0]) to access the first element.

### Multiple Nearest Points Color Blending

```vex
int pts[] = nearpoints(1, @P, ch('radius'));
vector pos, col;
int pt;
float d;

@Cd = 0; // set colour to black to start with

// first point
// ...
```

Extends the nearest point color blending technique to process multiple points from the nearpoints array by extracting individual points using bracket indexing (pts[0], pts[1]).

### Refactoring Point Cloud Color Blending

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Demonstrates proper variable declaration and reuse when processing multiple nearby points from a point cloud query.

### Variable Declaration Optimization

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Demonstrates proper variable declaration by moving all variable definitions to the top of the code block, allowing variables to be reused across multiple operations without redeclaring them.

### Blending Multiple Point Colors

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Demonstrates accumulative color blending from multiple source points using += operator.

### Blending Multiple Nearby Point Colors

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set colour to black to start with

// ...
```

Blends colors from multiple nearby points by accumulating their contributions using the += operator instead of direct assignment.

### Multiple Nearest Point Color Blending

```vex
int pts[] = nearpoints(1, @P, 40);
int pt = pts[0];
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;

// ...
```

Demonstrates extending single nearest point color sampling to multiple points by duplicating the calculation block and accessing pts[1] for the second nearest point.

### Blending Two Nearest Point Colors

```vex
int pt[];
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1,@P,40);
@Cd = 0;
// ...
```

Extends the nearest point color lookup to blend contributions from the two closest points.

### Blending Two Nearest Point Colors

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1,@P,40); // search within 40 units
@Cd = 0; // set colour to black to start with

// ...
```

Extends the single nearest point color lookup by duplicating the code block to process both the first and second nearest points from the nearpoints array.

### Multi-Point Color Blending

```vex
//first point
int pt = pts[0];
vector pos = point(1, 'P', pt);
float d;

pts = nearpoints(1, pos, ch('radius'));
@Cd = 0;

// ...
```

Extends color blending by accessing the second nearest point (pts[1]) in addition to the first, allowing colors to blend beyond initial Voronoi boundaries.

### Nearpoints Array Manual Access Pattern

```vex
int pts[];
pts = nearpoints(0, @P, 20);
i[]@a = pts;

// First point processing
int pt = pts[0];
vector pos = point(0, "P", pt);
vector d = normalize(pos);
// ...
```

This code demonstrates manually accessing and processing individual points from a nearpoints array by copying and pasting the same operations for pts[0] and pts[1].

### Nearpoints Multiple Point Queries

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, v@P, 40);
// if(len(pts))

// ...
```

Demonstrates querying multiple near points by accessing individual array elements from nearpoints() result.

### Nearpoints with Count Limit

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, v@P, 40, 3);

// first point
// ...
```

Demonstrates using the nearpoints() function with a maximum count parameter to limit the number of returned points to 3.

### Limiting nearpoints results

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40, 3);
```

The nearpoints() function accepts an optional fourth argument to limit the number of points returned.

### Limiting nearpoints results

```vex
int pts[];
pts = nearpoints(1, @P, chi('radius'), chi('numpoints'));
@P.y = len(pts);
```

The nearpoints function can be limited to return a specific maximum number of points by providing the fourth argument.

### Visualizing Point Cloud Density

```vex
int pts[];
pts = nearpoints(1, @P, ch('radius'), chi('num_points'));
@P.y = len(pts);
```

Uses nearpoints() to find neighboring points within a radius, then sets the Y position of each point to the count of neighbors found.

### Visualizing Point Density with nearpoints

```vex
int pts[];
pts = nearpoints(1, @P, ch('radius'), chi('numpoints'));
@P.y = len(pts);
```

Uses nearpoints() to find nearby points within a radius, then sets the Y position of each point based on the count of neighbors found.

### Declaring Variables for Nearpoints Analysis

```vex
int pts[] = nearpoints(1, @P, ch('radius'), chi('numpoints'));
@P.y = len(pts);

int pts[];
int pt;
vector pos;
float d, W;

// ...
```

Declares typed variables needed for nearpoints analysis: an integer array for storing point numbers, individual point integer, position vector, and float variables for distance and weight calculations.

### Setting up nearpoints variables

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch("radius"), ch("num"));
```

Declares variables needed for nearpoints query including an integer array for point numbers, individual point integer, vector for position, and floats for distance and weight.

### Animated sine wave displacement

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Creates animated sine wave displacement by calculating distance to nearest point, modulating it with a frequency parameter and time-based speed control, then applying the result as vertical displac....

### Wave Frequency and Radius Parameters

```vex
int pts[];
int pt;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('num_of_points'));

pt = pts[0];
@Cd = point(1, 'P', pt);
// ...
```

Demonstrates adjusting frequency and radius parameters to control wave behavior, showing how high frequencies can create visual artifacts and how radius affects wave overlap.

### Wave Frequency and Radius Control

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('max_pt_points'));

pt = pts[0];
// ...
```

Adjusts wave propagation by controlling frequency and radius parameters, demonstrating how higher frequency values can cause visual artifacts while lower frequencies produce smoother wave patterns.

### Accumulating Multiple Point Influences

```vex
int pts[];
int pt;
vector pos;
float d,w;

pts = nearpoints(1,@P,ch("radius"),chi("number_of_points"));

foreach(int i; pts){
// ...
```

Iterates through all nearby points found by nearpoints and accumulates their individual wave influences on the current point's Y position.

### Blending Multiple Ripple Effects

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

for(int i = 0; i < len(pts); i++) {
// ...
```

This code duplicates the ripple effect loop to blend multiple ripple influences together, using += on @P.y to accumulate the effects rather than overwriting them.

### Multi-wave interference with offsets

```vex
pos = pcfind(1, "P", p1);
id = distance(@P, pos);
w = d * ch('red');
s = sin(w);
w = sin(u);
w = ch(v, w, 0);
w = chramp('ramp', w);
w = ch(v, w, ch('radius'), 1, 0);
// ...
```

Extending multi-wave interference pattern by adding per-wave-center offsets to create non-uniform wave behavior.

### Array Loops and Near Points

```vex
int pts[];
int pt;
vector pos;
float d, m;

pts = nearpoints(1, @P, ch('radius'), chi('max_of_points'));

foreach(int pt; pts) {
// ...
```

Demonstrates looping through an array of nearby points using foreach syntax.

### Point Cloud Color Accumulation

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Finds nearby points within 40 units using nearpoints(), then iterates through each point to accumulate their color contributions.

### Color Blending with Nearpoints

```vex
vector pos, col;
int pts[];
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

foreach(int pt; pts){
// ...
```

Blends colors from multiple nearby points by finding all points within a radius, calculating distance-based weights using fit and clamp, and accumulating weighted color contributions.

### Foreach Loop Color Blending

```vex
foreach(element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;
// ...
```

Demonstrates using a foreach loop to iterate over an array of nearby points and blend their colors based on distance.

### Color Blending with Nearpoints

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(0, @P, chv("radius"));
@Cd = 0;

// ...
```

Blends colors from multiple nearby points by iterating through all points within a radius and accumulating their color contributions weighted by distance.

### Color Blending with Nearpoints

```vex
vector pos, col;
int pts[];
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

foreach(int pt; pts){
// ...
```

Iterates through all nearby points within a radius and additively blends their colors together based on distance falloff.

### Foreach Loop Color Averaging

```vex
foreach(element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;
// ...
```

Demonstrates foreach loop iteration over an array of nearby points found with nearpoints().

### Nearby Points Wave Deformation

```vex
vector pos;
int pts[];
int pt;
float d, d_f, t, f, g;

pts = nearpoints(1, @P, 40); // search within 40 units

foreach(pt; pts) {
// ...
```

Uses nearpoints to find surrounding points within 40 units, then applies a wave deformation to the Y position based on distance falloff and time.

### Distance-based animated wave deformation

```vex
vector pos;
int pts[];
int pt;
float u, d, f, t, a;

pts = nearpoints(1, @P, 40);

foreach(pt; pts) {
// ...
```

Animates point positions with a sine wave whose amplitude and frequency are modulated by distance from nearby points.

### Proximity-based wave displacement

```vex
vector pos;
int pts[];
int pt;
float d, f, t, a;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts) {
// ...
```

Uses nearpoints to find neighboring points within 40 units, then calculates distance-based falloff and applies sinusoidal wave displacement to each point's Y position.

### Time-based wave animation setup

```vex
vector pos;
int pts[];
int pt;
float d, a, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
// ...
```

Sets up time-based animation variables for wave effects by multiplying @Time with a speed parameter, adding per-point randomness using rand(pt) to offset timing, and computing amplitude and frequen....

### Foreach loop with nearpoints

```vex
v@Cd = 1;
int pt = 0;
int pts[];
vector pos;
float u, v, f, t, d;

pts = nearpoints(0, @P, 40);

// ...
```

Demonstrates foreach loop iterating over nearby points found with nearpoints, calculating distance-based falloff using fit and chramp, and accumulating trigonometric values.

### For Loop with Point Cloud Color Transfer

```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Demonstrates a for loop iterating over an array of nearby points found with nearpoints().

### Ink on Paper Point Cloud Effect

```vex
int pts[];
int p1;
vector col, pos;
float d;

pts = nearpoints(1, @P, ch("radius"));

// treat this as ink on paper, so start with white paper
// ...
```

Creates an ink-on-paper effect by starting with white and darkening each point based on nearby colored points from a second input.

### Color Blending from Nearby Points

```vex
vector pts = pts[];
int i, pt;
float d;
vector pos, col;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Uses nearpoints to find neighboring points within a radius, then accumulates their color contributions weighted by distance.

### Color Blending via Multiply Mode

```vex
int pts[];
int pt;
vector col, pos;
float d;

pts = nearpoints(1, @P, chf("radius"));

foreach(pt; pts) {
// ...
```

This snippet demonstrates a color blending exercise using nearpoints to sample nearby geometry colors and blend them additively with distance-based falloff.

### Color Blending from Nearby Points

```vex
int pts[];
int i, pt;
float d;
vector pos, col;

pts = nearpoints(0, @P, 40);
@Cd = 0;

// ...
```

Uses nearpoints to find surrounding points within a radius, then accumulates their colors weighted by distance.

### nearpoints vs pcfind comparison

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;
foreach (pt; pts) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}

// ...
```

Demonstrates using nearpoints() to find nearby points from input 1 within a given radius, then iterating through the results to add those points to the output geometry.

### nearpoints vs pcfind comparison

```vex
int pts[] = nearpoints(0, @P, ch('d'), 25);

int pt;

int pts[] = pcfind(1, 'P', @P, ch('d'), 25);
```

Demonstrates querying nearby points from a second input geometry using nearpoints() to find the closest points within a channel-controlled distance.

### nearpoints foreach loop setup

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;
foreach(pt; pts){
    
}
```

Sets up a nearpoints query to find up to 25 nearby points within a channel-controlled distance, storing results in an integer array.

### Nearpoints Array Setup with Foreach

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt1;
vector poss;
foreach(pt1; pts)
{
    
}
```

Creates an array of nearby point numbers using nearpoints() with a channel-controlled distance and maximum of 25 points, then declares variables for use in a foreach loop that will iterate through ....

### Foreach loop with nearpoints

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, "P", pt);
}
```

Declares variables for a nearpoints array, an iterator, and a position vector, then begins a foreach loop to iterate over nearby points.

### Foreach Loop Over Nearpoints

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;
foreach(pt; pts){
    pos = point(1, "P", pt);
}
```

Creates an array of nearby point indices using nearpoints(), then iterates through each point in the array using a foreach loop.

### Nearpoints Foreach Point Lookup

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
vector pos;
foreach (pt; pts) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}

// Alternative with pcfind:
// ...
```

Uses nearpoints() to find up to 25 points within a channel-controlled distance of the current point, then iterates through each found point with foreach to look up its position and create new point....

### Smoothing point snapping with nearpoints

```vex
@P = minpos(1, @P);

int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
vector pos = 0;
foreach (int pt; pts) {
    pos += point(1, 'P', pt);
}
@P = pos / len(pts);
```

Demonstrates smoothing point movement on a surface by replacing minpos (which snaps to the closest position) with nearpoints averaging.

### Smoothing Surface Movement with nearpoints

```vex
@P = attrib(1, "P", @P);

vector gP = attrib(1, "P", @P);

int pts[] = nearpoints(1, @P, ch("d"), chi("amt"));
vector pos = 0;
foreach (int pt; pts) {
    pos += point(1, "P", pt);
// ...
```

Instead of snapping to the single closest point (which causes jerky movement), this code finds multiple nearby points using nearpoints(), averages their positions, and moves the current point to th....

### Smoothing Surface Sampling with Near Points

```vex
@P = minpos(1, @P);

// Smoother version using averaging:
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
setpointgroup(0, "pts", pts, 1);
vector pos = 0;
foreach (int pt; pts) {
    pos += point(1, 'P', pt);
// ...
```

Instead of snapping points directly to the closest position on a surface using minpos (which causes visible jumping), this approach finds multiple nearby points using nearpoints, averages their pos....

### Smoothing Surface Movement with Nearpoints

```vex
@P = attoprim(1, @P);

int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int nt;
vector pos = 0;
foreach (int pt; pts) {
    pos += point(1, 'P', pt);
}
// ...
```

Instead of snapping directly to the closest point on a surface, this technique uses nearpoints() to find multiple nearby points, averages their positions, and then projects back to the surface.

### Nearpoints Setup for Smoothing

```vex
int pt[] = nearpoints(1, @P, ch("d"), chi("amt"));
```

Creates an array of nearby point numbers using nearpoints() to gather neighbors for smoothing operations.

### Point Position Smoothing with Neighbors

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));

vector pos = 0;
foreach (int pt; pts) {
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
```

This code smooths point positions by averaging the positions of nearby neighbors.

### Average Position from Nearby Points

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int @t;
vector pos = 0;

foreach(int pt; pts){
    pos += point(1, 'P', pt);
}

// ...
```

This code finds nearby points from a second input, accumulates their positions in a vector, then averages them by dividing by the count of points.

### Averaging Nearby Point Positions

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int @t;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

// ...
```

This snippet finds nearby points using nearpoints() and averages their positions to smooth or blend the current point's location.

### Point Cloud Averaging vs Manual Loop

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

// ...
```

Demonstrates two equivalent methods for averaging point positions: manually using nearpoints() with a foreach loop to accumulate and divide by length, versus using pcopen() and pcfilter() which aut....

### Averaging Point Positions with Nearpoints vs Point Cloud

```vex
// Method 1: Using nearpoints and foreach loop
int pts[] = nearpoints(1, @P, ch('d'), ch('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}
// ...
```

Demonstrates two methods for averaging point positions from neighboring points: the first uses nearpoints() to gather point numbers, iterates through them with foreach to accumulate positions, then....

### Point Cloud vs Manual Averaging

```vex
int pts[] = nearpoints(1, @P, ch('d'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, "P", pt);
}
@P = pos/len(pts);

// ...
```

Demonstrates two equivalent methods for averaging point positions: manually finding nearby points with nearpoints() and summing their positions, versus using the more efficient pcopen() and pcfilte....

### Point Averaging and Smoothing

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

// ...
```

Demonstrates point averaging by finding nearby points using nearpoints, accumulating their positions in a loop, and dividing by the count to get the average position.

### Averaging Near Points Positions

```vex
int pts[] = nearpoints(1, @P, ch('d'), ch('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, "P", pt);
}

// ...
```

Looks up nearby points on a surface geometry (input 1) and averages their positions to smooth point movement.

### Point Cloud Smoothing Comparison

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, "P", pt);
}

@P = pos/len(pts);
// ...
```

Demonstrates two equivalent approaches to point smoothing: a manual method using nearpoints() with a foreach loop to average neighbor positions, and a more concise point cloud method using pcopen()....

### Point Cloud Averaging Comparison

```vex
int pt[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;

foreach(pt; pt[]){
    pos += point(1, 'P', pt);
}

// ...
```

Demonstrates two approaches to averaging nearby point positions: the first uses nearpoints() with a foreach loop to manually accumulate and average positions, while the second shows the beginning o....

### Point Cloud Averaging vs Near Points

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, "P", pt);
}

// ...
```

Demonstrates two methods for smoothing point positions by averaging nearby points: the verbose approach using nearpoints() with a foreach loop to accumulate and average positions, versus the more c....

### Point Cloud Smoothing with Nearpoints

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int @i;
vector pos = 0;
foreach(int pt; pts){
    pos += point(1, "P", pt);
}

@P = pos/len(pts);
```

Uses nearpoints to find neighboring points within a radius, then averages their positions to smooth point movement across a surface.

### Point Averaging with nearpoints

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
```

This code demonstrates spatial averaging by finding nearby points using nearpoints() and computing their average position.

### Point Cloud vs Nearpoints Smoothing

```vex
// Manual approach with nearpoints
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach (pt; pts) {
    pos += point(1, 'P', pt);
}
pos /= len(pts);
// ...
```

Demonstrates two methods for smoothing points by averaging nearby positions: a manual approach using nearpoints with a foreach loop, and a more concise point cloud approach using pcopen and pcfilter.

### Averaging Nearby Points with nearpoints

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, "P", pt);
}

@P = pos/len(pts);
```

This code finds nearby points on a surface using nearpoints() and averages their positions to relocate the current point.

### Point Cloud Setup with pcopen

```vex
int pts[] = nearpoints(1, @P, ch('d'), ch('amnt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
// ...
```

Demonstrates setting up a point cloud query using pcopen() as an alternative to nearpoints().

### Point Cloud Normal Filtering

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
// ...
```

Opens a point cloud handle using pcopen() with the averaged position from nearby points, then uses pcfilter() to compute a weighted average normal from points within the cloud.

### Point Cloud Averaging with pcfilter

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int ptj
// vector pos = 0;

// foreach(int pti; pts){
//     pos += point(1, 'P', pti);
// }

// ...
```

This demonstrates using point cloud functions as an optimized alternative to manually averaging nearby point positions.

### Point Cloud Filtering with pcfilter

```vex
// int pts1 = nearpoints(1, @P, ch('d'), chi('amt'));
// int pts1;
// vector pos = 0;

// foreach(pt; pts1){
//     pos += point(1, 'P', pt);
// }

// ...
```

Demonstrates using pcopen() and pcfilter() to achieve the same averaging effect as the nearpoints/foreach approach but in just two lines of code.

### Point Cloud Filtering Shortcut

```vex
// int pts1 = nearpoints(1, @P, ch('d'), chi('amt'));
// int pts;
// vector pos = 0;

// foreach(pt; pts1){
//     pos += point(1, "P", pt);
// }

// ...
```

Demonstrates using pcfilter() as a two-line shortcut to replace the manual nearpoints/foreach/averaging workflow.

### Point Cloud Filter Normals

```vex
int mypc = pcopen(1, "P", @P, ch("d"), chi("maxpt"));
@P = pcfilter(mypc, "P");

int mypc = pcopen(1, "P", @P, ch("d"), chi("maxpt"));
@P = pcfilter(mypc, "P");
@N = normalize(@N * 2); // to make it easier to see!

int mypc = pcopen(1, "P", @P, ch("d"), chi("maxpt"));
// ...
```

Uses pcfilter to read and average the normal attribute (@N) from nearby points instead of position.

### Point Cloud Attribute Filtering

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
// foreach(int pt; pts){
//     vector pos = 0;
//     foreach(pt; pts){
//         pos += point(1, 'P', pt);
//     }
//     @P = pos/len(pts);
// }
// ...
```

Demonstrates using point clouds to filter and sample attributes from nearby geometry.

### Point Cloud Filtering Normals

```vex
int pts[] = nearpoints(1, @P, ch('d'), ch('maxpt'));
// int pts;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// ...
```

Creates a point cloud from nearby points and uses pcfilter to read and average the normal attribute from neighbors, then normalizes and scales the result.

### Point Cloud Attribute Filtering

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int pt;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// ...
```

Demonstrates the advantage of point clouds over nearpoints by using pcopen to create a point cloud handle, then pcfilter to efficiently query and average normal vectors from neighboring points.

### Point Cloud Attribute Filtering

```vex
int ptsli = nearpoints(1, @P, ch('d'), chi('amt'));
int pt1;
vector pos = 0;

foreach(pt; ptsli){
    addpoint(0, pt, @P);
}

// ...
```

Opens a point cloud handle using pcopen and extracts the normal attribute from nearby points using pcfilter.

### Point Cloud Filtering for Normals

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
// int pt[];
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// ...
```

Opens a point cloud handle from the first input using pcopen, then uses pcfilter to gather and average normal vectors from nearby points within the search radius.

### Color Blurring with Point Cloud

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('maxpt'));
// int pts[];
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// ...
```

Uses pcopen to create a point cloud from the current geometry at each point position, then applies pcfilter to average the color attribute (@Cd) from surrounding points within the specified distanc....

### Point Cloud Color Sampling

```vex
// VEX Wrangle
int pts[] = nearpoints(1, @P, ch('d'), chi('maxpt'));
// int pts;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }
// ...
```

Opens a point cloud handle using pcopen() at the current point position with controllable distance and max points parameters, then uses pcsample() to average the color (Cd) attribute from all point....

### Point Cloud Color Averaging

```vex
// int pts[] = nearpoints(1, @P, ch('d'), ch('maxpt'));
// int pts;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// ...
```

Uses pcopen() to create a point cloud handle, then pcfilter() to average the color (Cd) attribute across neighboring points.

### Point Cloud Color Filtering

```vex
// int pts[] = nearpoints(1, @P, ch('d'), ch('mont'));
int pts[] = nearpoints(1, @P, ch('d'), ch('mont'));
// int pt;
// vector pos = 0;

// foreach(pt; pts){
    pos += point(1, 'P', pt);
// }
// ...
```

Uses pcopen and pcfilter to blur color attributes by averaging the Cd values of nearby points within a specified radius.

### Point Cloud Color Filtering

```vex
// int pt[] = nearpoints(1, @P, ch('d'), ch('amt'));
// int pt;
// vector pos = 0;

// foreach(pt; pts;)
//     pos += point(1, 'P', pt);
// )

// ...
```

Demonstrates using point clouds to blur attributes by opening a point cloud based on position to filter colors, then inversely opening a point cloud based on color distance to filter positions.

### Point Cloud Attribute Blur

```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("maxpt"));
@Cd = pcfilter(pc, "Cd");

int pc = pcopen(0, "Cd", @Cd, ch("dist"), chi("maxpts"));
@P = pcfilter(pc, "P");
```

Demonstrates two complementary point cloud blur techniques: first, finding points near each point's position and averaging their color values, and second, finding points near each point's color in ....

### Point Cloud Attribute Swapping

```vex
int pc = pcopen(0, "P", @P, ch("dist"), ch("maxpoints"));
@Cd = pcfilter(pc, "Cd");

int pc = pcopen(0, "Cd", @Cd, ch("dist"), ch("maxpoints"));
@P = pcfilter(pc, "P");
```

Demonstrates swapping lookup attributes in point cloud queries.

### Point Cloud Query by Color

```vex
int pc = pcopen(0, 'cd', @Cd, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
```

Creates a point cloud handle by querying nearby points based on color similarity rather than spatial position.

### Point Cloud Lookup from Position

```vex
int pc = pcopen(0, "P", @P, ch("d"), ch("maxpt"));
@Cd = pcfilter(pc, "Cd");
```

Opens a point cloud handle using the current point's position (@P) as the query location, then samples and averages the color (Cd) attribute from nearby points found within the point cloud.

### Point Cloud Filtering with pcfilter

```vex
int pc = pcopen(0, 'id', @Cd, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
```

Opens a point cloud handle using the color attribute (@Cd) as the search position, then uses pcfilter to set the current point's position to the averaged position of all points found in the point c....

### Color-based Point Cloud Filtering

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpt"));
@Cd = pcfilter(pc, "Cd");

// Modified version:
int pc = pcopen(0, "Cd", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
```

Demonstrates switching the point cloud lookup criteria from position-based to color-based.

### Point Cloud Color-Based Clustering

```vex
int pc = pcopen(0, "P", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
```

Opens a point cloud using color (@Cd) as the lookup attribute instead of position, then filters and averages the position values from neighboring points.

### Point Cloud Color Clustering

```vex
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
```

Opens a point cloud handle based on color similarity (@Cd) within a specified distance and maximum point count, then uses pcfilter to average the positions of all points in that neighborhood, causi....

### Point Cloud Filtering by Normal

```vex
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");

int pc = pcopen(0, "N", @N, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
```

Demonstrates using point cloud queries to average point positions based on similarity of attributes.

### Point Cloud Filtering by Normal

```vex
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");

int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");

int pc = pcopen(0, "N", @N, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
// ...
```

Demonstrates using point cloud queries to group points by similarity, first by color (@Cd) and then by normal direction (@N).

### Point Cloud Filtering by Normals

```vex
int pc = pcopen(0, "N", @N, ch("d"), chi("amt"));
@P = pcfilter(pc, "P");
```

Opens a point cloud based on normal similarity rather than color, then filters the position attribute to average positions of points with similar normals.

### Point Cloud Filtering by Normals

```vex
int pc = pcopen(0, 'cd', @Cd, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');

int pc = pcopen(0, 'N', @N, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
@Cd = @N;
```

Demonstrates using pcopen with normal attributes instead of color to find similar points based on normal direction.

### Point Cloud Normal Filtering

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @Cd;
```

Opens a point cloud query based on position proximity, then applies pcfilter to smooth positions by averaging nearby points.

### Point Cloud Query by Normal

```vex
int pc = pcopen(0, "N", @P, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud lookup using normals (@N) as the search attribute instead of position, enabling queries based on surface orientation similarity.

### Point Cloud Normal Lookup

```vex
int pc = pcopen(0, "P", @P, ch("dist"), ch("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud using current point position, filters to get averaged position from nearby points, then visualizes normals by copying them to color.

### Point Cloud Normal Filtering

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud handle and uses pcfilter to average nearby point positions, effectively smoothing the geometry.

### Normal-based Point Cloud Filtering

```vex
int pc = pcopen(0, "N", @N, ch("dist"), chi("maxpts"));
vector avg = pcfilter(pc, "P");
@P = avg;
@Cd = @Cd;
```

This code uses point cloud lookup based on normals instead of color to find nearby points and average their positions.

### Point Cloud Normal-Based Filtering

```vex
int pc = pcopen(0, "P", @P, ch("d"), ch("maxct"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud using current point position, filters to get averaged position of nearby points, then visualizes normals by writing them to color attribute.

### Point Cloud Normal-Based Filtering

```vex
int pc = pcopen(0, "P", @P, ch("d"), ch("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(0, "P", @N, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Demonstrates two point cloud filtering approaches: first using position (@P) as the search origin, then using the normal vector (@N) as the search origin to find neighboring points and average thei....

### Point Cloud Filtering by Normal

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpt"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud searching by position, then uses pcfilter to average the position attribute of nearby points, effectively smoothing geometry.

### Point Cloud Averaging with Color

```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud around each point, then uses pcfilter to average the positions of neighboring points within the search radius, effectively smoothing the geometry.

### Point Cloud Filtering and Velocity

```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("mant"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv -= {1, 0, 1, 1};
// ...
```

Two point cloud examples: the first opens a point cloud from the first input and filters positions while coloring by normals.

### Point Cloud Filtering Example

```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("mxnt"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(0, "P", @P, 10, 30);
vector avgp = pcfilter(pc, "v");
vector avgv = pcfilter(pc, "P");
avgv -= {1, 0, 1, 1};
// ...
```

Demonstrates point cloud filtering using pcopen and pcfilter to average nearby point positions and velocities.

### Point Cloud Filtering and Velocity Adjustment

```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("maxpt"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(1, "P", @P, 10, 30);
vector avg0 = pcfilter(pc, "v");
vector avg1 = {1, 0, 1};
avg0 = {1, 0, 1};
// ...
```

Opens point clouds to filter position and velocity attributes, then adjusts the velocity vector by computing the difference between filtered velocity and a constant vector.

### Point Cloud Filtering with Normal Visualization

```vex
int pc = pcopen(0, "P", @P, ch("d"), ch("maxpt"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud handle using pcopen with distance and max point parameters from channels, then uses pcfilter to average the position of nearby points and moves the current point to that average....

### Point Cloud Filtering and Velocity

```vex
int pc = pcopen(0, "P", @P, ch("r"), chi("max"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(1, "P", @P, 10, 30);
vector avgp = pcfilter(pc, "v");
vector avgv = pcfilter(pc, "P");
avgp -= (1, 0.1, 1);
// ...
```

Demonstrates two point cloud filtering operations: first uses pcopen and pcfilter to average nearby point positions with channel-driven parameters, then opens a second point cloud to compute veloci....

### Point Cloud Filtering Examples

```vex
// Example 1: Filter position based on nearby points
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;

// Example 2: Average velocity from nearby points
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
```

Two point cloud examples demonstrating pcfilter usage: first filters position values from nearby points on the current geometry using channel-driven search parameters, then reads normal into color;....

### Point Cloud Filtering with Normals

```vex
int pc = pcopen(0, "N", @N, ch("d"), ch("maxpt"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Opens a point cloud using the normal vector as the search direction, then filters the results to average the position values of nearby points.

### Point Cloud Filtering Examples

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
vector gn = pcfilter(pc, "P");
@Cd = gn;

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
```

Two examples of using pcfilter() to query point cloud data: the first opens a point cloud using channel-referenced parameters and filters position data, assigning it to color; the second queries ve....

### Point Cloud Filtering Examples

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(1, "P", v@P, 10, 30);
vector avgp = pcfilter(pc, "v");
```

Two examples of using point cloud functions to query and filter neighboring points.

### Point Cloud Filtering Examples

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
vector gn = pcfilter(pc, "P");
@Cd = @n;

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
```

Two practical examples of point cloud filtering.

### Point Cloud Flocking Force

```vex
int pc = pcopen(1,"P",@P,10,30);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= {1,0,1};
avgp *= {1,0,1};
@v += avgv-avgp;
```

Opens a point cloud and filters neighboring particle velocities and positions, then masks the Y component to zero for both.

### Point Cloud Velocity Smoothing

```vex
int pc = pcopen(1,"P",@P,10,30);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= {1,0,1};
avgp -= {0,1,0};
@v += avgv-avgp;
```

Creates a point cloud query to find nearby points within radius 10 (max 30 points), then averages their velocity and position attributes.

### Point Cloud Velocity Averaging

```vex
vector pos = vector(@P.x * 0.2 * offset, 1) * {2, 0, 2};
@P = set(@P.x * @ez, @P.y, @P.z * @ez);

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
avgp -= {1, 0, 1};
// ...
```

Uses point cloud functions to query nearby points within a radius, calculates average velocity and position from neighbors, then adds the difference between averaged velocity and position to the cu....

### Point Cloud Velocity Averaging

```vex
int pc = pcopen(0, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
@v += (1, 0, 1, 1);
avgp -= (1, 0, 1, 1);
@v -= avgv - avgp;
```

Opens a point cloud with a search radius of 10 and maximum 30 points, then calculates average velocity and position of neighbors.

### Point Cloud UV Filtering

```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgu = pcfilter(pc, "u");
vector avgv = pcfilter(pc, "v");
avgu = {1, 0, 1, 1};
avgv = {1, 0, 1, 1};
@v = avgv - avgu;
```

Opens a point cloud and uses pcfilter to compute averaged u and v attribute vectors from nearby points.

### Point Cloud Velocity Averaging

```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
avgp -= @P;
@v -= avgv - avgp;
```

Opens a point cloud of 30 nearby points within radius 10, then averages their velocity and position attributes using pcfilter().

### Point Cloud Velocity Averaging

```vex
int pc = pcopen(1,"P",@P,10,30);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= {1,0,1};
avgp -= {1,0,1};
@v -= avgv-avgp;
```

Opens a point cloud of 30 nearby points within radius 10, then filters both velocity and position attributes.

### Point Cloud Velocity Filtering

```vex
vector uv = set(rand(@ptnum), rand(@ptnum+1));
@v += chvlen('line');
//rgb as curvelookup((1,1,1)@age*(sw*0.2)*(1,0,0));

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
// ...
```

Uses point cloud queries to average velocity and position from nearby points within a radius, then modifies the current point's velocity based on neighborhood averaging.

### Point Cloud Velocity Averaging in POPs

```vex
int pc = pcopen(1,"P",@P,10,30);
vector avgv = pcfilter(pc,'v');
vector avgp = pcfilter(pc,'P');
avgv *= {1,0,1};
avgp *= {1,0,1};
@v += avgv-avgp;
```

Uses point cloud queries within a POP Wrangle to find nearby particles (within 10 units, up to 30 points) and averages their velocity and position attributes.

### Point Cloud Velocity Averaging for Particles

```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
avgp *= {1, 0, 1};
@v += avgv - avgp;
```

Uses point cloud queries on second input geometry to calculate averaged velocity and position vectors, masking out the Y component, then modifies particle velocity based on the difference.

### Point Cloud Particle Velocity Filtering

```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
@v *= {1, 0, 1};
avgp *= {1, 0, 1};
@v += avgv * avgp;
```

Uses pcopen to find up to 30 nearest points within 10 units from the second input geometry, then filters to get average velocity and position.

### Point Cloud Particle Flocking

```vex
int pc = pcopen(0, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv *= {1, 0, 1};
avgp -= {1, 0, 1};
@v += avgv - avgp;
```

Uses point cloud queries to create particle flocking behavior by finding the 30 nearest points within 10 units and averaging their velocity and position.

### Velocity Smoothing with Point Cloud

```vex
int pc = pcopen(1, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv *= {1, 0.1, 1};
avgp *= {1, 0.1, 1};
@v += avgv - avgp;
```

Opens a point cloud to find nearby points, then filters both velocity and position attributes, scaling them down (particularly in Y by 0.1).

### Point Cloud Velocity Averaging

```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
@v *= (1, 0.1, 1);
@v += (1, 0.1, 1);
@v += avgv - avgp;
```

Opens a point cloud on input 1 to find nearby points, then uses pcfilter to average their velocity and position attributes.

### Point Cloud Velocity Averaging

```vex
i@tpc = pcopen(1, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv -= {1, 0, 1, 1};
avgp -= {1, 0, 1, 1};
@v += avgv - avgp;
```

Opens a point cloud on the first input and averages both velocity and position attributes from nearby points.

### Particle Clumping with Point Clouds

```vex
int pc = pcopen(1, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv *= {3, 0.1, 1};
avgp *= {3, 0.1, 1};
@v += avgv - avgp;
```

Uses point cloud queries to average nearby particle velocities and positions, then applies weighted differences to create clumping behavior.

### Point Cloud Particle Clumping

```vex
int pc = pcopen(0, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv = {1, 0, 1, 1};
avgp = {1, 0, 0, 1};
@v += avgv - avgp;

int pc2 = pcopen(1, "P", @P, 10, 30);
// ...
```

Uses point cloud queries on two input geometries to average neighboring particle positions and velocities, then modifies the current point's velocity based on the difference between averaged values.

### Particle Clumping with Point Clouds

```vex
int pc = pcopen(1, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv *= 0.1;
avgp -= @P;
avgp *= 0.1;
@v += avgv - avgp;
```

This technique uses point cloud queries to create particle clumping behavior by averaging both velocities and positions of nearby points.

### Particle Clumping with Point Clouds

```vex
int pc = pcopen(0, "P", @P, ch("rad"), 100);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= set(1, 0, 1);
avgp *= set(1, 0, 1);
@v += avgv - avgp;
```

Creates a clumping effect for particles by opening a point cloud around each point, averaging the velocity and position of nearby neighbors, masking Y-axis components, then adjusting the current ve....

### Point Cloud Particle Clumping

```vex
int pc = pcopen(0, "P", @P, ch('rad'), 100);
vector avgv = pcfilter(pc, "v");
avgv *= {1, 0, 1};
@P += avgv;

vector avgp = pcfilter(pc, "P");
avgp -= @P;
@P += avgp;
// ...
```

Uses point cloud queries to average nearby particle velocities and positions, causing particles with similar initial conditions to coalesce into clumped spiral patterns.

### Point Cloud Particle Averaging

```vex
int pc = pcopen(0,"P",@P,ch("radius"),chi("maxpts"));
vector avgv = pcfilter(pc,"v");
avgv *= {1,0,1};

vector avgp = pcfilter(pc,"P");
avgp *= {1,0,1};
@P += avgv-avgp;

// ...
```

Demonstrates averaging particle positions and velocities using point cloud queries to create coalescing spiral patterns.

### Point Cloud Filtering and Averaging

```vex
int pc = pcopen(0, "P", @P, ch("dist"), ch("maxlist"), ch("numpoints"));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Demonstrates point cloud filtering to average neighboring point positions and velocities, creating clumping behavior for particles.

### Fake Ambient Occlusion with Point Clouds

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Creates a fake ambient occlusion effect by opening a point cloud around each point, then computing both the dot product between the point's normal and averaged nearby normals, and the distance to a....

### Fake Ambient Occlusion with Point Clouds

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxpts'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Creates a fake ambient occlusion effect by opening a point cloud and filtering averaged position and normal values.

### Fake Ambient Occlusion with Point Clouds

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), ch('maxpoints'));
vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

dot = dot(@N, pcn);
// ...
```

This technique creates a fake ambient occlusion effect by opening a point cloud around each point, filtering the average position and normal of nearby points, then calculating both the dot product ....

### Fake Ambient Occlusion with Point Clouds

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxpt'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Creates a fake ambient occlusion effect by opening a point cloud around each point, filtering averaged position and normal data, then calculating both the dot product between the current point norm....

### Fake Ambient Occlusion

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), chi('maxpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Creates a fake ambient occlusion effect by opening a point cloud around each point, filtering the averaged position and normal, then computing dot product and distance values.

### Pseudo Ambient Occlusion via Point Cloud

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), chi('numpoints'));
vector pcP, pcN;
float dot, dist;

pcP = pcfilter(pc, "P");
pcN = pcfilter(pc, "N");

dot = dot(@P, pcN);
// ...
```

Creates a pseudo ambient occlusion effect by opening a point cloud around each point to get blurred position and normal values, then calculates dot product between current position and blurred norm....

### Point Cloud Ambient Occlusion

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

// ...
```

Creates a pseudo-ambient occlusion effect by opening a point cloud to find nearby geometry, filtering the blurred position and normal values, then comparing the current point's normal with the filt....

### Ambient Occlusion via Point Cloud

```vex
@P = pcimport(0, "P", @P, @N*ch('bias'), ch('maxdist'), chi('maxpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(0, 'P');
pcn = pcfilter(0, 'N');

// ...
```

Creates an ambient occlusion effect by using point cloud filtering to blur position and normal attributes, then comparing the original normal to the blurred normal via dot product (or measuring dis....

### Ambient Occlusion via Point Cloud

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), ch('numpoints'));
vector avgP = 0;
float dot, dist;

@Cd = chv("clr_in");

avgP = pcfilter(pc, "P");
vector pcN = pcfilter(pc, "N");
// ...
```

Creates an ambient occlusion effect by opening a point cloud lookup biased along the surface normal, then comparing the current point's normal to the averaged normals in the neighborhood via dot pr....

### Ambient Occlusion via Point Cloud

```vex
int pc = pcopen(0, "P", @P+ch('bias'), ch('maxdist'), chi('maxpt'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

// ...
```

Creates an ambient occlusion or curvature map by opening a point cloud near each point, filtering to get averaged position and normal values, then computing the dot product between the original and....

### Point Cloud Curvature Mapping

```vex
int pc = pcopen(0, "P", @P + @N * ch('bias'), ch('maxdist'), chi('maxpts'));
vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
// ...
```

Creates a curvature-like visualization by opening a point cloud with a biased lookup position (offset by normal), then filtering to get averaged position and normal values.

### Point Cloud Dot Product and Distance Analysis

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxpts'), chi('maxdist'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Opens a point cloud and computes both the dot product between the current point's normal and the averaged point cloud normal, and the distance between the current point and the averaged point cloud....

### Point Cloud Dot Product and Distance

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxpts'), chi('maxpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Opens a point cloud and calculates both the dot product between the current normal and averaged neighbor normals, and the distance to the averaged neighbor positions.

### Point Cloud Ramp Control

```vex
int pc = pcopen(0, "P", @P+@N*ch('bias'), ch('maxdist'),
chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");
// ...
```

Uses chramp() to apply user-controlled color ramps to both the dot product comparison and distance calculation from a point cloud query, allowing artistic control over the falloff curves.

### Fake AO with Ramp Controls

```vex
int pc = pcopen(0, "P", @P, chf('bias'), chi('maxlist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

Creates a fake ambient occlusion effect by computing both dot product and distance between point normals and positions using point clouds, then remapping those values through color ramps for artist....

### Fake Ambient Occlusion with Point Clouds

```vex
int pc = pcopen(0, "P", @P, chv("maxdist"), chi("maxptct"));
vector pos, pcn;
float dot, dist;

pcn = pcfilter(pc, "P");
pos = pcfilter(pc, "pos");

dot = dot(@N, pcn);
// ...
```

Demonstrates two approaches for creating fake ambient occlusion using point cloud queries.

### Ambient Occlusion with Dot Product

```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), i);
int numpnts;
vector pcN = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcN);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```

This code calculates ambient occlusion by comparing the current point's normal to the averaged normal of nearby points using a dot product.

### Point Cloud Normal Comparison with Gamma

```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcN = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcN);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```

Creates a point cloud lookup based on position, computes the normalized average normal from nearby points, then calculates the dot product between the point cloud normal and the current point's normal.

### Point Cloud and Color Fitting

```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), ch('numpts'));
vector pos = normalize(jitter(@P, 'B'));
vector norm = normalize(n1);
vector up = {0, 1, 0};
@Cd = fit(chv('a'), -1, 1, 0, 1);
@Cd = smooth(@Cd, chf('smooth'));
```

This code opens a point cloud query using pcopen with channel-driven parameters for maximum distance and number of points.

### Point Cloud Filtering and Color Mapping

```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi('numpts'));
vector pos = normalize(pcfilter(pc, "P"));
vector norm = normalize(pcfilter(pc, "N"));
@Cd = fit(sin(@Time), -1, 1, 0, 1);
@Cd = fit(cos(@Frame), -1, 1, 0, 1);
```

Opens a point cloud query and filters position and normal data from nearby points, then demonstrates various color mapping techniques using fit() with trigonometric functions.

### Day 20 Resources and External Links

```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi('numpoints'));
vector pos = normalize(pcfilter(pc, "P"));
vector nrml = normalize(chi);
@Cd = fit01(pos, -1, 1);
@Cd = fit(sin, -1, 1, 0, 1);
@Cd = switch, ch('maxdist'), chi('numpoints'));
```

This snippet appears to be incomplete and contains syntax errors, demonstrating point cloud operations with pcopen and pcfilter, followed by attempted color assignments using fit and fit01 functions.

### Day 20 Reference Resources

```vex
int list pc = pcopen(0, "P", @P, ch("maxdist"), ch("numpoints"));
vector pos = normalize(jitter(@P, 8));
vector norm = normalize(pos);
@Cd = fit01(pos, -1, 1, 0, 1);
@Cd = fit(pos, -1, 1, 0, 1);
@Cd = pcw(pos, 0, ch("seed"));
```

This code snippet demonstrates various VEX functions used throughout the Joy of Vex series, including point cloud queries, vector normalization, jittering, and color mapping with fit functions.

### Point Cloud and Color Fitting

```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi('numpts'));
vector pos = normalize(fit(i@ptnum, 0, i@numpt - 1, 0, 1));
vector parm = normalize(chi);
@Cd = set(pos);
@Cd = fit(chv("col"), -1, 1, 0, 1);
@N = fit(chv("col"), -1, 1, 0, 1);
```

This snippet demonstrates opening a point cloud with pcopen, normalizing fitted point numbers as vectors, and remapping channel vector values to color and normal attributes using the fit function.

### Transfer Attributes from Second Input

```vex
int pt = nearpoints(0, @P, 1);
v@Cd = point(0, 'Cd', pt);
```

Transfers color attributes from a second input geometry by finding the nearest point using nearpoints() and reading its color with point().

### Understanding point() Function Syntax

```vex
int pt = nearpoints(0, @P);
@Cd = point(0, 'Cd', pt);
```

This demonstrates the syntax of the point() function, which retrieves an attribute value from a specific point.

### Point function attribute syntax

```vex
int pt = nearpoint(0, @P);
@Cd = point(0, 'Cd', pt);
```

This snippet demonstrates using nearpoint() to find the closest point and then reading its Cd attribute with the point() function.

### Nearpoint attribute transfer and distance

```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = d;
```

This snippet finds the nearest point on the second input, transfers its color attribute to the current point, retrieves that neighbor's position, calculates the distance between the two points, and....

### Distance-based Height Transfer

```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
vector pos = point(1, 'P', pt);
float d = distance(@P, pos);
@P.y = d;
```

This code finds the nearest point from the second input and calculates the distance between the current point and that nearest point, then uses that distance value to set the Y position of the curr....

### Distance-Based Y Displacement

```vex
int pt = nearpoint(1, @P);
@Cd = point(1, "Cd", pt);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = -d;
```

Finds the nearest point on the second input, reads its color and position, calculates the distance between the current point and that nearest point, then uses that distance to displace the Y compon....

### Nearest Point Distance Mapping

```vex
int pt = nearpoint(1, @P);
v@Cd = point(1, "Cd", pt);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = d;
```

Finds the nearest point from a second input geometry and transfers its color attribute.

### Shifting Points by Distance to Nearest Neighbor

```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
vector pos = point(1, 'P', pt);
float d = distance(@P, pos);
@P.y = -d;
```

Finds the nearest point on the second input, reads its position and color, then calculates the distance between the current point and that nearest point.

### Distance-Based Color Transfer

```vex
int pt = nearpoint(0, @P);
v@Cd = point(0, 'Cd', pt);
vector pos = point(0, 'P', pt);
float d = distance(@P, pos);
v@Cd *= d;
```

This code finds the nearest point from the first input, reads its color and position, then calculates the distance between the current point and that nearest point.

### Sampling Input Geometry with Nearpoint

```vex
vector p1 = @opinput1_P;
vector cd1 = @opinput1_Cd;

@P = p1;
@Cd = cd1;

int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
// ...
```

This code samples position and color from a second input geometry by finding the nearest point, then uses the distance from that nearest point (with randomization) to drive a vertical displacement ....

### Finding Nearest Point Color and Distance Falloff

```vex
float myarray[] = array(1,2,3,4,5); // ok
f[]@myarray = array(1,2,3,4,5); // ok

int pt = nearpoint(1, @P);
vector col = point(1, "Cd", pt);
@Cd = col;

int pt = nearpoint(1, @P);
// ...
```

Demonstrates finding the nearest point on input 1, reading its color and position, then applying that color with a distance-based falloff.

### Voronoi pattern with nearpoint

```vex
float a = 4.21;
int s = set(a, 3, 3);

f[]@array = array(a, 3, 3, 4, 5);

int pt = nearpoint(1, @P);
vector col = point(1, 'Cd', pt);
@Cd = col;
// ...
```

Demonstrates creating a Voronoi-style color pattern by finding the nearest point on input 1 using nearpoint(), reading its color attribute, computing the distance to it, and using fit() and clamp()....

### Nearpoint Color Falloff

```vex
float myarray[] = array(1,2,3,4,5); // ok
f[]@myarray = array(1,2,3,4,5); // ok

int pt = nearpoint(1,@P);
vector col = point(1,'Cd',pt);
@Cd = col;

int pt = nearpoint(1,@P);
// ...
```

Demonstrates finding the nearest point from a second input using nearpoint(), then retrieves that point's position and color.

### Reading Nearest Point Attributes

```vex
int pt = nearpoint(1, v@P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);

v@Cd = col;
```

Uses nearpoint() to find the closest point on input 1, then reads both position and color attributes from that nearest point using the point() function.

### Distance-based color falloff

```vex
int pt = nearpoints(1, @P, 1)[0];
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```

Finds the nearest point on input 1, calculates the distance to it, then remaps that distance from 0 to a user-defined radius into a 1-to-0 falloff range.

### Distance-Based Color Falloff

```vex
int pt = nearpoint(0, @P);
vector pos = point(0, "P", pt);
float d = distance(@P, pos);
float r = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```

Finds the nearest point, calculates the distance to it, and uses that distance (clamped between 0-1) to create a falloff effect that modulates a color value.

### nearpoints array with radius search

```vex
int pts[] = nearpoints(1, @P, ch('d'));
int pt = pts[0];
vector pos = point(1, 'P', pt);
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, chf('mix'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col;
```

Demonstrates transitioning from nearpoint() to nearpoints() to get an array of nearby points within a search radius.

### Nearpoints Distance-Based Color Transfer

```vex
int pts[] = nearpoints(1, @P, ch('radius'), 1);
vector pos = point(1, "P", pts[0]);
vector col = point(1, "Cd", pts[0]);
float d = distance(pos, @P);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```

Uses nearpoints() to find nearby points within a radius, then samples the closest point's position and color.

### Multi-Point Color Blending

```vex
int pt = pts[0];
vector pos = point(1, 'P', pt);
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;

// ...
```

Demonstrates extending single-point color blending to multiple nearby points by duplicating the distance-based color blending logic for both the first and second nearest points.

### Blending Multiple Nearest Point Colors

```vex
int pt[];
float d;
vector pos, col;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// first point
// ...
```

This code extends the nearest point color blending by manually processing two separate points from the nearpoints array.

### Debugging with temporary attributes

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);

//first point
// ...
```

Demonstrates processing multiple nearby points using nearpoints() to find neighbors, then accessing individual points by array index to sample their colors and blend them based on distance.

### Debugging with Temporary Attributes

```vex
vector pos, col;
int pt;
int pts[];
float d;

pts = nearpoints(1, @P, 40);

@Cd = 0;
// ...
```

Demonstrates using temporary attributes for debugging by writing intermediate array results to a geometry attribute.

### Debugging with Array Attributes

```vex
int pts[];
pts = nearpoints(0, @P, 20);
i[]@a = pts;

// first point
int pt = pts[0];
vector col = point(0, 'Cd', pt);
vector pos = point(0, 'P', pt);
// ...
```

Demonstrates a debugging technique by writing the nearpoints array to a detail array attribute (@a) so you can visualize which points are being found in the point cloud search.

### Commenting and Near Points Limiting

```vex
vector pos, col;
int pt1;
int pt;
float d;

int[] pts = nearpoints(1, v@P, 40);
// slider = pt1;
@Cd = 0;
// ...
```

Demonstrates using Ctrl+/ to comment/uncomment lines in VEX for quick testing and debugging.

### Limiting nearpoints return count

```vex
// VEX code
int ptnum, pts, col;
int pt[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
// i[]@a = pts;
// ...
```

Demonstrates using the optional max count parameter in nearpoints() to limit the number of returned points.

### Limiting nearpoints with max count

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(0, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Demonstrates using nearpoints() with a maximum count argument to limit how many nearby points are returned, rather than returning all points within the radius.

### nearpoints with point limit

```vex
vector pts, pos;
int ptsi[];
vector pos[];
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_points'));

pt = pts[0];
// ...
```

Demonstrates using nearpoints() with a fourth argument to limit the number of returned points instead of returning all points within the search radius.

### Visualizing nearpoints array length

```vex
int pts1[];
pts1 = nearpoints(1, @P, 12, 3);

@P.y = len(pts1);
```

Demonstrates how to query nearby points using nearpoints() with a fixed radius of 12 and maximum of 3 points, then visualizes the result by setting the Y position to the length of the returned array.

### Visualizing nearpoints array length

```vex
int pts[];
pts = nearpoints(1, @P, ch("radius"), ch("max_points"));
@P.y = len(pts);
```

Uses nearpoints() to find nearby points within a channel-controlled radius and maximum count, then visualizes the result by setting each point's Y position to the array length using len().

### Visualizing Point Cloud Density

```vex
int pts[];
pts = nearpoints(1, @P, ch('radius'), chi('num_points'));
@pry = len(pts);
```

Creates a point cloud query to find nearby points within a specified radius, then stores the count of found points in a custom attribute for visualization.

### Nearpoints proximity displacement setup

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Sets up variables and uses nearpoints() to find nearby points from the second input geometry within a specified radius, preparing for proximity-based displacement.

### Near Points Position Query

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Retrieves the nearest points from the second input using nearpoints(), then extracts the first point from the array and queries its position using point().

### Animated Ripple Waves from Points

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Creates animated ripple waves emanating from nearby points by calculating distance-based sine waves that progress over time.

### Animated Sine Wave Ripples

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Creates animated sine wave ripples emanating from nearby points by finding the nearest point, calculating distance-based sine waves controlled by frequency and radius parameters, and displacing poi....

### Accessing Array Elements in Point Cloud

```vex
int pts[];
int pt;
float d, mind;

pts = nearpoints(1, @P, ch('radius'), chi('max_nf_points'));

pt = pts[0];
mind = distance(@P, point(1, 'P', pt));
// ...
```

Demonstrates iterating through a nearpoints array to find the closest point by comparing distances.

### Blending Multiple Ripple Effects

```vex
int pts[];
int pt;
vector pos;
float d, w, s;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

for(int i = 0; i < len(pts); i++) {
// ...
```

Iterates through multiple nearby points to accumulate ripple effects, using += operators to blend contributions from each neighbor rather than overwriting.

### Foreach Loop with Nearpoints

```vex
foreach(element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;
// ...
```

Demonstrates foreach loop syntax to iterate through an array of nearby point numbers.

### Color Blending with Foreach Loop

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set colour to black to start with

// ...
```

Uses a foreach loop to iterate through nearby points within a 40-unit radius, sampling their positions and colors.

### Color Blending from Nearby Points

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set point to black to start with

// ...
```

Accumulates color from nearby points within a search radius, weighting each neighbor's color contribution by its distance.

### Accumulating nearby point colors

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
foreach (pt; pts) {
    pos = point(1, "P", pt);
// ...
```

Searches for points within 40 units using nearpoints(), then iterates through each found point to accumulate its color contribution weighted by distance.

### Initialize nearpoints color loop

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;
```

Declares variables for position, color, point array, and distance, then uses nearpoints() to find all points within 40 units of the current point's position.

### Point Cloud Color and Distance

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(0, @P, 40);
d = 0;

// ...
```

This snippet retrieves nearby points using nearpoints, then iterates through each near point to read its color and position from the first input.

### Reading Attributes from Nearby Points

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Iterates through nearby points within a radius of 40 units, reading their position and color attributes into local variables, and calculating the distance between the current point and each nearby ....

### Weighted color blending from nearby points

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Accumulates weighted color contributions from nearby points, where each neighbor's color influence is determined by distance from the current point.

### Color Blending with Distance Falloff

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Accumulates color values from nearby points using distance-weighted blending, where each neighboring point's color contribution is scaled by a falloff based on its distance from the current point.

### Color Blending with Nearpoints

```vex
vector pos, col;
int pts[];
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

foreach(int pt; pts){
// ...
```

This snippet finds all points within a radius and blends their colors into the current point based on distance-weighted falloff.

### Color Blending with Nearpoints

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set colour to black to start with

// ...
```

This code blends colors from nearby points by finding all points within a radius using nearpoints, then iterating through each neighbor to accumulate its color contribution weighted by distance.

### Color blending with nearpoints

```vex
vector pos, col;
int pt[];
int n;
float d;

pt = nearpoints(0, @P, ch("radius"));
@Cd = 0;

// ...
```

This code blends colors from nearby points by iterating through all points found by nearpoints() and accumulating their colors weighted by distance.

### Multi-Point Color Blending Loop

```vex
vector pos, col;
int pts[];
int pt;
float d;

d = chf("radius");
pts = nearpoints(1, @P, 40);
@Cd = 0;
// ...
```

This code blends colors from multiple nearby points by finding all points within a radius, then accumulating their color contributions based on distance-weighted falloff.

### Color Blending with Foreach Loop

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, chf('r'));
@Cd = 0;

// ...
```

Iterates through all nearby points within a radius and blends their colors together based on distance-weighted contributions.

### Smooth color blending with nearpoints

```vex
vector pos, col;
int pts[];
float d;

pts = nearpoints(1, @P, 40);
pts = pts[1:];

foreach(int pt; pts) {
// ...
```

This code creates smooth color blending across geometry by finding nearby points within a radius, calculating distance-weighted color contributions from each neighbor, and accumulating them into th....

### Point Cloud Color Blending

```vex
foreach(i, element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;
// ...
```

Demonstrates smooth color blending across scattered points using nearpoints() to find neighbors within a radius, then accumulating their colors weighted by distance.

### Color Blending with Foreach and Nearpoints

```vex
foreach(element, array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;
// ...
```

This demonstrates smooth color blending by finding nearby points within a radius and accumulating their color contributions weighted by distance.

### Point Cloud Color Transfer Performance

```vex
vector pos, col;
int pts[];
int pt;
float d;

v@P = chv("points", @P, 0);
@Cd = 0;
i@num = 0;
// ...
```

Demonstrates VEX performance running point cloud color transfer calculations massively in parallel across 22,000 points.

### Foreach Loop Point Cloud Color Averaging

```vex
foreach(element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;
// ...
```

This code demonstrates using a foreach loop to iterate over nearby points found by nearpoints(), calculating distance-weighted color contributions from each neighbor.

### Color blending with nearpoints

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
d = 0;

// ...
```

Iterates through nearby points using nearpoints and accumulates their color contributions to the current point's color.

### Point Cloud Color Blending

```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@d = 0;

// ...
```

Accumulates weighted color values from nearby points using a point cloud search with nearpoints().

### Point Cloud Color Blending and Wave Animation

```vex
vector pos, col;
int pts[];
int pt;
float d;
@Cd = 0;

foreach (int ptc; pts) {
    pos = point(1, "P", pt);
// ...
```

Demonstrates point cloud-based color blending where each point accumulates weighted color contributions from nearby points based on distance falloff, then extends the technique to create wave anima....

### Near Point Wave Deformation

```vex
vector pos;
int pts[];
int pt;
float a, d, f, t;

pts = nearpoints(1, @P, 40);  // search within 40 units

foreach(pt; pts) {
// ...
```

Creates a wave deformation on points based on their proximity to nearby points within a search radius.

### Point Cloud Color Blending with Wave

```vex
vector pos;
int pts[];
int pt;
float d, s, t;

pts = nearpoints(1, @P, ch('radius'), 10);

foreach(pt; pts) {
// ...
```

Demonstrates combining point cloud color blending with wave deformation.

### Distance Calculation with Near Points

```vex
vector pos;
int pts[];
int pt;
float d, a, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
// ...
```

This snippet finds all points within a radius of 40 units from the current point using nearpoints(), then iterates through each found point to retrieve its position and calculate the distance from ....

### Distance-Based Fit with Near Points

```vex
vector pos;
int pts[];
int pt;
float d, s, f;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts) {
// ...
```

Finds nearby points within 40 units and calculates the distance from the current point to each neighbor.

### Distance-based Falloff with Fit

```vex
vector pos;
int pts[];
int pt;
float d, a, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
// ...
```

Calculates distance-based falloff by finding nearby points within a radius, computing the distance from the current point to each neighbor, and remapping that distance with fit() to create an inver....

### Time-based wave animation setup

```vex
vector pos;
int pts[];
int pt;
float u, s, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
// ...
```

Sets up time-based animation parameters for wave propagation by querying nearby points within a radius, calculating distance-based falloff using fit01 (inverted from 1 to 0), clamping the result, a....

### Distance-based time offset with nearpoints

```vex
t = @Time * ch('speed');

vector pos;
int pts[];
int pt;
float u, d, f, t;

pts = nearpoints(1, @P, 40);
// ...
```

Sets up a proximity-based time offset system by finding nearby points within a radius, calculating distance-based falloff using fit (inverted from 0 to 1), clamping the result, and multiplying time....

### Time-based wave animation with randomness

```vex
vector pos;
int pts[];
int pt;
float d, s, f, t, e, a;

pts = nearpoints(1, @P, ch('radius'));

foreach(int pt; pts) {
// ...
```

Creates animated waves by accumulating sine-based displacement values from nearby points.

### Distance-Based Wave Ripples

```vex
vector pos;
int pts[];
int pt;
float d, f, t, a;

pts = nearpoints(0, @P, ch('radius'));

foreach(pt; pts) {
// ...
```

Creates distance-based wave ripples by finding nearby points, calculating a distance-based falloff, and applying sine wave displacement to the Y position.

### Ripple Effect with Nearby Points

```vex
vector pos;
int pts[];
int pt;
float d, d1, f, t, a;

pts = nearpoints(1, @P, 40);

foreach(pt; pts){
// ...
```

Creates a ripple effect by searching for nearby points within 40 units and applying a sine wave displacement to the Y position.

### Smooth Blending Ripples with Point Cloud

```vex
vector pos;
int pts[];
int pt;
float d, f, t, a;

pts = nearpoints(1, @P, ch('radius'));

foreach(pt; pts) {
// ...
```

Uses nearpoints() to find neighboring geometry within a channel-controlled radius, then applies distance-based falloff with fit() and clamp() to create smoothly blending sine wave ripples.

### Multiple Point Cloud Ripple Effect

```vex
pts = nearpoints(1, @P, 40); // search within 40 units

foreach(int pt; pts) {
    pos = point(1, 'P', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
// ...
```

Creates overlapping ripple effects from multiple nearby points by iterating through points found within a 40-unit radius.

### Foreach Loop Point Iteration Performance

```vex
vector pos1 = nearpoint(1, @P, 40);

foreach(int i; pts) {
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch("speed");
// ...
```

Demonstrates a foreach loop iterating over nearby points found by nearpoint(), applying distance-based sine wave displacement to each point's Y position.

### Grid Size Parameter Adjustment

```vex
int pts[] = nearpoints(1, @P, 40);

foreach(int pt; pts){
    vector pos = point(1, 'P', pt);
    float d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    float t = @Time * ch('speed');
// ...
```

Demonstrates how parameter values need to scale proportionally with geometry size.

### Grid Resolution and Parameter Scaling

```vex
pts = nearpoints(1, @P, ch('radius'));

foreach(pt; pts) {
    pos = point(1, 'P', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
// ...
```

Demonstrates how grid resolution affects parameter scaling in proximity-based animation.

### Neighborhood Wave with Parameter Tuning

```vex
int pts[];
int pt;
float u, d, f, t;
vector pos;
float a;

pts = nearpoints(1, @P, ch('radius'));

// ...
```

Creates localized wave effects by finding nearby points and applying sine-based displacement that falls off with distance.

### Wave ripples with nearpoints

```vex
int ptx;
int pts[];
float q, d, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    ptx = point(1, "P", pt);
// ...
```

Creates a wave ripple effect by finding nearby points within a radius and modulating their Y position based on distance-attenuated sine waves.

### For Loop Syntax Introduction

```vex
int pts = npoints(0);
int pt = fit01(rand(@ptnum), 0, pts);
float d = 0.4, f = 1;

pts = nearpoints(1, @P, d);

foreach(int pt; pts) {
    vector Pnr = point(1, "P", pt);
// ...
```

Demonstrates the transition from foreach loops to traditional for loops, showing how foreach syntax differs in structure.

### For Loop Syntax Introduction

```vex
// VEXpression
int pts[];
int pt;
float d, e, f, t;
vector pos, col, c, p;

pts = nearpoints(1, @P, 40);

// ...
```

Introduction to for loop syntax as a transition from foreach loops.

### For Loop Syntax and Nearpoints Color Blending

```vex
for (starting value; test; value increment) {

}

int i;

for (i=1; i<11; i+=1) {
    @a = i;
// ...
```

Demonstrates for loop syntax with three components: starting value, test condition, and increment.

### For Loops with Array Length

```vex
int i;
for(i=1; i<11; i++){
    @a = i;
}

vector pos, col;
int pt;
int i;
// ...
```

Demonstrates using for loops to iterate a fixed number of times and to iterate over arrays by checking array length with len().

### For loops with array length

```vex
int i;
for(i=1; i<11; i--) {
    @a -= i;
}

int i;
for(i=1; i<11; i--){
    @a -= i;
// ...
```

Demonstrates using len() to get array size for loop termination instead of foreach.

### For loops with nearpoints

```vex
int i;
for(i=1; i<11; i++)
    @a = i;

int i;

for (i=1; i<11; i++) {
    @a = i;
// ...
```

Demonstrates how to replace foreach loops with traditional for loops by manually iterating through array indices.

### For loops with nearpoints

```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(0, @P, 10);

@Cd = {0,0,0};
// ...
```

Demonstrates using a for loop to iterate through an array of nearby points returned by nearpoints().

### Color Accumulation by Distance

```vex
vector pos, col;
int pts[];
int f, pt;
float d;

pts = nearpoints(1, @P, 40);
float gcd = 0;

// ...
```

Accumulates weighted color values from nearby points based on their distance.

### Color Blending from Nearby Points

```vex
vector pos, col;
int pts[];
int f, pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Iterates through nearby points within a search radius, reading their positions and colors.

### Color Blending with For Loop

```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, ch('radius'));
@Cd = 0;

// ...
```

This snippet demonstrates using a for loop to iterate through nearby points found with nearpoints, accumulating weighted color contributions based on distance.

### Color blending with for loop

```vex
int npts[];
int pts[];
int i, pt;
float d;
vector pos, col;

pts = nearpoints(0, @P, ch('radius'));
@Cd = 0;
// ...
```

Uses a for loop to iterate through nearby points, accumulating their color contributions weighted by distance falloff.

### Color Blending with For Loop

```vex
vector pos = @P;
int pt[];
int i, pt;
float d;

pt[] = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Uses a for loop to iterate through nearby points found by nearpoints(), accumulating their colors into the current point's @Cd attribute with distance-based falloff.

### For Loop Iteration Mechanics

```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// ...
```

Demonstrates for loop iteration over an array of nearby points, clarifying that the loop counter iterates a number of times equal to the array length rather than directly iterating over array elements.

### Nearpoints Color Blending Loop

```vex
int vector_size[];
int pts[];
int i, pt;
float d;
vector pos, col;

pts = nearpoints(1, @P, 40);
@Cd = 0;
// ...
```

Finds nearby points within a radius of 40 units and accumulates their color contributions weighted by distance.

### For Loop Array Iteration Pattern

```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0;

// ...
```

Demonstrates using a traditional for loop to iterate through an array of nearby points, manually accessing each element by index.

### foreach vs for loop comparison

```vex
int pts[];
int pt;
float d;
vector pos, col;

// Using for loop
pts = nearpoints(1, @P, 40);
@Cd = 0;
// ...
```

Demonstrates the difference between for loops and foreach loops when iterating over arrays in VEX.

### For Loop vs Foreach Iteration

```vex
int pts[];
int i, pt;
float d;
vector pos, col;

pts = nearpoints(0, @P, 40);
@Cd = 0;

// ...
```

Demonstrates using a for loop to iterate through an array of nearby points, where each point's color is accumulated into the current point's color based on distance-weighted falloff.

### Multiply Blend Mode Color Mixing

```vex
int pts[];
int pt;
vector col, pos;
float d;

pts = nearpoints(1, @P, ch("radius"));

// treat this as ink on paper, so start with white paper
// ...
```

Demonstrates color blending using multiply mode (like Photoshop multiply) rather than additive blending.

### Multiply Color Blending with Near Points

```vex
vector col, pos;
float d;

pts = nearpoints(1, @P, ch("radius"));

// treat this as ink on paper, so start with white paper
@Cd = 1;

// ...
```

This creates a Photoshop-like multiply blend effect by starting with white paper (@Cd = 1) and multiplying colors from nearby points.

### Find Nearest Points Array

```vex
int pts[] = nearpoints(1, @P, chf("d"), 25);
```

Creates an integer array containing point numbers of the nearest points on the second input (geometry input 1) within a channel-controlled distance, limited to a maximum of 25 points.

### Averaging Point Positions for Smoothing

```vex
int pts[] = nearpoints(1, @P, ch('d'), ch('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

// ...
```

Uses nearpoints() to find nearby points within a specified distance and count, then averages their positions to smooth point movement across a surface.

### Point cloud averaging with nearpoints

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
```

This code finds nearby points on a surface using nearpoints(), then averages their positions to move the current point toward a smoothed location.

### Point Cloud Setup with pcopen

```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
// ...
```

This code demonstrates the difference between nearpoints and pcopen.

### Point Cloud Filtering

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int pti;
// vector pos = 0;

// foreach(pti; pts){
//     pos += point(1, 'P', pti);
// }

// ...
```

This demonstrates using point cloud functions as a more efficient alternative to nearpoints() for averaging positions.

### Point Cloud Normal Filtering

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
// vector pos = 0;
// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }
// @P = pos/len(pts);

int nvpc = pcopen(1, 'P', @P, ch('d'), chi('amt'));
// ...
```

Demonstrates using pcopen() to create a point cloud handle and pcfilter() to compute the average normal from nearby points on the second input geometry.

### Point Cloud Color Filtering

```vex
int pc = pcopen(0, 'P', @P, ch('dist'), chi('maxpoints'));
@Cd = pcfilter(pc, 'Cd');
```

Opens a point cloud handle containing nearby points within a specified distance, then uses pcfilter to compute an averaged color value from all points in that point cloud.

### Point Cloud Attribute Filtering

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int pt;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// ...
```

Demonstrates using pcopen() to create point cloud handles and pcfilter() to extract and average attributes from nearby points.

### Point Cloud Open and Filtering

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
// int pt;
// vector pos = 0;
//
// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }
//
// ...
```

Uses pcopen() to create point cloud handles from different inputs, then applies pcfilter() to average normal and color attributes from nearby points.

### Point Cloud Color Blur

```vex
// Commented out nearpoints approach:
// int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
// int pt1
// vector pos = 0;
// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }
// @P = pos/len(pts);
// ...
```

Demonstrates using pcopen and pcfilter to blur color attributes by averaging neighboring points in space.

### Point cloud color lookup

```vex
int pc = pcopen(0, 'Cd', @P, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
```

Opens a point cloud using the current point's color (@Cd) as the search criterion instead of position, then filters to get averaged position from nearby points with similar colors.

### Color-Based Point Cloud Filtering

```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpts"));
@Cd = pcfilter(pc, "Cd");

// Changed to:
int pc = pcopen(0, "P", @Cd, ch("dist"), chi("maxpts"));
@P = pcfilter(pc, "P");
```

Demonstrates switching point cloud lookup from position-based to color-based by using @Cd as the query attribute in pcopen.

### Point Cloud Normal Lookup

```vex
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpts"));
@N = pcfilter(pc, "P");
```

Creates a point cloud handle based on color similarity, then uses pcfilter to average the positions of nearby points (based on similar colors) and assigns the result to the normal attribute.

### Point Cloud Filtering by Normals

```vex
int pc = pcopen(0, 'P', @P, ch('dist'), chi('maxpoints'));
@N = pcfilter(pc, 'P');

int pc = pcopen(0, 'N', @N, ch('dist'), chi('maxpoints'));
@N = pcfilter(pc, 'P');
@Cd = @N;
```

Demonstrates using pcopen() to query point clouds based on normal similarity rather than position.

### Point Cloud Normal Averaging

```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("maxpt"));
@P = pcfilter(pc, "P");
@Cd = @N;
```

Uses pcopen to find nearby points and pcfilter to average their positions, effectively grouping points based on their proximity.

### Point Cloud Velocity Averaging

```vex
int pc = pcopen(1,"P",@P,10,30);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= {1,0,1};
avgp -= {0,1,0};
@v -= avgv-avgp;
```

Opens a point cloud with 30 points within radius 10, then filters to compute average velocity and position of neighbors.

### Point Cloud Velocity Influence in POPs

```vex
int pc = pcopen(0, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= [-1, 0, 1];
avgp = [-1, 0, 2, 1];
@v += avgv + avgp;
```

Uses point cloud queries in a POP context to find nearby points (within 10 units, up to 30 points) and averages their velocity and position vectors.

### Point Cloud Particle Interaction

```vex
int pc = pcopen(0,"P",@P,10,30);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= {1,0.1,1};
avgp -= {1,0.1,1};
@v += avgv-avgp;
```

Opens a point cloud on a second input geometry (grid) to find up to 30 nearest points within 10 units, then filters and averages their velocity and position attributes.

### Point Cloud Velocity Clumping

```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0.1, 1};
avgp *= {1, 0.1, 1};
@v += avgv - avgp;
```

Opens a point cloud on the first input searching for 30 nearby points within a radius of 10 units, then averages their velocity and position.

### Point Cloud Ambient Occlusion

```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), ch('maxpts'));
vector pos, pcg;
float dot, dist;

pcg = pcfilter(pc, 'P');
pcg = pcfilter(pc, 'P');

dot = dot(@N, pcg);
// ...
```

Creates pseudo ambient occlusion by opening a point cloud around each point, computing a blurred position using pcfilter, then comparing the surface normal to the blurred position direction using a....

### Fake AO Using Point Clouds

```vex
int pc = pcopen(0, "P", @P, chf('bias'), chi('maxlist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

// ...
```

Demonstrates creating fake ambient occlusion by using point cloud queries to compare the current point's normal against averaged normals of nearby points.

### getblurP

```vex
vector p0 = getblurP(0);
int handle = pcopen("pcloud.pc", p0, ...);
```

Signature: vector p0 = getblurP(0);
int handle = pcopen("pcloud.pc", p0, ...);

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates an arr....

### pcfilter

```vex
floatpcfilter(inthandle;stringchannel){floatsum,w,d;floatvalue,result=0;while(pciterate(handle)){pcimport(handle,"point.distance",d);pcimport(handle,channel,value);w=1-smooth(0,radius,d);sum+=w;result+=w*value;}result/=sum;returnresult;}
```

Signature: floatpcfilter(inthandle;stringchannel){floatsum,w,d;floatvalue,result=0;while(pciterate(handle)){pcimport(handle,"point.distance",d);pcimport(handle,channel,value);w=1-smooth(0,radius,d)....

### pcgenerate

```vex
vectorposition;intohandle,ghandle,rval;ghandle=pcgenerate(texturename,npoints);while(pcunshaded(ghandle,"P")){// Compute 'position'...rval=pcexport(ghandle,"P",position);}ohandle=pcopen(texturename,"P",P,maxdistance,maxpoints);while(pciterate(ohandle)){rval=pcimport(ohandle,"P",position);// Do something with 'position'...}pcclose(ohandle);pcclose(ghandle);
```

Signature: vectorposition;intohandle,ghandle,rval;ghandle=pcgenerate(texturename,npoints);while(pcunshaded(ghandle,"P")){// Compute 'position'...rval=pcexport(ghandle,"P",position);}ohandle=pcopen(....

### pcopen

```vex
inthandle=pcopen(texturename,"P",P,maxdistance,maxpoints);while(pcunshaded(handle,"irradiance")){pcimport(handle,"P",cloudP);pcimport(handle,"N",cloudN);ir=computeIrraciance(cloudP,cloudN);pcexport(handle,"irradiance",ir);}pcfilter(handle,radius,"irradiance",ir);
```

Signature: inthandle=pcopen(texturename,"P",P,maxdistance,maxpoints);while(pcunshaded(handle,"irradiance")){pcimport(handle,"P",cloudP);pcimport(handle,"N",cloudN);ir=computeIrraciance(cloudP,cloud....

### pcopenlod

```vex
inthandle=pcopenlod(texturename,"P",P,8,"measure","distance","threshold",2.0,"aggregate:P","mean","aggregate:value","sum");Cf=0;while(pciterate(handle)){pcimport(handle,"value",valueSum);Cf+=valueSum;}pcclose(handle);
```

Signature: inthandle=pcopenlod(texturename,"P",P,8,"measure","distance","threshold",2.0,"aggregate:P","mean","aggregate:value","sum");Cf=0;while(pciterate(handle)){pcimport(handle,"value",valueSum)....

### pcsampleleaf

```vex
// Open a point cloud and retrieve a single aggregate point representing the// entire cloudstringtexturename="points.pc";inthandle=pcopenlod(texturename,"P",P,8,"measure","solidangle","area","A","samples",1,"aggregate:A","sum","aggregate:P","mean");Cf=0;// This loop will iterate only oncewhile(pciterate(handle)){// Query A from the averaged pointfloatptarea;pcimport(handle,"A",ptarea);pcsampleleaf(handle,nrandom());// Query P from a sampled leaf pointvectorpos;pcimport(handle,"P",pos);if(trace(pos,P-pos,Time))Cf+=ptarea/length2(P-pos);}
```

Signature: // Open a point cloud and retrieve a single aggregate point representing the// entire cloudstringtexturename="points.pc";inthandle=pcopenlod(texturename,"P",P,8,"measure","solidangle","a....

### Pattern: Neighbor Averaging

```vex
// Smooth attribute by averaging neighbors
int pts[] = nearpoints(0, @P, ch("radius"));
vector sum = {0,0,0};
foreach(int pt; pts) {
    sum += point(0, "Cd", pt);
}
@Cd = sum / max(len(pts), 1);
```

// Smooth attribute by averaging neighbors
int pts[] = nearpoints(0, @P, ch("radius"));
vector sum = {0,0,0};
foreach(int pt; pts) {
    sum += point(0, "Cd", pt);
}
@Cd = sum / max(len(pts), 1);.

### Pattern: Attribute Transfer

```vex
// Transfer attribute from nearest point on input 1
int nearpt = nearpoints(1, @P, 1e9, 1)[0];
@Cd = point(1, "Cd", nearpt);
```

---.

## Advanced (13 examples)

### Blurring attributes with vex and point clouds â

```vex
int width = 50; // say the grid is 50 points wide
vector left = point(0,'Cd', @ptnum-1);
vector right = point(0,'Cd', @ptnum+1);
vector top = point(0,'Cd', @ptnum+50);
vector bottom = point(0,'Cd', @ptnum-50);
@Cd = left + right + top + bottom;
@Cd /= 4.0;
```

Download scene: Download file: pc_blur.hipnc

Another thing that I learned but didn't really understand, forgot, learned again, forgot, then feared for a while, and now finally have an understandin....

### Pointclouds â

```vex
int pts[] = nearpoints(1,@P,ch('d'),25);
 int pt;
 vector pos;
 foreach (pt; pts) {
   pos = point(1,'P',pt);
   addpoint(0,pos);
 }
```

In a similar way that minpos is the 'simple' and primuv + xyzdist are the 'versatile' versions of the same thing, it helps to think of nearpoint and nearpoints as the simple version of the more adv....

### Average position â

```vex
@P = minpos(1, @P);
```

A handy feature of point clouds is the ability to filter or average values.

### Blurred colour â

```vex
int pc = pcopen(0,'P',@P, ch('dist'), chi('maxpoints'));
 @Cd = pcfilter(pc, 'Cd');
```

The trick I used to do with this a lot was to blur colour.

### Use lookups other than P â

```vex
int pc = pcopen(0,'Cd',@Cd, ch('dist'), chi('maxpoints'));
 @P = pcfilter(pc, 'P');
```

Going off the deep end here of pointcloud tricks you may never use, but now you can stick it in the back of your mind for one day...

Just to re-iterate what we've been doing here; each time we run....

### pop sim and pointclouds â

```vex
int pc = pcopen(1,'P',@P,10,30);
 vector avgv = pcfilter(pc,'v');
 vector avgp = pcfilter(pc,'P');
 avgv *= {1,0.1,1};
 avgp *= {1,0.1,1};
 @v += avgv-avgp;
```

Download scene: pc_popforce.hipnc

Slightly less silly example, one I half-remembered from an odforce post that I didn't understand when I first saw it, sort of understand now.

I have a wobbly tub....

### Ambient Occlusion â

```vex
int pc = pcopen(0, "P", @P+@N*ch('bias'), ch('maxdist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

// ...
```

Download scene: pbao.hiplc

Not quite AO, but it'll do.

### Point Cloud Creation with pcopen

```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int pt;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// ...
```

Demonstrates the creation of a point cloud handle using pcopen as an alternative to nearpoints-based averaging.

### Point Cloud Velocity Averaging

```vex
int pc = pcopen(0,"P",@P,10,100);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= [1,0.1,1];
avgp *= [1,0.1,1];
@v += avgv-avgp;
```

This snippet creates particle clumping behavior by opening a point cloud around each point and averaging the velocities and positions of nearby points.

### Fake Ambient Occlusion Point Cloud

```vex
int pc = pcopen(0, "P", @P, ch("bias"), chi("maxdist"), chi("numpoints"));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

// ...
```

This technique creates a fake ambient occlusion effect by opening a point cloud and using pcfilter to average nearby point positions and normals.

### Velocity Smoothing via Point Cloud

```vex
int pc = pcopen(1, @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= (1, 0, 1);
avgp *= (1, 0, 1);
@v += avgv - avgp;
```

Uses point cloud queries on a second input geometry to calculate averaged velocity and position values from nearby points, then modifies particle velocity by the difference between these smoothed v....

### Velocity Smoothing via Point Cloud

```vex
int pc = pcopen(1, "*", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= (1, 0, 1);
avgp *= (1, 0, 1);
@v += avgv - avgp;
```

This code blurs velocity by sampling nearby points from a cylinder geometry using a point cloud, filtering both velocity and position, masking out the Y component, and adding the difference to crea....

### Pattern: Point Cloud Relaxation

```vex
// Push points apart
int handle = pcopen(0, "P", @P, ch("radius"), chi("maxpts"));
vector avg = pcfilter(handle, "P");
pcclose(handle);
@P = lerp(@P, avg, ch("blend"));
```

// Push points apart
int handle = pcopen(0, "P", @P, ch("radius"), chi("maxpts"));
vector avg = pcfilter(handle, "P");
pcclose(handle);
@P = lerp(@P, avg, ch("blend"));.

## Expert (1 examples)

### Solver and wrangle for branching structures â

```vex
if (@active ==0) {
    float maxdist = ch('maxdist');
    int maxpoints = 5;
    int pts[] = nearpoints(0,@P, maxdist, maxpoints);
    int pt ;

    foreach  (pt;pts) {
        if (point(0,'active',pt)==1) {
// ...
```

Download scene: Download file: vex_brancher.hipnc

I watched this great video by Simon Holmedal about his work for Nike, lots of interesting branching structures, organic growth, fractals, really i....
