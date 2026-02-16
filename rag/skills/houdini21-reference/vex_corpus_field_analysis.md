# VEX Corpus: Field Analysis

> 15 examples from vex-corpus. Sources: sidefx-vex-reference

## Intermediate (15 examples)

### attribtype

```vex
// Get the type of the position attribute of "defgeo.bgeo"inttype=attribtype("defgeo.bgeo","point","P");
```

Signature: // Get the type of the position attribute of "defgeo.bgeo"inttype=attribtype("defgeo.bgeo","point","P");

When running in the context of a node (such as a wrangle SOP), this argument can....

### expand_udim

```vex
// sprintf() will leave the %(UDIM)d format sequence unmodified.stringmap=sprintf("%s/%s_%(UDIM)d.rat",texture_path,texture_base);// Expand the <UDIM>, returning an empty string if the map doesn't exist.map=expand_udim(u,v,map);if(map!="")Cf=texture(map,u,v);
```

Signature: // sprintf() will leave the %(UDIM)d format sequence unmodified.stringmap=sprintf("%s/%s_%(UDIM)d.rat",texture_path,texture_base);// Expand the <UDIM>, returning an empty string if the m....

### getattribute

```vex
vectorpos,uv,clr;// Get the position of point 3 in "defgeo.bgeo"getattribute("defgeo.bgeo",pos,"point","P",3,0);// Get the value of the "uv" attribute for vertex 2 of primitive// number 3 in the file defgeo.bgeogetattribute("defgeo.bgeo",uv,"vertex","uv",3,2);// Get the value of the "Cd" attribute for primitive 7// in the SOP specified by the path "/obj/geo1/color1" (Houdini// only)getattribute("op:/obj/geo1/color1",clr,"primitive","Cd",7);
```

Signature: vectorpos,uv,clr;// Get the position of point 3 in "defgeo.bgeo"getattribute("defgeo.bgeo",pos,"point","P",3,0);// Get the value of the "uv" attribute for vertex 2 of primitive// number ....

### hasattrib

```vex
// Check whether the point group "pointstouse" exists.if(hasattrib("defgeo.bgeo","pointgroup","pointstouse")){// Do something with the point group}
```

Signature: // Check whether the point group "pointstouse" exists.if(hasattrib("defgeo.bgeo","pointgroup","pointstouse")){// Do something with the point group}

When running in the context of a node....

### mask_bsdf

```vex
// outF will have every component from inF except refractionbsdfoutF=mask_bsdf(inF,PBR_ALL_MASK& ~PBR_REFRACT_MASK);
```

Signature: // outF will have every component from inF except refractionbsdfoutF=mask_bsdf(inF,PBR_ALL_MASK& ~PBR_REFRACT_MASK);

BSDF to mask.

### printf

```vex
printf("P = %g, dot(N, P) = %g, %d = %x\n",P,dot(N,P),ptnum,ptnum);printf("RGB = {%g,%g,%g}\n",clr.r,clr.g,clr.b);printf("P = %20s\n","20 chars");printf("%-+20s\n","Left justified and quoted");printf("%+08.3g\n",velocity);printf("%*.*g\n",width,precision,value);Cf=texture(sprintf("/maps/map%d.rat",i));Cf=texture(sprintf("/maps/map%04d.rat",i));
```

Signature: printf("P = %g, dot(N, P) = %g, %d = %x\n",P,dot(N,P),ptnum,ptnum);printf("RGB = {%g,%g,%g}\n",clr.r,clr.g,clr.b);printf("P = %20s\n","20 chars");printf("%-+20s\n","Left justified and qu....

### resolvemissedray

```vex
resolvemissedray(I, 0.0, PBR_REFLECT_MASK);
```

Signature: resolvemissedray(I, 0.0, PBR_REFLECT_MASK);

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates an array from its arguments.

### spline

```vex
spline("linear", t, v0, v1, v2, v3)
```

Signature: spline("linear", t, v0, v1, v2, v3)

This version takes a single basis to use for all keys, and takes the (linearly spaced) key values as variadic arguments.

### usd_clearmetadata

```vex
// Clear the metadata value.usd_clearmetadata(0,"/geo/sphere","customData:some_name");
```

Signature: // Clear the metadata value.usd_clearmetadata(0,"/geo/sphere","customData:some_name");

A handle to the stage to write to.

### usd_drawmode

```vex
// Get the cube's draw mode, eg, "default", "bounds", etc.stringdraw_mode=usd_drawmode(0,"/geo/cube");
```

Signature: // Get the cube's draw mode, eg, "default", "bounds", etc.stringdraw_mode=usd_drawmode(0,"/geo/cube");

When running in the context of a node (such as a wrangle LOP), this argument can b....

### usd_getbbox_center

```vex
// Get the center of the sphere's bounding box.vectorcenter=usd_getbbox_center(0,"/src/sphere","render");
```

Signature: // Get the center of the sphere's bounding box.vectorcenter=usd_getbbox_center(0,"/src/sphere","render");

When running in the context of a node (such as a wrangle LOP), this argument ca....

### usd_isstage

```vex
// Check if the first input has a valid stage.intis_valid_stage_on_first_input=usd_isstage(0);
```

Signature: // Check if the first input has a valid stage.intis_valid_stage_on_first_input=usd_isstage(0);

When running in the context of a node (such as a wrangle LOP), this argument can be an int....

### usd_pointinstance_getbbox_min

```vex
// Get the min of the first instance's boundsng box.vectormin=usd_pointinstance_getbbox_min(0,"/src/instanced_spheres",0,"render");
```

Signature: // Get the min of the first instance's boundsng box.vectormin=usd_pointinstance_getbbox_min(0,"/src/instanced_spheres",0,"render");

When running in the context of a node (such as a wran....

### usd_relationshiptargets

```vex
// Get the list of targets in cube's "some_relationship" relationship.stringtargets[] =usd_relationshiptargets(0,"/geo/cube","some_relationship");
```

Signature: // Get the list of targets in cube's "some_relationship" relationship.stringtargets[] =usd_relationshiptargets(0,"/geo/cube","some_relationship");

When running in the context of a node ....

### usd_setkind

```vex
// Set the sphere primitive to be an assembly.usd_setkind(0,"/geo/sphere","assembly");
```

Signature: // Set the sphere primitive to be an assembly.usd_setkind(0,"/geo/sphere","assembly");

A handle to the stage to write to.
