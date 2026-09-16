"""Repair the v5.73.0 provenance assets before publication.

The assets were composed at 21:08 on 2026-09-15, when HEAD was still the
pre-bump commit 85c8fe29. The release commit (f514ebb5) and its repair
(236fd2e5) landed the next day, and the tag moved with them -- but the
composer never ran a second time, so three fields still name the pre-bump
tree and one carries a baseline copied forward from v5.70.0.

This script corrects ONLY those fields. It does not rebuild, does not
recompose from scratch, and does not touch the Setup.exe or its hash.

Four corrections, each stated:

  1. source_revision   85c8fe29 -> the tag. The payload's python/synapse
     tree is byte-identical to v5.73.0 (proven below, and re-proven here
     before anything is written), so the tag is the honest source.
  2. ci.headSha        same, for the same reason.
  3. product_change_since_v5.70.0 -> ..._since_v5.72.0. The key named
     v5.70.0, its `check` string named v5.70.0, and the command actually
     run named v5.70.1. Three names, none of them the real predecessor.
  4. the note under it claimed "only python/synapse/__init__.py, the
     version string" while its own result listed 56 files. A note that
     its own data refutes is worse than no note.

Run:  python harness/notes/release-5.73.0/repair_assets.py [--write]
Without --write it prints the diff and changes nothing.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile

REPO = r"C:/Users/User/SYNAPSE"
OUT = r"C:/synapse-build/output-5.73.0/output"
PAYLOAD_ZIP = r"C:/synapse-build/output-5.73.0/stage-flfte0r0/payload.zip"
TAG = "v5.73.0"
PREV = "v5.72.0"
BUILD_REV = "85c8fe294e0d8001a77addb368ef70f3fa95537c"


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


def gitblob(b):
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def prove_payload_matches_tag():
    """The evidence the corrected source_revision rests on. Runs BEFORE any write.

    Every python/synapse file the payload and the tag share must be
    byte-identical. _vendor/ is excluded: RELEASE_CARD.md lists it under
    'Not surfaces' -- the builder vendors it at build time, so it legitimately
    differs from the tree.
    """
    z = zipfile.ZipFile(PAYLOAD_ZIP)
    pay = {n: gitblob(z.read(n)) for n in z.namelist()
           if n.startswith("python/synapse/") and not n.endswith("/")
           and "/_vendor/" not in n}
    tag = {}
    for line in git("ls-tree", "-r", TAG, "--", "python/synapse").splitlines():
        meta, path = line.split("\t", 1)
        if "/_vendor/" in path:
            continue
        tag[path] = meta.split()[2]
    only_pay = sorted(set(pay) - set(tag))
    only_tag = sorted(set(tag) - set(pay))
    differ = sorted(p for p in set(pay) & set(tag) if pay[p] != tag[p])
    if only_pay or only_tag or differ:
        raise SystemExit(
            "REFUSING: payload does not match %s.\n  only in payload: %s\n"
            "  only in tag: %s\n  content differs: %s"
            % (TAG, only_pay[:10], only_tag[:10], differ[:10]))
    return len(pay)


def main():
    write = "--write" in sys.argv
    rev = git("rev-list", "-n", "1", TAG)
    assert len(rev) == 40, "could not resolve " + TAG
    n = prove_payload_matches_tag()
    print("payload vs %s: %d non-_vendor files, 0 differences" % (TAG, n))
    print("tagged revision: %s" % rev)

    delta = git("diff", "--stat", PREV, TAG, "--", "python", "installer") or "(empty: identical)"

    # --- public-build.json -------------------------------------------------
    pub_path = os.path.join(OUT, "SYNAPSE-5.73.0-Setup.public-build.json")
    pub = json.load(open(pub_path))
    print("\npublic-build.json  source_revision: %s -> %s" % (pub["source_revision"][:12], rev[:12]))
    pub["source_revision"] = rev
    pub["build_revision"] = BUILD_REV

    # --- installer-verification.json --------------------------------------
    rep_path = os.path.join(OUT, "installer-verification.json")
    rep = json.load(open(rep_path))
    print("verification.json  source_revision: %s -> %s" % (rep["source_revision"][:12], rev[:12]))
    rep["source_revision"] = rev
    rep["build_revision"] = BUILD_REV
    if isinstance(rep.get("ci"), dict):
        print("verification.json  ci.headSha:      %s -> %s" % (rep["ci"]["headSha"][:12], rev[:12]))
        rep["ci"]["headSha"] = rev

    pa = rep["payload_audit"]
    stale = [k for k in pa if k.startswith("product_change_since_")]
    for k in stale:
        pa.pop(k)
    print("verification.json  %s -> product_change_since_%s" % (stale or ["(none)"], PREV))
    pa["product_change_since_" + PREV] = {
        "check": "git diff --stat %s %s -- python installer" % (PREV, TAG),
        "result": delta,
        "note": ("This release changed the panel, so the delta is not the version string alone; "
                 "the previous note claimed it was, and its own result already said otherwise. "
                 "The payload was built from the bumped working tree at %s, one commit before the "
                 "release commit, so the build revision and the tag differ. What binds them is not "
                 "the revision but the bytes: every non-_vendor file under python/synapse/ in the "
                 "shipped payload is byte-identical to the same file at %s, re-checked immediately "
                 "before this report was written (%d files, 0 differences). _vendor/ is excluded "
                 "because the builder vendors it at build time; RELEASE_CARD.md lists it as not a "
                 "surface." % (BUILD_REV[:12], TAG, n)),
    }

    if not write:
        print("\n(dry run -- pass --write to apply)")
        return
    for path, obj in ((pub_path, pub), (rep_path, rep)):
        blob = json.dumps(obj, indent=2, sort_keys=True) + "\n"
        low = blob.lower()
        for bad in ("c:\\\\", "c:/", "/users/", "\\users\\\\"):
            if bad in low:
                raise SystemExit("REFUSING: %s would carry a local path (%r)" % (path, bad))
        io.open(path, "w", encoding="utf-8", newline="\n").write(blob)
        print("wrote", os.path.basename(path))


main()
