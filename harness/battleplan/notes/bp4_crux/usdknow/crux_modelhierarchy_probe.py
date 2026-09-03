"""BP4-CRUX USDKNOW independent probe: is the nested kind=component a valid USD model hierarchy?
Own probe, own anchor. Not the builder's."""
import os, sys
from pxr import Usd, Kind
b6 = os.environ.get("BP4_WL_USDC") or (sys.argv[1] if len(sys.argv) > 1 else "")
print("USD:", ".".join(str(x) for x in Usd.GetVersion()))
try:
    import hou; print("Houdini:", hou.applicationVersionString())
except Exception as e: print("Houdini: n/a", e)
print("file:", b6)
st = Usd.Stage.Open(b6)
print()
print("{:<52} {:<10} {:<8} {:<8} {:<8}".format("path", "kind", "IsModel", "IsGroup", "IsComponent"))
comps = []
for p in st.Traverse():
    k = p.GetMetadata("kind") or "-"
    if k == "-":
        continue
    m = Usd.ModelAPI(p)
    print("{:<52} {:<10} {:<8} {:<8} {:<8}".format(
        str(p.GetPath())[:52], k, str(p.IsModel()), str(p.IsGroup()), str(m.IsKind(Kind.Tokens.component))))
    if k == "component":
        comps.append(p)
print()
print("[CRUX-EV:nested-component-count] prims carrying kind=component = {} -> {}".format(
    len(comps), [str(p.GetPath()) for p in comps]))
if len(comps) >= 2:
    outer, inner = comps[0], comps[1]
    nested = str(inner.GetPath()).startswith(str(outer.GetPath()) + "/")
    print("[CRUX-EV:nested-component] {} is a descendant of component {} -> nested={} ; "
          "USD model hierarchy forbids a model under a component (components are leaf models)".format(
              inner.GetPath(), outer.GetPath(), nested))
    print("[CRUX-EV:inner-IsModel] inner.IsModel()={} (False => the broken hierarchy makes the inner prim "
          "invisible to Usd.ModelAPI / model traversal)".format(inner.IsModel()))
# does a default model traversal see one model or two?
seen = [str(p.GetPath()) for p in st.Traverse(Usd.PrimIsModel)]
print("[CRUX-EV:model-traversal] Stage.Traverse(Usd.PrimIsModel) yields {} prim(s): {}".format(len(seen), seen))
print("DONE")
