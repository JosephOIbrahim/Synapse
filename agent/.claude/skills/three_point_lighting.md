# Skill: Three-Point Lighting Setup

## When to Use
When the artist asks for a lighting rig, standard lighting, or three-point setup.

## Steps
1. Inspect the scene to find existing lights and the main subject
2. Create or configure a KEY light (warm, main illumination, 45 deg above-right)
3. Create or configure a FILL light (cool, softer, from the left)
4. Create or configure a RIM/BACK light (accent, behind the subject)
5. Wire all lights into the scene merge
6. Verify each light exists and has correct parameters
7. Offer a preview render

## Parameter Guidelines
- Key: warm (2800-4000K equivalent), intensity 1.0-2.0
- Fill: cool (6500-8000K equivalent), intensity 0.3-0.5
- Rim: accent color matching scene mood, intensity 0.6-1.0

## H21 Notes
- Use `distantlight::2.0` for key and rim
- Use `rectlight::2.0` for fill (softer falloff)
- Or `domelight::2.0` for ambient fill
- Parameter names are encoded: inspect nodes to confirm exact names
