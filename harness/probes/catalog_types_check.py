"""Compare catalogue entries against the live H22.0.400 build.

The World Labs audit (docs/intake/worldlabs-gaussian-pipeline-audit.md, section 4.1)
claims the repo's node-type authority - rag/catalog/h22.0.400/ - mis-describes three
types: gltf, distantlight and usdrender. That claim is load-bearing: the catalogue
ships inside the product payload, so a wrong entry is a trap in a shipped file.

This probe does not trust the audit. It reads the LIVE build and compares.

FOUR SEPARATE QUESTIONS, kept separate because conflating them is how a wrong
verdict gets written:

  1. RESOLUTION - does a node type with this exact name exist in the registry,
     in the category the catalogue files it under?
  2. TEMPLATE FIDELITY - does the catalogue's parm list match the live type's
     parmTemplateGroup(), flattened through folders the same way the catalogue
     builder flattens it? The catalogue is BUILT from parmTemplateGroup(), so
     this is the like-for-like comparison.
  3. ALIAS RESOLUTION - when you createNode() the catalogue's key, what type do
     you actually get? An unversioned key can resolve to a versioned default.
  4. SET-ABILITY - read a parm name out of the catalogue, set it on a live node.
     This is the failure the audit describes ("Invalid parameter name").

A disagreement in (2) is a catalogue defect only if the catalogue was built from
a different definition than the live one. A disagreement in (4) is what actually
bites a script, and it can be caused by (3) even when (2) is perfect.

WHAT THIS PROBE ESTABLISHED (Houdini 22.0.400):

  The committed receipt is harness/probes/catalog_types_check_receipt.json.
  Every number below is in it, with the build, the catalogue directory and the
  comparison that produced it. This docstring summarises; the receipt is the
  evidence.

  - The catalogue is FAITHFUL. All six audited entries match their live type's
    parm template exactly (Jaccard 1.000 on each): gltf 17/17, gltf::2.0 42/42,
    distantlight 131/131, distantlight::2.0 123/123, Driver usdrender 194/194,
    Top usdrender 73/73.
  - The real trap is ALIAS RESOLUTION. createNode("gltf") returns a gltf::2.0
    node, so parm names read from the catalogue's unversioned "gltf" entry do
    not exist on the node you got (3 of 17 settable, 14 absent). createNode
    ("distantlight") behaves the same way (-> distantlight::2.0; 65 of 123
    settable, 58 absent). The catalogue is right; the CONSUMER has to know the
    unversioned key is an alias. Against the catalogue entry for the type
    createNode() actually returned, the absent count is ZERO for all six.
  - usdrender DOES resolve. The Driver usdrender creates in /out; the Top
    usdrender creates inside a topnet. A TOP type created directly under
    /tasks fails because /tasks is the scheduler, not a TOP network.
  - Parm names containing '#' are Houdini's SPARE-PARAMETER convention. They
    are present in the node's own parameter interface (Houdini's own label
    ends in '#') but the node exposes no value for them. 7,155 of 152,918
    catalogue parm names (4.68%) carry one, across eleven category files - it
    is a Houdini-wide convention, not a defect of the three audited types.

Run:
  hython -s -P harness/probes/catalog_types_check.py --catalog rag/catalog/h22.0.400

Exit code 0 means every catalogue entry that names a live type agrees with it.
Exit code 1 means at least one entry disagrees.

THE RECEIPT:
  --receipt <path> writes the same findings as JSON, so the numbers quoted in
  this docstring and in the audit have a committed producer. The receipt
  records the build, the catalogue directory, and every comparison it made.
  Without it, the six parm counts below are prose - true as far as anyone can
  tell, and re-derivable only by someone with a 22.0.400 seat.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _catalog_dir() -> Path:
    for i, arg in enumerate(sys.argv):
        if arg == "--catalog" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1])
    return ROOT / "rag/catalog/h22.0.400"


def _receipt_path():
    for i, arg in enumerate(sys.argv):
        if arg == "--receipt" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1])
    return None


def load_entry(catalog: Path, category: str, key: str):
    """Return the catalogue entry for one node type, or None.

    The category file is an envelope: metadata at the top level, the type map
    under "types". Reading the key from the top level finds nothing and makes
    the whole comparison vacuous, so the map is descended into explicitly.
    """
    path = catalog / (category + ".json")
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    types = data.get("types")
    if not isinstance(types, dict):
        raise SystemExit("catalogue %s has no 'types' map (top-level keys: %s)"
                         % (path, sorted(data)))
    return types.get(key)


def catalogue_parms(entry):
    if not entry:
        return []
    return sorted({p["name"] for p in entry.get("parms", []) if isinstance(p, dict) and "name" in p})


# Structural templates: present in the catalogue (the builder records their
# presence and order as part of the schema) but NOT settable parms.
STRUCTURAL = ("Folder", "FolderSet", "Separator", "Label")


def catalogue_settable_parms(entry):
    """Catalogue parm names that a script could actually set."""
    if not entry:
        return []
    return sorted({p["name"] for p in entry.get("parms", [])
                   if isinstance(p, dict) and "name" in p
                   and p.get("type") not in STRUCTURAL})


def flatten_group(group):
    """Every parm template name in the group, descended through folders.

    EXACT mirror of scripts/build_node_catalog.py::_walk_templates:
      - top level comes from group.entries()
      - a folder's CHILDREN come from folder.parmTemplates() (NOT
        folder.parmTemplateGroup(), which returns a different set)
      - the recursion has no depth limit

    Getting this wrong makes a live type look like it is missing most of its
    parms, which is a false accusation against a correct catalogue.
    """
    names = []

    def walk(entries):
        for tpl in entries:
            try:
                ttype = tpl.type().name()
            except Exception:
                ttype = None
            names.append(tpl.name())
            if ttype in ("Folder", "FolderSet"):
                try:
                    walk(tpl.parmTemplates())
                except Exception:
                    pass

    try:
        walk(group.entries())
    except Exception:
        walk(group.parmTemplates())
    return names


def live_template_parms(node_type):
    """The live type's flattened parm template names - the catalogue's own source."""
    return flatten_group(node_type.parmTemplateGroup())


def main() -> int:
    import hou

    catalog = _catalog_dir()
    print("catalogue: %s" % catalog)
    print("build: %s" % hou.applicationVersionString())
    print()

    cat_factories = {
        "Sop": hou.sopNodeTypeCategory,
        "Lop": hou.lopNodeTypeCategory,
        "Driver": hou.ropNodeTypeCategory,
        "Top": hou.topNodeTypeCategory,
    }
    live_types = {}
    for name, fn in cat_factories.items():
        try:
            # nodeTypes() is a dict of name -> NodeType, not a sequence.
            live_types[name] = dict(fn().nodeTypes())
        except Exception as exc:
            print("  (category %s unavailable: %s)" % (name, exc))

    # The context each category's types are created in. A Driver type failing
    # inside /stage is a context fact, not evidence the entry is wrong.
    # TOP types live in a topnet, NOT directly under /tasks (the scheduler).
    parents = {
        "Sop": hou.node("/obj").createNode("geo", "catalog_check_geo"),
        "Lop": hou.node("/stage"),
        "Driver": hou.node("/out"),
        "Top": hou.node("/tasks").createNode("topnet", "catalog_check_topnet"),
    }

    targets = [
        ("Sop", "gltf"),
        ("Sop", "gltf::2.0"),
        ("Lop", "distantlight"),
        ("Lop", "distantlight::2.0"),
        ("Driver", "usdrender"),
        ("Top", "usdrender"),
    ]

    problems = []
    checked = 0

    # Everything below is recorded as it is measured, so --receipt can write a
    # finding the reader can check rather than a number they have to trust.
    rec = {
        "probe": "catalog_types_check",
        "houdini": None,
        "catalogue": None,
        "targets": [],
        "resolution": [],
        "template_fidelity": [],
        "alias_resolution": [],
        "set_ability": [],
        "spare_name_scope": {},
        "identity": [],
        "checked": 0,
        "problems": [],
    }

    print("=" * 78)
    print("Q1 RESOLUTION  -  does the catalogue key name a live type in that category?")
    print("=" * 78)
    for category, key in targets:
        entry = load_entry(catalog, category, key)
        if entry is None:
            print("  %-8s %-18s not in the catalogue at all" % (category, key))
            rec["resolution"].append({"category": category, "key": key,
                                      "in_catalogue": False, "live_type_exists": False})
            continue
        types = live_types.get(category, {})
        print("  %-8s %-18s catalogue: yes    live type with this exact name: %s"
              % (category, key, "YES" if key in types else "NO"))
        rec["resolution"].append({"category": category, "key": key,
                                  "in_catalogue": True, "live_type_exists": key in types})
        checked += 1

    print()
    print("=" * 78)
    print("Q2 TEMPLATE FIDELITY  -  catalogue parms vs live parmTemplateGroup (flattened)")
    print("=" * 78)
    for category, key in targets:
        entry = load_entry(catalog, category, key)
        if entry is None:
            continue
        node_type = live_types.get(category, {}).get(key)
        if node_type is None:
            print("  %-8s %-18s SKIPPED - no live type with this exact name" % (category, key))
            continue
        cat_p = set(catalogue_parms(entry))
        live_p = set(live_template_parms(node_type))
        missing = sorted(cat_p - live_p)
        extra = sorted(live_p - cat_p)
        rec["template_fidelity"].append({
            "category": category, "key": key,
            "catalogue_parms": len(cat_p), "live_template_parms": len(live_p),
            "missing_from_live": missing, "extra_in_live": extra,
            "jaccard": round(len(cat_p & live_p) / float(len(cat_p | live_p)), 6)
            if (cat_p | live_p) else 1.0,
        })
        print("  %-8s %-18s catalogue: %3d   live template: %3d" % (category, key, len(cat_p), len(live_p)))
        if missing:
            print("        catalogue names, live type lacks : %s" % (missing[:8] or "none"))
        if extra:
            print("        live type has, catalogue lacks    : %s" % (extra[:8] or "none"))
        if missing:
            problems.append("%s/%s: the catalogue names %d parm(s) the live type does not "
                            "have: %s" % (category, key, len(missing), missing[:6]))
        checked += 1

    print()
    print("=" * 78)
    print("Q3 ALIAS RESOLUTION  -  createNode(catalogue key) -> which type?")
    print("=" * 78)
    aliases = []
    for category, key in targets:
        parent = parents.get(category)
        if parent is None:
            continue
        try:
            node = parent.createNode(key, "probe_alias")
        except hou.OperationFailed as exc:
            print("  %-8s %-18s DOES NOT CREATE in its own context: %s"
                  % (category, key, str(exc)[:90]))
            problems.append("%s/%s: the catalogue names a type that does not create in its "
                            "own category context" % (category, key))
            continue
        try:
            actual = node.type().name()
            same = "same" if actual == key else "DIFFERENT"
            print("  %-8s %-18s -> %-20s (%s)" % (category, key, actual, same))
            rec["alias_resolution"].append({"category": category, "key": key,
                                           "resolved_type": actual, "aliased": actual != key})
            if actual != key:
                aliases.append((category, key, actual))
        finally:
            node.destroy()
    if aliases:
        print()
        print("  ALIASES - the catalogue key and the node you get are different types.")
        print("  The catalogue entry for the KEY is not wrong; it describes a type that")
        print("  really is registered. But createNode(KEY) hands back the other one, so")
        print("  parm names read from the KEY's entry do not exist on the node you get.")
        for category, key, actual in aliases:
            print("    %s/%-18s -> %s" % (category, key, actual))

    print()
    print("=" * 78)
    print("Q4 SET-ABILITY  -  is each catalogue parm name a real, settable parm?")
    print("=" * 78)
    # A catalogue parm name can fail to be settable for two very different
    # reasons, and only one of them is a catalogue defect:
    #
    #   SPARE (Houdini's '#' convention) - the name is present in the node's
    #   OWN parameter interface (the instance's parmTemplateGroup carries it,
    #   and Houdini's own label ends in '#'), but the node exposes no value for
    #   it. It is a channel-reference slot, not a parameter. The catalogue
    #   records it faithfully; a script simply cannot set it.
    #
    #   ABSENT - the name is in no interface at all. THAT is a catalogue defect.
    #
    # So the test is: not-settable AND not in the type's interface = absent.
    # Q2 already proves the catalogue's name set EQUALS the interface's name
    # set, so a non-settable name is by construction a spare, not an error.
    def parm_is_settable(node, name):
        base = name[:-1] if name.endswith("#") else name
        if node.parm(name) is not None:
            return True
        if node.parmTuple(base) is not None:
            return True
        if base and node.parm(base + "1") is not None:
            return True
        return False

    for category, key in targets:
        entry = load_entry(catalog, category, key)
        if entry is None:
            continue
        parent = parents.get(category)
        if parent is None:
            continue
        try:
            node = parent.createNode(key, "probe_set")
        except hou.OperationFailed as exc:
            print("  %-8s %-18s SKIPPED - does not create here: %s" % (category, key, str(exc)[:70]))
            continue
        try:
            resolved = node.type().name()
            names = catalogue_settable_parms(entry)
            settable = [n for n in names if parm_is_settable(node, n)]
            spare = [n for n in names if n not in settable and "#" in n]
            absent = [n for n in names if n not in settable and "#" not in n]
            aliased = resolved != key
            entry_rec = {
                "category": category, "key": key, "resolved_type": resolved,
                "aliased": aliased,
                "catalogue_parms": len(names), "settable": len(settable),
                "spare": len(spare), "absent": len(absent),
                "absent_names": absent,
                "like_for_like": None,
            }
            rec["set_ability"].append(entry_rec)
            if aliased:
                # createNode(KEY) handed back a DIFFERENT type. A name from
                # KEY's entry that is not on the node is the ALIAS effect, not
                # an absence: Q2 proved KEY's own live type carries it.
                print("  %-8s %-18s -> live as %-18s catalogue parms: %3d   settable: %3d   "
                      "spare('#'): %3d   absent-because-aliased: %d"
                      % (category, key, resolved, len(names), len(settable), len(spare), len(absent)))
            else:
                print("  %-8s %-18s -> live as %-18s catalogue parms: %3d   settable: %3d   "
                      "spare('#'): %3d   ABSENT: %d"
                      % (category, key, resolved, len(names), len(settable), len(spare), len(absent)))
            if spare:
                print("        spare (interface slot, not a value): %s" % (spare[:6] or "none"))
            if absent:
                if aliased:
                    print("        not on this node (the node is %s, not %s): %s"
                          % (resolved, key, absent[:10] or "none"))
                else:
                    print("        ABSENT from the live node            : %s" % (absent[:10] or "none"))
                    problems.append("%s/%s: %d catalogue parm name(s) exist in no live interface: %s"
                                    % (category, key, len(absent), absent[:6]))
            # The catalogue key names one type; createNode(key) may hand back a
            # DIFFERENT (aliased) type. Parms that are valid for the KEY's own
            # type but absent from the created node are an alias effect, not a
            # catalogue error. Test against the catalogue entry of the RESOLVED
            # type as well - that is the like-for-like check.
            resolved_entry = load_entry(catalog, category, resolved)
            if resolved_entry is not None:
                r_names = catalogue_settable_parms(resolved_entry)
                r_spare = [n for n in r_names if not parm_is_settable(node, n) and "#" in n]
                r_absent = [n for n in r_names if not parm_is_settable(node, n) and "#" not in n]
                print("        like-for-like against catalogue[%s]: %3d parms, %d settable, "
                      "%d spare, %d ABSENT"
                      % (resolved, len(r_names), len(r_names) - len(r_spare) - len(r_absent),
                         len(r_spare), len(r_absent)))
                entry_rec["like_for_like"] = {
                    "catalogue_key": resolved,
                    "parms": len(r_names),
                    "settable": len(r_names) - len(r_spare) - len(r_absent),
                    "spare": len(r_spare),
                    "absent": len(r_absent),
                    "absent_names": r_absent,
                }
                if r_absent:
                    print("          ABSENT : %s" % (r_absent[:10] or "none"))
                    problems.append("%s/%s: %d parm name(s) in the catalogue entry for the "
                                    "RESOLVED type exist in no live interface: %s"
                                    % (category, resolved, len(r_absent), r_absent[:6]))
            else:
                problems.append("%s: the live build resolves %s to %s, which the catalogue "
                                "has no entry for" % (category, key, resolved))
        finally:
            node.destroy()

    print()
    print("=" * 78)
    print("Q4b SPARE-NAME SCOPE  -  how big is the '#' convention across the catalogue?")
    print("=" * 78)
    # If '#'-suffixed names were a defect of these three types, the census would
    # be small and local. It is neither: it is a Houdini-wide convention, so the
    # three types are not special and no per-type fix is warranted.
    total_hash = 0
    total_names = 0
    per_file = {}
    for cat_file in sorted(catalog.glob("*.json")):
        if cat_file.name.startswith("_"):
            continue
        try:
            data = json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        types = data.get("types")
        if not isinstance(types, dict):
            continue
        n_hash = 0
        n_names = 0
        for t in types.values():
            for p in t.get("parms", []):
                if not isinstance(p, dict):
                    continue
                nm = p.get("name")
                if not isinstance(nm, str):
                    continue
                n_names += 1
                if "#" in nm:
                    n_hash += 1
        total_hash += n_hash
        total_names += n_names
        per_file[cat_file.name] = {"spare": n_hash, "parms": n_names}
        if n_hash:
            print("  %-22s %5d of %6d parm names carry '#'" % (cat_file.name, n_hash, n_names))
    print("  %-22s %5d of %6d parm names carry '#'  (%.1f%% catalogue-wide)"
          % ("TOTAL", total_hash, total_names, 100.0 * total_hash / max(total_names, 1)))
    rec["spare_name_scope"] = {
        "total_spare": total_hash, "total_parms": total_names,
        "percent": round(100.0 * total_hash / max(total_names, 1), 3),
        "per_file": per_file,
    }
    print("  -> the '#' convention is Houdini-wide; these three types are not special.")

    print()
    print("=" * 78)
    print("Q5 IDENTITY  -  which live type does each catalogue entry ACTUALLY describe?")
    print("=" * 78)
    # The decisive question behind the audit's claim. If the catalogue's unversioned
    # 'gltf' entry has the parm set of some live type, that entry is not "wrong" -
    # it describes a type that exists under a different name (an alias / a
    # superseded HDA that is still registered). If NO live type matches, the entry
    # is genuinely stale.
    for category, key in targets:
        entry = load_entry(catalog, category, key)
        if entry is None:
            continue
        cat_set = set(catalogue_parms(entry))
        if not cat_set:
            continue
        best = []
        for tname, tnode in live_types.get(category, {}).items():
            try:
                live_set = set(live_template_parms(tnode))
            except Exception:
                continue
            if not live_set:
                continue
            overlap = len(cat_set & live_set)
            ratio = overlap / float(len(cat_set | live_set))
            if ratio >= 0.85:
                best.append((ratio, overlap, tname, len(live_set)))
        best.sort(reverse=True)
        rec["identity"].append({
            "category": category, "key": key, "catalogue_parms": len(cat_set),
            "matches": [{"type": tname, "overlap": ov, "jaccard": round(r, 6),
                         "live_parms": nl} for (r, ov, tname, nl) in best[:3]],
        })
        print("  %-8s %-18s catalogue parms: %d" % (category, key, len(cat_set)))
        if not best:
            print("        NO live type in this category matches (best overlap below 85%%)")
            problems.append("%s/%s: the catalogue entry matches NO live type in its "
                            "category" % (category, key))
        else:
            for ratio, overlap, tname, nlive in best[:3]:
                print("        matches %-20s overlap %d/%d  jaccard %.3f  (live has %d parms)"
                      % (tname, overlap, len(cat_set), ratio, nlive))
        checked += 1

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print("checked %d catalogue entries" % checked)

    rec["houdini"] = hou.applicationVersionString()
    rec["catalogue"] = str(catalog)
    rec["targets"] = [list(t) for t in targets]
    rec["checked"] = checked
    rec["problems"] = list(problems)
    rec["verdict"] = "AGREEMENT" if not problems else "DISAGREEMENT"

    receipt = _receipt_path()
    if receipt is not None:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                           encoding="utf-8", newline="")
        print()
        print("receipt: %s" % receipt)

    if problems:
        print("DISAGREEMENTS (%d):" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("AGREEMENT: every catalogue entry that names a live type matches the live type.")
    print("The catalogue is FAITHFUL to the live build.")
    if aliases:
        print()
        print("CONSUMER TRAP (not a catalogue defect): %d unversioned catalogue key(s) are"
              % len(aliases))
        print("aliases. createNode() hands back a different type than the entry names, so")
        print("parm names taken from the unversioned entry are absent on the node you get.")
        print("Read the catalogue entry for the type createNode() actually returned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
