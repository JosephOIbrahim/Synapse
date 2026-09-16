"""Compare what the installer SHIPS against what the release COMMITS.

Why this exists
---------------
Every release before this one asserted, in its published verification report, that
"python/ and installer/ match the tag, see payload_audit" -- and payload_audit never
opened the payload. What it actually held was a repo-to-repo `git diff` between two
git revisions. That diff cannot see the payload at all: it compares the tree to the
tree, so it would report "match" for a payload that was never built, built from the
wrong branch, or built and then replaced.

Two specific things that claim gets wrong, both measured here rather than argued:

  * `installer/` has NO referent in the payload. Nothing under that prefix is shipped.
    A claim that installer/ "matches the tag" is neither true nor false; it has no
    subject. This script reports the count so the absence is visible instead of implied.
  * `python/` does not match at tree level either. The builder vendors dependencies at
    build time, so the payload legitimately holds files (`websockets`, `filelock`) that
    are not in git, and legitimately omits pip metadata stubs that are. Every one of
    those differences is under `_vendor/`, which RELEASE_CARD.md lists under "Not
    surfaces". The claim that IS checkable, and the one this script makes, is about the
    non-_vendor source: byte-for-byte, file for file.

So: compare the bytes. A git blob hash over the payload member versus the blob hash
git records for the same path, which is an identity check, not a heuristic.

    python harness/notes/release-5.74.0/payload_vs_tag.py [<ref>]

With no ref, the comparison is against the WORKING TREE -- correct before the release
commit exists, which is when the payload is built. With a ref (`v5.74.0`), it compares
against that committed tree, which is the check worth re-running after the tag.

Writes payload-vs-tag-<version>.json beside this file. Exit 1 on any mismatch.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile

REPO = r"C:/Users/User/SYNAPSE"
HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = io.open(os.path.join(REPO, "VERSION"), encoding="utf-8").read().strip()
BUILD_REPORT = r"C:/synapse-build/output-%s/output/SYNAPSE-%s-Setup.build.json" % (VERSION, VERSION)
PREFIX = "python/synapse/"
VENDOR = "/_vendor/"


def git(*a):
    return subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def blob(b):
    """git's own object id for this content -- the same function git used to record it."""
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else None
    report = json.load(open(BUILD_REPORT))
    zip_path = report["payload"]["path"]
    declared = report["payload"]["sha256"]

    h = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != declared:
        raise SystemExit("STOP: payload.zip on disk (%s) is not the one the build report names "
                         "(%s). Comparing it would prove nothing about the shipped file."
                         % (h.hexdigest()[:16], declared[:16]))

    z = zipfile.ZipFile(zip_path)
    members = z.namelist()
    installer_members = [n for n in members if n.startswith("installer/")]

    pay, pay_vendor = {}, 0
    for n in members:
        if not n.startswith(PREFIX) or n.endswith("/"):
            continue
        if VENDOR in n:
            pay_vendor += 1
            continue
        pay[n] = blob(z.read(n))

    tree, tree_vendor = {}, 0
    if ref:
        for line in git("ls-tree", "-r", ref, "--", "python/synapse").splitlines():
            if not line.strip():
                continue
            meta, _, path = line.partition("\t")
            if VENDOR in path:
                tree_vendor += 1
                continue
            tree[path] = meta.split()[2]
    else:
        # Hash the files ON DISK, not `git ls-files -s`.
        #
        # ls-files reports the INDEX, and the whole reason this runs before the release
        # commit is that the bump is not staged yet -- so the index still holds the
        # PREVIOUS version's __init__.py. The first run of this script compared a 5.74.0
        # payload against a 5.73.0 index and reported MISMATCH on exactly that file: an
        # instrument defect that reads precisely like the defect it was written to find.
        # "Working tree" has to mean the bytes on disk, or the name is a lie.
        for path in git("ls-files", "--", "python/synapse").splitlines():
            path = path.strip()
            if not path:
                continue
            if VENDOR in path:
                tree_vendor += 1
                continue
            full = os.path.join(REPO, path)
            if not os.path.exists(full):
                continue
            with open(full, "rb") as f:
                tree[path] = blob(f.read())

    only_payload = sorted(set(pay) - set(tree))
    only_tree = sorted(set(tree) - set(pay))
    differs = sorted(p for p in set(pay) & set(tree) if pay[p] != tree[p])
    ok = not (only_payload or only_tree or differs)

    out = {
        "probe": "synapse-payload-vs-tag-1",
        "version": VERSION,
        "compared_against": ref or "WORKING TREE (no release commit yet)",
        "payload_sha256": declared,
        "payload_members_total": len(members),
        "installer_members_in_payload": len(installer_members),
        "non_vendor_python_files_compared": len(pay),
        "vendor_files_excluded_payload": pay_vendor,
        "vendor_files_excluded_tree": tree_vendor,
        "only_in_payload": only_payload,
        "only_in_tree": only_tree,
        "content_differs": differs,
        "verdict": "MATCH" if ok else "MISMATCH",
        "scope": ("Byte identity over non-_vendor files under python/synapse/ only. _vendor/ is "
                  "excluded because the builder vendors it at build time and RELEASE_CARD.md lists "
                  "it as not a surface."),
        "not_proven": ("Anything about installer/. It has %d members in the payload, so a claim that "
                       "installer/ matches the tag has no subject." % len(installer_members)),
    }
    # The output is named for WHAT IT COMPARED AGAINST, so the two passes cannot overwrite
    # each other. They answer different questions and both are worth keeping: the pre-commit
    # run asks "does the payload match what we are about to commit" and is the evidence that
    # goes INTO the tag; the post-tag run asks "does the payload match what we just tagged"
    # and, by construction, cannot be inside the tag it names. One filename for both meant
    # the second silently replaced the first and left the committed artifact disagreeing
    # with the published asset that cites it.
    path = os.path.join(HERE, "payload-vs-%s-%s.json" % (ref.replace("/", "_"), VERSION)
                        if ref else "payload-vs-tag-%s.json" % VERSION)
    io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1) + "\n")

    print("payload           :", declared[:16], "(%d members)" % len(members))
    print("compared against  :", out["compared_against"])
    print("installer/ in zip :", len(installer_members), "(so installer/ has no subject to match)")
    print("non-_vendor python:", len(pay), "compared;", pay_vendor, "vendor files excluded")
    print("only in payload   :", only_payload or "none")
    print("only in tree      :", only_tree or "none")
    print("content differs   :", differs or "none")
    print("VERDICT           :", out["verdict"])
    print("wrote", os.path.basename(path))
    return 0 if ok else 1


sys.exit(main())
