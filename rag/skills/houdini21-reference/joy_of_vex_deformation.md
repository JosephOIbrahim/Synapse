# Joy of VEX: Deformation

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
v = fit(0, ch("radius"), 1, 0);  // Fit and Sine Wave Deformation
float d = length(@P);  // Applying Sine Wave to Position
float d = length(@P);  // Distance-Based Displacement
```

## Wave Deformation

### Surface Displacement with Normals [[Ep2, 11:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=674s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d *= @Time;
@P.y = sin(d);

@P += @N * ch('push');  // @N-based push respects surface direction; @P.y = sin(d) does not
```

### Normal-based displacement [Needs Review] [[Ep2, 11:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=676s)]
```vex
float d = length(@P);
d *= ch('N_scale');
d *= @Frame;
@P.y = sin(d);

@P += @N * ch('push');  // correct: displaces along surface normal, not world Y
```

### Normal-based Surface Displacement [[Ep2, 11:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=692s)]
```vex
float d = length(@P);
d *= ch("v_scale");
d *= PI;
@P.y = sin(d);

@P += @N * ch("push");  // normal offset follows surface topology, not world space
```

### Animated Wave Displacement with Controls [[Ep2, 12:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=752s)]
```vex
float d = length(@P);
d *= ch('x_scale');
d += @Frame;
@P += @N * sin(d) * ch('wave_height');  // radial waves propagate outward; @Frame drives animation
```

### Animated Sine Wave Deformation [[Ep2, 13:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=832s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d)*ch('wave_height');  // distance + @Time phase creates ripples from center
```

### Animated Sine Wave Displacement [[Ep2, 13:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=838s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d) * ch('wave_height');  // same pattern; @Time subtraction drives outward motion
```

### Animated Wavelength Displacement [[Ep2, 14:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=842s)]
```vex
float d = length(@P);
d ^= ch('v_scale');
d += @Time;
@P += @N*sin(d);  // ^= is VEX exponentiation, controls wavelength nonlinearly
```

### Animated wave with channel controls [[Ep2, 14:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=886s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N * sin(d) * ch('wave_height');  // v_scale = frequency; wave_height = amplitude
```

### Animated Wave Displacement [[Ep2, 14:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=892s)]
```vex
float d = length(@P);
d *= ch("v_scale");
d += @Frame;
@P = @P * sin(d) * ch("wave_height");  // NOTE: @P *= sin collapses toward origin; prefer @P += @N*sin(d)*ch()
```

### Animated Wave Deformation [[Ep2, 15:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=924s)]
```vex
float d = length(@P);
d *= ch("y_scale");
d += @Time;
@P += @N*sin(d)*ch("wave_height");  // y_scale = frequency; wave_height = amplitude
```

### Animated Wave Deformation with Channels [[Ep2, 16:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=960s)]
```vex
float d = length(@P);
d += @Time;
@P.y = @P.y * sin(d) * ch("wave_height");  // modulates existing Y, not @N direction
```

### Wave Distortion with Distance [Needs Review] [[Ep2, 17:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1052s)]
```vex
float d = length(@P);
d -= ch("v_scale");
d *= 6*@Time;
@P.y = @P.y*sin(d) *ch("wave_height");  // v_scale offsets freq; 6*@Time speeds animation
```

### Sine Wave Ripple Effect [[Ep2, 18:06](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1086s)]
```vex
float d = length(@P);
v@v = ch("_scale");
@P += @N * sin(d) * ch("wave_height");  // distance = phase; wave_height = amplitude; concentric rings
```

### Creating Sine Waves with Length [[Ep2, 18:38](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1118s)]
```vex
float d = length(@P);
d *= ch("scale");
@P += @N * sin(d) * ch("wave_height");  // scale = wavelength; wave_height = amplitude
```

## Ramp-Driven Deformation

### Ramp-Driven Position Deformation [[Ep2, 43:44](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2624s)]
```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('my-ramp', d);  // chramp gives artistic shape control vs fixed math
```

### Scaling distance with ramp and channels [Needs Review] [[Ep2, 47:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2836s)]
```vex
float d = length(@P);
d *= ch('scale');
d = chramp('myramp', d);
@P.y = chramp('myramp', d);  // double chramp: first remaps d, second drives Y
```

### Ramp-Driven Height Displacement [[Ep2, 48:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2898s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= ch('time');
@P.y = chramp('myramp', d);
@P.y *= ch('height');  // ch('time') animates ramp lookup; height = amplitude multiplier
```

### Animated Ramp Displacement with Height Control [[Ep2, 48:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2926s)]
```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
@P.y = chramp("myramp", d);
@P.y *= ch("Height");  // subtracting @Time from d animates ramp lookup outward
```

## Wave Deformation

### Animated Ramp-Driven Displacement [[Ep2, 49:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2940s)]
```vex
float d = length(@P);
d *= ch('scale');
d += $T;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');  // fit() maps sin() [-1,1] to [0,1] for valid chramp input
```

### Animated ramp with time offset [[Ep2, 49:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2968s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d,-1,1,0,1);
@P.y = chramp('my_ramp',d);
@P.y *= ch('height');  // fit() required: sin() returns [-1,1] but chramp expects [0,1]
```

### Animated radial wave with point offset [Needs Review] [[Ep2, 51:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3116s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = sin(d*ch('freq')/(@ptnum/100.0)*d);
@Cd *= ch('height');  // @ptnum/100.0 offsets each point's wave phase for variation
```

## Ramp-Driven Deformation

### Radial Ramp Displacement [Needs Review] [[Ep2, 52:42](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3162s)]
```vex
float d = length(@P);
d *= ch("scale");
d = qs(d);
d *= $PI;
@P.y = chramp("myamp", d);
@P.y *= ch("height");  // qs() wraps d to create repeating radial pattern; $PI scales lookup
```

## Wave Deformation

### Animated Sine Wave Displacement [[Ep2, 52:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3178s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = .1*sin(d);
@v.y = sin(length(@P));  // @v.y stores velocity for downstream simulation
```

## Ramp-Driven Deformation

### Ramp-driven radial displacement [Needs Review] [[Ep2, 53:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3194s)]
```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@P.y = chramp('myramp', d);
@Cd = chramp('height', d);  // d %= 1 normalizes to [0,1] for repeating concentric ring lookup
```

## Wave Deformation

### Animated Radial Wave with Ramp [[Ep2, 54:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3296s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
@N.y = ch('height');  // sets normal Y for downstream shading, not displacement
```

### Animated Ramp Wave Effect [[Ep2, 55:38](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3338s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');  // ramp shapes the wave; scale=freq, height=amplitude
```

## Ramp-Driven Deformation

### Animated Ramp Height Displacement [[Ep2, 56:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3384s)]
```vex
float d = length(@P);
d -= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');  // d -= scale then d -= @Time: offset + animate ramp lookup outward
```

## Wave Deformation

### Animated Ramp-Driven Wave Patterns [[Ep2, 56:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3416s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-map', d);
@P.y *= ch('height');  // subtracting @Time animates ramp lookup; height = amplitude
```

### Animated Waves with Ramp Control [[Ep2, 57:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3450s)]
```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
d %= 1;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("myRamp", d);
@P.y *= ch("height");  // chain: @Time animate -> %= wrap -> sin oscillate -> fit normalize -> chramp shape
```

### Ramp and Distance Deformation [[Ep2, 58:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3494s)]
```vex
float d = length(@P);
d *= ch("scale");
d = abs(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("myram", d);
@P.y *= ch("height");  // abs(d) ensures positive input; fit() normalizes for chramp
```

### Distance-based Height with ID Offset [Needs Review] [[Ep2, 59:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3540s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @id;
d += sin(d);
d *= ch('height');
@P.y = d;  // @id offsets each point's wave phase; final @P.y = d (not *= height)
```

### Fit and Ramp for Wave Displacement [[Ep2, 59:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3566)]
```vex
float d = length(@P);
d *= ch("scale");
d -= sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");  // d -= sin(d) warps distance field; fit() maps to [0,1] for chramp
```

### Ramp-driven displacement with fit [[Ep2, 59:44](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3584s)]
```vex
float d = length(@P);
d *= ch("scale");
d += 0;
d *= sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");  // d *= sin(d) self-modulates; fit clamps to [0,1] for chramp
```

### Ramp-driven height displacement [[Ep2, 62:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3774s)]
```vex
float d = length(@P);
d *= ch("scale");
d *= @Time;
d = sin(d);

@P.y = chramp("my-ramp", d);
@P.y *= ch("height");  // multiply d by @Time before sin() for time-varying oscillation
```

### Ramp-Driven Height Displacement [Needs Review] [[Ep2, 68:12](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4092s)]
```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d) * ch("height");  // double sin() creates interference; fit() normalizes for chramp
```

### Distance-Based Deformation with Ramps [[Ep2, 70:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4218s)]
```vex
float d = length(@P);
d *= ch('scale');
d *= sin(d);
d *= fit(d, -1, 1, 0, 1);
d = chramp('my-ramp', d);
@P.y *= ch('height');  // chain: sin -> fit normalize -> chramp shape; @P.y not reassigned from d
```

### Animated Radial Wave Pattern [[Ep2, 71:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4262s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');  // d %= 1 creates repeating concentric rings for chramp lookup
```

### Animated Radial Sine Wave [[Ep2, 71:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4274s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d = sin(d);
d = fit(d, -1, 0, 0, 1);
d = chramp('my_control_ramp', d);
@P.y += ch('height');  // fit(d,-1,0,0,1) maps only negative half of sine to [0,1]
```

### Distance-based height displacement with ramps [[Ep2, 74:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4472s)]
```vex
float d = length(@P);
v@Cd = ch('color');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
d = chramp('height', d);
@P.y *= ch('height');  // core pattern: distance -> sin -> fit [0,1] -> chramp -> scale
```

## Ramp-Driven Deformation

### Ramp-Driven Height Displacement [[Ep2, 99:42](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5982s)]
```vex
float d = length(@P);
d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;  // pre_scale controls ramp input range; post_scale multiplies ramp output
```

## Wave Deformation

### Point Displacement with Channels [[Ep2, 9:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=598s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d = @Time;
@P.y = sin(d);

@P += @N;

@P += @N * ch('push');  // progressive: d=@Time sine -> @N push -> @N*ch(push) controlled
```

### Distance-Based Displacement [[Ep3, 10:42](https://www.youtube.com/watch?v=fOasE4T9BRY&t=642s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = d;
@P.y = sin(d);  // @Cd = d visualizes distance; @P only writable in point context, not prim
```

### Distance to Surface Point [Needs Review] [[Ep3, 27:48](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1668s)]
```vex
vector pos = point(1, @P);
float d = distance(@P, pos);
d *= chf("M1");
@Cd.r = sin(d);  // point(1, @P) queries input 1 geometry; distance drives color visualization
```

### Sine Wave Color and Position [[Ep3, 7:26](https://www.youtube.com/watch?v=fOasE4T9BRY&t=446s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = @P;
@P.y = sin(d);  // @Cd = @P stores XYZ as RGB for spatial color visualization
```

### Applying Sine Wave to Position [[Ep3, 8:58](https://www.youtube.com/watch?v=fOasE4T9BRY&t=538s)]
```vex
float d = length(@P);
d *= ch('scale');
@P.y = sin(d);  // same as color calculation but applied to geometry: color -> deformation
```

## Ramp-Driven Deformation

### Relative BBox Deformation with Ramps [[Ep4, 52:42](https://www.youtube.com/watch?v=66WGmbykQhI&t=3162s)]
```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float k = chramp('inflate', bbox.y);
@P += @N * k * ch('scale');  // relpointbbox returns 0-1 coords; scale-independent unlike world @P
```

### Ramp-Driven Inflation Using Bounding Box [[Ep4, 53:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=3236s)]
```vex
vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');  // bbox.y: 0=bottom, 1=top; ramp replaces linear scale for artistic control
```

### Ramp-driven geometry deformation [[Ep4, 55:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=3300s)]
```vex
vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```
Uses a ramp parameter to control point displacement along the normal direction based on the point's relative Y position in the bounding box. The chramp function samples the ramp with the normalized bbox.y value (0-1), allowing for non-linear deformation profiles. This creates bulging or pinching effects on geometry by varying displacement strength across the vertical axis.

### Ramp-driven Geometry Inflation [[Ep4, 55:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=3316s)]
```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox;

vector bbox = relpointbbox(0, @P);
@Cd = @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
Demonstrates using a ramp parameter to control geometry inflation based on normalized bounding box position. The chramp() function samples a ramp using bbox.y (0-1 vertical position) as input, allowing non-linear scaling control. The geometry is inflated along normals with the ramp-modulated scale value, creating effects like variable bulging across the vertical axis.

### Normalized Bounding Box Deformation [[Ep4, 56:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=3376s)]
```vex
vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```
Uses relpointbbox() to get normalized bounding box coordinates (0-1 range) for each point's position, then applies deformation along the normal based on the Y-axis bbox value. A ramp parameter provides artistic control over the inflation profile, while a scale channel controls overall displacement intensity, creating effects like bulges or localized geometry inflation.

### Ramp-Driven Inflation Effect [[Ep4, 56:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=3414s)]
```vex
vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
Uses relpointbbox() to get normalized bounding box coordinates (0-1) and drives displacement along normals with a ramp parameter. The chramp() function samples the 'inflate' ramp using the Y-axis bbox coordinate, allowing for vertical gradients and precise control over the inflation effect at different heights.

### Relative Bounding Box Scaling [[Ep4, 57:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=3476s)]
```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
Uses relpointbbox to get normalized (0-1) bounding box coordinates for each point, making position-based effects scale-independent. The pattern progresses from visualizing the normalized Y coordinate as color, to using it for uniform displacement, to using it with a ramp for controlled inflation effects. This approach allows geometry of any size to be processed consistently since coordinates are relative to the bounding box rather than absolute world space.

### Relative Bounding Box Scaling [[Ep4, 58:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=3482s)]
```vex
vector bbox = relpointbbox(0,@P);
float t = chramp('inflate',bbox.y);
@P += @N * t * ch('scale');  // relpointbbox makes effect scale-independent; same ramp works on any geometry
```

### Relative Bounding Box Inflation [[Ep4, 58:24](https://www.youtube.com/watch?v=66WGmbykQhI&t=3504s)]
```vex
vector bbox = relbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```
Uses relbbox() to get normalized position within bounding box (0-1 space), then samples a ramp parameter based on the Y component to drive a displacement along normals. This makes effects scale-independent and transferable between different geometry, maintaining the same relative deformation regardless of the input geometry's absolute size.

## Wave Deformation

### Animated Ripple Waves from Points [[Ep5, 63:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3810s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, "P", pt);
d = distance(@P, pos);
w = d * d / ch('freq');
w = w - @Time * ch('speed');
w = sin(w);
w = w * ch('amp');
w = fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Creates animated ripple waves emanating from nearby points by calculating distance-based sine waves that progress over time. The frequency is controlled by distance squared, animated by subtracting time multiplied by speed, then modulated by amplitude and attenuated using fit to fade out at the radius boundary.

### Animated sine wave displacement [[Ep5, 63:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3814s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d * ch('freq') - @Time * ch('speed');
w = sin(w);
w = fit(w, -1, 1, ch('radius'), 1, 0);

@P.y += w;
```
Creates animated sine wave displacement by calculating distance to nearest point, modulating it with a frequency parameter and time-based speed control, then applying the result as vertical displacement. The subtraction of @Time * speed creates the wave progression animation, while fit() remaps the sine output to control amplitude based on distance from the nearest point.

### Animated sine wave ripples [Needs Review] [[Ep5, 66:20](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3980s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d * ch('freq');
w = @Frame * ch('speed');
w = sin(w);
w *= ch('amp');
w = fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Creates animated sine wave ripples by finding nearby points and using their distance to modulate a time-based sine wave that displaces points vertically. The wave amplitude is attenuated based on distance using fit(), and the animation is driven by @Frame. Multiple parameters control radius, frequency, speed, and amplitude of the ripples.

### Animated Sine Wave Ripples [[Ep5, 66:22](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3982s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, "P", pt);
d = distance(@P, pos);
w = d * ch('freq');
w = sin(w);
w = fit(w, -1, 1, ch('radius'), 1, 0);
@P.y += w;
```
Creates animated sine wave ripples emanating from nearby points by finding the nearest point, calculating distance-based sine waves controlled by frequency and radius parameters, and displacing points vertically. The frequency parameter controls wave density while radius affects both search distance and wave amplitude falloff.

### Wave Frequency and Radius Control [Needs Review] [[Ep5, 66:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3992s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('max_pt_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d * ch('freq');
d = sin(w);
w *= d;
@P.y += w;
```
Adjusts wave propagation by controlling frequency and radius parameters, demonstrating how higher frequency values can cause visual artifacts while lower frequencies produce smoother wave patterns. The code modifies the Y position based on sine wave calculations influenced by distance and frequency, though overlapping waves don't properly accumulate in this implementation.

### Fit and Sine Wave Deformation [[Ep5, 67:22](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4042s)]
```vex
v = fit(0, ch("radius"), 1, 0);
@P.y = sin(v) * 0.2;
```
Uses fit() to remap a value from 0 to a channel reference into a 0-1 range, then applies a sine wave to the Y position with a small amplitude. Higher geometry resolution is needed to avoid artifacts when deforming with high-frequency waves, as insufficient point density causes ugly angular deformation instead of smooth curves.

### Blending ripples with falloff [[Ep5, 69:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4170s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d / ch('from');
w = @Time * ch('speed');
w = sin(w);
w *= fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Extends the ripple effect to blend smoothly across multiple influence points by calculating a falloff weight based on distance. The fit() function creates a 0-1 falloff from the center to the radius edge, which is multiplied by the sinusoidal wave to create soft transitions between overlapping ripples. Using += instead of = allows multiple ripple influences to accumulate additively.

### Blending Multiple Ripple Effects [Needs Review] [[Ep5, 70:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4206s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

for(int i = 0; i < len(pts); i++) {
    pt = pts[i];
    pos = point(0, 'P', pt);
    d = distance(@P, pos);
    w = d * ch('freq');
    w += @Time * ch('speed');
    w = sin(w);
    w *= ch('amp');
    w *= fit(d, 0, ch('radius'), 1, 0);
    @P.y += w;
}

for(int i = 0; i < len(pts); i++) {
    pt = pts[i];
    pos = point(0, 'P', pt);
    d = distance(@P, pos);
    w = d * ch('freq');
    w += @Time * ch('speed');
    w = sin(w);
    w *= ch('amp');
    w *= fit(d, 0, ch('radius'), 1, 0);
    @P.y += w;  // += accumulates ripples from all pts; = overwrites and breaks blending
}
```

### Multi-Point Ripple Accumulation [[Ep5, 70:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4208s)]
```vex
v@pos = point(1, 'P', @ptnum);
f@d = distance(@P, v@pos);
v@w = f@d * ch('freq');
v@w -= @Time * ch('speed');
v@w = sin(v@w);
v@w *= fit(f@d, 0, ch('radius'), 1, 0);
@P.y = v@w;  // single ripple: assignment overwrites

// Multiple ripples: += accumulates across all source points
int pt = i[]@ps[0];
v@pos = point(1, 'P', pt);
f@d = distance(@P, v@pos);
float w = f@d * ch('freq');
w -= @Time * ch('speed');
w = sin(w);
w *= fit(f@d, 0, ch('radius'), 1, 0);
@P.y += w;  // += blends ripples from multiple pts beyond Voronoi boundaries
```

### Multi-Point Distance Blending [Needs Review] [[Ep5, 70:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4252s)]
```vex
v@P = set(i@ptnum, 0, 0);
pos = point(1, "P", i@ptnum);
d = distance(@P, pos);
freq = ch("freq");
w = d * cos(freq);
w = sin(w);
amp = ch("amp") * ch("speed");
w *= amp;
w *= fit(d, 0, ch("radius"), 1, 0);

pt = primpoint(1, 0, 0);
pos = point(1, "P", pt);
d = distance(@P, pos);
w = d * cos(freq);
w = sin(w);
amp = ch("amp") * ch("speed");
w *= amp;
w *= fit(d, 0, ch("radius"), 1, 0);
@P.y += w;
```
Demonstrates blending multiple distance-based wave influences by computing wave effects from multiple source points and accumulating them. The code calculates distance-based wave deformation from different primitive points, using falloff and frequency controls to blend the effects smoothly across the geometry.

### Scale Animation with Length and Fit [Needs Review] [[Ep6, 26:24](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1584s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Creates animated scaling effect on geometry by computing distance from origin using length(@P), adding time-based offset, applying sine wave, and fitting the result to min/max range. The scale vector is constructed with min on X and Z axes while the animated value d controls Y axis, creating vertical scaling animation. This demonstrates how Houdini uses Z-axis as the up direction for geometry.

### Vector Component Swapping for Scale [[Ep6, 26:26](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1586s)]
```vex
float min, max, d, f;
min = ch('min');
max = ch('max');
f = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
```
Demonstrates swapping vector components in the scale attribute to control which axis receives the animated scaling effect. The code uses distance from origin with sine wave animation, then constructs a scale vector with min on X, max on Y, and the animated value d on Z, causing boxes to scale along the Z-axis which is Houdini's default up axis.

### Animated Scale with Radial Wave [[Ep6, 28:52](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1732s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@Cd.y = d;
```
Creates an animated radial wave effect by calculating distance from origin, modulating it with time-based sine wave, and applying the result to point scale and color. The distance calculation combined with sine and fit functions produces concentric rings that expand outward over time, with scale varying primarily in one axis and green channel reflecting the wave amplitude.

## Ramp-Driven Deformation

### Packed Geometry with Scale and Color [Needs Review] [[Ep6, 29:56](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1796s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = fit01(v@pred);
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, min, max, 0, 1);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('cd', d));
```
Creates packed geometry instances with non-uniform scaling based on distance from origin and a predecessor attribute. Uses distance and fit operations to control per-axis scale values via the @scale attribute, adjusts point positions vertically, and applies color using a channel ramp. This approach efficiently handles hundreds of packed geometries instead of millions of points.

## Wave Deformation

### Animated Scale and Color with Packing [[Ep6, 30:04](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1804s)]
```vex
float min, max, d, t;
min = 0;
max = ch("max");
t = fit(v@P.x, ch("speed"));
d = length(@P);
d *= ch("frequency");
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp("color", d));
```
Creates animated wave pattern by computing distance from origin, modulating it with sine wave based on frequency and speed parameters, then applying results to non-uniform scale attribute and vertical position offset. The computed distance value is remapped and used to drive color via a ramp parameter, demonstrating integration with packed geometry instancing workflow.

### Scaling and displacement with color ramp [Needs Review] [[Ep6, 30:16](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1816s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d;
d = fit(d, min, max, 0, 1);
@Cd = chramp("color", d);
```
Creates animated scaling and vertical displacement based on distance from origin using sine waves. The displacement value is remapped to drive both the scale attribute (with min/max for x/y and calculated d for z) and a color ramp for point coloring. This builds on the previous snippet by adding position displacement and color ramping.

### Animated scaling with ground plane offset [[Ep6, 31:28](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1888s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Frame * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@Py += d/2;

float min, max, d, t;
min = ch('min');
max = ch('max');
t = @primnum * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@Py += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates animating copy-to-points geometry with sine wave-driven scaling while offsetting the Y position by half the calculated distance to anchor objects to the ground plane. The second variant uses @primnum instead of @Frame for per-primitive variation and adds color ramping based on the normalized distance value.

### Animating Up Vector with Time Offsets [[Ep6, 47:56](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2876s)]
```vex
v@up = set(sin(@Time), 0, cos(@Time));

v@up = set(sin(@Frame), 0, cos(@Frame));

float t = @Time - @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

float d = length(@P);
float t = @Time + d * ch("offset");
v@up = set(sin(t), 0, cos(t));
```
Demonstrates animating the up vector attribute to create spinning motion by using sine and cosine functions with time values. Progresses from global animation using @Time or @Frame to per-point offsets using @ptnum, and finally to distance-based offsets using point position and a channel parameter, creating wave-like spinning patterns across copied geometry.

### Animated Y displacement with up vector [Needs Review] [[Ep6, 52:16](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3136s)]
```vex
float d = length(@P);
float t = @Time + d*ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Calculates a time-varying Y displacement based on distance from origin, where each point oscillates at different phases determined by its distance. The up vector is set to rotate in the XZ plane using sine and cosine, while the Y position is offset by a sine wave scaled to ±0.5 units that oscillates twice as fast as the base time.

### Animated Wave Displacement with Up Vector [Needs Review] [[Ep6, 52:26](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3146s)]
```vex
float d = length(@P);
float blob = @Time + d * chf('offset');
v@up = set(sin(blob), 0, cos(blob));
@P.y += sin(blob * 2) * 0.5;
```
Creates an animated wave displacement by combining time and distance from origin. The sine function applied to the blob variable drives both a custom up vector and vertical position displacement, with the displacement multiplied by 2 to speed up the animation and scaled by 0.5 to limit amplitude to ±0.5 range.

### Instance Orientation with Up Vector [[Ep6, 53:32](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3212s)]
```vex
float d = length(@P);
float t = @Time * d - d * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Demonstrates animating instance orientation by setting the @up vector using time-based trigonometric functions, creating rotating instances. The position is also offset vertically with a wave motion that's double the frequency of the rotation, while the distance from origin modulates the animation timing.

### Animating up vector for instances [[Ep6, 53:36](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3216s)]
```vex
float d = length(@P);
float t = @Time * d * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates animated dancing instances by computing a time-based offset from point distance, then using sine and cosine to rotate the up vector in a circular pattern while simultaneously offsetting point Y positions. The up vector combined with the normal vector defines the orientation of instanced geometry.

### Animating up vector for instance orientation [[Ep6, 53:38](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3218s)]
```vex
float d = length(@P);
float t = @Time*ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Demonstrates animating an up vector for controlling instance orientations using trigonometric functions. The up vector rotates in the XZ plane over time while the Y position oscillates, allowing instances to maintain proper orientation as they move. This approach uses both the up vector and normal vector to define where instances are positioned and how they're rotated.

### Animated Circle with Up Vector [[Ep6, 56:22](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3382s)]
```vex
float d = length(@P);
float t = @Time * d * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates an animated circular pattern by calculating distance-based time offset and using trigonometric functions to set both the up vector rotation and vertical displacement. The up vector rotates around the Y-axis based on the animated time value, while the Y position oscillates at twice the frequency.

### Time-Based Wave with Offset [[Ep6, 56:42](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3402s)]
```vex
float d = length(@P);
float t = @Time * (1-@offset);
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * d;
```
Creates a time-animated wave effect that varies by distance from origin, using an offset attribute to control timing. The code calculates distance-based amplitude modulation, sets a rotating up vector, and applies a vertical sine wave displacement that oscillates at twice the offset-modified time rate.

### Circular Path with Sine and Cosine [[Ep8, 35:06](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2106s)]
```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);

@P = primv(1, 'P', 0, uv);
@N = primv(1, 'N', 0, uv);
```
Creates circular motion by using sine and cosine functions on the same time value for UV coordinates, then uses fit() to scale the range from [-1,1] to [-0.2,0.2]. The scaled UV coordinates are used with primv() to sample position and normal attributes from the second input, creating a point that moves in a circular path across a primitive's parametric space.

## See Also
- **VEX Common Patterns** (`vex_patterns.md`) -- deformation pattern recipes
