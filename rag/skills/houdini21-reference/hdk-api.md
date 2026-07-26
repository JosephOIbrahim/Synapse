# HDK API Reference (Houdini Development Kit)

## Core Classes

### GU_Detail
Main geometry container class.
```cpp
#include <GU/GU_Detail.h>

GU_Detail gdp;

// Points
GA_Offset ptoff = gdp.appendPoint();
gdp.setPos3(ptoff, UT_Vector3(x, y, z));

// Primitives
GU_PrimPoly* poly = GU_PrimPoly::build(&gdp, 4, GU_POLY_CLOSED);

// Attributes
GA_RWHandleV3 Phandle(gdp.findPointAttribute("P"));
Phandle.set(ptoff, UT_Vector3(1, 2, 3));

// Create attribute
GA_Attribute* attr = gdp.addFloatTuple(
    GA_ATTRIB_POINT, "myattr", 1);
```

### GA_Attribute
Attribute storage and access.
```cpp
GA_RWHandleF handle(gdp->findPointAttribute("myattr"));
GA_ROHandleV3 Phandle(gdp->findPointAttribute("P"));

// Iterate
GA_FOR_ALL_PTOFF(gdp, ptoff) {
    float val = handle.get(ptoff);
    UT_Vector3 pos = Phandle.get(ptoff);
}
```

### OP_Node / SOP_Node
Node base classes.
```cpp
class SOP_MyNode : public SOP_Node {
public:
    static OP_Node* myConstructor(OP_Network*, const char*, OP_Operator*);
    static PRM_Template myTemplateList[];

protected:
    OP_ERROR cookMySop(OP_Context& context) override;
};
```

### PRM_Template
Parameter definition.
```cpp
static PRM_Name names[] = {
    PRM_Name("scale", "Scale"),
    PRM_Name("offset", "Offset"),
};

static PRM_Default defaults[] = {
    PRM_Default(1.0),
    PRM_Default(0.0),
};

PRM_Template SOP_MyNode::myTemplateList[] = {
    PRM_Template(PRM_FLT, 1, &names[0], &defaults[0]),
    PRM_Template(PRM_XYZ, 3, &names[1]),
    PRM_Template()  // Sentinel
};
```

## Common Patterns

### Compiled SOP Block
```cpp
// Register as compilable
void newSopOperator(OP_OperatorTable* table) {
    OP_Operator* op = new OP_Operator(
        "mynode", "My Node",
        SOP_MyNode::myConstructor,
        SOP_MyNode::myTemplateList,
        1, 1,  // min/max inputs
        nullptr,
        OP_FLAG_GENERATOR
    );
    op->setIsThreadSafe(true);  // For compiled blocks
    table->addOperator(op);
}
```

### Thread-Safe Cooking
```cpp
OP_ERROR SOP_MyNode::cookMySop(OP_Context& context) {
    UT_AutoInterrupt boss("Computing...");

    GA_FOR_ALL_PTOFF(gdp, ptoff) {
        if (boss.wasInterrupted())
            return error();
        // ... work ...
    }
    return error();
}
```

## Build System (CMake)
```cmake
find_package(Houdini REQUIRED)

add_library(SOP_mynode SHARED
    SOP_MyNode.cpp
)
target_link_libraries(SOP_mynode Houdini)
houdini_configure_target(SOP_mynode)
```

---
*Expand from HDK documentation. Cross-reference: hdk-build-recipes skill for patterns.*
