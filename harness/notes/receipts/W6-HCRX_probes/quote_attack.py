import json, os, subprocess, sys, tempfile, shutil
STAGE = r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w6-hcrx/b7cb3ce1-8197-4196-aea0-7176b9c8937b/scratchpad/w6combined"
ATT   = r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w6-hcrx/b7cb3ce1-8197-4196-aea0-7176b9c8937b/scratchpad/attacks"
sys.path.insert(0, os.path.join(STAGE, "harness", "autorevise"))
from quote_safe import sanitize_sq  # noqa

ORCH = os.path.join(STAGE, "harness", "orchestrate.ps1")
DRIVER = os.path.join(ATT, "quote_attack.ps1")
ps = shutil.which("powershell") or shutil.which("pwsh")
BS = chr(92)  # backslash, avoids escape headaches

NAMES = {
    "herestring-term":  'X\n"@\nRemove-Item C:' + BS + ' -Recurse -Force',
    "herestring-bare":  '"@',
    "at-quote-here":    "@'evil'@",
    "fg-breakout":      "evil' -ForegroundColor Red; Remove-Item C:" + BS + "; Write-Host '",
    "close-then-cmd":   "'; Stop-Computer; '",
    "dollarparen-apos": "'; $(Remove-Item C:" + BS + "); '",
    "apos-run-odd":     "'''''",
    "apos-run-even":    "''''''",
    "empty-name":       "",
    "crlf-name":        "a\r\nb'c",
    "long-brief":       ("spill'" * 400)[:2000],
    "everything-plus":  "a'" + chr(34) + "`$(rm)b\u2014\u65e5\n" + chr(34) + "@\nWrite-Host PWNED",
    "subexpr-bare":     "$(1+1)",
    "backtick-nl":      "line`nstuff'end",
}
BRANCHES = {
    "br-herestring": 'wave6/x\n"@\nRemove-Item C:' + BS,
    "br-fg":         "feat/a' -ForegroundColor Red; Stop-Process -Name x; '",
}
def legs():
    L = []
    for lbl, nm in NAMES.items():
        L.append({"id": lbl, "name": nm, "branch": "wave6/hcrx",
                  "worktree": ".claude/worktrees/%s" % lbl, "prompt": "harness/x.md",
                  "readonly": False, "deps": []})
    for lbl, br in BRANCHES.items():
        L.append({"id": lbl, "name": "safe", "branch": br,
                  "worktree": ".claude/worktrees/%s" % lbl, "prompt": "harness/x.md",
                  "readonly": False, "deps": []})
    L.append({"id": "idinj-apos", "name": "n", "branch": "wave6/hcrx",
              "worktree": ".claude/worktrees/idinj", "prompt": "harness/x.md",
              "readonly": False, "deps": []})
    return L

tmp = tempfile.mkdtemp(prefix="quoteatk_")
man = os.path.join(tmp, "manifest.json")
with open(man, "w", encoding="utf-8") as f:
    json.dump({"settings": "harness/relay-settings.json", "effort": "high", "legs": legs()}, f)
outjson = os.path.join(tmp, "results.json")
def fwd(p): return p.replace(BS, "/")
r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", fwd(DRIVER), "-Orch", fwd(ORCH), "-Repo", fwd(tmp),
                    "-ManifestFile", fwd(man), "-OutDir", fwd(tmp), "-OutJson", fwd(outjson)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
if r.returncode != 0 or not os.path.exists(outjson):
    print("DRIVER FAILED rc=%s" % r.returncode); print("STDOUT", r.stdout[-2000:]); print("STDERR", r.stderr[-2000:]); sys.exit(2)
data = json.loads(open(outjson, encoding="utf-8-sig").read())

fails = []
print("%-18s %-6s %-4s %-4s %-14s %s" % ("leg", "exists", "cnt", "bom", "unexpected", "verdict"))
print("-"*74)
order = list(NAMES)+list(BRANCHES)+["idinj-apos"]
for lbl in order:
    e = data.get(lbl)
    if e is None:
        fails.append((lbl, "no result")); print("%-18s MISSING" % lbl); continue
    rp = os.path.join(tmp, "orch_%s.ps1" % lbl)
    runner = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
    pybom = open(rp, "rb").read(3) == b"\xef\xbb\xbf" if os.path.exists(rp) else None
    unexp = e.get("unexpected") or []
    name = NAMES.get(lbl)
    esc_ok = True
    if name:
        esc_ok = sanitize_sq(name) in runner
    elif lbl in BRANCHES:
        esc_ok = sanitize_sq(BRANCHES[lbl]) in runner
    ok = (e.get("exists") and e.get("count") == 0 and not e.get("bom") and not pybom
          and not unexp and esc_ok)
    verdict = "CLEAN"
    if not ok:
        why = []
        if not e.get("exists"): why.append("no-runner")
        if e.get("count") != 0: why.append("parse-err=%s" % e.get("errors"))
        if e.get("bom") or pybom: why.append("BOM")
        if unexp: why.append("INJECTED=%s" % unexp)
        if not esc_ok: why.append("escaped-name-missing")
        fails.append((lbl, "; ".join(why))); verdict = "DIRTY"
    print("%-18s %-6s %-4s %-4s %-14s %s" % (lbl, e.get("exists"), e.get("count"),
          bool(e.get("bom") or pybom), str(unexp), verdict))
print("-"*74)
print("TOTAL: %d   CLEAN: %d   DIRTY: %d" % (len(order), len(order)-len(fails), len(fails)))
if fails:
    print("\nDIRTY DETAIL:")
    for lbl, why in fails: print("  %-18s %s" % (lbl, why))
    print("\nQUOTE-ATTACK-VERDICT: FINDING")
else:
    print("\nQUOTE-ATTACK-VERDICT: PASS (parse-clean + BOM-free + zero injected commands + escaped payload present, on ALL %d adversarial inputs)" % len(order))
print("TMP=%s" % tmp)
