import sys, json, glob
sys.path.insert(0, r"C:\Users\User\SYNAPSE\.claude\worktrees\bp2-integration\harness\battleplan")
import mission_schema as ms
errs = 0
for p in sorted(glob.glob(r"C:\Users\User\SYNAPSE\harness\battleplan\missions\BP2-*.json")):
    m = json.load(open(p, encoding="utf-8"))
    fn = getattr(ms, "validate", None) or getattr(ms, "validate_mission", None)
    try:
        r = fn(m) if fn.__code__.co_argcount == 1 else fn(m, p)
    except TypeError:
        r = fn(p)
    problems = r if isinstance(r, list) else ([] if r in (None, True, 0) else [str(r)])
    errs += len(problems)
    print(f"{m['id']:16s} tier={m.get('tier','-'):10s} deps={m['deps']} -> {'OK' if not problems else problems}")
print("errors:", errs)
