import zipfile

Z = r"C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\hom.zip"
with zipfile.ZipFile(Z) as z:
    for entry in ("hou/ActiveRender.txt", "hou/activeRenders.txt", "hou/IPRViewer.txt"):
        try:
            t = z.read(entry).decode("utf-8", errors="replace")
        except KeyError:
            print(entry, "ABSENT"); continue
        print("=" * 72)
        print(entry, "|", len(t), "chars")
        print("=" * 72)
        if "IPRViewer" in entry:
            i = t.lower().find("killrender")
            print(" ".join(t[max(0, i - 400):i + 700].split())[:1000])
        else:
            print(t[:1800])
        print()
