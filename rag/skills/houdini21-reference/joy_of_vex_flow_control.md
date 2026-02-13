# Joy of VEX: Flow Control

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Conditionals & Control Flow

### Multi-line Operations Clarity [Needs Review] [[Ep1, 102:12](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=6132s)]
```vex
float foo = 1;

// Single line version:
// foo = foo * 3 + 1 / @Cd.x + @N.y;

// Multi-line version for clarity:
foo *= 3;        // set range
foo += 1;        // make sure values never get below 0
foo /= @Cd.x;    // reduce range to within red value
foo += @N.y;     // addition normal on y
```
Demonstrates how breaking complex mathematical operations across multiple lines with comments improves code readability. The same expression can be written as a single line or decomposed into sequential operations, making it easier to understand each transformation step.

### Multi-line Code Organization [Needs Review] [[Ep1, 102:26](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=6146s)]
```vex
float foo = 1;

vector pos = set(0, sin(@Time), 0);
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * chf('time')), -1, 1, 0, 1);

foo *= 3;  // set range
foo = max(foo, 0);  // make sure values never get below 0
foo /= @Cd.x;  // reduce range to within red value
foo += @N.y;  // addition normal on y
```
Breaking complex calculations into multiple lines with descriptive comments makes code easier to understand and debug. This example shows how to organize operations step-by-step, with each line performing a single clear operation on the foo variable.

### If Statement Syntax Basics [Needs Review] [[Ep4, 61:38](https://www.youtube.com/watch?v=66WGmbykQhI&t=3698s)]
```vex
if (test in regular brackets) {
    code to execute in curly brackets;
    end each line in a semi colon;
    inside the if statement - curly bracket;
}

if (@foo > 1) {

if (@ptnum < 50) {

if (@name == "piece5") {
```
Introduction to if statement syntax in VEX, demonstrating the structure with test conditions in parentheses and code blocks in curly braces. Shows practical examples testing attribute values, point numbers, and string comparisons.

### If Statement Syntax [Needs Review] [[Ep4, 62:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=3720s)]
```vex
if (test in regular brackets) {
    code to execute in curly brackets;
    end each line in a semi colon;
    finish the if statement with a curly bracket;
}

if (@foo > 1) {

if (@ptnum < 50) {

if (@name == "piece5") {
```
Introduction to if statement syntax in VEX showing the basic structure with test conditions in parentheses and code blocks in curly brackets. Demonstrates three common conditional tests: comparing an attribute value to a number, testing point numbers, and checking string attribute values.

## Loops

### For Loop Syntax Overview [Needs Review] [[Ep4, 62:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=3722s)]
```vex
for(brackets) {
    // for in curly brackets;
    // semicolon;
    // curly bracket;
}
```
This demonstrates the basic syntax structure of a for loop in VEX, showing the use of parentheses for the loop condition, curly brackets to define the loop body, and semicolons for statement separation. The actual loop implementation is incomplete and serves as a structural reference.

## Conditionals & Control Flow

### If Statement Syntax and Structure [[Ep4, 62:04](https://www.youtube.com/watch?v=66WGmbykQhI&t=3724s)]
```vex
// If statement structure:
if (test in regular brackets) {
    code to execute in curly brackets;
    end each line in a semi colon;
    follow the if with a test in curly bracket;
}

// Examples:
if (@foo < 1) {
    // code here
}

if (@ptnum < 50) {
    // code here
}

if (@name == "piece5") {
    // code here
}
```
If statements allow conditional execution of code based on logical tests. The syntax requires a test condition in parentheses followed by code blocks in curly braces, with each statement ending in a semicolon. Examples show testing numeric attributes like @foo and @ptnum, as well as string attributes like @name.

### If Statement Syntax Basics [[Ep4, 62:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=3732s)]
```vex
if (test in regular brackets) {
    code to execute in curly brackets;
    you can have multiple lines of code,
    and close the if statement with a curly bracket;
}

if (@foo > 1) {
    // code here
}

if (@ptnum < 50) {
    // code here
}

if (@name == 'piece5') {
    // code here
}
```
Introduction to if statement syntax in VEX, showing the basic structure with test conditions in parentheses and code blocks in curly brackets. Examples demonstrate conditional logic testing attributes like @foo, @ptnum, and @name with comparison operators.

### Assignment vs Equality Operators [[Ep4, 64:52](https://www.youtube.com/watch?v=66WGmbykQhI&t=3892s)]
```vex
if (@foo > 1) {
}

if (@ptnum < 50) {
}

if (@name == "piece5") {
}

float foo = 5; // single equals sign means 'set foo to 5'

// GOOD
if (foo == 5) {  // double equals sign asks 'is foo equal to 5?'
    // do something
}

// BAD
if (foo = 5) {  // single equals sign! assignment, not comparison
    // do something
}
```
Testing for equality in conditional statements requires the double equals operator (==), not the single equals used for assignment (=). A common mistake is using a single equals sign in an if statement, which performs assignment instead of comparison and can lead to unexpected behavior.

### Conditional comparison operators [[Ep4, 66:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=3980s)]
```vex
int foo;
if (foo == 3) {  // double equals sign for comparison
    // do something
}
```
Demonstrates the correct syntax for conditional comparison in VEX using the double equals operator (==) for testing equality, as opposed to the single equals (=) used for assignment. A common beginner mistake is using a single equals sign in if statements, which performs assignment rather than comparison.

### Conditional statements and channel references [[Ep4, 66:24](https://www.youtube.com/watch?v=66WGmbykQhI&t=3984s)]
```vex
int ifoo;
if (foo == 5) {
    // do something
}

vector bbox = relpointbbox(0, @P);
@Cd = {1, 0, 0};
if (bbox.y < 0.5) {
    @Cd = {0, 1, 0};
}

float d = dot(@N, {0, 1, 0});
@Cd = {0, 0, 1};
if (d > 0.5) {
    @Cd = {1, 1, 1};
}

float d = dot(@N, {0, 1, 0});
@Cd = {0, 0, 1};
if (d > ch('cutoff')) {
    @Cd = {1, 1, 1};
}

float d = dot(@N, {0, 1, 0});
if (d > ch('cutoff')) {
    @Cd = {1, 1, 1};
} else {
    @Cd = {0, 0, 1};
}
```
Demonstrates proper conditional syntax with double equals (==) for comparison versus single equals (=) for assignment, a common pitfall. Shows progressively refined examples using if statements to color geometry based on bounding box position, surface normal direction, and channel-referenced threshold values. Illustrates how to gate operations and make VEX code responsive to user parameters.

### Threshold-based normal masking [[Ep4, 71:08](https://www.youtube.com/watch?v=66WGmbykQhI&t=4268s)]
```vex
float d = dot(@N, {0,1,0});
@Cd = {0,0,1};
if(d > ch('cutoff')){
    @Cd = {1,1,1};
}
```
Uses a dot product between the point normal and up vector to determine surface orientation, then colors points white if they face upward beyond a threshold value controlled by a channel parameter. The cutoff parameter creates a controllable width for the effect, allowing selection of surfaces based on how much they face upward versus horizontal or downward.

### If-Else Color Assignment [[Ep4, 72:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=4334s)]
```vex
float d = dot(@N, {0,1,0});
if(d > ch('cutoff')){
    @Cd = {1,1,1};
} else {
    @Cd = {1,0,0};
}
```
Uses an if-else statement to explicitly assign white color when the dot product exceeds the cutoff threshold, and red color otherwise. This approach makes the logic clearer by explicitly setting both color states rather than relying on default values, which can be helpful when attributes are set elsewhere or when clarity is needed.

### Conditional Color Assignment with Dot Product [[Ep4, 72:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=4340s)]
```vex
float d = dot(@P, {0,1,0});
@Cd = {0,0,1};
if (d > ch('cutoff')) {
    @Cd = {1,1,1};
} else {
    @Cd = {1,0,0};
}
```
Uses dot product to classify points based on their Y-position, then explicitly sets color to white if above the cutoff threshold or red if below. The initial blue assignment demonstrates that attributes can be set multiple times, with later assignments overwriting earlier ones, which can aid in understanding control flow logic.

### Conditional Color Based on Height [[Ep4, 72:32](https://www.youtube.com/watch?v=66WGmbykQhI&t=4352s)]
```vex
float d = dot(@P, {0,1,0});
if(d < ch('cutoff')){
    @Cd = {1,1,1};
} else {
    @Cd = {1,0,0};
}
```
Uses a dot product to calculate the vertical position (height) of each point by projecting @P onto the Y-axis, then conditionally sets the color (@Cd) to white or red based on whether the height is below a user-controlled cutoff parameter. The if-else statement provides explicit control for visualizing which points meet the threshold condition.

### If-Else Conditional Logic [[Ep4, 73:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=4434s)]
```vex
int a = 3;
int b = 3;

if(a == b) {
    @Cd = {1,1,0};
}
else {
    @Cd = {1,0,0};
}
```
Demonstrates basic if-else conditional logic by comparing two integer variables. If the variables are equal, the color is set to yellow (or green as intended); otherwise, it's set to red. This establishes a visual feedback pattern for testing conditions.

### Floating-Point Precision and Conditionals [[Ep4, 75:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=4520s)]
```vex
float foo = 0;
float bar = sin(@P);

if(foo == bar) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```
Demonstrates floating-point precision issues when comparing calculated values. The sine of PI mathematically equals zero, but computationally returns approximately -8.74228e-08, causing the equality test to fail. This illustrates why direct equality comparisons with floats can be unreliable.

### Float comparison tolerance [[Ep4, 76:44](https://www.youtube.com/watch?v=66WGmbykQhI&t=4604s)]
```vex
float foo = 0;
float bar = sin(@P[1]);

if(foo - bar < 0.00001) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```
Demonstrates safe float comparison by using a tolerance threshold instead of testing for exact equality. Instead of checking if foo equals bar directly, subtracts them and tests if the result is less than 0.00001, treating values within this tolerance as equal. This approach avoids floating-point precision errors that would cause exact equality tests to fail even when values should be considered equal.

## Loops

### Epsilon Test for Float Comparison [[Ep4, 79:22](https://www.youtube.com/watch?v=66WGmbykQhI&t=4762s)]
```vex
float foo = 1.25;
float bar = -1.25;

if(abs(foo - bar) < 0.00001) {
    @Cd = {1,1,0};
}
else {
    @Cd = {1,0,0};
}
```
Demonstrates an epsilon test for comparing floating-point numbers, which checks if the absolute difference between two values is below a small threshold (0.00001) rather than testing exact equality. This technique accounts for floating-point precision errors that occur in computer arithmetic. The geometry is colored yellow if the values are considered equal within the epsilon tolerance, otherwise red.

### Epsilon Comparison for Floating Point [[Ep4, 79:26](https://www.youtube.com/watch?v=66WGmbykQhI&t=4766s)]
```vex
float foo = 1.25;
float bar = 1.25;

if(abs(foo - bar) < 0.00001) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```
Demonstrates epsilon testing for comparing floating-point numbers by checking if their absolute difference is less than a small threshold (0.00001) rather than testing exact equality. This technique avoids floating-point precision errors that can occur when comparing floats directly. Points are colored yellow if the values match within epsilon tolerance, red otherwise.

## Conditionals & Control Flow

### Floating Point Epsilon Comparison [[Ep4, 79:32](https://www.youtube.com/watch?v=66WGmbykQhI&t=4772s)]
```vex
float foo = 1.251;
float bar = 1.251;

if(abs(foo - bar) < 0.00001) {
    @Cd = {0,1,0};
} else {
    @Cd = {1,0,0};
}
```
Demonstrates epsilon testing for comparing floating point numbers, using a small tolerance value (0.00001) instead of direct equality to account for floating point precision errors. If the absolute difference between two floats is less than epsilon, they are considered equal (green color), otherwise they are different (red color).

### Floating Point Comparison and Multiple Conditionals [[Ep4, 79:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=4774s)]
```vex
if ( abs(foo - bar) < 0.00001 ) {
    @Cd = {1,0,0};
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.y < 2 ) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2 ) {
    @Cd = {1,0,0};
}
```
Demonstrates epsilon testing for floating point comparison using absolute value to avoid precision errors, and shows multiple ways to combine conditional tests including nested if statements, AND (&&) operators, and OR (||) operators. The epsilon test checks if two floating point values are effectively equal within a small tolerance (0.00001).

### Compound Conditional with AND Operator [[Ep4, 80:26](https://www.youtube.com/watch?v=66WGmbykQhI&t=4826s)]
```vex
if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1, 0, 0};
}
```
Uses the AND operator (&&) to combine two conditions: checking if the point number is greater than 50 AND if the Y position is less than 2. When both conditions are true, the point color is set to red.

### Logical Operators AND and OR [[Ep4, 80:50](https://www.youtube.com/watch?v=66WGmbykQhI&t=4850s)]
```vex
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1,0,0};
}
```
Demonstrates how to combine conditional tests using logical operators. The AND operator (&&) requires both conditions to be true simultaneously, while the OR operator (||) requires only one condition to be true. This allows for more concise code than nested if statements when testing multiple conditions.

### Logical Operators and Nested Conditionals [[Ep4, 80:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=4854s)]
```vex
if ( abs(foo - bar) < 0.00001 ) {  // close enough
    // say they're equal, and won't be fooled by negative
    // numbers
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.x < 2 ) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2 ) {
    @Cd = {1,0,0};
}
```
Demonstrates logical operators (AND &&, OR ||) and nested conditionals in VEX. Shows how nested if statements can be simplified using logical operators, and demonstrates the use of epsilon comparisons for floating point equality checks. The examples color points red based on point number and position, with nested conditions being equivalent to AND operations, while OR operations require either condition to be true.

### Logical Operators AND and OR [[Ep4, 81:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=4872s)]
```vex
if ( abs(foo - bar) < 0.00001 ) {
    // close enough to say they're equal, and won't be fooled by negative
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.x < 2 ) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2 ) {
    @Cd = {1,0,0};
}
```
Demonstrates logical operators in VEX: the AND operator (&&) requires both conditions to be true, while the OR operator (||) requires only one condition to be true. Nested if-statements can be made more compact using logical operators, with && combining multiple conditions that all must pass, and || allowing any condition to pass.

### Nested if statements with point filtering [[Ep4, 81:30](https://www.youtube.com/watch?v=66WGmbykQhI&t=4890s)]
```vex
if(@ptnum > 50){
    if(@P.x < 2){
        @Cd = {1,0,0};
    }
}
```
Demonstrates nested if statements to set point color to red based on two conditions: point number greater than 50 AND x position less than 2. This creates a filtering effect where only points meeting both criteria have their color modified, visible as white stripes on geometry where conditions fail.

### Logical Operators AND and OR [[Ep4, 82:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=4934s)]
```vex
if(@ptnum > 50 && @P.x < 2){
    @Cd = {1,0,0};
}

if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1,0,0};
}

if (@ptnum != 5) {
    @Cd = {1,0,0};
}

if (@ptnum <= 5) {
    @Cd = {1,0,0};
}
```
Demonstrates logical operators in conditional statements: the AND operator (&&) requires both conditions to be true, while the OR operator (||) requires only one condition to be true. Shows how nested if statements can be simplified using the && operator, and demonstrates various comparison operators including inequality (!=) and less-than-or-equal (<=).

### Logical OR operator in conditionals [[Ep4, 82:44](https://www.youtube.com/watch?v=66WGmbykQhI&t=4964s)]
```vex
if(@ptnum > 50 || @P.x < 2){
    @Cd = (1,0,0);
}
```
Demonstrates using the logical OR operator (||) to combine two conditions in an if statement. If either the point number is greater than 50 OR the x-position is less than 2, the point color is set to red. Only points that fail both conditions (point numbers less than 50 AND x-position greater than or equal to 2) remain uncolored.

### Conditional Operators Comparison [[Ep4, 83:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=4980s)]
```vex
if (@ptnum > 50) {
    if (@P.x > 2) {
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1,0,0};
}

if (@ptnum != 5) {
    @Cd = {1,0,0};
}

if (@ptnum <= 5) {
    @Cd = {1,0,0};
}

if (@ptnum >= 5) {
    @Cd = {1,0,0};
}
```
Demonstrates various conditional operators in VEX including comparison operators (>, <, >=, <=, !=), logical AND (&&), and logical OR (||). The examples show how to combine multiple conditions to test point numbers and position attributes, with the OR operator (||) being particularly useful when either condition passing should trigger the color assignment.

### Comparison Operators in Conditionals [[Ep4, 83:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=4982s)]
```vex
if(@ptnum > 50) {
    if (@P.x < 2){
        @Cd = {1,0,0};
    }
}

if (@ptnum > 50 && @P.y < 2 ) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2 ) {
    @Cd = {1,0,0};
}

if ( @ptnum != 5) {
    @Cd = {1,0,0};
}

if ( @ptnum <= 5) {
    @Cd = {1,0,0};
}

if ( @ptnum >= 5) {
    @Cd = {1,0,0};
}
```
Demonstrates various comparison operators in VEX conditionals including greater than (>), less than (<), not equal (!=), less than or equal (<=), and greater than or equal (>=). Also shows the use of logical operators AND (&&) and OR (||) to combine multiple conditions, affecting which points get colored red based on point number and position criteria.

### Conditional color assignment with less than [[Ep4, 84:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=5060s)]
```vex
if(@ptnum < 5){
    @Cd = {1,0,0};
}
```
Uses an if statement with the less-than operator to set points 0-4 to red color while leaving point 5 and above unchanged. This demonstrates basic conditional logic for selective point coloring based on point number comparison.

### Comparison Operators and Modulo [[Ep4, 84:36](https://www.youtube.com/watch?v=66WGmbykQhI&t=5076s)]
```vex
if(@ptnum >= 5){
    @Cd = {1,0,0};
}

if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1,0,0};
}

if (@ptnum != 5) {
    @Cd = {1,0,0};
}

if (@ptnum <= 5) {
    @Cd = {1,0,0};
}

if (@ptnum >= 5) {
    @Cd = {1,0,0};
}

if (@ptnum % 5 == 0) {
    @Cd = {1,0,0};
}
```
Demonstrates various comparison operators (>=, <=, !=) and the modulo operator (%) for conditional color assignment. The examples show how to filter points based on point number comparisons, including testing for equality with modulo to select every Nth point. The transcript focuses on explaining the less-than-or-equal-to (<=) and greater-than-or-equal-to (>=) operators, as well as introducing modulo division for pattern selection.

### Comparison Operators and Modulo [[Ep4, 84:48](https://www.youtube.com/watch?v=66WGmbykQhI&t=5088s)]
```vex
if(@ptnum >= 5){
    @Cd = {1,0,0};
}
```
Demonstrates using comparison operators (greater than or equal to) to conditionally set point color. Points with @ptnum >= 5 are colored red, while points below that threshold remain white (default).

### Comparison and Modulo Operators [[Ep4, 85:06](https://www.youtube.com/watch?v=66WGmbykQhI&t=5106s)]
```vex
if(@ptnum == 5){
    @Cd = {1,0,0};
}

if (@ptnum > 50 || @P.x < 2 ) {
    @Cd = {1,0,0};
}

if ( @ptnum != 5) {
    @Cd = {1,0,0};
}

if ( @ptnum <= 5) {
    @Cd = {1,0,0};
}

if ( @ptnum >= 5) {
    @Cd = {1,0,0};
}

if ( @ptnum % 5 == 0) {
    @Cd = {1,0,0};
}
```
Demonstrates various comparison operators (==, !=, >, <, >=, <=) and logical operators (||) for conditional point coloring. The modulo operator (%) is used to select every fifth point by testing if the remainder equals zero, creating a pattern of red points on white.

### Modulo Conditionals and Order of Operations [[Ep4, 85:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=5116s)]
```vex
if(@ptnum != 5)
    @Cd = {1,0,0};

if ( @ptnum != 5 ) {
    @Cd = {1,0,0};
}

if ( @ptnum % 5) {
    @Cd = {1,0,0};
}

if ( @ptnum % 5 == 0) {
    @Cd = {1,0,0};
}

if ( length(@P)^2+@ptnum % 5 > dot(@N,{0,1,0})*@Time) {
    @Cd = {1,0,0};
}
```
Demonstrates various conditional statements testing point numbers, including modulo operations to select every fifth point. The modulo operator returns the remainder of division, so testing for zero (e.g., @ptnum % 5 == 0) selects points divisible by 5. The final example shows that complex expressions within conditionals follow standard order of operations, with the comparison performed last.

## Loops

### Modulo for Point Selection [[Ep4, 85:40](https://www.youtube.com/watch?v=66WGmbykQhI&t=5140s)]
```vex
if(@ptnum % 5 == 0){
    @Cd = {1,0,0};
}
```
Uses the modulo operator to select every fifth point and color it red. The modulo operator returns the remainder of division, so @ptnum % 5 == 0 is true for points 0, 5, 10, 15, etc. This creates a regular pattern of selection across the geometry.

## Conditionals & Control Flow

### Conditional Coloring with Complex Expression [[Ep4, 85:44](https://www.youtube.com/watch?v=66WGmbykQhI&t=5144s)]
```vex
if (length(@P)*2+@ptnum % 5 > dot(@N,{0,1,0})*@Time) {
    @Cd = {1,0,0};
}
```
Uses a conditional statement to set points to red based on a complex comparison combining position length, point number modulo, and the dot product of the normal with the up vector scaled by time. The order of operations performs the comparison last, evaluating all mathematical expressions before the conditional check.

### Time-based conditional color assignment [[Ep4, 86:36](https://www.youtube.com/watch?v=66WGmbykQhI&t=5196s)]
```vex
if (length(@P) * 2 + @ptnum % 5 > dot(@N, {0,1,0}) * @Time){
    @Cd = {1,0,0};
}
```
This conditional statement compares two complex expressions to determine point color over time. The left side combines the distance from origin (doubled) with a modulo pattern based on point number, while the right side multiplies the dot product of the normal with the up vector by the current time value. Points meeting this condition are colored red, creating a time-animated pattern that evolves based on both geometric properties and temporal progression.

### Complex conditional with time-based comparison [[Ep4, 87:22](https://www.youtube.com/watch?v=66WGmbykQhI&t=5242s)]
```vex
if (length(@P) * 2 + @ptnum % 5 > dot(@N, {0,1,0} * @Time)){
    @Cd = {1,0,0};
}
```
This conditional compares two calculated values: the left side combines point position length, point number modulo, and multiplication, while the right side uses the dot product of the normal with an animated up vector. When the left value exceeds the right, points are colored red, creating a time-based animated selection effect.

## Loops

### Code Formatting with Variables [[Ep4, 89:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=5354s)]
```vex
float a = length(@P)*2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```
Demonstrates using variables to improve code readability by storing complex calculations in named variables 'a' and 'b' before comparison. This refactoring makes the conditional logic cleaner and easier to understand while maintaining identical functionality.

### Code Formatting with Variables [[Ep4, 89:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=5356s)]
```vex
float a = length(@P)^2 + @ptnum % 5;
float b = dot(@N, {0,1,0}*@Time);
if( a > b){
    @Cd = {1,0,0};
}
```
Demonstrates cleaner code formatting by extracting complex conditional expressions into named variables. The variables 'a' and 'b' make the logic more readable while producing identical results to inline expressions.

## Conditionals & Control Flow

### If Statement Curly Brace Styles [[Ep4, 90:32](https://www.youtube.com/watch?v=66WGmbykQhI&t=5432s)]
```vex
float a = length(@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```
Demonstrates two common code formatting styles for if statements: curly braces on the same line versus on separate lines. Both approaches are valid; separate lines can improve readability when tracking nested blocks. The example compares a distance-based value with a time-animated normal comparison to conditionally set color to red.

### Conditional Color Based on Comparisons [[Ep4, 92:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=5540s)]
```vex
float a = length(v@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```
This exercise demonstrates conditional coloring using if statements. It compares two computed values: 'a' (based on position length and point number modulo) and 'b' (based on normal dot product with up vector scaled by time), coloring points red when 'a' exceeds 'b'.

### If statement conditional coloring [Needs Review] [[Ep4, 93:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=5594s)]
```vex
float s = length(v@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (s > b){
    @Cd = {1,0,0};
}
```
Demonstrates conditional coloring using an if statement that compares two computed values: one based on position length and point number modulo, and another based on normal direction dot product with up vector scaled by time. Points are colored red when the first value exceeds the second.

### Conditional color based on math expression [[Ep4, 95:36](https://www.youtube.com/watch?v=66WGmbykQhI&t=5736s)]
```vex
vector @P;
float a = length(@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```
Compares two mathematical expressions to conditionally set point color to red. Variable 'a' combines point distance from origin with point number modulo, while 'b' uses dot product between normal and up vector scaled by time. Points are colored red when the first expression exceeds the second.

## Loops

### foreach vs for loop comparison [[Ep5, 101:14](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6074s)]
```vex
int pts[];
int pt;
float d;
vector pos, col;

// Using for loop
pts = nearpoints(1, @P, 40);
@Cd = 0;

for(int i=0; i<len(pts); i++) {
    pt = pts[i];
    pos = point(1, 'P', pt);
    col = point(1, 'Cd', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}

// Using foreach loop (cleaner approach)
pts = nearpoints(1, @P, 30);

foreach(pt; pts) {
    pos = point(1, 'P', pt);
    col = point(1, 'Cd', pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Demonstrates the difference between for loops and foreach loops when iterating over arrays in VEX. The foreach loop is cleaner and more idiomatic for array iteration since it directly accesses each element without manual indexing, while for loops are necessary when you don't have an array or need explicit index control.

### For loops with iteration-based spacing [[Ep5, 112:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6756s)]
```vex
for(int i = 0; i < 10; i++){
    addpoint(0, @P + (i * @N * 4));
}

for(int i = 0; i < 10; i++){
    addpoint(0, @P, @N * (i * 0.1));
}

addpoint(0, @P + (@N * 4));
```
Demonstrates using the loop counter variable to create progressively spaced points along the normal direction. By multiplying the normal vector by the iteration counter times 0.1, each new point is positioned 0.1 units further from the original point position than the previous point.

## Conditionals & Control Flow

### Variable in Vector Literal [Needs Review] [[Ep5, 33:40](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=2020s)]
```vex
float a = 42;
vector myvec = {a, 2, 3};
```
Demonstrates that variables cannot be directly used inside vector literal syntax with curly braces {a, 2, 3}. This code will produce a syntax error because VEX does not allow variable substitution within curly-brace vector literals. The set() function must be used instead to construct vectors from variables.

## Loops

### Array Iteration with For Loop [Needs Review] [[Ep5, 74:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4494s)]
```vex
int pts[];
int pt;
pts = inpointgroup(0, 'ring', pt);
for(int i=0; i<len(pts); i++){
    pt = pts[i];
    pts = pointneighbors(0, pt);
    vector pos = point(0, 'P', pt);
    float s = distance(@P, pos);
    s = s * ch('freq');
    s += @Time * ch('speed');
    s = sin(s);
    s *= ch('amp');
    s = fit(s, -1, 1, 0, 1);
    float val = chramp('offset', s, ch('radius'), i, 0);
    @P.y += val;
}
```
Iterates through points in a group using a for loop, accessing array elements with an index variable. For each point, retrieves neighbors and calculates animated displacement based on distance, applying sine wave deformation controlled by channel parameters and a ramp.

### For Loop Syntax Introduction [Needs Review] [[Ep5, 90:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5452s)]
```vex
int pts = npoints(0);
int pt = fit01(rand(@ptnum), 0, pts);
float d = 0.4, f = 1;

pts = nearpoints(1, @P, d);

foreach(int pt; pts) {
    vector Pnr = point(1, "P", pt);
    d = fit(Pnr.y, chs("min"), 1, 0);
    d = clamp(d, 0, 1);
    float c = @Time * ch("speed");
    c = rand(pt);
    vector p = @P;
    p.y = sin((c + @Time));
    p.y += ch("freq");
}
```
Demonstrates the transition from foreach loops to traditional for loops, showing how foreach syntax differs in structure. The code includes point cloud queries and uses foreach to iterate over nearby points, applying time-based sine wave deformation with randomization.

### For Loop Syntax Introduction [Needs Review] [[Ep5, 90:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5454s)]
```vex
// VEXpression
int pts[];
int pt;
float d, e, f, t;
vector pos, col, c, p;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, chf("max"), 1, 0);
    d = clamp(d, 0, 1);
    t = prim(0, "speed", 0);
    t = t * chf("t");
    c = e * set(1, 0, 0);
    p = e * chf("freq");
    @P.y += t * d;
}
```
Introduction to for loop syntax as a transition from foreach loops. The speaker is demonstrating the structural differences between foreach and traditional for loops, emphasizing that for loops require explicit initialization, test condition, and increment operations, making the syntax more complex but potentially more flexible for certain operations.

### For Loop Syntax and Nearpoints Color Blending [[Ep5, 90:56](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5456s)]
```vex
for (starting value; test; value increment) {

}

int i;

for (i=1; i<11; i+=1) {
    @a = i;
}

vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, 40); // search within 40 units
@Cd = 0;

for (i=0; i<len(pts); i++) {
    pt = pts[i];
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, 40, 1, 0);
    d = chramp("radius", d);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Demonstrates for loop syntax with three components: starting value, test condition, and increment. Shows practical application by iterating through nearby points found with nearpoints(), calculating distance-based weights using fit() and chramp(), then blending their colors into the current point's color attribute with distance falloff.

### For Loops with Array Length [[Ep5, 93:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5616s)]
```vex
int i;
for(i=1; i<11; i++){
    @a = i;
}

vector pos, col;
int pt;
int i;
float d;
int pts[];

pts = nearpoints(1,@P,40);
d = 0;

for(i=0; i<len(pts); i++) {
    pt = pts[i];
    pos = point(1,'P',pt);
    col = point(1,'Cd',pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col*d;
}
```
Demonstrates using for loops to iterate a fixed number of times and to iterate over arrays by checking array length with len(). The second example finds nearby points, loops through them using their array length, and accumulates color contributions based on distance, using fit() and clamp() to control the falloff.

### For Loop Initialization [[Ep5, 94:26](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5666s)]
```vex
int i;

for(i=1; i<11; i++){
    i += 1;
}
```
Demonstrates the initialization and basic structure of a for loop in VEX. The loop declares an integer counter variable, iterates from 1 to 10, and increments the counter in both the loop declaration and body (though incrementing twice is redundant and for demonstration purposes).

### For Loop Over Point Array [Needs Review] [[Ep5, 94:28](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5668s)]
```vex
int i;

for(i=1; i<11; i+=1) {
    @a = i;
}

for(i=0; i<len(pts); i++) {
    pt = pts[i];
    pos = point(0, "P", pt);
    col = point(0, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, chf("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd = col * d;
}
```
Demonstrates using a for loop to iterate over an array of points as an alternative to foreach. The loop uses an index variable to access each point number, then fetches position and color attributes to compute distance-based color blending.

### Color Blending with For Loop [Needs Review] [[Ep5, 97:58](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5878s)]
```vex
vector pos = @P;
int pt[];
int i, pt;
float d;

pt[] = nearpoints(1, @P, 40);
@Cd = 0;

for(int i=1; i<len(pt[]); i++) {
    pt = pt[i];
    pos = point(1, "P", pt);
    vector col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Uses a for loop to iterate through nearby points found by nearpoints(), accumulating their colors into the current point's @Cd attribute with distance-based falloff. The += operator adds each neighbor's weighted color contribution rather than replacing it, creating a blended result where multiple nearby point colors influence the final output.

### For Loop Iteration Mechanics [[Ep5, 98:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5922s)]
```vex
vector pos, col;
int pts[];
int i, pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

for(i=0; i<len(pts); i++) {
    pt = pts[i];
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(pos, @P);
    d = fit(d, 0, chf('radius'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd = col*d;
}
```
Demonstrates for loop iteration over an array of nearby points, clarifying that the loop counter iterates a number of times equal to the array length rather than directly iterating over array elements. The i++ increment operator is shorthand for i = i + 1, and each iteration retrieves the point number from the array using pts[i] to access point attributes and calculate distance-based color blending.

## Conditionals & Control Flow

### Handling Negative Color Values [[Ep6, 42:34](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2554s)]
```vex
@Cd = @N;
if (min(@Cd)<0) {
    @Cd = 0.1;
}
```
Assigns normal vectors to color attributes, then checks if any color component is negative using min(). If negative values are found (from normals pointing in negative axis directions), the entire color is set to a neutral gray (0.1) to avoid dark or invalid colors.
