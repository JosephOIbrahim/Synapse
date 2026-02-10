# Skill: Karma Render Preview

## When to Use
When the artist wants to see a quick render of the current scene state.

## Steps
1. Find the Karma ROP (typically /stage/karma_rop or /out/karma)
2. If no ROP exists, create one
3. Set preview resolution (512x512)
4. Set low samples for speed
5. Set output path to C:/Users/User/.synapse/renders/preview.exr
6. Trigger render
7. Report completion and file path

## Iteration Pattern
If the artist wants adjustments:
1. Adjust the scene (lights, materials, camera)
2. Re-render preview
3. Compare results
4. Repeat until satisfied
5. Offer final render at full resolution
