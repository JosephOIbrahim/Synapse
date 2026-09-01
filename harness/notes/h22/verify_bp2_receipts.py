import json, glob
for p in sorted(glob.glob(r'C:/Users/User/SYNAPSE/.claude/worktrees/bp2-*/harness/notes/receipts/BP2-*.json')):
    d = json.load(open(p, encoding='utf-8'))
    acc = d.get('acceptance') or d.get('acceptance_rows') or d.get('rows') or []
    def res(a):
        return str(a.get('result', a.get('status', a.get('verdict', '')))).lower()
    ps = sum(1 for a in acc if res(a).startswith(('pass', 'true', 'green')))
    un = sum(1 for a in acc if 'unknown' in res(a))
    keys = [k for k in d.keys()][:12]
    print(f"{d.get('id', d.get('leg', p.split('/')[-1])):16s} status={str(d.get('status', d.get('leg_status', '?'))):22s} "
          f"acc={ps}/{len(acc)} unknown={un} head={str(d.get('head', d.get('commit', d.get('receipt_commit', '?'))))[:8]} "
          f"product={str(d.get('product_commit', d.get('product', '?')))[:8]}")
    print("   keys:", ", ".join(keys))
