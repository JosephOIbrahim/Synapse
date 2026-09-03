# BP4-CRUX · PANELFONT lane — mutation log

Scratch clone (mutations happened ONLY here):
`.../scratchpad/p` = fresh `git clone --shared` of `bp4/panelfont` @ 4b3b3967
(product 81f3fb08, base 28a0e183). Restore method after every mutation:
`git show HEAD:<path> > <path>` then `git status --short` (empty = tracked clean).

Green baseline before any mutation:
- `python -m pytest tests -k panel -q` -> 352 passed, 85 skipped, 0 failed
- `python -m pytest tests/test_panel_typography.py -q` -> 6 passed
- 5-scale hashes: 1779b114 / 7a1a99e7 / e7d4298e / be8d2aaa / c99024cd (len 18076 each)

---

## PANELFONT-M1 — re-introduce a hardcoded px size  →  REDDENED

Edit: `designsystem/qss.py:51`  `font-size: {s(t.SIZE_UI)}px;` -> `font-size: 13px;`

Reddened: `tests/test_panel_typography.py::test_qss_stylesheet_source_has_no_literal_typography`
```
AssertionError: literal typography in designsystem/qss.py (must be a token ref such as
{s(t.SIZE_UI)}px or {t.WEIGHT_SEMIBOLD}): ['L42: font-size: 13px']
1 failed, 5 passed
```
5-scale hashes under mutation (all five moved):
```
1.0   2c26ba32   1.15  b1532305   1.25  b6061705   1.4  b0ca38ae   1.6  17de59f5
```
NIT: the failure message reports `L42`; the real source line is 51. The test computes
the line number from the COMMENT-STRIPPED body, so every reported line number is
offset by the bytes of the comments above it. Cosmetic, but it misdirects the reader.

Restored -> 6 passed, hashes back to 1779b114 / 7a1a99e7 / e7d4298e / be8d2aaa / c99024cd.

---

## PANELFONT-M2 — size token below the floor  →  REDDENED

Edit: `designsystem/tokens.py:308`  `SIZE_MICRO = 10` -> `SIZE_MICRO = 9`

Reddened: `tests/test_panel_typography.py::test_no_size_token_below_floor`
```
AssertionError: size token(s) below FONT_FLOOR_PX=10: {'SIZE_LABEL': 9, 'SIZE_MICRO': 9}
1 failed, 5 passed
```
(`SIZE_LABEL` is an alias of `SIZE_MICRO`, so both report.)

Full `-k panel` sweep under M2: **1 failed, 351 passed** — the ONLY test that catches
it is the new one. Before this leg, lowering `SIZE_MICRO` was undetectable by the suite.

5-scale hashes under mutation (all five moved; scale 1.0 also shrank by 2 bytes as
`10`->`9` in two badge/micro rules):
```
1.0   071b00a6 (len 18074)   1.15  f1f29567   1.25  b450201a   1.4  4a267bba   1.6  b583d8e5
```
Restored -> tracked clean, 6 passed.

---

## PANELFONT-M3 — QWidget subclass with hardcoded hex + px  →  SURVIVED `-k panel`

Appended to `python/synapse/panel/synapse_panel.py`:
```python
class CruxProbeWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("color: #ff0066; font-size: 13px;")
```
`python -m pytest tests -k panel -q` -> **352 passed, 85 skipped, 0 failed. NOTHING reddened.**

Run DIRECTLY, the BP3-precedent guard does catch it:
```
python -m pytest tests/test_rope_design_conformance.py -v
  test_no_hardcoded_hex_or_px_outside_designsystem FAILED
  python\synapse\panel\synapse_panel.py:2757: ['#ff0066', '13px']
  1 failed, 3 passed
```
ROOT CAUSE of the survival — `-k panel` DESELECTS the guard:
```
python -m pytest tests/test_rope_design_conformance.py -k panel --collect-only -q
  collected 4 items / 3 deselected / 1 selected
```
Neither the module name (`test_rope_design_conformance`) nor the test name
(`test_no_hardcoded_hex_or_px_outside_designsystem`) contains the substring
"panel", so `-k panel` — the exact command the leg's acceptance-4 evidence
names — never runs the guard. Only `test_panel_consumes_designsystem` is selected.

The crux's own T-A diff-scope check also reddens under M3
(`git diff 28a0e183 -- .../synapse_panel.py | wc -c` -> 727, expected 0).

Restored -> tracked clean; guard 4 passed; `-k panel` 352 passed.

---

## PANELFONT-M4 — TYPE_ROLES "body" weight back to a BARE literal 400  →  SURVIVED

Edit: `tokens.py` `"body": (FONT_SANS_CSS, SIZE_BODY, WEIGHT_REGULAR, 0.0)`
   -> `"body": (FONT_SANS_CSS, SIZE_BODY, 400, 0.0)`

`test_type_roles_use_weight_tokens` -> **PASSED**. Full `-k panel` -> 352 passed.
5-scale hashes UNCHANGED (400 == WEIGHT_REGULAR, so the render is identical).

Honest reading: this is a guard NUANCE, not a defect. The test asserts set
membership of the weight VALUE (`spec[2] in {400,500,600}`), so a bare literal that
happens to equal a token is indistinguishable from the token at runtime. The
mutation is a semantic no-op. But the test's own docstring claims TYPE_ROLES weights
are "never bare literals" — that half of the claim is NOT enforced by any test.

## PANELFONT-M4b — TYPE_ROLES "body" weight -> 450 (value outside the token set)  →  REDDENED

`test_type_roles_use_weight_tokens` FAILED. So the guard is real for out-of-set
VALUES; it is blind to bare-literal STYLE. Restored -> tracked clean, 6 passed.

---

Final state: `git status --short` empty, `git diff --stat HEAD` empty,
`tests/test_panel_typography.py` 6 passed, `tests -k panel` 352 passed / 85 skipped.
