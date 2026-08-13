import re, py_compile, sys
BASE = r'C:\Users\User\SYNAPSE\harness\autoresearch'
FILES = [BASE + r'\mission_schema.py', BASE + r'\probes.py', BASE + r'\runner.py']

def union_resolve(path):
    lines = open(path, encoding='utf-8').read().splitlines(keepends=True)
    out, mode, ours, theirs = [], 0, [], []
    for ln in lines:
        s = ln.lstrip()
        if s.startswith('<<<<<<<'):
            mode, ours, theirs = 1, [], []
            continue
        if s.startswith('|||||||'):
            mode = 3  # diff3 base section - discard
            continue
        if s.startswith('======='):
            mode = 2
            continue
        if s.startswith('>>>>>>>'):
            out += ours + theirs
            mode = 0
            continue
        if mode == 0: out.append(ln)
        elif mode == 1: ours.append(ln)
        elif mode == 2: theirs.append(ln)
        # mode 3: dropped
    open(path, 'w', encoding='utf-8').writelines(out)

for f in FILES:
    union_resolve(f)

# semantic fix: VALID_KINDS set closed twice after union -> single line with both kinds
ms = FILES[0]
txt = open(ms, encoding='utf-8').read()
pat = re.compile(r'"fixture_hash", "usd_schema_probe"\}\n(\s*)"fixture_hash", "store_census"\}')
txt2, n = pat.subn('"fixture_hash", "usd_schema_probe", "store_census"}', txt)
open(ms, 'w', encoding='utf-8').write(txt2)
print('VALID_KINDS collapsed:', n)

for f in FILES:
    leftover = [i + 1 for i, ln in enumerate(open(f, encoding='utf-8'))
                if ln.lstrip().startswith(('<<<<<<<', '=======', '>>>>>>>', '|||||||'))]
    print(f.split('\\')[-1], 'markers-left:', leftover or 'none')
    py_compile.compile(f, doraise=True)
    print(f.split('\\')[-1], 'py_compile: OK')

r = open(FILES[2], encoding='utf-8').read()
print('runner usd_schema kind refs:', r.count('usd_schema_probe'), '| store_census refs:', r.count('store_census'))
