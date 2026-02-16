# VEX Corpus: Conditional Logic

> 52 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (10 examples)

### Search an array with find â

```vex
int myint = 0;
if (@Frame == 1 || @Frame == 25 || @Frame == 225 || @Frame == 35) {
    myint=1;
}
```

Super nice tip from one man Houdini army Tomas Slancik.

Say you want to set an int attib to be 1 on Frame 1, 25, 225,35.

### Conditional comparison operators

```vex
int foo;
if (foo == 3) {  // double equals sign for comparison
    // do something
}
```

Demonstrates the correct syntax for conditional comparison in VEX using the double equals operator (==) for testing equality, as opposed to the single equals (=) used for assignment.

### Nested Conditionals with Point Position

```vex
if(@ptnum > 50){
    if(@P.x < 2){
        @Cd = {1,0,0};
    }
}
```

Demonstrates nested if statements to apply color conditionally based on two criteria: point number must be greater than 50 AND the x-position must be less than 2.

### Conditional color assignment with less than

```vex
if(@ptnum < 5){
    @Cd = {1,0,0};
}
```

Uses an if statement with the less-than operator to set points 0-4 to red color while leaving point 5 and above unchanged.

### Comparison Operators and Modulo

```vex
if(@ptnum >= 5){
    @Cd = {1,0,0};
}
```

Demonstrates using comparison operators (greater than or equal to) to conditionally set point color.

### Flipping normals based on Z direction

```vex
@Cd = @N;
if (@Cd.z < 0) {
    @Cd = -@N;
}
```

Colors points by their normal vector, then checks if the Z component is negative.

### Conditional Color with If-Else

```vex
int a = 3;
int b = 3;

if(a == b) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates basic if-else conditional logic by comparing two integer variables.

### Compound Conditional with AND Operator

```vex
if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1, 0, 0};
}
```

Uses the AND operator (&&) to combine two conditions: checking if the point number is greater than 50 AND if the Y position is less than 2.

### Logical OR operator in conditionals

```vex
if(@ptnum > 50 || @P.x < 2){
    @Cd = (1,0,0);
}
```

Demonstrates using the logical OR operator (||) to combine two conditions in an if statement.

### Modulo Operator for Pattern Selection

```vex
if(@ptnum % 5 == 0){
    @Cd = {1,0,0};
}
```

Uses the modulo operator (%) to test if a point number is divisible by 5, setting every fifth point to red color.

## Intermediate (37 examples)

### Example: Random delete points by threshold â

```vex
if ( rand(@ptnum) > ch('threshold') ) {
   removepoint(0,@ptnum);
}
```

After Matt Ebb showed me this, I use it a million times a day.

### Remove points that don't have normals directly along an axis â

```vex
if (max(abs(normalize(@N))) != 1) {
ââremovepoint(0,@ptnum);
}
```

Brilliant tip from the brilliant Matt Ebb.

### Joy of Vex Day 11 â

```vex
if (test in regular brackets)  {
     code to execute in curly brackets;
     end each line in a semi colon;
     and close the if statement with a curly bracket;
 }
```

If statements

Vex works like most C style languages, you can control execution based on testing against a value.

The trickiest thing with if statements is the punctuation, its easy to trip up and....

### How to format your code â

```vex
if ( length(@P)*2+@ptnum % 5 == 0) {  @Cd = {1,0,0}; }
```

Vex, unlike say python, doesn't care where you put space, returns, any of that.

### If Statement Syntax Basics

```vex
if (test in regular brackets) {
    code to execute in curly brackets;
    end each line in a semi colon;
    inside the if statement - curly bracket;
}

if (@foo > 1) {

// ...
```

Introduction to if statement syntax in VEX, demonstrating the structure with test conditions in parentheses and code blocks in curly braces.

### If Statement Syntax

```vex
if (test in regular brackets) {
    code to execute in curly brackets;
    end each line in a semi colon;
    finish the if statement with a curly bracket;
}

if (@foo > 1) {

// ...
```

Introduction to if statement syntax in VEX showing the basic structure with test conditions in parentheses and code blocks in curly brackets.

### If Statement Syntax and Structure

```vex
// If statement structure:
if (test in regular brackets) {
    code to execute in curly brackets;
    end each line in a semi colon;
    follow the if with a test in curly bracket;
}

// Examples:
// ...
```

If statements allow conditional execution of code based on logical tests.

### If Statement Syntax Basics

```vex
if (test in regular brackets) {
    code to execute in curly brackets;
    you can have multiple lines of code,
    and close the if statement with a curly bracket;
}

if (@foo > 1) {
    // code here
// ...
```

Introduction to if statement syntax in VEX, showing the basic structure with test conditions in parentheses and code blocks in curly brackets.

### Assignment vs Equality Operators

```vex
if (@foo > 1) {
}

if (@ptnum < 50) {
}

if (@name == "piece5") {
}
// ...
```

Testing for equality in conditional statements requires the double equals operator (==), not the single equals used for assignment (=).

### Conditional statements and channel references

```vex
int ifoo;
if (foo == 5) {
    // do something
}

vector bbox = relpointbbox(0, @P);
@Cd = {1, 0, 0};
if (bbox.y < 0.5) {
// ...
```

Demonstrates proper conditional syntax with double equals (==) for comparison versus single equals (=) for assignment, a common pitfall.

### Logical Operators and Nested Conditionals

```vex
if ( abs(foo - bar) < 0.00001 ) {  // close enough
    // say they're equal, and won't be fooled by negative
    // numbers
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
// ...
```

Demonstrates logical operators (AND &&, OR ||) and nested conditionals in VEX.

### Logical Operators AND and OR

```vex
if ( abs(foo - bar) < 0.00001 ) {
    // close enough to say they're equal, and won't be fooled by negative
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
// ...
```

Demonstrates logical operators in VEX: the AND operator (&&) requires both conditions to be true, while the OR operator (||) requires only one condition to be true.

### Modulo Conditionals and Order of Operations

```vex
if(@ptnum != 5)
    @Cd = {1,0,0};

if ( @ptnum != 5 ) {
    @Cd = {1,0,0};
}

if ( @ptnum % 5) {
// ...
```

Demonstrates various conditional statements testing point numbers, including modulo operations to select every fifth point.

### Time-based conditional color assignment

```vex
if (length(@P) * 2 + @ptnum % 5 > dot(@N, {0,1,0}) * @Time){
    @Cd = {1,0,0};
}
```

This conditional statement compares two complex expressions to determine point color over time.

### Complex conditional with time-based comparison

```vex
if (length(@P) * 2 + @ptnum % 5 > dot(@N, {0,1,0} * @Time)){
    @Cd = {1,0,0};
}
```

This conditional compares two calculated values: the left side combines point position length, point number modulo, and multiplication, while the right side uses the dot product of the normal with ....

### Random Primitive Removal

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
```

Uses random per-primitive values to selectively delete primitives based on a threshold.

### Random Primitive Removal

```vex
if(rand(i@primnum, ch('seed')) < ch('cutoff')) {
    removeprims(0, @primnum, 1);
}
```

Conditionally removes primitives based on a random threshold, using the primitive number and a seed parameter to generate deterministic randomness.

### If-Else Conditional Logic

```vex
int a = 3;
int b = 3;

if(a == b) {
    @Cd = {1,1,0};
}
else {
    @Cd = {1,0,0};
// ...
```

Demonstrates basic if-else conditional logic by comparing two integer variables.

### Logical Operators AND and OR

```vex
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1,0,0};
// ...
```

Demonstrates how to combine conditional tests using logical operators.

### Conditional Coloring with Complex Expression

```vex
if (length(@P)*2+@ptnum % 5 > dot(@N,{0,1,0})*@Time) {
    @Cd = {1,0,0};
}
```

Uses a conditional statement to set points to red based on a complex comparison combining position length, point number modulo, and the dot product of the normal with the up vector scaled by time.

### Creating Points with addpoint

```vex
int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
    addpoint(0, {0,1,0});
}
```

Introduces the addpoint() function for creating new geometry in VEX.

### Creating Points with addpoint

```vex
int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
  addpoint(0, {0,1,0});
}
```

Introduction to creating geometry in VEX using the addpoint() function.

### addpoint return value storage

```vex
int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
    addpoint(1, {0,1,0});
}
```

The addpoint() function returns the point number index of the newly created point, which can be stored in a variable.

### Conditional Point Creation

```vex
if(@ptnum == 0){
    addpoint(0, {0,0,0});
}
```

Uses a conditional statement to add a single point at the origin only when processing point number 0.

### Random Point Removal with Seed

```vex
if(rand(@ptnum) < ch('cutoff')){
    removepoint(0, @ptnum);
}

if(rand(@ptnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @ptnum, 1);
}
```

Demonstrates randomly removing points using rand() compared against a channel slider threshold.

### Random Primitive Deletion

```vex
if(rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}
```

Uses a random threshold to conditionally delete primitives based on a channel slider value.

### Random Primitive Removal with Seed Control

```vex
if(rand(@primuv, ch('seed')) < ch('cutoff')){
    removepoint(0, @primuv, 1);
}
```

Uses a seeded random function to probabilistically remove points based on primitive UV coordinates and a cutoff threshold.

### Random Primitive Removal

```vex
if(rand(@primnum, ch('seed')) < ch('chance'))
    removepoint(0, @primnum, 1);
```

Uses a random value per primitive to conditionally remove primitives based on a user-controlled chance parameter.

### Common Syntax Error: Missing Brackets

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @primnum, 1);
}
```

A common syntax error occurs when forgetting to close brackets in conditional statements, especially when using channel references with the ch() function.

### Random Primitive Removal

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}
```

Conditionally removes primitives based on a random threshold comparison.

### Random Primitive Removal

```vex
if(rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}
```

Conditionally removes primitives based on a random threshold.

### getsmoothP

```vex
shadowfastshadow(){vectorsurfP;if(!getsmoothP(surfP,Eye,I))surfP=Ps;// Set to the Ps (surface P) variablevectorshad=trace(surfP,normalize(L),Time,"raystyle","shadow");Cl*= ({1,1,1}-shad);}
```

Signature: shadowfastshadow(){vectorsurfP;if(!getsmoothP(surfP,Eye,I))surfP=Ps;// Set to the Ps (surface P) variablevectorshad=trace(surfP,normalize(L),Time,"raystyle","shadow");Cl*= ({1,1,1}-shad)....

### lightstate

```vex
vectorCd;if(!lightstate("packed:Cd",Cd))Cd=1;// There was no Cd attribute on packed geometry
```

Signature: vectorCd;if(!lightstate("packed:Cd",Cd))Cd=1;// There was no Cd attribute on packed geometry

The following properties are commonly useful and are reproduced here
for convenience, but yo....

### objectstate

```vex
vectorCd;if(!objectstate("packed:Cd",Cd))Cd=1;// There was no Cd attribute on packed geometry
```

Signature: vectorCd;if(!objectstate("packed:Cd",Cd))Cd=1;// There was no Cd attribute on packed geometry

The following properties are commonly useful and are reproduced here
for convenience, but y....

### renderstate

```vex
vectorCd;if(!renderstate("packed:Cd",Cd))Cd=1;// There was no Cd attribute on packed geometry
```

Signature: vectorCd;if(!renderstate("packed:Cd",Cd))Cd=1;// There was no Cd attribute on packed geometry

The following properties are commonly useful and are reproduced here
for convenience, but y....

### sample_geometry

```vex
surfacegeolight(intnsamples=64){vectorsam;vectorclr,pos;floatangle,sx,sy;intsid;inti;sid=newsampler();Cf=0;for(i=0;i<nsamples;i++){nextsample(sid,sx,sy,"mode","qstrat");sam=set(sx,sy,0.0);if(sample_geometry(P,sam,Time,"distribution","solidangle","scope","/obj/sphere_object*","ray:solidangle",angle,"P",pos,"Cf",clr)){if(!trace(P,normalize(pos-P),Time,"scope","/obj/sphere_object*","maxdist",length(pos-P)-0.01)){clr*=angle/ (2*PI);clr*=max(dot(normalize(pos-P),normalize(N)),0);}elseclr=0;}Cf+=clr;}Cf/=nsamples;}
```

In this mode, points will be distributed over multiple primitives according to
their area.

### teximport

```vex
matrixndc;if(teximport(map,"texture:worldtoNDC",ndc)){vectorP_ndc=pos*ndc;// If the camera is a perspective camera,// dehomogenize the pointif(getcomp(ndc,2,3) !=0){P_ndc.x=P_ndc.x/P_ndc.z;P_ndc.y=P_ndc.y/P_ndc.z;}// Finally, scale and offset XY// from [-1,1] to [0,1]P_ndc*={.5,.5,1};P_ndc+={.5,.5,0};}
```

Signature: matrixndc;if(teximport(map,"texture:worldtoNDC",ndc)){vectorP_ndc=pos*ndc;// If the camera is a perspective camera,// dehomogenize the pointif(getcomp(ndc,2,3) !=0){P_ndc.x=P_ndc.x/P_ndc....

## Advanced (5 examples)

### Logical Operators AND and OR

```vex
if(@ptnum > 50 && @P.x < 2){
    @Cd = {1,0,0};
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
// ...
```

Demonstrates logical operators in conditional statements: the AND operator (&&) requires both conditions to be true, while the OR operator (||) requires only one condition to be true.

### Comparison Operators and Modulo

```vex
if(@ptnum >= 5){
    @Cd = {1,0,0};
}

if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1,0,0};
}

// ...
```

Demonstrates various comparison operators (>=, <=, !=) and the modulo operator (%) for conditional color assignment.

### Comparison and Modulo Operators

```vex
if(@ptnum == 5){
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2 ) {
    @Cd = {1,0,0};
}

// ...
```

Demonstrates various comparison operators (==, !=, >, <, >=, <=) and logical operators (||) for conditional point coloring.

### Conditional Operators Comparison

```vex
if (@ptnum > 50) {
    if (@P.x > 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1,0,0};
// ...
```

Demonstrates various conditional operators in VEX including comparison operators (>, <, >=, <=, !=), logical AND (&&), and logical OR (||).

### Comparison Operators in Conditionals

```vex
if(@ptnum > 50) {
    if (@P.x < 2){
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.y < 2 ) {
    @Cd = {1,0,0};
// ...
```

Demonstrates various comparison operators in VEX conditionals including greater than (>), less than (<), not equal (!=), less than or equal (<=), and greater than or equal (>=).
