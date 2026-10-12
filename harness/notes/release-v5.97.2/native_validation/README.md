# Scoped Solaris native evidence

`native-evidence.json` is the sanitized producer receipt for the seven-fix source
at `b7301f3f985d1c0a9876b8ee629472392422bc26`. No user scene, HIP, private asset,
key, licence report, host name or local user path is included. Measured outcomes
and raw-report digests are retained; source/runtime input pins and the exact
executed worker/controller/loader are supplied for reproduction.

**Result:** 21 preflight controls, seven graph/USD cases, three native product
rollbacks and seven independent-process reopen/replays passed. Both headless
H22.0.400/Indie workers exited zero. The original controller measured 5.6373359
seconds for both processes; this is not a production speed or benefit benchmark.

The release version metadata can change without changing the listed native input
bytes. `prepare_packet.py` verifies the loaded source closure and scoped regression
file, never assumes that a newer release tag was natively tested as a whole.
Package startup, panel/HTTP/WebSocket/bridge runtime and an outer GUI undo group
were not included. Native fault injection follows an actual cook and mutates real
HOM sockets. No model call or running-installation self-training occurred.

## Reproduce without changing the running installation

This packet is for the existing Windows Houdini 22.0.400 installation and bundled
Python 3.13.10. No install, licence-service restart/reclaim, security change or
live scene edit is part of preparation or execution.

Prepare a **new owned directory**, using a source checkout with the pinned bytes:

```text
python harness/notes/release-v5.97.2/native_validation/prepare_packet.py --repo <source-checkout> --packet-root <new-owned-packet>
```

This command verifies and copies only public source and original test code; it
creates no native process. Read its generated prepared-manifest SHA256.

An operator/resource owner must then issue a **fresh** receipt based on
`slot-template.json`, binding that generated hash, the tested source commit, a
current resource snapshot and launch deadline, headless Indie availability and
live-GUI preservation. The template is deliberately not cleared. Never reuse a
historical receipt or edit its timestamps.

Use the supported reviewed command execution route if normal execution cannot
reach the existing licence service. No standing security expansion or reusable
permission prefix is needed. The controller preflights TCP reachability before
creating each child; actual H22/Indie/headless/main-thread identity is persisted
before the candidate imports. Failure stops with evidence and no automatic retry.

```powershell
& '<new-owned-packet>/run_when_coordinated.ps1' -SlotReceipt '<fresh-owner-receipt>' -SlotSha256 '<receipt-sha256>'
```

The worker uses existing `$HFS/python313/python.exe -I -S -B` with explicit HFS
Python/DLL paths, child PATH/HB/HHP, private preferences/temp/logs and user
packages/environment disabled. It namespace-loads the complete copied handler
and its real dependencies without production package startup.

Ceilings: two serial children, 120 seconds each, 300 seconds aggregate, two
configured threads, sampled 4 GiB memory, 64 MiB output and 32 nodes per fixture.
Sampling/thread settings are not kernel-enforced resource guarantees. No render,
simulation, live bridge, installer or user scene is exercised.

## Acceptance and evidence

Require controller `NATIVE_ASSERTIONS_COMPLETE`, both worker reports
`ASSERTIONS_PASSED`, 21 controls, seven cases, three native product restorations
and seven fresh reopen/replays. Read full raw state/diff artifacts and early gates,
not just the exit codes. Every equality includes raw user data, parameters,
metadata, sockets and composed USD. Houdini save adds `___Version___` metadata;
pre-save and post-save states remain recorded, and the actual saved checkpoint
state is the restoration reference. No field is normalized away.

Keep failed attempts, unsupported observations and remaining gaps. The result is
scoped native correctness, not production install/seat qualification, GitHub
final-commit CI, release approval or copied-scene benefit. See the release notes
and `native-evidence.json` for the explicit unqualified surfaces.
