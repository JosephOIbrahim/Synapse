"""V1 / Q2a + Q4b — the exact ID-AOV and denoiser parm spellings, with DEFAULTS.

Read before the render matrix is written, so the render script guesses no
spellings. Guessing a spelling is how a phantom enters a codebase; the menus and
defaults below are the build's own answer.

Answers:
  * every parm on `rendervar` (which one carries the data type / format)
  * primid / element / cryptomatte parms on karmarendersettings, with DEFAULTS
    and menu items -- incl. primidfilter and primidprecision
  * the denoiser default (Q4: "is it on by default")

Run:  hython3.13.exe harness/notes/v1_q2_parmdetail.py
Emits: harness/notes/v1_q2_parmdetail.json
"""
from __future__ import annotations

import json
import os
import sys

import hou

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "v1_q2_parmdetail.json")

WANTED_KRS = [
    "primid", "primidfilter", "primidprecision",
    "element", "elementfilter", "elementprecision",
    "denoiser", "denoise_aovs", "denoise_cpu_only", "denoise_separate_aovs",
    "denoise_useN", "denoise_usealbedo",
]


def parm_info(p):
    t = p.parmTemplate()
    info = {
        "name": p.name(),
        "label": t.label(),
        "type": type(t).__name__,
        "default": None,
        "eval": None,
        "menu_items": None,
        "menu_labels": None,
    }
    try:
        dv = t.defaultValue()
        info["default"] = list(dv) if isinstance(dv, (list, tuple)) else dv
    except Exception:  # noqa: BLE001
        pass
    try:
        info["eval"] = p.eval()
    except Exception:  # noqa: BLE001
        pass
    try:
        items = t.menuItems()
        if items:
            info["menu_items"] = list(items)
            info["menu_labels"] = list(t.menuLabels())
    except Exception:  # noqa: BLE001
        pass
    return info


def main() -> int:
    report = {
        "schema": "v1-q2-parmdetail/1",
        "build": hou.applicationVersionString(),
    }
    stage = hou.node("/stage")

    # --- rendervar: the COMPLETE parm list (R58 control -- read it all) ------
    rv = stage.createNode("rendervar", "_v1_rv")
    report["rendervar_all_parms"] = [parm_info(p) for p in rv.parms()]
    report["rendervar_parm_names"] = [p.name() for p in rv.parms()]
    rv.destroy()

    # --- karmarendersettings: the ID + denoiser parms, with defaults --------
    krs = stage.createNode("karmarendersettings", "_v1_krs")
    got = {}
    for name in WANTED_KRS:
        p = krs.parm(name)
        got[name] = parm_info(p) if p is not None else {"ABSENT": True}
    report["karmarendersettings"] = got
    # Any parm mentioning cryptomatte, in full.
    report["krs_cryptomatte_parms"] = [
        p.name() for p in krs.parms() if "cryptomatte" in p.name().lower()
    ]
    krs.destroy()

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("=== rendervar parms (%d) ===" % len(report["rendervar_parm_names"]))
    for pi in report["rendervar_all_parms"]:
        extra = ""
        if pi["menu_items"]:
            extra = f"  MENU={pi['menu_items'][:12]}"
        print(f"  {pi['name']:52s} {str(pi['type'])[:18]:18s} "
              f"default={str(pi['default'])[:26]:26s} eval={str(pi['eval'])[:20]}{extra}")

    print("\n=== karmarendersettings ID + denoiser ===")
    for name, pi in report["karmarendersettings"].items():
        if pi.get("ABSENT"):
            print(f"  {name:24s} ABSENT")
            continue
        extra = f"  MENU={pi['menu_items']}" if pi["menu_items"] else ""
        print(f"  {name:24s} default={str(pi['default'])[:20]:20s} "
              f"eval={str(pi['eval'])[:20]:20s}{extra}")
    print("\ncryptomatte parms:", report["krs_cryptomatte_parms"])
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
