import py_compile
f = r'C:\Users\User\SYNAPSE\docs\SUPPORT_MATRIX.md'
lines = open(f, encoding='utf-8').read().splitlines(keepends=True)
assert lines[60].startswith('<<<<<<<'), lines[60]
assert lines[78].startswith('======='), lines[78]
assert lines[153].startswith('>>>>>>>'), lines[153]
head_side = lines[61:78]    # W2 registration section (2026-08-09)
theirs    = lines[79:153]   # wave-3 contracts section (2026-08-13)
update = [
    "\n",
    "> **Update (2026-08-13, post-PAPER):** the paragraph above records the board at\n",
    "> PAPER's writing time. Since then: all five durability-blocked legs received their\n",
    "> named-file commits, the W3-CRUX receipt was committed on `wave3/crux`, and the\n",
    "> full wave (dim..harden, crux, paper) merged to `master` with zero code conflicts;\n",
    "> the dim root-cause test was re-pinned to the FIXED contract (init succeeds via\n",
    "> loud derived-data rebuild). Live-seat `moneta_substrate=ok` remains gated on the\n",
    "> next Houdini relaunch + reinstall, per this matrix's own rule.\n",
]
out = lines[:60] + head_side + ["\n"] + theirs + update + lines[154:]
open(f, 'w', encoding='utf-8').writelines(out)
leftover = [i + 1 for i, ln in enumerate(open(f, encoding='utf-8'))
            if ln.startswith(('<<<<<<<', '=======', '>>>>>>>'))]
print('markers-left:', leftover or 'none')
print('lines:', len(out))
