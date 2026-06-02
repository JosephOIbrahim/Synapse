"""Headless probe v2: find the AMD material library dropdown on materiallinker.

materiallinker is a multiparm node (files_group/num_files, links_group/num_links).
The library dropdown lives *inside* those multiparms, so we instantiate one file
and one link, then dump the now-materialized inner parms + their menu items and
hunt for the AMD / library token. Run with hython 21.0.671.
"""
import sys

try:
    import hou
except Exception as e:  # pragma: no cover
    sys.stderr.write(f"no hou: {e}\n")
    raise SystemExit(2)

lines = []
def emit(s): lines.append(str(s))

stage = hou.node("/stage") or hou.node("/").createNode("lopnet", "stage_probe")
ml = stage.createNode("materiallinker")
emit(f"=== {ml.type().nameWithCategory()} ===")

# Instantiate one of each multiparm instance so inner parms appear.
for mp in ("num_files", "num_links"):
    p = ml.parm(mp)
    if p is not None:
        try:
            p.set(1)
            emit(f"set {mp}=1")
        except Exception as ex:
            emit(f"could not set {mp}: {ex}")

menu_report = []
parm_names = []
for p in ml.parms():
    pt = p.parmTemplate()
    parm_names.append(p.name())
    try:
        items = list(getattr(pt, "menuItems", lambda: ())())
        labels = list(getattr(pt, "menuLabels", lambda: ())())
        if items:
            menu_report.append((p.name(), list(zip(items, labels))[:80]))
    except Exception as ex:
        menu_report.append((p.name(), f"<menu err: {ex}>"))

emit("--- parm names ---")
emit(", ".join(parm_names))
emit("--- menus (name -> items) ---")
for name, pairs in menu_report:
    emit(f"{name}: {pairs}")

# Real hit test over PARM DATA ONLY (exclude our own headers).
data_blob = (", ".join(parm_names) + " " + repr(menu_report)).lower()
emit("--- token hits (parm data only) ---")
for kw in ("amd", "library", "matlib", "gpuopen", "materialx", "preset", "source"):
    emit(f"  '{kw}': {kw in data_blob}")

sys.stdout.write("\n".join(lines) + "\n")
