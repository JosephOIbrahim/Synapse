# Houdini Expressions Reference

## Frame and Time Variables
| Variable | Description |
|----------|-------------|
| `$F` | Current frame number (integer) |
| `$FF` | Current frame number (float, for subframes) |
| `$T` | Current time in seconds |
| `$FSTART` | Start frame of playbar range |
| `$FEND` | End frame of playbar range |
| `$FPS` | Frames per second |
| `$TLENGTH` | Total length in seconds |
| `$NFRAMES` | Total number of frames |

## Geometry Variables
| Variable | Description |
|----------|-------------|
| `$PT` | Current point number |
| `$NPT` | Total number of points |
| `$PR` | Current primitive number |
| `$NPR` | Total number of primitives |
| `$CEX/$CEY/$CEZ` | Centroid of geometry |
| `$SIZEX/$SIZEY/$SIZEZ` | Bounding box size |
| `$XMIN/$XMAX` | Bounding box extents X |
| `$YMIN/$YMAX` | Bounding box extents Y |
| `$ZMIN/$ZMAX` | Bounding box extents Z |

## Channel References
| Expression | Description |
|------------|-------------|
| `ch("parm")` | Read float parm on same node |
| `ch("../node/parm")` | Read parm from relative path |
| `chs("parm")` | Read string parm |
| `chf("parm", frame)` | Read float at specific frame |
| `chramp("ramp", pos)` | Evaluate ramp at position 0-1 |

## Input References
| Expression | Description |
|------------|-------------|
| `opinput(".", 0)` | Path to first input node |
| `opinput(".", 1)` | Path to second input node |
| `opinputpath(".", 0)` | Full path to first input |
| `opninputs(".")` | Number of connected inputs |

## String Expressions
| Expression | Description |
|------------|-------------|
| `$HIP` | HIP file directory |
| `$HIPNAME` | HIP file name (no extension) |
| `$HIPFILE` | Full HIP file path |
| `$JOB` | Job directory |
| `$OS` | Current node name |
| `$ACTIVETAKE` | Current take name |

## Common Expression Patterns

### Oscillation
```
sin($T * 360 * frequency) * amplitude
```

### Random per-copy
```
fit01(rand($PT), min, max)
```

### Frame-based file path
```
$HIP/render/$HIPNAME.$F4.exr
```
(`$F4` = frame padded to 4 digits)

### Conditional
```
if($F < 100, value_a, value_b)
```

### Referencing another node's output
```
point(opinputpath(".", 0), $PT, "P", 0)
```

## HScript vs Python vs VEX
- **HScript expressions**: `ch()`, `$F`, etc. (default for parm fields in non-VEX contexts)
- **Python expressions**: toggle via parm RMB > "Expression > Change Language to Python"
- **VEX**: Used in `attribwrangle`. Different syntax — `@P`, `@ptnum`, `ch("parm")` all work

### When to Use Which
| Context | Language | Example |
|---------|----------|---------|
| Parameter field | HScript | `$F`, `ch("tx")` |
| Parameter field (complex) | Python | `hou.pwd().evalParm("tx")` |
| Attribute wrangle | VEX | `@P`, `f@density = ch("val")` |
| Execute Python node | Python | `hou.node("/obj/geo1")` |

### Common Gotcha
HScript `ch()` in parameter fields and VEX `ch()` in wrangles look the same but are different:
- HScript `ch()`: Evaluates at current frame, returns node parm value
- VEX `ch()`: Reads spare parm on the wrangle node itself (used with sliders)
