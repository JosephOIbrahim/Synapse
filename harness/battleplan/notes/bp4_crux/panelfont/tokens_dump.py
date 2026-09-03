import synapse.panel.designsystem.tokens as t
print("BOUND tokens.__file__ =", t.__file__)
print()
print("FONT_SANS_CSS =", repr(getattr(t, "FONT_SANS_CSS", None)))
print("FONT_MONO_CSS =", repr(getattr(t, "FONT_MONO_CSS", None)))
for n in sorted(dir(t)):
    if n.startswith("FONT_") and n not in ("FONT_SANS_CSS","FONT_MONO_CSS"):
        print(f"{n} = {repr(getattr(t,n))[:120]}")
print()
sizes = {n: getattr(t, n) for n in sorted(dir(t)) if n.startswith("SIZE_") and isinstance(getattr(t, n), int)}
for k, v in sizes.items():
    print(f"{k} = {v}")
print("min(SIZE_*) =", min(sizes.values()), " FONT_FLOOR_PX =", t.FONT_FLOOR_PX,
      " -> min >= floor:", min(sizes.values()) >= t.FONT_FLOOR_PX)
print()
for n in sorted(dir(t)):
    if n.startswith("WEIGHT_"):
        print(f"{n} = {getattr(t,n)}")
print()
for n in sorted(dir(t)):
    if "LEADING" in n or "LINE" in n or "TRACK" in n:
        print(f"{n} = {repr(getattr(t,n))[:200]}")
print()
print("FONT_FLOOR_PROVENANCE[:60] =", repr(t.FONT_FLOOR_PROVENANCE[:60]))
print("provenance starts with UNKNOWN:", t.FONT_FLOOR_PROVENANCE.strip().upper().startswith("UNKNOWN"))
print()
print("TYPE_ROLES:")
for k, v in t.TYPE_ROLES.items():
    print("   ", k, "->", v)
print()
print("FONT_SCALE_DEFAULT =", getattr(t, "FONT_SCALE_DEFAULT", None))
