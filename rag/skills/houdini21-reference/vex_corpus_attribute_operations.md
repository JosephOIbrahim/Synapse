# VEX Corpus: Attribute Operations

> 55 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (19 examples)

### Implicit vs explicit attribute type â

```vex
// BAD
@Cd = @mycolour; // This will treat it as a float and only read the first value (ie, just the red channel of @mycolour)

// GOOD
@Cd = v@mycolour; // Explicitly tells the wrangle that its a vector.
```

Note that wrangles implicitly know certain common attribute types (@P, @Cd, @N, @v, @orient, @id, @name, several others), but if you have your own attributes, Houdini will assume its a float unless....

### Get attributes from other inputs â

```vex
vector otherP = point(1,"P", @ptnum);
// do something with it
```

As mentioned earlier, you have 2 similar meshes feeding into the one wrangle, and you want to access the matching P of the 2nd mesh:

An alternative method is to prefix the attribute you want with ....

### CamelCase to snake_case with regex and re_replace â

```vex
string a = 'thisAttributeName';
    a = re_replace('(?<!^)(?=[A-Z])', '_', a);
    a = tolower(a);
    // a is now 'this_attribute_name'
```

Had some attributes in a csv saved as camel case like 'thisAttributeName', I needed to convert to snake case like 'this_attribute_name'.

Stackoverflow had a python example, was pleased that vex's ....

### Vector Subtraction Setup

```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@N = b - a;

vector a = @P;
vector h = point(1, "P", 0);
```

Demonstrates setting up vector subtraction between two points by reading their positions from different input geometries.

### Vector Subtraction Between Points

```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@N = b - a;

vector a = @P;
vector b = point(1, "P", 0);
```

Demonstrates vector subtraction by reading positions from two different input points using the point() function.

### Vector Subtraction with Points

```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@i = b - a;

vector a = @P;
vector b = point(1, "P", 0);
```

Demonstrates vector subtraction by reading positions from two different input points using the point() function.

### Vector Subtraction Direction

```vex
vector a = point(0, "P", @ptnum);
vector b = point(1, "P", @ptnum);

@N = b - a;

// Alternative: using current point position
vector a = @P;
vector b = point(1, "P", @ptnum);
```

Subtracting vectors creates a direction vector pointing from the first vector to the second.

### Vectors Pointing Away from Point

```vex
vector a = {0};
vector b = point(1, "P", 0);

@N = a - b;
```

Creates vectors pointing away from a specific point by reversing the subtraction order.

### Velocity from Origin Point

```vex
vector origin = point(1, 'P', 0);
@v = -origin;
```

Reads the position of point 0 from the second input and sets the velocity vector to point away from that origin position.

### Normal Vector From Two Points

```vex
vector a = {0};
vector b = point(1, "P", 0);

@N = a-b;
```

Creates a normal vector by subtracting the position of point 0 from the second input (point 1) from the origin vector.

### Vector Subtraction for Normal Calculation

```vex
vector a = {0};
vector b = point(1, 'P', 0);

@N = a-b;
```

Calculates a normal vector by subtracting point position from a reference point at the origin.

### Vector Multiplication Setup

```vex
vector a = @P;
vector b = point(1, "P", 0);

@N = a + b;
```

This code demonstrates setting up vectors for a multiplication operation by storing the current point position in vector 'a' and fetching point 0's position from input 1 into vector 'b'.

### VOP Input Parameter Shorthand

```vex
@P = point(1, 'P', @ptnum);

@vopinput1_P;
```

Demonstrates using the @vopinput syntax as a shorthand to access input geometry attributes in VEX.

### Reading Points from Second Input

```vex
@P = point(1, 'P', @ptnum);

@opinput1_P;
```

Demonstrates two methods for reading point positions from the second input: using the point() function with input index 1, and using the @opinput1_P syntax which is shorthand for accessing attribut....

### Reading Point Positions with point()

```vex
vector a = @P;
vector b = point(1, 'P', 0);
```

Demonstrates two methods of accessing point positions: using the @P attribute binding for the current point, and using the point() function to read the position of a specific point (point 0) from i....

### Reading point positions from multiple inputs

```vex
vector a = @P;
vector b = point(1, "P", 0);
```

Demonstrates reading point positions from different inputs in a wrangle node.

### Vector Subtraction for Direction

```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@N = b - a;

// Alternative: using current point
vector a = @P;
vector b = point(1, "P", 0);
```

Demonstrates how subtracting vectors creates a direction vector from point A to point B.

### Vector Subtraction for Direction

```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;
```

Demonstrates vector subtraction to calculate direction from one point to another.

### Setting Velocity from Origin

```vex
vector origin = point(1, 'P', 0);
@v = @origin;
```

Reads the position of point 0 from input 1 and assigns it directly to the velocity attribute.

## Intermediate (36 examples)

### Vector subtraction â

```vex
vector a = point(0,'P',0);
vector b = point(1,'P',0);

@N = b-a;
```

The textbook definition of vector subtraction is.

### Reading points from multiple inputs

```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@i = b - a;

vector a = point(0, 0, "P", 0);
vector b = point(1, 0, "P", 0);

// ...
```

Demonstrates reading point positions from multiple wrangle inputs using the point() function with different input indices.

### Vector subtraction pointing direction

```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;

vector a = @P;
vector b = point(1, 'P', 0);

// ...
```

Demonstrates vector subtraction to create a direction vector from one point to another.

### Vector Subtraction for Direction

```vex
vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;

// Alternative: vectors pointing away from origin
vector origin = point(1, 'P', 0);
@v = @P - origin;
// ...
```

Demonstrates using vector subtraction to create vectors that point from each point toward (or away from) a specific reference point in space.

### Direct Point Attribute Access

```vex
@P = point(1, 'P', @ptnum);

@P = @opinput1_P;
```

Demonstrates two equivalent methods for directly copying point positions from the second input.

### Point Function with Input Index

```vex
@P = point(1, 'P', @ptnum);
```

The point() function can read attributes from a specific input by using an input index as the first argument.

### Point-to-Point Normal Direction

```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;

// Alternative using current point
vector a = @P;
vector b = point(1, 'P', 0);
// ...
```

Demonstrates calculating a normal vector by subtracting two point positions.

### Point Cloud Weighted Color Accumulation

```vex
//first point
int pt0 = pts[0];
vector pos = point(0, "P", pt0);
vector col = point(0, "Cd", pt0);
float d = rint(pos, pcol);
d = clamp(d, 0, s);
gcd += col * d;

// ...
```

This code reads position and color attributes from the first two points in a nearby points array, calculates a distance-based weight using rint(), clamps the weight to a valid range, and accumulate....

### chattr

```vex
intsuccess=0intinput=0;stringattrname="export";stringattrclass="channel";intchannel=0;// Or use C global variable for current channel index.intsample= -1;// Or use I global variable for current sample index.strings=chattr(input,attrname,attrclass,channel,sample,success)if(success){// Do something with sprintf("s=%s\n",s);}else{// Couldn't read attribute, usually because an attribute with that// name doesn't exist}
```

Signature: intsuccess=0intinput=0;stringattrname="export";stringattrclass="channel";intchannel=0;// Or use C global variable for current channel index.intsample= -1;// Or use I global variable for ....

### forpoints

```vex
forpoints(position[,distance] ){}
```

Signature: forpoints(position[,distance] ){}

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates an array from its arguments.

### hasdetailattrib

```vex
intexists;// Determine if the P attribute exists.exists=hasdetailattrib("defgeo.bgeo","P");
```

Signature: intexists;// Determine if the P attribute exists.exists=hasdetailattrib("defgeo.bgeo","P");

When running in the context of a node (such as a wrangle SOP), this argument can be an intege....

### haspointattrib

```vex
// Determine if the P attribute exists.intexists=haspointattrib("defgeo.bgeo","P");
```

Signature: // Determine if the P attribute exists.intexists=haspointattrib("defgeo.bgeo","P");

When running in the context of a node (such as a wrangle SOP), this argument can be an integer repres....

### hasprimattrib

```vex
// Determine if the P attribute exists.intexists=hasprimattrib("defgeo.bgeo","P");
```

Signature: // Determine if the P attribute exists.intexists=hasprimattrib("defgeo.bgeo","P");

When running in the context of a node (such as a wrangle SOP), this argument can be an integer represe....

### hasvertexattrib

```vex
// Determine if the P attribute exists.intexists=hasvertexattrib("defgeo.bgeo","P");
```

Signature: // Determine if the P attribute exists.intexists=hasvertexattrib("defgeo.bgeo","P");

When running in the context of a node (such as a wrangle SOP), this argument can be an integer repre....

### len

```vex
len("hello") ==5;len({{1,0,0},{0,1,0},{0,0,1}}) ==9;len({0,10,20,30}) ==4;
```

Signature: len("hello") ==5;len({{1,0,0},{0,1,0},{0,0,1}}) ==9;len({0,10,20,30}) ==4;

Returns the number of items/components in the given object.

### makevalidvarname

```vex
// Returns "foo_bar"strings=makevalidvarname("foo:bar");// Returns "_123"s=makevalidvarname("123");// Returns "foo:_bar"s=makevalidvarname("foo:?bar",":");
```

Signature: // Returns "foo_bar"strings=makevalidvarname("foo:bar");// Returns "_123"s=makevalidvarname("123");// Returns "foo:_bar"s=makevalidvarname("foo:?bar",":");

String that should be turned ....

### osd_limit

```vex
intnpatches=osd_patchcount(file);for(intpatch=0;patch<npatches;patch++){for(intv=0;v<100;v++){vectorP,du,dv,duu,duv,dvv;if(osd_limit(file,"P",patch,nrandom(),nrandom(),P,du,dv,duu,duv,dvv)){intptid=addpoint(geohandle,P);setpointattrib(0,"du",ptid,du);setpointattrib(0,"dv",ptid,dv);setpointattrib(0,"duu",ptid,duu);setpointattrib(0,"duv",ptid,duv);setpointattrib(0,"dvv",ptid,dvv);}}}
```

Signature: intnpatches=osd_patchcount(file);for(intpatch=0;patch<npatches;patch++){for(intv=0;v<100;v++){vectorP,du,dv,duu,duv,dvv;if(osd_limit(file,"P",patch,nrandom(),nrandom(),P,du,dv,duu,duv,dv....

### pointprimuv

```vex
intprims[] =pointprims(file,ptnum);if(len(prims)){intprimnum=prims[0];floatprim_u,prim_v;if(pointprimuv(file,ptnum,primnum,prim_u,prim_v)){intpatch_id;floatpatch_u,patch_v;osd_lookuppatch(file,primnum,prim_u,prim_v,patch_id,patch_u,patch_v);vectorP,du,dv,duu,duv,dvv;if(osd_limit(file,"P",patch_id,patch_u,patch_v,P,du,dv,duu,duv,dvv)){setpointattrib(file,"P",ptnum,P);setpointattrib(file,"du",ptnum,du);setpointattrib(file,"dv",ptnum,dv);setpointattrib(file,"duu",ptnum,duu);setpointattrib(file,"duv",ptnum,duv);setpointattrib(file,"dvv",ptnum,dvv);}}}
```

Signature: intprims[] =pointprims(file,ptnum);if(len(prims)){intprimnum=prims[0];floatprim_u,prim_v;if(pointprimuv(file,ptnum,primnum,prim_u,prim_v)){intpatch_id;floatpatch_u,patch_v;osd_lookuppatc....

### removevalue

```vex
floatnums[] ={0,1,2,3,1,2,3};removevalue(nums,2);// == 1// nums == {0, 1, 3, 1, 2, 3}
```

Signature: floatnums[] ={0,1,2,3,1,2,3};removevalue(nums,2);// == 1// nums == {0, 1, 3, 1, 2, 3}

Removes the first instance ofvaluefound from the array.

### sort

```vex
intnumbers[] ={5,2,90,3,1};intdescending_nums[] =reverse(sort(numbers));// {90, 5, 3, 2, 1}
```

Signature: intnumbers[] ={5,2,90,3,1};intdescending_nums[] =reverse(sort(numbers));// {90, 5, 3, 2, 1}

argsortandsortuse a stable sort.

Usereverseto reverse the order of the sort.

### usd_attrib

```vex
// Get the value of some attributes on the cube primitive.floata=usd_attrib("opinput:0","/geo/cube","attribute_name_a");vectorb[] =usd_attrib(0,"/geo/cube","attribute_name_b");// Get the value of attribute "bar" at various time codes.f[]@b_at_current_frame=usd_attrib(0,"/geo/sphere","bar");f[]@b_at_frame_7=usd_attrib(0,"/geo/sphere","bar",7.0);
```

Signature: // Get the value of some attributes on the cube primitive.floata=usd_attrib("opinput:0","/geo/cube","attribute_name_a");vectorb[] =usd_attrib(0,"/geo/cube","attribute_name_b");// Get the....

### usd_attribelement

```vex
// Get the value of an element at index 3 in the array attribute.floata=usd_attribelement("opinput:0","/geo/cube","array_attrib_name",3);// Get the value of an element at index 2 of the "bar" array attribute.@b_element_2_at_current_frame=usd_attribelement(0,"/geo/sphere","bar",2);@b_element_2_at_frame_11=usd_attribelement(0,"/geo/sphere","bar",2,11.0);
```

Signature: // Get the value of an element at index 3 in the array attribute.floata=usd_attribelement("opinput:0","/geo/cube","array_attrib_name",3);// Get the value of an element at index 2 of the ....

### usd_attriblen

```vex
// Get the array length of an attribute on the cube primitive.intlength=usd_attriblen(0,"/geo/cube","attribute_name");
```

Signature: // Get the array length of an attribute on the cube primitive.intlength=usd_attriblen(0,"/geo/cube","attribute_name");

When running in the context of a node (such as a wrangle LOP), thi....

### usd_attribnames

```vex
// Get the attribute names from the primitive.stringattrib_names[] =usd_attribnames(0,"/geo/sphere");
```

Signature: // Get the attribute names from the primitive.stringattrib_names[] =usd_attribnames(0,"/geo/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be....

### usd_attribsize

```vex
// Get the tuple size of an attribute on the cube primitive.inttuple_size=usd_attribsize(0,"/geo/cube","attribute_name");
```

Signature: // Get the tuple size of an attribute on the cube primitive.inttuple_size=usd_attribsize(0,"/geo/cube","attribute_name");

When running in the context of a node (such as a wrangle LOP), ....

### usd_attribtypename

```vex
// Get the type name of the attribute.stringtype_name=usd_attribtypename(0,"/geo/cube","attribute_name");
```

Signature: // Get the type name of the attribute.stringtype_name=usd_attribtypename(0,"/geo/cube","attribute_name");

When running in the context of a node (such as a wrangle LOP), this argument ca....

### usd_blockattrib

```vex
// Block the attribute.usd_blockattrib(0,"/geo/sphere","attribute_name");
```

Signature: // Block the attribute.usd_blockattrib(0,"/geo/sphere","attribute_name");

A handle to the stage to write to.

### usd_isarraymetadata

```vex
// Check if the metadata is an array.intis_array=usd_isarraymetadata(0,"/geo/sphere","documentation");intis_array_too=usd_isarraymetadata(0,"/geo/cube","customData:foo:bar");
```

Signature: // Check if the metadata is an array.intis_array=usd_isarraymetadata(0,"/geo/sphere","documentation");intis_array_too=usd_isarraymetadata(0,"/geo/cube","customData:foo:bar");

When runni....

### usd_isattrib

```vex
// Check if the sphere has an attribute "some_attribute".intis_valid_attrib=usd_isattrib(0,"/geometry/sphere","some_attribute");
```

Signature: // Check if the sphere has an attribute "some_attribute".intis_valid_attrib=usd_isattrib(0,"/geometry/sphere","some_attribute");

When running in the context of a node (such as a wrangle....

### usd_iscollection

```vex
// Check if cube has a collection "some_collection".stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");intis_collection_existing=usd_iscollection(0,collection_path);
```

Signature: // Check if cube has a collection "some_collection".stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");intis_collection_existing=usd_iscollection(0,collection_....

### usd_isprim

```vex
// Check if the stage coming on the first input has a sphere primitive// at scene graph location "/geometry/sphere".intis_valid_primitive=usd_isprim(0,"/geometry/sphere");
```

Signature: // Check if the stage coming on the first input has a sphere primitive// at scene graph location "/geometry/sphere".intis_valid_primitive=usd_isprim(0,"/geometry/sphere");

When running ....

### usd_makeattribpath

```vex
// Obtain the full path to the attribute "attrib_name" on the cube primitive.stringattrib_path=usd_makeattribpath(0,"/geo/cube","attrib_name");
```

Signature: // Obtain the full path to the attribute "attrib_name" on the cube primitive.stringattrib_path=usd_makeattribpath(0,"/geo/cube","attrib_name");

When running in the context of a node (su....

### usd_primvarattribname

```vex
// Get the attribute name for the given primvar.stringattrib_name=usd_primvarattribname(0,"some_primvar");intis_attrib=usd_isattrib(0,"/geo/sphere",attrib_name);
```

Signature: // Get the attribute name for the given primvar.stringattrib_name=usd_primvarattribname(0,"some_primvar");intis_attrib=usd_isattrib(0,"/geo/sphere",attrib_name);

When running in the con....

### usd_setattrib

```vex
// Set the value of some attributes.usd_setattrib(0,"/geo/sphere","float_attrib",0.25);usd_setattrib(0,"/geo/sphere","string_attrib","foo bar baz");usd_setattrib(0,"/geo/sphere","vector_attrib",{1.25,1.50,1.75});floatf_arr[] ={0,0.25,0.5,0.75,1};usd_setattrib(0,"/geo/sphere","float_array_attrib",f_arr);
```

Signature: // Set the value of some attributes.usd_setattrib(0,"/geo/sphere","float_attrib",0.25);usd_setattrib(0,"/geo/sphere","string_attrib","foo bar baz");usd_setattrib(0,"/geo/sphere","vector_....

### usd_setattribelement

```vex
// Set the value of element at index 2 in the array attribute.usd_setattribelement(0,"/geo/sphere","float_array_attrib",2,0.25);
```

Signature: // Set the value of element at index 2 in the array attribute.usd_setattribelement(0,"/geo/sphere","float_array_attrib",2,0.25);

A handle to the stage to write to.

### usd_setmetadata

```vex
// Set a documentation string on the sphere.usd_setmetadata(0,"/geo/sphere","documentation","This is new documentation.");// Set the value of some custom data on the sphere.usd_setmetadata(0,"/geo/sphere","customData:a_float",0.25);usd_setmetadata(0,"/geo/sphere","customData:a_string","foo bar baz");usd_setmetadata(0,"/geo/sphere","customData:a_vector",{1.25,1.50,1.75});floatf_arr[] ={0,0.25,0.5,0.75,1};usd_setmetadata(0,"/geo/sphere","customData:a_float_array",f_arr);// Set the metadata value on an attribute.stringattrib_path=usd_makeattribpath(0,"/geo/sphere","attrib_name");sd_setmetadata(0,attrib_path,"customData:foo",1.25);
```

Signature: // Set a documentation string on the sphere.usd_setmetadata(0,"/geo/sphere","documentation","This is new documentation.");// Set the value of some custom data on the sphere.usd_setmetada....
