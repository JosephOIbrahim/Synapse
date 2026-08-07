# Scout triage

evidence  `C:\Users\User\SYNAPSE\harness\autoresearch\runs\solaris_basic_20260805_181235\lop_truth_22.0.368.json`  ·  build `22.0.368`  ·  tier `scout`

**dead_literals_confirmed**
```json
[
 "usdrender",
 "usd",
 "graft",
 "geometryclipsequence"
]
```

**successors**
```json
{
 "usdrender": [
  "usdrender_rop"
 ],
 "usd": [
  "inlineusd",
  "usd_rop",
  "usdrender_rop"
 ],
 "graft": [
  "graftbranches",
  "graftstages"
 ],
 "geometryclipsequence": [
  "geoclipsequence",
  "valueclip"
 ]
}
```

**chain_verdict**
```json
"The candidate chain 'basic_chain_candidate' (sopcreate, domelight, materiallibrary, camera, karmarenderproperties) is stable but uses deprecated karmarenderproperties; karmarendersettings is the non-deprecated alternative and should be tested."
```

**surprises**
```json
[
 "Decoded parm names for domelight and camera contain corrupted strings (e.g., semicolons inserted), indicating a possible decoder issue or actual parm name encoding quirk."
]
```

**gaps**
```json
[
 "No parm probe for karmarendersettings (non-deprecated render settings).",
 "No parm probe for sopimport, distantlight, lightmixer, materiallinker, rendersettings, usdrender_rop, inlineusd, graftbranches, geoclipsequence.",
 "No chain_hash test with karmarendersettings or alternative node choices.",
 "Existence of successors like inlineusd, usd_rop, graftbranches, graftstages, geoclipsequence, valueclip not yet confirmed."
]
```

**proposed mission** → `missions/proposed/next_solaris_basic_fixture.json`

run it: `Start-AutoResearch -Mission proposed/next_solaris_basic_fixture`
