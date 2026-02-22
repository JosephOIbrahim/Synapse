# Joy of VEX: Nearpoints & Proximity

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
vector pos = minpos(1, @P);  // Finding Closest Point Position
int pts[] = nearpoints(1, @P, chf("d"), 25);  // Find Nearest Points Array
int pt = nearpoint(1, @P);  // Transfer Color from Nearest Point
```

## Proximity Operations

### Distance-based coloring using minpos [[Ep3, 33:26](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2006s)]
```vex
vector pos = minpos(1, @P);
float d = distance(pos, @P);
f@r = ch('scale');
@Cd = d;
@Cd.y = sin(d);
```
For each point on a grid, this code finds the closest position on another geometry (input 1) and stores it in a variable. It then calculates the distance between the current point and that closest position, uses that distance to drive the color, and applies a sine wave to the green channel to create a wave pattern based on proximity.

### Finding Closest Point Position [[Ep3, 35:52](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2152s)]
```vex
vector pos = minpos(1, @P);
```
The minpos() function finds the position of the closest point on the geometry in input 1 to the current point's position (@P). This returns a vector representing the 3D coordinates of that nearest surface point, which can be used to analyze proximity relationships or create deformation effects based on closest point mapping.

## Nearpoints Lookup

### Transfer Color from Nearest Point [[Ep3, 38:52](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2332s)]
```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
```
This code finds the nearest point from the second input geometry (input 1) to the current point's position, stores that point number in a variable, then reads and applies that nearest point's color attribute to the current point. This is a common technique for transferring attributes between geometries based on spatial proximity.

### Nearpoint attribute transfer and distance [[Ep3, 46:54](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2814s)]
```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = d;
```
This snippet finds the nearest point on the second input, transfers its color attribute to the current point, retrieves that neighbor's position, calculates the distance between the two points, and then sets the Y position to that distance value. This demonstrates basic proximity queries and attribute transfer combined with distance-based geometric manipulation.

### Distance-based Height Transfer [[Ep3, 49:10](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2950s)]
```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
vector pos = point(1, 'P', pt);
float d = distance(@P, pos);
@P.y = d;
```
This code finds the nearest point from the second input and calculates the distance between the current point and that nearest point, then uses that distance value to set the Y position of the current point. It also transfers the color attribute from the nearest point, creating a height field based on proximity to the reference geometry.

### Distance-Based Color Transfer [[Ep3, 50:10](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3010s)]
```vex
int pt = nearpoint(0, @P);
v@Cd = point(0, 'Cd', pt);
vector pos = point(0, 'P', pt);
float d = distance(@P, pos);
v@Cd *= d;
```
This code finds the nearest point from the first input, reads its color and position, then calculates the distance between the current point and that nearest point. The color is then scaled by this distance value, creating a falloff effect where colors become brighter or dimmer based on proximity to the source geometry.

### Sampling Input Geometry with Nearpoint [Needs Review] [[Ep3, 57:58](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3478s)]
```vex
vector p1 = @opinput1_P;
vector cd1 = @opinput1_Cd;

@P = p1;
@Cd = cd1;

int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector clr = point(1, "Cd", pt);
float d = distance(@P, pos);
d += rand(pt);
d = 1 - d;
d *= 1;
@P.y = chramp("pulse", d) * ch("amp");
```
This code samples position and color from a second input geometry by finding the nearest point, then uses the distance from that nearest point (with randomization) to drive a vertical displacement via a ramp and amplitude parameter. The pattern creates an organic, wave-like deformation based on proximity to the second input's geometry.

### For Loop Array Iteration Pattern [[Ep5, 101:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6070s)]
```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0;

for(i=0; i<len(pts); i++) {
    pt = pts[i];
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = length(pos - @P);
    d = fit(d, 0, chf("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd = col * d;
}
```
Demonstrates using a traditional for loop to iterate through an array of nearby points, manually accessing each element by index. This pattern extracts position and color data from neighboring points within 40 units, calculates distance-based falloff, and accumulates weighted color contributions to @Cd. While functional, this approach is noted as less clean than a foreach loop since it manually implements iteration behavior that foreach provides natively.

### Voronoi pattern with nearpoint [[Ep5, 37:48](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2268s)]
```vex
float a = 4.21;
int s = set(a, 3, 3);

f[]@array = array(a, 3, 3, 4, 5);

int pt = nearpoint(1, @P);
vector col = point(1, 'Cd', pt);
@Cd = col;

int pt = nearpoint(1, @P);
vector pos = point(1, 'P', pt);
vector dir = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
Demonstrates creating a Voronoi-style color pattern by finding the nearest point on input 1 using nearpoint(), reading its color attribute, computing the distance to it, and using fit() and clamp() to create a gradient falloff controlled by a channel parameter. The final color is the source color multiplied by the distance falloff.

### Reading Color from Nearest Point [[Ep5, 40:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2430s)]
```vex
int pt = nearpoint(1, v@P);
vector col = point(1, "Cd", pt);

// Extended example:
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
Uses nearpoint() to find the closest point on input 1 to the current point's position, then reads that point's color attribute using point(). The extended example shows how to use this pattern to blend colors based on distance, fetching both position and color from the nearest point, calculating distance, and applying a falloff.

### Voronoi Pattern with Nearest Point Lookup [[Ep5, 41:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2476s)]
```vex
float myarray[] = array(x,y,x,y,5); // ok
f[]@myarray = array(x,y,x,y,5); // ok

int pt = nearpoint(1,@P);
vector col = point(1,"Cd",pt);
@Cd = col;

int pt = nearpoint(1,@P);
vector pos = point(1,"P",pt);
vector col = point(1,"Cd",pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
Uses nearpoint() to find the closest point from input 1, then reads that point's color attribute with point(). The code creates a Voronoi pattern by assigning each point on a grid the color of its nearest scattered point, then extends this by calculating distance falloff using fit() and clamp() to create smooth color transitions between regions.

### Distance-based Color Transfer [[Ep5, 42:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2572s)]
```vex
int pt = nearpoint(1, @P);
vector pos = point(1, 'P', pt);
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
Finds the nearest point on a second input geometry, retrieves its position and color, then calculates the distance from the current point to that nearest point. The distance is remapped using fit() and clamp() to create a falloff value, which is multiplied by the retrieved color to create a distance-based color blend effect.

### Distance-based color transfer with fit [Needs Review] [[Ep5, 43:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2616s)]
```vex
int pt = nearpoint(1, v@P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(pos, v@P);
v@Cd = fit(d, 0, chf("radius"), col, v@Cd);
```
Finds the nearest point on input 1, calculates the distance to it, then uses fit() to blend between the nearest point's color and the current point's color based on distance within a controllable radius. This creates a distance-based color transfer effect where colors from the second input blend into the geometry based on proximity.

### Distance-based color transfer with falloff [[Ep5, 44:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2670s)]
```vex
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
This code transfers color from the nearest point on the second input while applying a distance-based falloff. The distance is remapped using fit() to invert the falloff (close points get value 1, far points get 0), clamped to valid range, and then multiplied with the transferred color to create a smooth gradient effect controlled by a radius channel parameter.

### Distance-Based Color Blending with Nearest Point [Needs Review] [[Ep5, 45:24](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2724s)]
```vex
int pt = nearpoints(1, @P, 1)[0];
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
Finds the nearest point on input 1, retrieves its position and color, then calculates distance-based color blending using a channel-controlled radius. The distance is fitted and clamped to create a falloff effect, multiplying the nearest point's color by the falloff value. However, this approach only considers a single nearest point and cannot blend across Voronoi cell boundaries.

### Expanding nearpoints search radius [[Ep5, 45:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2742s)]
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
Modifies the nearpoints function to search within a specified distance (10 units) rather than finding just the closest point, allowing for blending across cell boundaries. This enables the color transfer to extend beyond the immediate nearest point and blend multiple point values for smoother transitions at Voronoi cell edges.

### Multiple Nearest Points Color Blending [[Ep5, 48:00](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2880s)]
```vex
int pts[] = nearpoints(1, @P, ch('radius'));
vector pos, col;
int pt;
float d;

@Cd = 0; // set colour to black to start with

// first point
pt = pts[0];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;

// second point
pt = pts[1];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Extends the nearest point color blending technique to process multiple points from the nearpoints array by extracting individual points using bracket indexing (pts[0], pts[1]). The code initializes @Cd to zero, then additively blends colors from the two closest points, each weighted by their distance-based falloff, allowing for multi-point color influence.

### Refactoring Point Cloud Color Blending [[Ep5, 48:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2896s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// first point
pt = pts[0];
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;

// second point
pt = pts[1];
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Demonstrates proper variable declaration and reuse when processing multiple nearby points from a point cloud query. Variables are declared once at the top (pos, col, pt, d) and reused for both the first and second closest points, with color contributions accumulated using the += operator to blend colors from multiple sources based on distance.

### Multi-Point Color Blending [[Ep5, 48:20](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2900s)]
```vex
int pt = pts[0];
vector pos = point(1, 'P', pt);
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// first point
pt = pts[0];
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;

// second point
pt = pts[1];
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Demonstrates extending single-point color blending to multiple nearby points by duplicating the distance-based color blending logic for both the first and second nearest points. The code initializes @Cd to zero, then additively blends colors from multiple nearby points, though it shows repetitive code that needs refactoring with proper variable declarations.

### Multiple Nearest Point Color Blending [[Ep5, 51:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3090s)]
```vex
int pts[] = nearpoints(1, @P, 40);
int pt = pts[0];
vector col = point(1, 'Cd', pt);
float d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;

vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// first point
pt = pts[0];
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;

// second point
pt = pts[1];
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Demonstrates extending single nearest point color sampling to multiple points by duplicating the calculation block and accessing pts[1] for the second nearest point. The additive assignment (@Cd +=) allows colors from multiple nearby points to blend together, creating smooth transitions that extend beyond the initial Voronoi pattern boundaries.

### Blending Two Nearest Point Colors [[Ep5, 51:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3096s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1,@P,40); // search within 40 units
@Cd = 0; // set colour to black to start with

// first point
pt = pts[0];
pos = point(1,'P',pt);
col = point(1,'Cd',pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d,0,1);
@Cd += col*d;

// second point
pt = pts[1];
pos = point(1,'P',pt);
col = point(1,'Cd',pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d,0,1);
@Cd += col*d;
```
Extends the single nearest point color lookup by duplicating the code block to process both the first and second nearest points from the nearpoints array. By accumulating the distance-weighted color contributions from both neighbors, this creates a blended color effect that begins to go beyond simple Voronoi patterns, though only using two points means the blending is still limited.

### Blending Multiple Nearest Point Colors [[Ep5, 51:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3098s)]
```vex
int pt[];
float d;
vector pos, col;

pts = nearpoints(1, @P, 40);
@Cd = 0;

// first point
pt = pts[0];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;

// second point
pt = pts[1];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
This code extends the nearest point color blending by manually processing two separate points from the nearpoints array. Each point's color contribution is calculated based on distance, fit to a parameter-controlled radius, and clamped before being accumulated into the final color attribute, demonstrating the manual accumulation approach before converting to a foreach loop.

### Nearpoints Array Manual Access Pattern [Needs Review] [[Ep5, 52:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3152s)]
```vex
int pts[];
pts = nearpoints(0, @P, 20);
i[]@a = pts;

// First point processing
int pt = pts[0];
vector pos = point(0, "P", pt);
vector d = normalize(pos);
d = clamp(pos);
float c = fit(d.x, d.y, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd += c * d;

// Second point processing
int pt = pts[1];
vector pos = point(0, "P", pt);
vector d = normalize(pos);
d = clamp(pos);
float c = fit(d.x, d.y, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd += c * d;
```
This code demonstrates manually accessing and processing individual points from a nearpoints array by copying and pasting the same operations for pts[0] and pts[1]. This illustrates the repetitive nature of the code before introducing loops, showing how the same processing logic is applied to each nearby point to accumulate color values. The example is intentionally verbose to motivate the need for looping constructs.

## Proximity Operations

### Nearpoints Array Manual Processing [Needs Review] [[Ep5, 52:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3156s)]
```vex
int pts[];
int pt;
float d;
vector pos;
vector col;

d = 0;
pt = pts[0];
pos = point(0, 'P', pt);
d = distance(pos, @P);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;

pt = pts[1];
pos = point(1, 'P', pt);
d = distance(pos, @P);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Demonstrates manually processing each point in a nearpoints array by explicitly accessing pts[0] and pts[1] individually, calculating distance, fitting values, and accumulating color contributions. This repetitive approach illustrates why looping is necessary when dealing with multiple nearby points, serving as a stepping stone to understanding iteration patterns.

## Nearpoints Lookup

### Debugging with temporary attributes [Needs Review] [[Ep5, 53:14](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3194s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);

//first point
pt = pts[0];
col = point(1, "Cd", pt);
vector s = relbbox(0, @P, pos);
d = clamp(length(s.yz), 0, 1);
d = clamp(d, 0, 1);
@Cd += col * d;

//second point
pt = pts[1];
col = point(1, "Cd", pt);
s = relbbox(0, @P, pos);
d = clamp(length(s.yz), 0, 1);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Demonstrates processing multiple nearby points using nearpoints() to find neighbors, then accessing individual points by array index to sample their colors and blend them based on distance. The code introduces the debugging technique of storing intermediate results in temporary attributes for inspection in the geometry spreadsheet, showing how to work with point arrays without loops (preparing for loop introduction).

## Proximity Operations

### Nearest Points Array Assignment [Needs Review] [[Ep5, 54:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3256s)]
```vex
v@p = v@opinput1_P(0, v@P, 0);
int pts[];
int pt;
vector pos;
vector col;
float d;

// first point
pt = pts[0];
col = point(1, 'Cd', pt);
pos = point(1, 'P', pt);
d = distance(v@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
v@Cd += col * d;

// second point
pt = pts[1];
col = point(1, 'Cd', pt);
pos = point(1, 'P', pt);
d = distance(v@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
v@Cd += col * d;
```
Demonstrates storing nearpoints results in an array and accessing individual elements by index to read their attributes. The code iterates through the first two nearest points, retrieves their color and position, calculates distance-based falloff, and additively blends their colors onto the current point based on proximity within a specified radius.

### Point Cloud Weighted Color Accumulation [Needs Review] [[Ep5, 54:22](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3262s)]
```vex
//first point
int pt0 = pts[0];
vector pos = point(0, "P", pt0);
vector col = point(0, "Cd", pt0);
float d = rint(pos, pcol);
d = clamp(d, 0, s);
gcd += col * d;

//second point
int pt = pts[1];
pos = point(0, "P", pt);
col = point(0, "Cd", pt);
d = rint(pos, pcol);
d = clamp(d, 0, s);
gcd += col * d;
```
This code reads position and color attributes from the first two points in a nearby points array, calculates a distance-based weight using rint(), clamps the weight to a valid range, and accumulates the weighted colors into a gcd variable. This demonstrates building up a weighted average by processing individual neighboring points sequentially.

## Nearpoints Lookup

### Nearpoints Multiple Point Queries [[Ep5, 55:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3338s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, v@P, 40);
// if(len(pts))

//first point
pt = pts[0];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(pos, v@P);
d = fit01(d, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
v@Cd *= d;

//second point
pt = pts[1];
pos = point(1, "P", pt);
col = point(1, "Cd", pt);
d = distance(pos, v@P);
d = fit01(d, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
v@Cd *= d;
```
Demonstrates querying multiple near points by accessing individual array elements from nearpoints() result. The code processes the first two points from the array separately, computing distance-based color falloff for each point using the same pattern of accessing position, color, computing distance, and applying clamped fit01 result to the current point's color.

### Setting up nearpoints variables [Needs Review] [[Ep5, 60:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3630s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch("radius"), ch("num"));
```
Declares variables needed for nearpoints query including an integer array for point numbers, individual point integer, vector for position, and floats for distance and weight. Uses nearpoints to find points from second input geometry within a channel-referenced radius, returning up to a channel-specified number of points.

### Near Points Position Query [Needs Review] [[Ep5, 61:58](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3718s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d / ch('freq');
w = @ptnum * ch('speed');
w = sin(w);
w = ch('amp') * w;
w = fit(w, 0, ch('radius'), 1, 0);
@P.y += w;
```
Retrieves the nearest points from the second input using nearpoints(), then extracts the first point from the array and queries its position using point(). Calculates the distance between the current point and the near point, then uses that distance to drive a sine wave displacement on the y-axis with frequency, speed, and amplitude controls.

## Proximity Operations

### Voronoi Cell Ripple Blending [[Ep5, 70:26](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4226s)]
```vex
int pt = pt3[];
vector pos = point(1, 'P', pt);
float d = distance(@P, pos);
float w = d * ch('freq');
w = @Time * ch('speed');
w = sin(w);
w = ch('amp') * w;
w = fit(w, -1, 1, ch('radius'), 1, 0);
@P.y += w;
```
Creates ripple effects across Voronoi cell boundaries by sampling neighboring cell points and applying distance-based sine waves. The fit function controls how ripples blend across cell boundaries, allowing waves to propagate beyond individual cells. This demonstrates blending multiple point influences to create continuous ripple patterns.

### Multiple Point Ripple Blending [[Ep5, 70:28](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4228s)]
```vex
int pt = pts[i];
vector pos = point(0, 'P', pt);
float d = distance(@P, pos);
float w = d * ch('freq');
w += @Time * ch('speed');
float s = sin(w);
w = s * ch('amp');
w *= fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Creates blended ripple effects from multiple source points by calculating distance-based sine waves that fade out based on a radius parameter. Each point in the pts array creates a ripple that blends smoothly with neighboring ripples, though some boundary artifacts may appear at cell edges. This demonstrates how multiple point sources can create overlapping wave patterns that combine naturally.

## Nearpoints Lookup

### Color Blending with Foreach Loop [[Ep5, 75:04](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4504s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set colour to black to start with

foreach(pts; pt) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, radius(), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Uses a foreach loop to iterate through nearby points within a 40-unit radius, sampling their positions and colors. For each neighbor, calculates distance-based falloff using fit and clamp, then accumulates weighted color contributions to the current point's color attribute, creating a distance-weighted color blend effect.

### Color Blending from Nearby Points [[Ep5, 75:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4506s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set point to black to start with

foreach(pt; pts) {
    pos = point(1, 'P', pt);
    col = point(1, 'Cd', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Accumulates color from nearby points within a search radius, weighting each neighbor's color contribution by its distance. Uses foreach to iterate through points found by nearpoints, then blends their colors using distance-based falloff controlled by a channel reference. The final color is the weighted sum of all nearby point colors.

### Reading Attributes from Nearby Points [[Ep5, 77:48](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4668s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

foreach(int pt; pts){
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
}
```
Iterates through nearby points within a radius of 40 units, reading their position and color attributes into local variables, and calculating the distance between the current point and each nearby point. This demonstrates nested iteration where the outer loop processes each point in the geometry while the inner foreach loop processes each nearby point found by nearpoints().

### Color Blending with Nearpoints [Needs Review] [[Ep5, 80:04](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4804s)]
```vex
vector pos, col;
int pts[];
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

foreach(int pt; pts){
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = fit(distance(@P, pos), 0, 40, chramp("r"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
This snippet finds all points within a radius and blends their colors into the current point based on distance-weighted falloff. A ramp parameter controls the falloff curve, and each nearby point's color is accumulated additively after being multiplied by the falloff weight. The result creates smooth color transitions without visible lines between point influences.

### Color Blending with Nearpoints [[Ep5, 80:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4808s)]
```vex
vector pos, col;
int pts[];
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

foreach(int pt; pts){
    pos = point(1, 'P', pt);
    col = point(1, 'Cd', pt);
    d = distance(@P, pos);
    d = fit(d, 0, chv('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Blends colors from multiple nearby points by finding all points within a radius, calculating distance-based weights using fit and clamp, and accumulating weighted color contributions. This creates smooth color gradients without visible lines by considering all points in the search radius rather than just the closest one.

### Color Blending with Nearpoints [[Ep5, 80:24](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4824s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set colour to black to start with

foreach(pt; pts) {
    pos = point(1, 'P', pt);
    col = point(1, 'Cd', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
This code blends colors from nearby points by finding all points within a radius using nearpoints, then iterating through each neighbor to accumulate its color contribution weighted by distance. The distance is remapped using fit() and clamped, creating smooth color gradients without hard edges as it blends across all neighboring points.

### Color blending with nearpoints [Needs Review] [[Ep5, 80:28](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4828s)]
```vex
vector pos, col;
int pt[];
int n;
float d;

pt = nearpoints(0, @P, ch("radius"));
@Cd = 0;

foreach (int pci; pt) {
    pos = point(0, "P", pci);
    col = point(0, "Cd", pci);
    n = fit(pci, 0, len(pt), 0, 10);
    d = distance(@P, pos);
    d = fit(d, 0, chramp("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
This code blends colors from nearby points by iterating through all points found by nearpoints() and accumulating their colors weighted by distance. The distance-based falloff is controlled by a ramp parameter, allowing smooth color blending across multiple neighbors without harsh edges. This demonstrates efficient point cloud sampling running on thousands of points simultaneously.

### Multi-Point Color Blending Loop [Needs Review] [[Ep5, 80:46](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4846s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

d = chf("radius");
pts = nearpoints(1, @P, 40);
@Cd = 0;
for(int pt=0; pt<len(pts); pt++){
    pos = point(1, "P", pts[pt]);
    col = point(1, "Cd", pts[pt]);
    d = length(@P - pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
This code blends colors from multiple nearby points by finding all points within a radius, then accumulating their color contributions based on distance-weighted falloff. Instead of selecting a single closest point, it loops through all points in the nearpoints array, applying a fit/clamp operation to create smooth color gradients across up to 40 neighboring points without visible edges.

### Smooth color blending with nearpoints [[Ep5, 81:04](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4864s)]
```vex
vector pos, col;
int pts[];
float d;

pts = nearpoints(1, @P, 40);
pts = pts[1:];

foreach(int pt; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, chf("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
This code creates smooth color blending across geometry by finding nearby points within a radius, calculating distance-weighted color contributions from each neighbor, and accumulating them into the current point's color. The distance falloff is controlled by a user parameter and clamped to prevent overshooting, resulting in smooth gradient transitions without hard edges.

### Point Cloud Color Blending [[Ep5, 81:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4868s)]
```vex
foreach(i, element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1,@P,40); // search within 40 units
@Cd = 0; // set point to black to start with

foreach(pt; pts) {
    pos = point(1,'P',pt);
    col = point(1,'Cd',pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1,0);
    d = clamp(d,0,1);
    @Cd += col*d;
}
```
Demonstrates smooth color blending across scattered points using nearpoints() to find neighbors within a radius, then accumulating their colors weighted by distance. Each point searches for nearby points, retrieves their positions and colors, calculates distance-based falloff using fit() and clamp(), and additively blends the colors. This runs efficiently in parallel across 22,000+ points, creating seamless color transitions without visible edges.

### Color Blending with Foreach and Nearpoints [[Ep5, 81:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4870s)]
```vex
foreach(element, array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1,@P,40); // search within 40 units
@Cd = 0; // set colour to black to start with

foreach(pt; pts) {
    pos = point(1,"P",pt);
    col = point(1,"Cd",pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1,0);
    d = clamp(d,0,1);
    @Cd += col*d;
}
```
This demonstrates smooth color blending by finding nearby points within a radius and accumulating their color contributions weighted by distance. The foreach loop iterates through all points found by nearpoints, fitting and clamping the distance to create falloff, then additively blending each neighbor's color into the current point's color. This technique runs efficiently in parallel across 22,000+ points to create seamless color gradients without visible edges.

### Foreach Loop Color Averaging [[Ep5, 81:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4872s)]
```vex
foreach(element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0; // set colour to black to start with

foreach(pt; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Demonstrates foreach loop iteration over an array of nearby points found with nearpoints(). For each neighbor, the code retrieves its position and color, calculates distance-based falloff using fit() and clamp(), then accumulates weighted color contributions into @Cd. This runs in parallel across 22,000+ points, showcasing VEX's computational performance for point cloud operations.

### Foreach Loop Point Cloud Color Averaging [[Ep5, 81:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4876s)]
```vex
foreach(element; array) {
    // do things to element
}

vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1,@P,40); // search within 40 units
@Cd = 0; // set point to black to start with

foreach(pt; pts) {
    pos = point(1,"P",pt);
    col = point(1,"Cd",pt);
    d = distance(@P, pos);
    d = fit(d, 0, chf("radius"), 1,0);
    d = clamp(d,0,1);
    @Cd += col*d;
}
```
This code demonstrates using a foreach loop to iterate over nearby points found by nearpoints(), calculating distance-weighted color contributions from each neighbor. For each neighboring point, it reads position and color, calculates distance, remaps it with fit() and clamp(), then accumulates the weighted color into the current point's @Cd attribute, creating smooth color blending based on proximity.

### Point Cloud Color Blending [Needs Review] [[Ep5, 81:24](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4884s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@d = 0;

foreach(int pt; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @d += col * d;
}
```
Accumulates weighted color values from nearby points using a point cloud search with nearpoints(). For each nearby point, retrieves its position and color, calculates distance-based weight using fit() and clamp(), then adds the weighted color contribution to the current point's @d attribute. This creates smooth color blending across geometry based on proximity to scattered color sources.

### Point Cloud Color Blending and Wave Animation [Needs Review] [[Ep5, 81:26](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4886s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;
@Cd = 0;

foreach (int ptc; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}

vector pos;
int pts[];
int pt;
float d, r, t;

pts = nearpoints(1, @P, 40);  // search within 40 units

foreach(pt; pts) {
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    t = rand(pt);
    r = d * ch("amp");
    @P.y = sin(t) * r;
}
```
Demonstrates point cloud-based color blending where each point accumulates weighted color contributions from nearby points based on distance falloff, then extends the technique to create wave animation by modulating Y position with sine waves. The code uses nearpoints to find neighbors within a radius, calculates distance-based weights with fit and clamp, and combines multiple influences to create smooth interpolated results across 22,000 points running in parallel.

### Nearby Points Wave Deformation [Needs Review] [[Ep5, 81:28](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4888s)]
```vex
vector pos;
int pts[];
int pt;
float d, d_f, t, f, g;

pts = nearpoints(1, @P, 40); // search within 40 units

foreach(pt; pts) {
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch("speed");
    d += sin(pt);
    f = d * ch("freq");
    g = d * ch("amp");
    @P.y += sin(t * f) * g;
}
```
Uses nearpoints to find surrounding points within 40 units, then applies a wave deformation to the Y position based on distance falloff and time. Each point's influence is calculated using distance fitting and clamping, with sine waves controlled by frequency and amplitude parameters to create smooth animated ripples across the geometry.

### Point Cloud Color Blending with Wave [Needs Review] [[Ep5, 81:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4912s)]
```vex
vector pos;
int pts[];
int pt;
float d, s, t;

pts = nearpoints(1, @P, ch('radius'), 10);

foreach(pt; pts) {
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
    s = sin(d * t);
    float a = d * ch('amp');
    a = d * ch('freq');
    @P.y += sin(d * t) * a;
}

vector pos, col;
int pts[];
int pt;
float d;

d = 0;
pts = nearpoints(1, @P, 40, 10);
@Cd = 0;

foreach(pt; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Demonstrates combining point cloud color blending with wave deformation. The first block applies a sine wave displacement to Y position based on neighbor distances, while the second block blends colors from nearby points using distance-weighted accumulation. Both use nearpoints() to find neighbors within a search radius and apply distance-based falloff with fit() and clamp().

### Distance Calculation with Near Points [[Ep5, 82:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4972s)]
```vex
vector pos;
int pts[];
int pt;
float d, a, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    pos = point(1, "P", pt);
    d = distance(@P, pos);
}
```
This snippet finds all points within a radius of 40 units from the current point using nearpoints(), then iterates through each found point to retrieve its position and calculate the distance from the current point. The code sets up the framework for distance-based operations on neighboring points, though the distance calculation is being rewritten.

### Distance-based Falloff with Fit [Needs Review] [[Ep5, 83:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4986s)]
```vex
vector pos;
int pts[];
int pt;
float d, a, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    t = @time * ch("speed");
    t += rand(pt);
    a = d * ch("amp");
    f = d * ch("freq");
}
```
Calculates distance-based falloff by finding nearby points within a radius, computing the distance from the current point to each neighbor, and remapping that distance with fit() to create an inverted falloff (1 at close range, 0 at radius). The falloff value is then clamped and used to modulate amplitude and frequency parameters for each point.

### Time-based wave animation setup [Needs Review] [[Ep5, 83:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5022s)]
```vex
vector pos;
int pts[];
int pt;
float u, s, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    pos = point(1, "P", pt);
    u = distance(@P, pos);
    s = fit01(u, ch("radius"), 1, 0);
    t = clamp(s, 0, 1);
    f = @Time * ch("speed");
}
```
Sets up time-based animation parameters for wave propagation by querying nearby points within a radius, calculating distance-based falloff using fit01 (inverted from 1 to 0), clamping the result, and creating a time multiplier controlled by a speed channel parameter. The @Time pseudo-attribute is multiplied by a speed slider to control animation rate.

### Distance-based time offset with nearpoints [Needs Review] [[Ep5, 83:44](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5024s)]
```vex
t = @Time * ch('speed');

vector pos;
int pts[];
int pt;
float u, d, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    u = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(u, 0, 1);
    t = @Time * ch('speed');
}
```
Sets up a proximity-based time offset system by finding nearby points within a radius, calculating distance-based falloff using fit (inverted from 0 to 1), clamping the result, and multiplying time by a speed parameter. This creates the foundation for distance-driven wave propagation effects where timing varies based on point proximity.

### Distance-Based Wave Ripples [[Ep5, 85:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5150s)]
```vex
vector pos;
int pts[];
int pt;
float d, f, t, a;

pts = nearpoints(0, @P, ch('radius'));

foreach(pt; pts) {
    pos = point(0, 'P', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
    t += rand(pt);
    a = d * ch('amp');
    f = d * ch('freq');
    @P.y += sin(t * f) * a;
}
```
Creates distance-based wave ripples by finding nearby points, calculating a distance-based falloff, and applying sine wave displacement to the Y position. The amplitude and frequency are modulated by the distance falloff, with randomized timing per point, and uses += to accumulate multiple wave influences from different nearby points.

### Ripple Effect with Nearby Points [[Ep5, 86:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5192s)]
```vex
vector pos;
int pts[];
int pt;
float d, d1, f, t, a;

pts = nearpoints(1, @P, 40);

foreach(pt; pts){
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch("speed");
    t += rand(pt);
    a = d * ch("amp");
    f = d * ch("freq");
    @P.y += sin(t * f) * a;
}
```
Creates a ripple effect by searching for nearby points within 40 units and applying a sine wave displacement to the Y position. For each nearby point, the displacement is modulated by distance-based falloff and per-point random phase offset, allowing multiple overlapping sine waves to blend together with both positive and negative contributions.

### Smooth Blending Ripples with Point Cloud [[Ep5, 88:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5292s)]
```vex
vector pos;
int pts[];
int pt;
float d, f, t, a;

pts = nearpoints(1, @P, ch('radius'));

foreach(pt; pts) {
    pos = point(1, 'P', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
    t += rand(pt);
    a = d * ch('amp');
    f = d * ch('freq');
    @P.y += sin(t * f) * a;
}
```
Uses nearpoints() to find neighboring geometry within a channel-controlled radius, then applies distance-based falloff with fit() and clamp() to create smoothly blending sine wave ripples. Each point's ripple is offset by rand(pt) for variation, and the amplitude and frequency are modulated by the distance falloff, creating organic wave patterns that blend seamlessly regardless of point count.

### Multiple Point Cloud Ripple Effect [[Ep5, 88:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5314s)]
```vex
pts = nearpoints(1, @P, 40); // search within 40 units

foreach(int pt; pts) {
    pos = point(1, 'P', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
    t += rand(pt);
    a = d * ch('amp');
    f = d * ch('freq');
    @P.y += sin(t * f) * a;
}
```
Creates overlapping ripple effects from multiple nearby points by iterating through points found within a 40-unit radius. Each nearby point influences the current point's Y position with a sine wave, where amplitude and frequency are modulated by the distance (fitted and clamped to 0-1), and timing is offset by random values per point. The result is multiple ripples that blend together smoothly as distance increases, performing efficiently even with dense geometry.

### Grid Resolution and Parameter Scaling [[Ep5, 89:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5374s)]
```vex
pts = nearpoints(1, @P, ch('radius'));

foreach(pt; pts) {
    pos = point(1, 'P', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
    t += rand(pt);
    a = d * ch('amp');
    f = d * ch('freq');
    @P.y += sin(t * f) * a;
}
```
Demonstrates how grid resolution affects parameter scaling in proximity-based animation. The code uses nearpoints to create ripples on a grid, but the radius, frequency, and amplitude parameters must be adjusted proportionally to the grid size (50x50 requires radius=8, freq=10, higher amplitude, whereas 10x10 grid needs much smaller values). This illustrates the importance of understanding the relationship between geometry scale and effect parameters.

### Neighborhood Wave with Parameter Tuning [[Ep5, 89:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5382s)]
```vex
int pts[];
int pt;
float u, d, f, t;
vector pos;
float a;

pts = nearpoints(1, @P, ch('radius'));

foreach(int pt; pts){
    pos = point(1, 'P', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    t = @Time * ch('speed');
    t += rand(pt);
    a = d * ch('amp');
    f = d * ch('freq');
    @P.y += sin(f * t) * a;
}
```
Creates localized wave effects by finding nearby points and applying sine-based displacement that falls off with distance. The code demonstrates how parameter values (radius, frequency, amplitude) must be tuned proportionally to geometry scale - larger grids require different values than smaller ones to achieve similar visual results.

### Animating Wave with Delays [Needs Review] [[Ep5, 90:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5406s)]
```vex
v@visualize;
int npts[];
int pts[];
float d, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    npt = minpos(1, v@P, pt);
    d = fit01(rand(pt+@ptnum), 0, 1);
    d = clamp(d, 0, 1);
    t = @Time;
    t = fit(t, 0, 1, 0, ch('speed'));
    t += d + sin(t)*f;
    f = d*ch('freq');
    @P.y += sin(t)*ch('a');
}
```
Creates an animated wave effect with per-point delays by finding nearby points within a radius, calculating randomized time offsets using fit01 and rand, then modifying Y position with a sine function controlled by frequency and amplitude parameters. The time offset creates a ripple effect where each point animates with a delay based on its random seed and the speed parameter.

### Wave ripples with nearpoints [Needs Review] [[Ep5, 90:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5412s)]
```vex
int ptx;
int pts[];
float q, d, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    ptx = point(1, "P", pt);
    d = distance(@P, ptx);
    q = fit(d, 0, chf("size"), 1, 0);
    t = chf("w") * @Time + d * chf("speed");
    f = sin(t);
    @P.y += f * q;
    f *= sin(t + chf("freq"));
    @P.y += sin(t + f) * q;
}
```
Creates a wave ripple effect by finding nearby points within a radius and modulating their Y position based on distance-attenuated sine waves. The effect uses time, distance, and frequency parameters to create traveling wave patterns with falloff. Parameters control wave size, speed, and frequency for fine-tuning the ripple behavior.

### Color Blending with For Loop [[Ep5, 97:48](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5868s)]
```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, ch('radius'));
@Cd = 0;

for(i = 0; i < len(pts); i++) {
    pt = pts[i];
    pos = point(1, 'P', pt);
    col = point(1, 'Cd', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
This snippet demonstrates using a for loop to iterate through nearby points found with nearpoints, accumulating weighted color contributions based on distance. Each nearby point's color is multiplied by a falloff factor (computed with fit and clamp) and added to the current point's color, creating a smooth color blend effect.

### Nearpoints and Dot Product Color Mapping [Needs Review] [[Ep8, 100:32](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=6032s)]
```vex
int pts[] = nearpoints(0, "P", @P, ch('maxdist'), chi('numpoints'));
vector pos = point(0, pts[0], "P");
vector dir = normalize(@P - pos);
vector norm = normalize(chi('dir'));
float dot = dot(dir, norm);
@Cd = fit(dot, -1, 1, 0, 1);
```
This code finds the nearest point within a specified distance, calculates the direction vector from that point to the current point, then computes the dot product between this direction and a normalized reference direction (likely from a channel). The dot product result is remapped from [-1,1] to [0,1] and assigned to color, creating a directional gradient effect based on alignment between the two vectors.

## Proximity Operations

### xyzdist with primitive UVs [[Ep8, 45:02](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2702s)]
```vex
i@primid;
v@up;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```
Uses xyzdist to find the closest point on a second input geometry, returning the distance and writing the primitive ID and UV coordinates to attributes. This demonstrates UV space behavior on different primitive types like tubes, spheres, and discs, which is particularly relevant for texture mapping in Mantra rendering when explicit UVs are absent.

### xyzdist output attributes [[Ep8, 48:56](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2936s)]
```vex
i@prim1d;
v@uv1;
f@dist;

@dist = xyzdist(1, @P, @prim1d, @uv1);
```
Demonstrates that xyzdist() returns multiple values: the distance (explicit return), primitive ID (written to @prim1d), and UV coordinates (written to @uv1). By declaring these attributes beforehand, the function automatically populates them with the closest primitive information when finding the nearest point on input 1.

### xyzdist Multi-Value Return [[Ep8, 50:00](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3000s)]
```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
```
The xyzdist() function demonstrates a powerful VEX pattern where a single function call can return multiple values through its parameters. While the function returns the distance to @dist, it simultaneously writes the closest primitive ID to @primid and UV coordinates to @uv, which are then used by primuv() to lookup the exact position on that primitive's surface.

### Surface Projection with xyzdist and primuv [[Ep8, 51:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3118s)]
```vex
i@primid;
v@uv;
f@dist;
@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, "P", @primid, @uv);
```
Uses xyzdist to find the closest point on a surface and stores the primitive ID and UV coordinates, then uses primuv to project the current point's position to that exact location on the surface. This creates a surface projection effect by first querying distance information and then repositioning points based on that data.

### Querying Attributes with primuv [[Ep8, 53:28](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3208s)]
```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);

i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
```
The primuv() function allows querying any attribute from a primitive at UV coordinates, not just position like minpos() does. In this example, after finding the closest point with xyzdist(), primuv() retrieves both position and color attributes from the target geometry, enabling transfer of multiple attributes based on proximity.

## Nearpoints Lookup

### nearpoints lookup and point generation [[Ep8, 62:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3740s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;
foreach (pt; pts) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
```
Finds up to 25 nearest points within a specified distance from the current point using nearpoints(), then iterates through each found point to retrieve its position and create a new point at that location. This demonstrates the basic workflow of proximity-based point lookup and geometry creation, which serves as a simpler alternative to point cloud functions.

### Find Nearest Points Array [[Ep8, 63:10](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3790s)]
```vex
int pts[] = nearpoints(1, @P, chf("d"), 25);
```
Creates an integer array containing point numbers of the nearest points on the second input (geometry input 1) within a channel-controlled distance, limited to a maximum of 25 points. The nearpoints() function searches from the current point's position (@P) and returns point indices that can be used for further operations like copying or connecting geometry.

### Nearpoints Array Setup with Foreach [[Ep8, 63:56](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3836s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt1;
vector poss;
foreach(pt1; pts)
{
    
}
```
Creates an array of nearby point numbers using nearpoints() with a channel-controlled distance and maximum of 25 points, then declares variables for use in a foreach loop that will iterate through each found point. The pt1 variable will hold each point number during iteration, and poss will store position data to be retrieved within the loop.

### Nearpoint with Channel Parameter [[Ep8, 65:36](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3936s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, 'P', pt);
    addpoint(0, pos);
}
```
Uses nearpoints() with a channel parameter to dynamically query points within a variable distance from the current point's position. The returned point numbers are stored in an array and iterated through with foreach, copying each found point's position to the output geometry. This demonstrates how to use channel references for interactive control of proximity queries.

## pcfind Queries

### Point Cloud Query with Foreach [[Ep8, 68:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4100s)]
```vex
int pts[] = pcfind(1, 'P', @P, ch('d'), 25);
i[]@a = pts;
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, 'P', pt);
    addpoint(0, pos);
}
```
Uses pcfind to find nearby points within a specified distance and stores the results in an array. Iterates through the found points with foreach, retrieves each point's position from the second input, and creates new points in the output geometry at those positions. This demonstrates the basic pattern of querying a point cloud and processing the results, which serves as a foundation for more optimized point cloud operations.

### Point Cloud Manual Point Iteration [[Ep8, 68:22](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4102s)]
```vex
int pts[] = pcfind(1, 'P', @P, ch('d'), 25);
int pt;
vector pos;
foreach (pt; pts){
    pos = point(1, 'P', pt);
    addpoint(0, pos);
}
```
This code demonstrates a manual approach to point cloud operations by finding nearby points with pcfind, then iterating through each point number to retrieve its position and create new points. While this produces identical results to direct point cloud queries, it serves as a foundation for understanding how to filter and process point cloud data with custom logic before the introduction of optimized point cloud functions.

### Point Cloud Query and Geometry Creation [[Ep8, 68:50](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4130s)]
```vex
int ptsi[] = pcfind(1, 'P', @P, ch('d'), 25);
i@num = len(ptsi);
int pti;
vector pos;

foreach(pti; ptsi){
    pos = point(1, 'P', pti);
    addpoint(0, pos);
}
```
Uses pcfind to find nearby points within a channel-controlled distance, stores the count of found points, then iterates through each found point to read its position and create new geometry points at those locations. This demonstrates an optimized workflow for point cloud queries by finding neighbors once and reusing the result list.

## Nearpoints Lookup

### Smoothing Surface Movement with nearpoints [[Ep8, 71:18](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4278s)]
```vex
@P = attrib(1, "P", @P);

vector gP = attrib(1, "P", @P);

int pts[] = nearpoints(1, @P, ch("d"), chi("amt"));
vector pos = 0;
foreach (int pt; pts) {
    pos += point(1, "P", pt);
}
@P = pos / len(pts);
```
Instead of snapping to the single closest point (which causes jerky movement), this code finds multiple nearby points using nearpoints(), averages their positions, and moves the current point to that averaged location. This creates smoother motion across the surface by interpolating between multiple neighboring positions rather than jumping directly to the nearest point.

### Smoothing Surface Sampling with Near Points [[Ep8, 71:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4280s)]
```vex
@P = minpos(1, @P);

// Smoother version using averaging:
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
setpointgroup(0, "pts", pts, 1);
vector pos = 0;
foreach (int pt; pts) {
    pos += point(1, 'P', pt);
}
@P = pos / len(pts);
```
Instead of snapping points directly to the closest position on a surface using minpos (which causes visible jumping), this approach finds multiple nearby points using nearpoints, averages their positions, and moves the current point to that averaged location. This creates a smoother interpolation across the surface rather than discrete snapping to the single nearest point.

### Averaging Point Positions for Smoothing [[Ep8, 74:10](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4450s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), ch('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
```
Uses nearpoints() to find nearby points within a specified distance and count, then averages their positions to smooth point movement across a surface. By accumulating nearby point positions and dividing by the array length, each point moves toward the average position of its neighbors, creating a smoothing effect that becomes more pronounced as more points are averaged.

### Point Averaging with nearpoints [[Ep8, 74:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4494s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);
```
This code demonstrates spatial averaging by finding nearby points using nearpoints() and computing their average position. It queries neighboring points within a radius, accumulates their positions in a loop, then divides by the count to move the current point to the averaged location. This creates a smoothing effect that averages both point motion and surface shape, causing points to adhere less strictly to the original geometry.

### Averaging Nearby Points with nearpoints [[Ep8, 74:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4498s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, "P", pt);
}

@P = pos/len(pts);
```
This code finds nearby points on a surface using nearpoints() and averages their positions to relocate the current point. By accumulating all found point positions and dividing by the count, it creates a smoothing effect that adheres to the underlying geometry. The technique provides smooth motion but may deviate from the original surface shape as more points are averaged.

## See Also
- **VEX Functions Reference** (`vex_functions.md`) -- nearpoints, pcfind function signatures
