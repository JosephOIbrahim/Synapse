# VEX Corpus: Attribute Operations

> 55 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (19 examples)
### Implicit vs explicit attribute type
```vex
// BAD: treats @mycolour as float, reads only the red channel
@Cd = @mycolour;

// GOOD: v@ prefix tells the wrangle it is a vector
@Cd = v@mycolour;
// Common attribute types (@P, @Cd, @N, @v, @orient, @id, @name) are implicitly typed. Custom attributes default to float unless prefixed.
```
### Get attributes from other inputs
```vex
// Read matching point position from second input (input index 1)
vector otherP = point(1, "P", @ptnum);
```
### CamelCase to snake_case with regex and re_replace
```vex
string a = 'thisAttributeName';
a = re_replace('(?<!^)(?=[A-Z])', '_', a);
a = tolower(a);
// a is now 'this_attribute_name'
```
### Vector Subtraction Setup
```vex
// Read positions from two different inputs
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

// Direction from a to b
@N = b - a;
```
### Vector Subtraction Between Points
```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

// b - a produces a vector pointing from a toward b
@N = b - a;
```
### Vector Subtraction with Points
```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@i = b - a;
```
### Vector Subtraction Direction
```vex
// Using explicit point indices
vector a = point(0, "P", @ptnum);
vector b = point(1, "P", @ptnum);
@N = b - a;

// Alternative: use current point position as base
vector base = @P;
vector target = point(1, "P", @ptnum);
@N = target - base;
```
### Vectors Pointing Away from Point
```vex
// Reverse subtraction order to point away from origin
vector a = {0};
vector b = point(1, "P", 0);

@N = a - b;
```
### Velocity from Origin Point
```vex
// Point velocity away from a reference origin
vector origin = point(1, 'P', 0);
@v = -origin;
```
### Normal Vector From Two Points
```vex
vector a = {0};
vector b = point(1, "P", 0);

@N = a - b;
```
### Vector Subtraction for Normal Calculation
```vex
vector a = {0};
vector b = point(1, 'P', 0);

@N = a - b;
```
### Vector Multiplication Setup
```vex
vector a = @P;
vector b = point(1, "P", 0);

@N = a + b;
```
### VOP Input Parameter Shorthand
```vex
// Explicit form using point()
@P = point(1, 'P', @ptnum);

// Shorthand using @vopinput syntax
@vopinput1_P;
```
### Reading Points from Second Input
```vex
// Using point() with input index
@P = point(1, 'P', @ptnum);

// Equivalent shorthand
@opinput1_P;
```
### Reading Point Positions with point()
```vex
// Current point position
vector a = @P;

// Specific point from second input
vector b = point(1, 'P', 0);
```
### Reading point positions from multiple inputs
```vex
// Input 0 (first input)
vector a = @P;

// Input 1 (second input), point 0
vector b = point(1, "P", 0);
```
### Vector Subtraction for Direction
```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

// b - a points from a toward b
@N = b - a;

// Alternative: current point as base
vector cur = @P;
vector ref = point(1, "P", 0);
@N = ref - cur;
```
### Vector Subtraction for Direction (single input)
```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;
```
### Setting Velocity from Origin
```vex
// Read position from input 1 and assign directly to velocity
vector origin = point(1, 'P', 0);
@v = @origin;
```

## Intermediate (36 examples)
### Vector subtraction
```vex
// Textbook vector subtraction: direction from a to b
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;
```
### Reading points from multiple inputs
```vex
// Input 0 and input 1, point 0
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@i = b - a;

// Alternative: explicit 4-argument form
vector c = point(0, 0, "P", 0);
vector d = point(1, 0, "P", 0);
```
### Vector subtraction pointing direction
```vex
// Direction from input 0 to input 1
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);
@N = b - a;

// Using current point as start
vector cur = @P;
vector ref = point(1, 'P', 0);
@N = ref - cur;
```
### Vector Subtraction for Direction
```vex
vector a = @P;
vector b = point(1, 'P', 0);
@N = b - a;

// Vectors pointing away from origin
vector origin = point(1, 'P', 0);
@v = @P - origin;
```
### Direct Point Attribute Access
```vex
// Explicit form
@P = point(1, 'P', @ptnum);

// Equivalent shorthand
@P = @opinput1_P;
```
### Point Function with Input Index
```vex
// First argument is input index (0-based)
@P = point(1, 'P', @ptnum);
```
### Point-to-Point Normal Direction
```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);
@N = b - a;

// Alternative using current point
vector cur = @P;
vector ref = point(1, 'P', 0);
@N = ref - cur;
```
### Point Cloud Weighted Color Accumulation
```vex
// Accumulate weighted color from nearby points
int pt0 = pts[0];
vector pos = point(0, "P", pt0);
vector col = point(0, "Cd", pt0);
float d = rint(pos, pcol);
d = clamp(d, 0, s);
gcd += col * d;
```
### chattr
```vex
// Read a channel attribute by name, class, index, and sample
int success = 0;
int input = 0;
string attrname = "export";
string attrclass = "channel";
int channel = 0;   // or use C global for current channel index
int sample = -1;   // or use I global for current sample index

string s = chattr(input, attrname, attrclass, channel, sample, success);

if (success) {
    // Do something with s
    printf("s=%s\n", s);
} else {
    // Attribute not found
}
```
### forpoints
```vex
// Iterate over all points within a radius
forpoints(position [, distance]) {
    // body executes for each point in range
}
```
### hasdetailattrib
```vex
// Determine if the P attribute exists on a detail
int exists;
exists = hasdetailattrib("defgeo.bgeo", "P");

// Inside a wrangle: use integer input index
exists = hasdetailattrib(0, "P");
```
### haspointattrib
```vex
// Check whether a point attribute exists
int exists = haspointattrib("defgeo.bgeo", "P");

// Inside a wrangle SOP:
exists = haspointattrib(0, "myattr");
```
### hasprimattrib
```vex
// Check whether a primitive attribute exists
int exists = hasprimattrib("defgeo.bgeo", "P");

// Inside a wrangle SOP:
exists = hasprimattrib(0, "name");
```
### hasvertexattrib
```vex
// Check whether a vertex attribute exists
int exists = hasvertexattrib("defgeo.bgeo", "P");

// Inside a wrangle SOP:
exists = hasvertexattrib(0, "uv");
```
### len
```vex
// Length of string
len("hello") == 5;

// Total components in a matrix (3x3 = 9)
len({{1,0,0},{0,1,0},{0,0,1}}) == 9;

// Length of an array
len({0, 10, 20, 30}) == 4;
```
### makevalidvarname
```vex
// Colons replaced with underscores
string s = makevalidvarname("foo:bar");
// s == "foo_bar"

// Leading digits get underscore prefix
s = makevalidvarname("123");
// s == "_123"

// Custom allowed separators
s = makevalidvarname("foo:?bar", ":");
// s == "foo:_bar"
```
### osd_limit
```vex
// Evaluate OpenSubdiv limit surface for all patches
int npatches = osd_patchcount(file);

for (int patch = 0; patch < npatches; patch++) {
    for (int v = 0; v < 100; v++) {
        vector P, du, dv, duu, duv, dvv;
        if (osd_limit(file, "P", patch, nrandom(), nrandom(),
                      P, du, dv, duu, duv, dvv)) {
            int ptid = addpoint(geohandle, P);
            setpointattrib(0, "du",  ptid, du);
            setpointattrib(0, "dv",  ptid, dv);
            setpointattrib(0, "duu", ptid, duu);
            setpointattrib(0, "duv", ptid, duv);
            setpointattrib(0, "dvv", ptid, dvv);
        }
    }
}
```
### pointprimuv
```vex
// Look up OSD limit surface at a point's UV location
int prims[] = pointprims(file, ptnum);
if (len(prims)) {
    int primnum = prims[0];
    float prim_u, prim_v;
    if (pointprimuv(file, ptnum, primnum, prim_u, prim_v)) {
        int patch_id;
        float patch_u, patch_v;
        osd_lookuppatch(file, primnum, prim_u, prim_v,
                        patch_id, patch_u, patch_v);
        vector P, du, dv, duu, duv, dvv;
        if (osd_limit(file, "P", patch_id, patch_u, patch_v,
                      P, du, dv, duu, duv, dvv)) {
            setpointattrib(file, "P",   ptnum, P);
            setpointattrib(file, "du",  ptnum, du);
            setpointattrib(file, "dv",  ptnum, dv);
            setpointattrib(file, "duu", ptnum, duu);
            setpointattrib(file, "duv", ptnum, duv);
            setpointattrib(file, "dvv", ptnum, dvv);
        }
    }
}
```
### removevalue
```vex
float nums[] = {0, 1, 2, 3, 1, 2, 3};

// Removes only the FIRST occurrence of 2
removevalue(nums, 2);
// return value == 1 (one item removed)
// nums == {0, 1, 3, 1, 2, 3}
```
### sort
```vex
int numbers[] = {5, 2, 90, 3, 1};

// Sort ascending, then reverse for descending
int descending_nums[] = reverse(sort(numbers));
// descending_nums == {90, 5, 3, 2, 1}
```
### usd_attrib
```vex
// Read a float attribute from a USD prim
float a = usd_attrib("opinput:0", "/geo/cube", "attribute_name_a");

// Read a vector array attribute using integer input index
vector b[] = usd_attrib(0, "/geo/cube", "attribute_name_b");

// Read attribute at the current frame
f[] @ b_at_current_frame = usd_attrib(0, "/geo/sphere", "bar");

// Read attribute at a specific time code (frame 7)
f[] @ b_at_frame_7 = usd_attrib(0, "/geo/sphere", "bar", 7.0);
```
### usd_attribelement
```vex
// Read element at index 3 from an array attribute
float a = usd_attribelement("opinput:0", "/geo/cube", "array_attrib_name", 3);

// Read element at index 2 at the current frame
@b_element_2_at_current_frame = usd_attribelement(0, "/geo/sphere", "bar", 2);

// Read element at index 2 at frame 11
@b_element_2_at_frame_11 = usd_attribelement(0, "/geo/sphere", "bar", 2, 11.0);
```
### usd_attriblen
```vex
// Get the array length of an attribute on a USD prim
int length = usd_attriblen(0, "/geo/cube", "attribute_name");
```
### usd_attribnames
```vex
// List all attribute names on a USD prim
string attrib_names[] = usd_attribnames(0, "/geo/sphere");
```
### usd_attribsize
```vex
// Get the tuple size (e.g. 3 for a vector) of an attribute
int tuple_size = usd_attribsize(0, "/geo/cube", "attribute_name");
```
### usd_attribtypename
```vex
// Get the USD type name string for an attribute
string type_name = usd_attribtypename(0, "/geo/cube", "attribute_name");
```
### usd_blockattrib
```vex
// Block (opinion-block) an attribute so it is invisible to downstream prims
usd_blockattrib(0, "/geo/sphere", "attribute_name");
```
### usd_isarraymetadata
```vex
// Check whether metadata value is an array
int is_array     = usd_isarraymetadata(0, "/geo/sphere", "documentation");
int is_array_too = usd_isarraymetadata(0, "/geo/cube",   "customData:foo:bar");
```
### usd_isattrib
```vex
// Check whether a named attribute exists on a USD prim
int is_valid_attrib = usd_isattrib(0, "/geometry/sphere", "some_attribute");
```
### usd_iscollection
```vex
// Build the collection path, then check if it exists
string collection_path      = usd_makecollectionpath(0, "/geo/cube", "some_collection");
int    is_collection_existing = usd_iscollection(0, collection_path);
```
### usd_isprim
```vex
// Check whether a prim exists at a given scene graph location
int is_valid_primitive = usd_isprim(0, "/geometry/sphere");
```
### usd_makeattribpath
```vex
// Build the full attribute path string for a prim + attribute name
string attrib_path = usd_makeattribpath(0, "/geo/cube", "attrib_name");
```
### usd_primvarattribname
```vex
// Get the internal attribute name for a named primvar
string attrib_name = usd_primvarattribname(0, "some_primvar");

// Use the result to check existence
int is_attrib = usd_isattrib(0, "/geo/sphere", attrib_name);
```
### usd_setattrib
```vex
// Set scalar attributes
usd_setattrib(0, "/geo/sphere", "float_attrib",  0.25);
usd_setattrib(0, "/geo/sphere", "string_attrib", "foo bar baz");
usd_setattrib(0, "/geo/sphere", "vector_attrib", {1.25, 1.50, 1.75});

// Set an array attribute
float f_arr[] = {0, 0.25, 0.5, 0.75, 1};
usd_setattrib(0, "/geo/sphere", "float_array_attrib", f_arr);
```
### usd_setattribelement
```vex
// Set one element (index 2) of an existing array attribute
usd_setattribelement(0, "/geo/sphere", "float_array_attrib", 2, 0.25);
```
### usd_setmetadata
```vex
// Set a documentation string on the sphere prim
usd_setmetadata(0, "/geo/sphere", "documentation", "This is new documentation.");

// Set custom data values of various types
usd_setmetadata(0, "/geo/sphere", "customData:a_float",  0.25);
usd_setmetadata(0, "/geo/sphere", "customData:a_string", "foo bar baz");
usd_setmetadata(0, "/geo/sphere", "customData:a_vector", {1.25, 1.50, 1.75});

// Array custom data
float f_arr[] = {0, 0.25, 0.5, 0.75, 1};
usd_setmetadata(0, "/geo/sphere", "customData:a_float_array", f_arr);

// Set metadata on an attribute path (not a prim path)
string attrib_path = usd_makeattribpath(0, "/geo/sphere", "attrib_name");
usd_setmetadata(0, attrib_path, "customData:foo", 1.25);
```
