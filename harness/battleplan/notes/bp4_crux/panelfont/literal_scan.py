"""Apply the test's own _LITERAL_TYPO regex (post comment-strip) to EVERY file
under python/synapse/panel/ — the crux's independent re-run of the check the
builder pointed at exactly one file."""
import os, re, sys
ROOT = sys.argv[1]
PANEL = os.path.join(ROOT, "python", "synapse", "panel")
_LITERAL_TYPO = re.compile(r"font-(?:size|weight|family)\s*:\s*(?!\{)[^\s;\n]")
def strip(src):
    return re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
rows = []
for dirpath, _dn, fn in os.walk(PANEL):
    for f in sorted(fn):
        if not f.endswith(".py"):
            continue
        p = os.path.join(dirpath, f)
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        try:
            src = open(p, "r", encoding="utf-8").read()
        except Exception as e:
            rows.append((rel, -1, [str(e)])); continue
        body = strip(src)
        hits = []
        for m in _LITERAL_TYPO.finditer(body):
            ln = body[: m.start()].count("\n") + 1
            seg = body[m.start():].split(";", 1)[0].split("\n", 1)[0].strip()
            hits.append("L%d: %s" % (ln, seg[:70]))
        rows.append((rel, len(hits), hits))
tot = sum(r[1] for r in rows if r[1] > 0)
print("TOTAL literal-typography hits under python/synapse/panel/ =", tot)
print("files scanned =", len(rows))
print()
print("--- per-file, nonzero, sorted desc ---")
for rel, n, hits in sorted(rows, key=lambda r: -r[1]):
    if n > 0:
        print(f"{n:5d}  {rel}")
print()
print("--- designsystem/*.py explicitly (incl zeros) ---")
for rel, n, hits in sorted(rows):
    if "/designsystem/" in rel:
        print(f"{n:5d}  {rel}")
print()
print("--- sample hits from the 3 biggest offenders ---")
for rel, n, hits in sorted(rows, key=lambda r: -r[1])[:3]:
    print(f"### {rel} ({n} hits) — first 4:")
    for h in hits[:4]:
        print("     ", h)
