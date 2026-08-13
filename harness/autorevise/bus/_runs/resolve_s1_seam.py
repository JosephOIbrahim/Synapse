import py_compile
f = r'C:\Users\User\SYNAPSE\python\synapse\memory\store.py'
lines = open(f, encoding='utf-8').read().splitlines(keepends=True)
# conflict block spans lines 1106..1128 (1-based) inclusive
assert lines[1105].lstrip().startswith('<<<<<<<'), lines[1105]
assert lines[1127].lstrip().startswith('>>>>>>>'), lines[1127]
head_comment = lines[1106:1116]  # HEAD's comment block (keep - accurate history)
new_block = head_comment + [
    "            # MERGE COMPOSITION (W1 x W2-S1): _safe_unsaved_base reads hou\n",
    "            # internally, so the CALL is marshalled via _read_on_main -- W1's\n",
    "            # path semantics on S1's thread discipline; direct passthrough on\n",
    "            # main keeps headless/hython behaviour byte-identical.\n",
    "            temp_root = _read_on_main(\n",
    "                _safe_unsaved_base, label=\"synapse_store_resolve_unsaved\"\n",
    "            )\n",
]
out = lines[:1105] + new_block + lines[1128:]
open(f, 'w', encoding='utf-8').writelines(out)
leftover = [i + 1 for i, ln in enumerate(open(f, encoding='utf-8'))
            if ln.lstrip().startswith(('<<<<<<<', '=======', '>>>>>>>'))]
print('markers-left:', leftover or 'none')
py_compile.compile(f, doraise=True)
print('py_compile: OK')
print(''.join(out[1112:1123]))
