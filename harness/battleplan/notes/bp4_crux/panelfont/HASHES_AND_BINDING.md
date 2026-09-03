# BP4-CRUX · PANELFONT lane — binding proof + 5-scale stylesheet hashes

## Import-binding proof (the trap the referee named)

NEGATIVE (unbound `python -c`, run from `C:/Users/User` — the editable install
points `import synapse` at the MASTER tree):
```
__file__: C:\Users\User\Synapse\python\synapse\panel\designsystem\tokens.py
AttributeError: module 'synapse.panel.designsystem.tokens' has no attribute 'FONT_FLOOR_PX'
```
POSITIVE (`PYTHONPATH="<SCR_P>/python;<SCR_P>"`):
```
__file__: ...\scratchpad\p\python\synapse\panel\designsystem\tokens.py
FONT_FLOOR_PX: 10
```
pytest binds itself (pyproject.toml `pythonpath = ["python"]`, line 108); every
pytest run above printed `rootdir: ...\scratchpad\p` (or `\m`).
Interpreter: Python 3.14.2, pytest 8.4.2, no PySide6 (Qt tests skip honestly).

## 5-scale stylesheet hashes — crux re-run, both trees

`sha256(qss.stylesheet(scale).encode('utf-8')).hexdigest()[:8]`

| scale | branch (SCR_P @ 4b3b3967) | master (SCR_M @ 3a27d1ff) | builder claimed | len |
|---|---|---|---|--:|
| 1.0  | 1779b114 | 1779b114 | 1779b114 | 18076 |
| 1.15 | 7a1a99e7 | 7a1a99e7 | 7a1a99e7 | 18076 |
| 1.25 | e7d4298e | e7d4298e | e7d4298e | 18076 |
| 1.4  | be8d2aaa | be8d2aaa | be8d2aaa | 18076 |
| 1.6  | c99024cd | c99024cd | c99024cd | 18076 |

Branch == master at all five scales, and both == the builder's five hashes.
The "byte-identical stylesheet" claim REPRODUCES independently.
Sensitivity is proven, not assumed: M1 and M2 each moved all five hashes.

## Token surface (bound to the branch tree)

FONT_SANS = 'Space Grotesk'  (+ DM Sans, Segoe UI, sans-serif)
FONT_MONO = 'Space Mono'     (+ JetBrains Mono, Consolas, monospace)
SIZE_MICRO 10 · SIZE_LABEL 10 (alias) · SIZE_SMALL 11 · SIZE_UI 12 · SIZE_BODY 12
SIZE_TITLE 15 · SIZE_HERO 19          -> 5 DISTINCT sizes (cap is 5; at the boundary)
WEIGHT_REGULAR 400 · WEIGHT_MEDIUM 500 · WEIGHT_SEMIBOLD 600
FONT_FLOOR_PX = 10 ;  min(SIZE_*) = 10  ->  min >= floor  TRUE (equality, not slack)
CHAT_LEADING_PT = 0.75   (the leading token that stands in for line-height)
FONT_FLOOR_PROVENANCE[:60] = "UNKNOWN - the local H22.0.400 help cache states no default U"

## Independent H22 help-cache search (crux, broader than the builder's)

Builder searched `ref` + `basics` + `hom`. The crux searched the WHOLE cache
(`.../houdini22.0/config/Help/cache`, 2280 files):
- files containing "font" (any case): 23 — node docs (Font COP, Labs UV grid,
  MOPs Typography), font-library LICENSES (fontconfig/fonttools/freetype/SIL-OFL),
  and index/search blobs.
- files matching `UI font|default font|font size|fontsize|interface font`: **1**,
  `nodes/sop/MOPSPlus--Typography-1.0.json` — and its hits are that node's own
  "Font Size" PARAMETER doc ("Use this slider to change the preview font size"),
  a third-party SOP parameter, not a Houdini preferences statement.
- files matching `General User Interface|Interface font|preference.*font`: **0**.

VERDICT: the builder's DOC-STATED = absent claim is CONFIRMED over a wider surface.
The floor's UNKNOWN provenance is honest.
