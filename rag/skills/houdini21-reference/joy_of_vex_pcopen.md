# Joy of VEX: Point Clouds (pcopen)

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
int pc = pcopen(0, "N", @N, ch("d"), chi("amt"));  // Point Cloud Filtering by Normals
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpts"));  // Point Cloud Normal Lookup
int pc = pcopen(0, "P", @Cd, ch("dist"), chi("maxpoints"));  // Point Cloud Color-Based Clustering
```

## Point Cloud Iteration

### Disconnected Code Conclusion [Needs Review] [[Ep8, 100:30](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=6030s)]
```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pos = normalize(jitter(pc, 'R'));
vector norm = normalize(nml);
@Cd = fit(den, -1, 1, 0, 1);
@Cd = fit(den, -1, 1, 0, 1);
@Cd = pow(@Cd, chf("gamma"));
```
This code snippet demonstrates disconnected operations that are not actively functioning in the scene setup. It includes point cloud queries, jitter for randomization, and color fitting with gamma correction, but the speaker notes these operations are not connected and therefore do not execute. This concludes Day 20 of the Joy of Vex tutorial series.

### Point Cloud and Color Fitting [Needs Review] [[Ep8, 100:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=6034s)]
```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), ch('numpts'));
vector pos = normalize(jitter(@P, 'B'));
vector norm = normalize(n1);
vector up = {0, 1, 0};
@Cd = fit(chv('a'), -1, 1, 0, 1);
@Cd = smooth(@Cd, chf('smooth'));
```
This code opens a point cloud query using pcopen with channel-driven parameters for maximum distance and number of points. It then normalizes a jittered position vector and sets up orientation vectors. Finally, it remaps a channel value from -1 to 1 range into 0 to 1 for the color attribute and applies smoothing based on a parameter.

## Point Cloud Filtering

### Day 20 Resources and External Links [Needs Review] [[Ep8, 100:52](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=6052s)]
```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi('numpoints'));
vector pos = normalize(pcfilter(pc, "P"));
vector nrml = normalize(chi);
@Cd = fit01(pos, -1, 1);
@Cd = fit(sin, -1, 1, 0, 1);
@Cd = switch, ch('maxdist'), chi('numpoints'));
```
This snippet appears to be incomplete and contains syntax errors, demonstrating point cloud operations with pcopen and pcfilter, followed by attempted color assignments using fit and fit01 functions. The transcript indicates this is a closing section discussing Day 20 resources and external learning materials rather than a specific code tutorial.

## Point Cloud Iteration

### Point Cloud and Color Fitting [Needs Review] [[Ep8, 101:22](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=6082s)]
```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi('numpts'));
vector pos = normalize(fit(i@ptnum, 0, i@numpt - 1, 0, 1));
vector parm = normalize(chi);
@Cd = set(pos);
@Cd = fit(chv("col"), -1, 1, 0, 1);
@N = fit(chv("col"), -1, 1, 0, 1);
```
This snippet demonstrates opening a point cloud with pcopen, normalizing fitted point numbers as vectors, and remapping channel vector values to color and normal attributes using the fit function. The code shows multiple approaches to setting @Cd, combining normalized position-based colors with channel-driven color remapping from -1 to 1 range into 0 to 1 range.

## Point Cloud Filtering

### Point Cloud Averaging vs Manual Loop [[Ep8, 73:50](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4430s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);

int mypc = pcopen(1, 'P', @P, ch('d'), chi('amt'));
@P = pcfilter(mypc, 'P');
```
Demonstrates two equivalent methods for averaging point positions: manually using nearpoints() with a foreach loop to accumulate and divide by length, versus using pcopen() and pcfilter() which automatically performs the same averaging operation. Both approaches find nearby points within a specified distance and count, then set the current point position to the average of those positions.

### Averaging Point Positions with Nearpoints vs Point Cloud [[Ep8, 73:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4434s)]
```vex
// Method 1: Using nearpoints and foreach loop
int pts[] = nearpoints(1, @P, ch('d'), ch('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);

// Method 2: Using point cloud and pcfilter
int mypc = pcopen(1, 'P', @P, ch('d'), ch('amt'));
@P = pcfilter(mypc, 'P');
```
Demonstrates two methods for averaging point positions from neighboring points: the first uses nearpoints() to gather point numbers, iterates through them with foreach to accumulate positions, then divides by the array length to compute the average. The second method achieves the same result more efficiently using pcopen() to create a point cloud handle and pcfilter() to automatically compute the average of the 'P' attribute across the found points.

### Point Cloud vs Manual Averaging [[Ep8, 74:00](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4440s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, "P", pt);
}
@P = pos/len(pts);

int mypc = pcopen(1, "P", @P, ch('d'), ch('amt'));
@P = pcfilter(mypc, "P");
```
Demonstrates two equivalent methods for averaging point positions: manually finding nearby points with nearpoints() and summing their positions, versus using the more efficient pcopen() and pcfilter() workflow. Both approaches smooth geometry by averaging positions across neighboring points, with the number of points and search distance controlled by channel references.

### Point Cloud Smoothing Comparison [[Ep8, 74:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4478s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, "P", pt);
}

@P = pos/len(pts);

int mypc = pcopen(1, "P", @P, ch('d'), chi('amt'));
@P = pcfilter(mypc, "P");
```
Demonstrates two equivalent approaches to point smoothing: a manual method using nearpoints() with a foreach loop to average neighbor positions, and a more concise point cloud method using pcopen() and pcfilter(). Both approaches sample nearby surface points and average their positions, but increasing the sample count causes points to adhere less strictly to the original surface geometry while achieving smoother motion.

### Point Cloud Averaging Comparison [Needs Review] [[Ep8, 74:40](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4480s)]
```vex
int pt[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;

foreach(pt; pt[]){
    pos += point(1, 'P', pt);
}

@P = pos/len(pt[]);


int mypc = pcopen(0, 'P', @P, ch('d'), chi('amt'));
mypc = pcfilter(mypc, 'P');
```
Demonstrates two approaches to averaging nearby point positions: the first uses nearpoints() with a foreach loop to manually accumulate and average positions, while the second shows the beginning of a point cloud approach using pcopen() and pcfilter() which can achieve the same result more concisely. The averaging smooths point motion across a surface but reduces adherence to the underlying geometry shape.

## Point Cloud Iteration

### Point Cloud Averaging vs Near Points [Needs Review] [[Ep8, 74:42](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4482s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;

foreach(pt; pts){
    pos += point(1, "P", pt);
}

@P = pos/len(pts);

// Point cloud alternative:
int mypc = pcopen(1, "P", @P, ch('d'), chi('amt'));
@P = pcfind(mypc, "P");
```
Demonstrates two methods for smoothing point positions by averaging nearby points: the verbose approach using nearpoints() with a foreach loop to accumulate and average positions, versus the more concise point cloud method using pcopen() and pcfind(). Increasing the number of averaged points creates smoother motion but reduces adherence to the original surface geometry.

## Point Cloud Filtering

### Point Cloud vs Nearpoints Smoothing [[Ep8, 74:56](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4496s)]
```vex
// Manual approach with nearpoints
int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
int pt;
vector pos = 0;
foreach (pt; pts) {
    pos += point(1, 'P', pt);
}
pos /= len(pts);
@P = pos;

// Point cloud approach (more concise)
int vpc = pcopen(1, 'P', @P, ch('d'), chi('amt'));
@P = pcfilter(vpc, 'P');
```
Demonstrates two methods for smoothing points by averaging nearby positions: a manual approach using nearpoints with a foreach loop, and a more concise point cloud approach using pcopen and pcfilter. Both methods average positions of neighboring points, causing smoothing that moves points away from the original surface geometry, but the point cloud version achieves the same result in just two lines.

## Point Cloud Iteration

### Point Cloud Setup with pcopen [[Ep8, 75:48](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4548s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
int pt;
vector pos = 0;
foreach(pt; pts){
    pos += point(1, 'P', pt);
}

@P = pos/len(pts);

int mypc = pcopen(1, 'P', @P, ch('d'), chi('amnt'));
```
This code demonstrates the difference between nearpoints and pcopen. While the first section averages nearby point positions using nearpoints, the pcopen function creates a point cloud handle that can be queried later for multiple attributes efficiently. The pcopen call sets up a temporary point cloud structure limited by distance and maximum point count.

### Point Cloud Creation with pcopen [[Ep8, 76:48](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4608s)]
```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int pt;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// @P = pos/len(pts);

int nvpc = pcopen(1, 'P', @P, ch('d'), chi('amnt'));
```
Demonstrates the creation of a point cloud handle using pcopen as an alternative to nearpoints-based averaging. The point cloud is opened on geometry input 1, searching from the current point position @P within a distance and point count controlled by channel parameters. Unlike the commented-out nearpoints approach which directly averages positions, pcopen creates a temporary point cloud handle stored in 'nvpc' that can be queried with subsequent pcfilter or pciterate functions.

## Point Cloud Filtering

### Point Cloud Filtering [[Ep8, 76:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4618s)]
```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int pti;
// vector pos = 0;

// foreach(pti; pts){
//     pos += point(1, 'P', pti);
// }

// @P = pos/len(pts);

int nvpc = pcopen(1, 'P', @P, ch('d'), chi('amnt'));
@P = pcfilter(nvpc, 'P');
```
This demonstrates using point cloud functions as a more efficient alternative to nearpoints() for averaging positions. The pcopen() creates a point cloud handle, and pcfilter() automatically computes the averaged position from nearby points, replacing the manual sum-and-divide approach shown in the commented code above.

### Point Cloud Averaging with pcfilter [[Ep8, 77:02](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4622s)]
```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int ptj
// vector pos = 0;

// foreach(int pti; pts){
//     pos += point(1, 'P', pti);
// }

// @P = pos/len(pts);

int mypc = pcopen(1, 'P', @P, ch('d'), chi('amnt'));
@P = pcfilter(mypc, 'P');
```
This demonstrates using point cloud functions as an optimized alternative to manually averaging nearby point positions. The pcopen function creates a point cloud handle referencing input 1, then pcfilter automatically computes the averaged position of all points in that cloud, replacing the manual foreach loop approach shown in the commented code above.

### Point Cloud Filtering with pcfilter [[Ep8, 77:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4654s)]
```vex
// int pts1 = nearpoints(1, @P, ch('d'), chi('amt'));
// int pts1;
// vector pos = 0;

// foreach(pt; pts1){
//     pos += point(1, 'P', pt);
// }

// @P = pos/len(pts1);
int mypc = pcopen(1, 'P', @P, ch('d'), chi('amt'));
@P = pcfilter(mypc, 'P');
```
Demonstrates using pcopen() and pcfilter() to achieve the same averaging effect as the nearpoints/foreach approach but in just two lines of code. The pcfilter() function automatically sums and averages the specified attribute ('P' in this case) from all points in the point cloud handle, eliminating the need for manual iteration and division.

### Point Cloud Normal Filtering [[Ep8, 79:02](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4742s)]
```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amt'));
// vector pos = 0;
// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }
// @P = pos/len(pts);

int nvpc = pcopen(1, 'P', @P, ch('d'), chi('amt'));
@N = pcfilter(nvpc, 'N');
@N = normalize(@N) * 2;  // to make it easier to see!

int pc = pcopen(0, 'P', @P, ch('dist'), chi('maxpoints'));
@Cd = pcfilter(pc, 'Cd');
```
Demonstrates using pcopen() to create a point cloud handle and pcfilter() to compute the average normal from nearby points on the second input geometry. The normals are averaged from neighboring points within a specified distance and point count, then normalized and scaled by 2 for visibility. A second point cloud is used to filter and average color attributes from the first input.

### Point Cloud Attribute Filtering [[Ep8, 79:50](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4790s)]
```vex
// int pts[] = nearpoints(1, @P, ch('d'), chi('amnt'));
// int pt;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// @P = pos/len(pts);

int nvpc = pcopen(1, 'P', @P, ch('d'), chi('amnt'));
@N = pcfilter(nvpc, 'N');
@N = normalize(@N) * 2;

int pc = pcopen(0, 'P', @P, ch('dist'), chi('maxpoints'));
@Cd = pcfilter(pc, 'Cd');
```
Demonstrates using pcopen() to create point cloud handles and pcfilter() to extract and average attributes from nearby points. The code opens one point cloud to filter normals (normalizing and scaling the result), and another to filter color attributes, showing how to pull different attributes from different inputs using the point cloud workflow.

### Point Cloud Color Filtering [[Ep8, 80:16](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4816s)]
```vex
int pc = pcopen(0, 'P', @P, ch('dist'), chi('maxpoints'));
@Cd = pcfilter(pc, 'Cd');
```
Opens a point cloud around the current point using pcopen() with distance and point count parameters controlled by channel references, then uses pcfilter() to average the color (Cd) attribute from all points in that point cloud and assign it to the current point. This creates a color smoothing/blurring effect based on neighboring point colors.

### Color Blurring with Point Cloud [[Ep8, 81:28](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4888s)]
```vex
int pts[] = nearpoints(1, @P, ch('d'), chi('maxpt'));
// int pts[];
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// @P = pos/len(pts);
int pc = pcopen(0, 'P', @P, ch('d'), chi('maxpt'));
@Cd = pcfilter(pc, 'Cd');

int pc = pcopen(0, 'P', @P, ch('dist'), chi('maxpoints'));
@Cd = pcfilter(pc, 'Cd');
```
Uses pcopen to create a point cloud from the current geometry at each point position, then applies pcfilter to average the color attribute (@Cd) from surrounding points within the specified distance and max point count. This creates a color blur effect where each point's color becomes the weighted average of its neighbors, with the blur intensity controlled by the number of points included.

## Point Cloud Iteration

### Point Cloud Color Sampling [[Ep8, 81:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4894s)]
```vex
// VEX Wrangle
int pts[] = nearpoints(1, @P, ch('d'), chi('maxpt'));
// int pts;
// vector pos = 0;

// foreach(pt; pts){
//     pos += point(1, 'P', pt);
// }

// @P = pos/len(pts);
int pc = pcopen(0, 'P', @P, ch('d'), chi('maxpt'));
@Cd = pcsample(pc, 'Cd');
```
Opens a point cloud handle using pcopen() at the current point position with controllable distance and max points parameters, then uses pcsample() to average the color (Cd) attribute from all points within the point cloud. This creates a blur effect on colors by averaging neighboring point colors together, with the amount of blur controlled by the number of points sampled.

## Point Cloud Filtering

### Point Cloud Color Filtering [[Ep8, 82:10](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4930s)]
```vex
// int pt[] = nearpoints(1, @P, ch('d'), ch('amt'));
// int pt;
// vector pos = 0;

// foreach(pt; pts;)
//     pos += point(1, 'P', pt);
// )

// @P = pos/len(pts);

int pc = pcopen(0, 'P', @P, ch('d'), ch('amt'));
@Cd = pcfilter(pc, 'Cd');

int pc = pcopen(0, 'Cd', @Cd, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
```
Demonstrates using point clouds to blur attributes by opening a point cloud based on position to filter colors, then inversely opening a point cloud based on color distance to filter positions. This creates an attribute blur effect by averaging nearby point values, with increasing point counts producing greater blur as more neighbors are averaged together.

### Point Cloud Attribute Blur [[Ep8, 82:12](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4932s)]
```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("maxpt"));
@Cd = pcfilter(pc, "Cd");

int pc = pcopen(0, "Cd", @Cd, ch("dist"), chi("maxpts"));
@P = pcfilter(pc, "P");
```
Demonstrates two complementary point cloud blur techniques: first, finding points near each point's position and averaging their color values, and second, finding points near each point's color in color space and averaging their positions. Increasing the maximum points parameter creates more blur by averaging across more neighbors.

### Point Cloud Attribute Swapping [[Ep8, 82:16](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4936s)]
```vex
int pc = pcopen(0, "P", @P, ch("dist"), ch("maxpoints"));
@Cd = pcfilter(pc, "Cd");

int pc = pcopen(0, "Cd", @Cd, ch("dist"), ch("maxpoints"));
@P = pcfilter(pc, "P");
```
Demonstrates swapping lookup attributes in point cloud queries. The first snippet opens a point cloud using position (@P) to find neighbors and averages their color (@Cd), creating a blur effect. The second snippet inverts this by using color (@Cd) as the spatial lookup key to remap positions (@P), creating interesting distortion effects based on color similarity rather than spatial proximity.

### Point Cloud Filtering with pcfilter [[Ep8, 82:50](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4970s)]
```vex
int pc = pcopen(0, 'id', @Cd, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
```
Opens a point cloud handle using the color attribute (@Cd) as the search position, then uses pcfilter to set the current point's position to the averaged position of all points found in the point cloud. This creates a blur or smoothing effect where each point moves toward the average position of nearby points with similar colors.

### Point cloud color lookup [[Ep8, 83:10](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=4990s)]
```vex
int pc = pcopen(0, 'Cd', @P, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
```
Opens a point cloud using the current point's color (@Cd) as the search criterion instead of position, then filters to get averaged position from nearby points with similar colors. This creates a color-based spatial clustering effect where points are moved to positions that share similar color values within the specified distance.

### Point Cloud Color-Based Clustering [[Ep8, 83:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5014s)]
```vex
int pc = pcopen(0, "P", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
```
Opens a point cloud using color (@Cd) as the lookup attribute instead of position, then filters and averages the position values from neighboring points. This causes points with similar colors to cluster together spatially, as their positions get averaged based on color proximity rather than spatial proximity.

### Point Cloud Color Clustering [[Ep8, 84:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5064s)]
```vex
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
```
Opens a point cloud handle based on color similarity (@Cd) within a specified distance and maximum point count, then uses pcfilter to average the positions of all points in that neighborhood, causing points with similar colors to cluster together spatially. As the maxpoints parameter increases, more points contribute to the averaged position, creating tighter groupings based on color similarity.

### Point Cloud Normal Lookup [[Ep8, 84:52](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5092s)]
```vex
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpts"));
@N = pcfilter(pc, "P");
```
Creates a point cloud handle based on color similarity, then uses pcfilter to average the positions of nearby points (based on similar colors) and assigns the result to the normal attribute. This creates a color-based spatial clustering effect where points with similar colors influence each other's normal direction, causing geometry to coalesce into color-grouped sections.

### Point Cloud Filtering by Normal [[Ep8, 84:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5094s)]
```vex
int pc = pcopen(0, "cd", @Cd, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");

int pc = pcopen(0, "N", @N, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
```
Demonstrates using point cloud queries to average point positions based on similarity of attributes. The first example groups points by color (@Cd), causing similar colors to coalesce together in space. The second example switches to using normals (@N) as the query attribute, grouping points with similar surface orientations instead.

### Point Cloud Filtering by Normals [Needs Review] [[Ep8, 85:16](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5116s)]
```vex
int pc = pcopen(0, "N", @N, ch("d"), chi("amt"));
@P = pcfilter(pc, "P");
```
Opens a point cloud based on normal similarity rather than color, then filters the position attribute to average positions of points with similar normals. This creates a smoothing effect that groups geometry by surface orientation, effectively creating a spatial color-space-like representation based on normal direction.

### Point Cloud Filtering by Normals [[Ep8, 85:18](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5118s)]
```vex
int pc = pcopen(0, 'cd', @Cd, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');

int pc = pcopen(0, 'N', @N, ch('dist'), chi('maxpoints'));
@P = pcfilter(pc, 'P');
@Cd = @N;
```
Demonstrates using pcopen with normal attributes instead of color to find similar points based on normal direction. The code opens a point cloud filtering by normal similarity, averages positions with pcfilter, and visualizes the normals by assigning them to color. This creates spatial groupings based on surface orientation rather than color.

### Point Cloud Filtering by Normals [[Ep8, 85:26](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5126s)]
```vex
int pc = pcopen(0, 'P', @P, ch('dist'), chi('maxpoints'));
@N = pcfilter(pc, 'P');

int pc = pcopen(0, 'N', @N, ch('dist'), chi('maxpoints'));
@N = pcfilter(pc, 'P');
@Cd = @N;
```
Demonstrates using pcopen() to query point clouds based on normal similarity rather than position. Opens a point cloud handle using the normal attribute (@N) as the query vector, then filters to compute averaged normals from nearby points with similar normal directions, finally visualizing the result by assigning normals to color.

### Normal-based Point Cloud Filtering [Needs Review] [[Ep8, 85:44](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5144s)]
```vex
int pc = pcopen(0, "N", @N, ch("dist"), chi("maxpts"));
vector avg = pcfilter(pc, "P");
@P = avg;
@Cd = @Cd;
```
This code uses point cloud lookup based on normals instead of color to find nearby points and average their positions. By using @N as the lookup attribute, points with similar normal directions will be grouped together, creating a smoothing effect that respects the surface orientation. The filtered position is then assigned back to @P to move the point.

### Point Cloud Normal Averaging [Needs Review] [[Ep8, 86:56](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5216s)]
```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("maxpt"));
@P = pcfilter(pc, "P");
@Cd = @N;
```
Uses pcopen to find nearby points and pcfilter to average their positions, effectively grouping points based on their proximity. The normal is written to color (@Cd = @N) to visualize how points are grouped by their averaged normal directions, creating a visual representation of surface orientation similarity.

### Point Cloud Filtering and Velocity [[Ep8, 87:42](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5262s)]
```vex
int pc = pcopen(0, "P", @P, ch("d"), chi("mant"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv -= {1, 0, 1, 1};
avgp -= {1, 0, 1, 1};
@v += avgv - avgp;
```
Two point cloud examples: the first opens a point cloud from the first input and filters positions while coloring by normals. The second example opens a point cloud from the second input with fixed search parameters, filters both velocity and position attributes, offsets them by a constant vector, and adds their difference to the point's velocity attribute.

### Point Cloud Filtering Examples [[Ep8, 88:30](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5310s)]
```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
vector gn = pcfilter(pc, "P");
@Cd = gn;

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
```
Two examples of using pcfilter() to query point cloud data: the first opens a point cloud using channel-referenced parameters and filters position data, assigning it to color; the second queries velocity attributes from a second input within a fixed radius of 10 units and maximum of 30 points. These demonstrate real-world applications of point cloud filtering for attribute averaging.

### Point Cloud Filtering Examples [[Ep8, 88:32](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5312s)]
```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
@P = pcfilter(pc, "P");
@Cd = @N;

int pc = pcopen(1, "P", v@P, 10, 30);
vector avgp = pcfilter(pc, "v");
```
Two examples of using point cloud functions to query and filter neighboring points. The first opens a point cloud on input 0 using the current point position and channel-referenced parameters, then filters the positions and assigns the normal to color. The second queries input 1 with hardcoded distance and max points, filtering a vector attribute 'v'.

### Point Cloud Filtering Examples [Needs Review] [[Ep8, 88:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5314s)]
```vex
int pc = pcopen(0, "P", @P, ch("dist"), chi("maxpoints"));
vector gn = pcfilter(pc, "P");
@Cd = @n;

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
```
Two practical examples of point cloud filtering. The first opens a point cloud using a normal attribute for search orientation, filters positions, and assigns the normal to color. The second opens a point cloud from input 1 with fixed search parameters and computes an averaged velocity vector from nearby points.

### Point Cloud Flocking Force [[Ep8, 88:56](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5336s)]
```vex
int pc = pcopen(1,"P",@P,10,30);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= {1,0,1};
avgp *= {1,0,1};
@v += avgv-avgp;
```
Opens a point cloud and filters neighboring particle velocities and positions, then masks the Y component to zero for both. The velocity is adjusted by adding the difference between average neighbor velocity and average neighbor position, creating a flocking-like force that considers nearby particle motion in the XZ plane only.

### Point Cloud Velocity Averaging [Needs Review] [[Ep8, 89:10](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5350s)]
```vex
vector pos = vector(@P.x * 0.2 * offset, 1) * {2, 0, 2};
@P = set(@P.x * @ez, @P.y, @P.z * @ez);

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
avgp -= {1, 0, 1};
@v += avgv - avgp;
```
Uses point cloud functions to query nearby points within a radius, calculates average velocity and position from neighbors, then adds the difference between averaged velocity and position to the current point's velocity. This creates a flocking or cohesion-like behavior where points influence each other based on proximity.

### Point Cloud Velocity Averaging [Needs Review] [[Ep8, 90:10](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5410s)]
```vex
int pc = pcopen(0, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
@v += (1, 0, 1, 1);
avgp -= (1, 0, 1, 1);
@v -= avgv - avgp;
```
Opens a point cloud with a search radius of 10 and maximum 30 points, then calculates average velocity and position of neighbors. Applies vertical lift to velocity (adding to y-component), adjusts the averaged position by the same offset, and modifies the current point's velocity based on the difference between neighbor average velocity and adjusted position.

### Point Cloud Velocity Averaging [Needs Review] [[Ep8, 90:22](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5422s)]
```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
avgp -= @P;
@v -= avgv - avgp;
```
Opens a point cloud of 30 nearby points within radius 10, then averages their velocity and position attributes using pcfilter(). The averaged velocity is masked to exclude Y-axis contributions, and the final velocity is adjusted by subtracting the difference between averaged velocity and relative position offset, creating a smoothed directional flow effect.

### Point Cloud Velocity Filtering [[Ep8, 90:30](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5430s)]
```vex
vector uv = set(rand(@ptnum), rand(@ptnum+1));
@v += chvlen('line');
//rgb as curvelookup((1,1,1)@age*(sw*0.2)*(1,0,0));

int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
avgp -= {1, 0, 1};
@v += avgv - avgp;
```
Uses point cloud queries to average velocity and position from nearby points within a radius, then modifies the current point's velocity based on neighborhood averaging. The velocity is adjusted by masking the Y component and combining the filtered velocity with a position offset to create directional flow along a tube geometry.

### Point Cloud Velocity Influence in POPs [Needs Review] [[Ep8, 90:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5454s)]
```vex
int pc = pcopen(0, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= [-1, 0, 1];
avgp = [-1, 0, 2, 1];
@v += avgv + avgp;
```
Uses point cloud queries in a POP context to find nearby points (within 10 units, up to 30 points) and averages their velocity and position vectors. These averaged vectors are modified and added to the current particle's velocity to influence its direction, creating a lift effect that makes the trail vector point up and to the right.

### Point Cloud Velocity Averaging in POPs [[Ep8, 90:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5458s)]
```vex
int pc = pcopen(1,"P",@P,10,30);
vector avgv = pcfilter(pc,'v');
vector avgp = pcfilter(pc,'P');
avgv *= {1,0,1};
avgp *= {1,0,1};
@v += avgv-avgp;
```
Uses point cloud queries within a POP Wrangle to find nearby particles (within 10 units, up to 30 points) and averages their velocity and position attributes. The averaged vectors are masked to Y-only ({1,0,1}) and the difference is added to the particle's velocity, creating a flocking-like behavior that influences particle motion based on neighbors.

### Point Cloud Particle Interaction [[Ep8, 91:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5484s)]
```vex
int pc = pcopen(0,"P",@P,10,30);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= {1,0.1,1};
avgp -= {1,0.1,1};
@v += avgv-avgp;
```
Opens a point cloud on a second input geometry (grid) to find up to 30 nearest points within 10 units, then filters and averages their velocity and position attributes. The averaged values are scaled/offset and combined to modify the particle velocity, creating swirling upward motion by influencing particles based on nearby geometry.

### Point Cloud Particle Velocity Averaging [Needs Review] [[Ep8, 91:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5498s)]
```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0, 1};
avgp *= {1, 0, 1};
@v += avgv - avgp;
```
Opens a point cloud on the second input geometry to find up to 30 points within 10 units, then calculates the average velocity and position from those neighbors. The averaged values are masked in Y (keeping only X and Z components) and combined to influence the current particle's velocity, creating a swirling upward motion based on neighbor information.

### Point Cloud Particle Flocking [[Ep8, 91:42](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5502s)]
```vex
int pc = pcopen(0, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv *= {1, 0, 1};
avgp -= {1, 0, 1};
@v += avgv - avgp;
```
Uses point cloud queries to create particle flocking behavior by finding the 30 nearest points within 10 units and averaging their velocity and position. The averaged velocity and position are masked to XZ plane (zeroing Y component), then the difference between average velocity and offset position is added to current particle velocity to create cohesive swarming motion.

### Point Cloud Velocity Smoothing [[Ep8, 92:32](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5552s)]
```vex
int pc = pcopen(1, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv *= {1, 0.1, 1};
avgp *= {1, 0.1, 1};
@v += avgv - avgp;
```
Opens a point cloud and filters both velocity and position attributes from nearby points. Scales the Y component of both filtered attributes by 0.1 to dampen vertical motion, then adds the difference between averaged velocity and averaged position to the current point's velocity, creating a smooth cohesive force that pulls points together while they move upward.

### Point Cloud Velocity Averaging [[Ep8, 92:46](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5566s)]
```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
@v *= (1, 0.1, 1);
@v += (1, 0.1, 1);
@v += avgv - avgp;
```
Opens a point cloud on input 1 to find nearby points, then uses pcfilter to average their velocity and position attributes. The velocity is scaled and offset, then adjusted by the difference between average velocity and average position to create a smoothing force that pulls points together as they move upward from a cylinder.

### Point Cloud Velocity Clumping [[Ep8, 93:26](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5606s)]
```vex
int pc = pcopen(1, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= {1, 0.1, 1};
avgp *= {1, 0.1, 1};
@v += avgv - avgp;
```
Opens a point cloud on the first input searching for 30 nearby points within a radius of 10 units, then averages their velocity and position. The averaged values are scaled down in Y by 0.1, and the velocity is adjusted by the difference between averaged velocity and position to create clumping behavior as points emerge and group together.

### Point Cloud Particle Clumping [Needs Review] [[Ep8, 94:00](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5640s)]
```vex
int pc = pcopen(0, "P", @P, 10, 30);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv = {1, 0, 1, 1};
avgp = {1, 0, 0, 1};
@v += avgv - avgp;

int pc2 = pcopen(1, "P", @P, 10, 30);
vector avgv2 = pcfilter(pc2, "v");
vector avgp2 = pcfilter(pc2, "P");
avgv2 = {1, 0, 1, 1};
avgp2 = {1, 0, 1, 1};
@v += avgv2 - avgp2;
```
Uses point cloud queries on two input geometries to average neighboring particle positions and velocities, then modifies the current point's velocity based on the difference between averaged values. This creates a clumping effect where particles coalesce into spiral arm patterns by synchronizing their motion with nearby neighbors.

### Particle Clumping with Point Clouds [Needs Review] [[Ep8, 94:12](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5652s)]
```vex
int pc = pcopen(1, 'P', @P, 10, 30);
vector avgv = pcfilter(pc, 'v');
vector avgp = pcfilter(pc, 'P');
avgv *= 0.1;
avgp -= @P;
avgp *= 0.1;
@v += avgv - avgp;
```
This technique uses point cloud queries to create particle clumping behavior by averaging both velocities and positions of nearby points. By blending the averaged velocity with a vector pointing toward the averaged position, particles gradually coalesce into spiral arm shapes or clumps as they move together over time.

### Point Cloud Velocity Averaging [[Ep8, 94:18](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5658s)]
```vex
int pc = pcopen(0,"P",@P,10,100);
vector avgv = pcfilter(pc,"v");
vector avgp = pcfilter(pc,"P");
avgv *= [1,0.1,1];
avgp *= [1,0.1,1];
@v += avgv-avgp;
```
This snippet creates particle clumping behavior by opening a point cloud around each point and averaging the velocities and positions of nearby points. The Y-axis is scaled down by 0.1 to flatten the influence, then the difference between averaged velocity and averaged position is added to the current point's velocity, causing particles to coalesce into spiral arm shapes.

### Particle Clumping with Point Clouds [[Ep8, 94:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5660s)]
```vex
int pc = pcopen(0, "P", @P, ch("rad"), 100);
vector avgv = pcfilter(pc, "v");
vector avgp = pcfilter(pc, "P");
avgv *= set(1, 0, 1);
avgp *= set(1, 0, 1);
@v += avgv - avgp;
```
Creates a clumping effect for particles by opening a point cloud around each point, averaging the velocity and position of nearby neighbors, masking Y-axis components, then adjusting the current velocity to pull points toward the local average. This causes particles with similar initial conditions to coalesce into spiral arm shapes as they move together over time.

### Point Cloud Particle Clumping [Needs Review] [[Ep8, 94:22](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5662s)]
```vex
int pc = pcopen(0, "P", @P, ch('rad'), 100);
vector avgv = pcfilter(pc, "v");
avgv *= {1, 0, 1};
@P += avgv;

vector avgp = pcfilter(pc, "P");
avgp -= @P;
@P += avgp;

int pc2 = pcopen(0, "P", @P, ch('bias') * ch('maxdist'), ch('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc2, "P");
pcn = pcfilter(pc2, "N");
```
Uses point cloud queries to average nearby particle velocities and positions, causing particles with similar initial conditions to coalesce into clumped spiral patterns. The technique filters velocity and position data from neighboring points and blends them to create cohesive particle groupings during simulation.

### Point Cloud Particle Averaging [Needs Review] [[Ep8, 94:28](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5668s)]
```vex
int pc = pcopen(0,"P",@P,ch("radius"),chi("maxpts"));
vector avgv = pcfilter(pc,"v");
avgv *= {1,0,1};

vector avgp = pcfilter(pc,"P");
avgp *= {1,0,1};
@P += avgv-avgp;

int pc = pcopen(0, "P", @P, ch("bias"), chi("numpoints"));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");
```
Demonstrates averaging particle positions and velocities using point cloud queries to create coalescing spiral patterns. The technique uses pcfilter to average nearby point attributes, then offsets positions based on the difference between averaged velocity and position (masked to XZ plane). This creates emergent clumping behavior where particles gradually converge into organized structures.

### Point Cloud Filtering and Averaging [Needs Review] [[Ep8, 94:36](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5676s)]
```vex
int pc = pcopen(0, "P", @P, ch("dist"), ch("maxlist"), ch("numpoints"));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

vector avgp = pcfilter(pc, "P");
vector avgv = pcfilter(pc, "v");
vector argv = {1, 0, 1};
avgv *= argv;
avgp *= argv;

@P += avgp - @P;
```
Demonstrates point cloud filtering to average neighboring point positions and velocities, creating clumping behavior for particles. The code opens a point cloud query, filters to get average position and normal values, then selectively weights the results using a mask vector to control which axes are affected.

### Fake Ambient Occlusion Point Cloud [[Ep8, 94:38](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5678s)]
```vex
int pc = pcopen(0, "P", @P, ch("bias"), chi("maxdist"), chi("numpoints"));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp("dot_cc", dot);
dist = chramp("dist_cc", dist);
```
This technique creates a fake ambient occlusion effect by opening a point cloud and using pcfilter to average nearby point positions and normals. The dot product between the current point's normal and averaged nearby normals, along with the distance to the averaged position, are remapped via color ramps to generate occlusion-like values.

### Fake Ambient Occlusion with Point Clouds [[Ep8, 94:40](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5680s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates a fake ambient occlusion effect by opening a point cloud around each point, then computing both the dot product between the point's normal and averaged nearby normals, and the distance to averaged nearby positions. These values are remapped through color ramps and can be used to drive color, simulating occlusion in concave areas.

### Fake Ambient Occlusion with Point Clouds [Needs Review] [[Ep8, 94:44](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5684s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), ch('maxpoints'));
vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
This technique creates a fake ambient occlusion effect by opening a point cloud around each point, filtering the average position and normal of nearby points, then calculating both the dot product between the current normal and the averaged normal, and the distance to the averaged position. The dot product (remapped through a color ramp) is assigned to color to simulate occlusion based on surface orientation similarity.

### Fake Ambient Occlusion with Point Clouds [[Ep8, 94:46](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5686s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxpt'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates a fake ambient occlusion effect by opening a point cloud around each point, filtering averaged position and normal data, then calculating both the dot product between the current point normal and averaged normal, and the distance between current and averaged positions. The dot product (representing surface concavity) and distance values are remapped through color ramps and used to drive the color attribute for shading.

### Point Cloud Ambient Occlusion [[Ep8, 95:02](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5702s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), ch('maxpts'));
vector pos, pcg;
float dot, dist;

pcg = pcfilter(pc, 'P');
pcg = pcfilter(pc, 'P');

dot = dot(@N, pcg);
dist = distance(@P, pcg);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates pseudo ambient occlusion by opening a point cloud around each point, computing a blurred position using pcfilter, then comparing the surface normal to the blurred position direction using a dot product. The dot product and distance values are remapped through color ramps and can be visualized via the color attribute.

### Pseudo Ambient Occlusion via Point Cloud [[Ep8, 95:04](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5704s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), chi('numpoints'));
vector pcP, pcN;
float dot, dist;

pcP = pcfilter(pc, "P");
pcN = pcfilter(pc, "N");

dot = dot(@P, pcN);
dist = distance(@P, pcP);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates a pseudo ambient occlusion effect by opening a point cloud around each point to get blurred position and normal values, then calculates dot product between current position and blurred normal to determine occlusion. The dot product and distance values are remapped through color ramps before being assigned to color, allowing artistic control over the occlusion falloff.

### Point Cloud Ambient Occlusion [[Ep8, 95:18](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5718s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates a pseudo-ambient occlusion effect by opening a point cloud to find nearby geometry, filtering the blurred position and normal values, then comparing the current point's normal with the filtered normal via dot product (or comparing distances). The dot product between the real normal and blurred normal, or the distance between real and blurred positions, creates a curvature-like map that reveals geometric concavity and convexity.

### Ambient Occlusion via Point Cloud [[Ep8, 95:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5754s)]
```vex
@P = pcimport(0, "P", @P, @N*ch('bias'), ch('maxdist'), chi('maxpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(0, 'P');
pcn = pcfilter(0, 'N');

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates an ambient occlusion effect by using point cloud filtering to blur position and normal attributes, then comparing the original normal to the blurred normal via dot product (or measuring distance between original and blurred positions). The results are remapped through ramps and visualized as color, producing a curvature-like map that indicates surface occlusion.

### Ambient Occlusion via Point Cloud [Needs Review] [[Ep8, 95:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5758s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxdist'), ch('numpoints'));
vector avgP = 0;
float dot, dist;

@Cd = chv("clr_in");

avgP = pcfilter(pc, "P");
vector pcN = pcfilter(pc, "N");

dot = dot(v@N, pcN);
dist = distance(@P, avgP);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates an ambient occlusion effect by opening a point cloud lookup biased along the surface normal, then comparing the current point's normal to the averaged normals in the neighborhood via dot product. The result is remapped through a ramp parameter and can alternatively visualize distance to the averaged position as a curvature-like map.

### Ambient Occlusion via Point Cloud [[Ep8, 96:02](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5762s)]
```vex
int pc = pcopen(0, "P", @P+ch('bias'), ch('maxdist'), chi('maxpt'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates an ambient occlusion or curvature map by opening a point cloud near each point, filtering to get averaged position and normal values, then computing the dot product between the original and averaged normals or the distance between original and averaged positions. The results are remapped through color ramps and assigned to color to visualize surface concavity and convexity.

### Point Cloud Curvature Mapping [[Ep8, 96:04](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5764s)]
```vex
int pc = pcopen(0, "P", @P + @N * ch('bias'), ch('maxdist'), chi('maxpts'));
vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates a curvature-like visualization by opening a point cloud with a biased lookup position (offset by normal), then filtering to get averaged position and normal values. The dot product between the current normal and averaged normal is remapped through a color ramp and assigned to color, creating a curvature map effect based on surface orientation similarity.

### Point Cloud Dot Product and Distance Analysis [[Ep8, 96:58](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5818s)]
```vex
int pc = pcopen(0, "P", @P, ch('bias'), ch('maxpts'), chi('maxdist'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Opens a point cloud and computes both the dot product between the current point's normal and the averaged point cloud normal, and the distance between the current point and the averaged point cloud position. These values are then remapped through separate ramp parameters for control, allowing visualization of either metric via the color attribute.

### Point Cloud Ramp Control [Needs Review] [[Ep8, 97:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5840s)]
```vex
int pc = pcopen(0, "P", @P+@N*ch('bias'), ch('maxdist'),
chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Uses chramp() to apply user-controlled color ramps to both the dot product comparison and distance calculation from a point cloud query, allowing artistic control over the falloff curves. The ramps ('dot_cc' and 'dist_cc') enable fine-tuning of how the dot product alignment and distance values map to the final color output.

### Fake AO with Ramp Controls [[Ep8, 97:32](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5852s)]
```vex
int pc = pcopen(0, "P", @P, chf('bias'), chi('maxlist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, "P");
pcn = pcfilter(pc, "N");

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;
//@Cd = dist;
```
Creates a fake ambient occlusion effect by computing both dot product and distance between point normals and positions using point clouds, then remapping those values through color ramps for artistic control. The user can switch between visualizing the dot product calculation (showing surface orientation differences) or the distance calculation (showing spatial proximity) by commenting/uncommenting the final @Cd assignments.

### Fake AO Using Point Clouds [[Ep8, 97:52](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5872s)]
```vex
int pc = pcopen(0, "P", @P, chf('bias'), chi('maxlist'), chi('numpoints'));

vector pcp, pcn;
float dot, dist;

pcp = pcfilter(pc, 'P');
pcn = pcfilter(pc, 'N');

dot = dot(@N, pcn);
dist = distance(@P, pcp);

dot = chramp('dot_cc', dot);
dist = chramp('dist_cc', dist);

@Cd = dot;

// Alternative version:
int pc = pcopen(0, "P", @P, chf('maxdist'), chi('numpoints'));

vector pch = normalize(pcfilter(pc, 'N'));
vector norm = normalize(@N);
float dot = dot(norm, pch);
@Cd = fit(dot, 0.1, 1, 0, 1);
@Cd = pow(@Cd, chf('gamma'));
```
Demonstrates creating fake ambient occlusion by using point cloud queries to compare the current point's normal against averaged normals of nearby points. The dot product between normals indicates surface concavity, which is then remapped using color ramps or fit/pow functions to create an AO-like shading effect with adjustable contrast and gamma control.

### Fake Ambient Occlusion via DOT Product [[Ep8, 97:54](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5874s)]
```vex
@Cd = @dist;

int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```
Demonstrates creating a fake ambient occlusion effect by computing the dot product between a point's normal and the averaged normals of nearby points from a point cloud. The dot product is remapped from [-1,1] to [0,1] using fit() and then gamma-corrected with pow() to adjust contrast, providing artistic control over the AO appearance.

### Fake Ambient Occlusion with Point Clouds [[Ep8, 98:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5900s)]
```vex
int pc = pcopen(0, "P", @P, ch("maxdist"),
    chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```
Creates a fake ambient occlusion effect by opening a point cloud and comparing the averaged normals of nearby points to the current point's normal using a dot product. The dot product result is remapped from [-1,1] to [0,1] and assigned to color, then gamma correction is applied for contrast control. This technique simulates how occluded areas receive less ambient light.

### Fake Ambient Occlusion with Point Clouds [[Ep8, 98:22](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5902s)]
```vex
int pc = pcopen(0, "P", @P, chv("maxdist"), chi("maxptct"));
vector pos, pcn;
float dot, dist;

pcn = pcfilter(pc, "P");
pos = pcfilter(pc, "pos");

dot = dot(@N, pcn);
dist = distance(@P, pos);

dot = chramp("dot_rn", dot);
dist = chramp("dist_rn", dist);

@Cd = dot;
// @Cd = dist;

int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```
Demonstrates two approaches for creating fake ambient occlusion using point cloud queries. The first method uses distance and normal comparison with ramps for remapping values, while the second uses normalized normals with dot product fitted from [-1,1] to [0,1] and applies gamma correction for contrast control.

### Ambient Occlusion with Fit [[Ep8, 98:24](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5904s)]
```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch('gamma'));
```
Creates ambient occlusion by opening a point cloud, computing the dot product between the current point's normal and the averaged normal from nearby points, then remapping the dot product range from [-1, 1] to [0, 1] using fit() and applying a gamma correction for visual control. This approach uses fit() to handle the full range of dot product values including negatives, as suggested by viewer feedback.

### Ambient Occlusion with Gamma Correction [[Ep8, 98:36](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5916s)]
```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, chi("gamma"));
```
This creates an ambient occlusion effect by sampling nearby normals using a point cloud, computing the dot product between the point's normal and the averaged nearby normals, then remapping the result to color with a gamma correction multiplier for visual adjustment. The gamma parameter allows artistic control over the contrast and brightness of the occlusion effect.

### Point Cloud Normal Comparison with Gamma [[Ep8, 99:34](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5974s)]
```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcN = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcN);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```
Creates a point cloud lookup based on position, computes the normalized average normal from nearby points, then calculates the dot product between the point cloud normal and the current point's normal. The dot product is remapped from [-1,1] to [0,1] and assigned to color, then raised to a gamma power for contrast control.

## See Also
- **VEX Functions Reference** (`vex_functions.md`) -- pcopen, pcfilter function signatures
