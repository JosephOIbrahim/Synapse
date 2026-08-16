#!/usr/bin/env hython
# -*- coding: utf-8 -*-
"""W5-SEAT - panel parity 2/2: prove the seat resolution order, first-hand.

Runs under the LIVE hython of the target Houdini build with the LIVE user prefs
dir, and OBSERVES (never assumes) that the SYNAPSE panel "seat" resolves 1:1 to
the repo. Disjoint from W5-PARITY (which proves byte-equality of the modules);
this leg proves the *load path*:

  T1  package + hpath : the synapse Houdini package actually loaded -
                        hou.houdiniPath() contains <repo>/houdini AND
                        os.environ["SYNAPSE_ROOT"] == the repo. If it did NOT
                        load, that IS the finding - we diagnose why (pref-dir
                        token, package scan) and never fake a pass.
  T2  resources       : houdini/toolbar/synapse.shelf and ALL 7
                        config/Icons/SYNAPSE_*.png (incl. SYNAPSE_synapse.png,
                        committed @2dd6bab6) resolve via hou.findFile to paths
                        INSIDE the repo; icon count is asserted == 7.
  T3  shadow sweep    : every provider of a top-level `synapse` package across
                        sys.path + site-packages + importlib.metadata is
                        enumerated; ORDER is proven with indices (repo/python is
                        first); zero shadows is a COUNTED claim.
  T4  multi-build     : installed Houdini builds are enumerated; every 22.x maps
                        to the one houdini22.0 prefs dir; WHICH build Joe's GUI
                        launch used stays UNKNOWN unless a prefs/log artifact
                        proves it - never guessed.
  T5  pypanel flush   : the live-loaded synapse_panel.pypanel carries the
                        sys.modules flush block (panel-reopen == hot reload;
                        restart only for icons/shelf).

Constitution: no claim without observation. Every resolution claim carries the
hou.findFile stdout. Unobtainable renders UNKNOWN, never a pass.

Run (from the repo root, prefs dir = the live GUI seat):
  env -u SYNAPSE_ROOT -u HOUDINI_PACKAGE_DIR \
      HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0" \
      "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
      harness/probes/parity_seat/probe_seat.py \
      --expect-root "C:/Users/User/SYNAPSE" \
      --out harness/probes/parity_seat/results.json

SYNAPSE_ROOT/HOUDINI_PACKAGE_DIR are unset on purpose so the load can ONLY come
through the prefs-dir package scan - the exact mechanism the GUI seat uses.
"""

import argparse
import glob
import json
import os
import re
import sys

EXPECT_ROOT_DEFAULT = "C:/Users/User/SYNAPSE"
EXPECT_ICON_COUNT = 7                    # brief target 2; SYNAPSE_synapse.png @2dd6bab6
SEF_DIR = "C:/Program Files/Side Effects Software"


# --------------------------------------------------------------------------- #
# path helpers - normalized, case-folded (Windows), forward-slash for display  #
# --------------------------------------------------------------------------- #
def _n(p):
    """Absolute, normcased, forward-slash form for comparison + display."""
    if p is None:
        return None
    return os.path.normcase(os.path.abspath(os.path.expandvars(p))).replace("\\", "/")


def _inside(child, parent):
    """True if `child` is `parent` itself or lives under it (normcased)."""
    if not child or not parent:
        return False
    c, pa = _n(child), _n(parent)
    return c == pa or c.startswith(pa.rstrip("/") + "/")


def _emit(line=""):
    print(line, flush=True)


# --------------------------------------------------------------------------- #
# T1 - package + hpath                                                         #
# --------------------------------------------------------------------------- #
def probe_package_hpath(hou, expect_root, prefs_dir):
    expect_houdini = os.path.join(expect_root, "houdini")
    syn_root = os.environ.get("SYNAPSE_ROOT", "")
    result = {
        "expect_root": _n(expect_root),
        "expect_houdini_on_path": _n(expect_houdini),
        "SYNAPSE_ROOT_env": syn_root,
        "SYNAPSE_ROOT_normalized": _n(syn_root) if syn_root else None,
        "houdini_path": [],
        "hpath_contains_repo": False,
        "root_matches_repo": False,
        "diagnostics": {},
    }
    try:
        hpaths = list(hou.houdiniPath())
    except Exception as e:                                   # noqa: BLE001
        hpaths = []
        result["diagnostics"]["houdiniPath_error"] = repr(e)
    result["houdini_path"] = [_n(p) for p in hpaths]
    result["hpath_contains_repo"] = any(_n(p) == _n(expect_houdini) for p in hpaths)
    result["root_matches_repo"] = bool(syn_root) and _n(syn_root) == _n(expect_root)

    # Tie the effect (SYNAPSE_ROOT + hpath) to its PRODUCER (always, not only on
    # fail): the prefs-dir synapse.json that the package scan loads. This rules
    # out a "parent-env leak manufactured the pass" reading.
    producer = {"prefs_dir": _n(prefs_dir) if prefs_dir else None}
    if prefs_dir:
        sj = os.path.join(prefs_dir, "packages", "synapse.json")
        producer["synapse_json"] = _n(sj)
        producer["synapse_json_present"] = os.path.isfile(sj)
    result["producer"] = producer

    _emit("== T1  package + hpath (live seat) ==")
    _emit("  SYNAPSE_ROOT (env)      : %s" % (syn_root or "(UNSET)"))
    _emit("  expect repo             : %s" % _n(expect_root))
    _emit("  root matches repo       : %s" % result["root_matches_repo"])
    _emit("  <repo>/houdini on HPATH : %s" % result["hpath_contains_repo"])
    _emit("  producer (synapse.json) : %s (present=%s)"
          % (producer.get("synapse_json", "(no prefs dir)"), producer.get("synapse_json_present")))
    _emit("  HOUDINI_PATH entries    : %d" % len(hpaths))
    for p in result["houdini_path"]:
        _emit("      %s%s" % (p, "   <== repo" if _n(p) == _n(expect_houdini) else ""))

    passed = result["hpath_contains_repo"] and result["root_matches_repo"]
    if not passed:
        # The load did NOT resolve to the repo -> diagnose (never fake a pass).
        diag = result["diagnostics"]
        diag["HOUDINI_USER_PREF_DIR"] = os.environ.get("HOUDINI_USER_PREF_DIR", "(unset)")
        diag["HOUDINI_PACKAGE_DIR"] = os.environ.get("HOUDINI_PACKAGE_DIR", "(unset)")
        pkg_glob = os.path.join(prefs_dir, "packages", "*.json") if prefs_dir else ""
        scanned = sorted(glob.glob(pkg_glob)) if pkg_glob else []
        diag["prefs_packages_scanned"] = [_n(p) for p in scanned]
        diag["synapse_json_present"] = any(
            os.path.basename(p).lower() == "synapse.json" for p in scanned
        )
        try:
            diag["homeHoudiniDirectory"] = _n(hou.homeHoudiniDirectory())
        except Exception as e:                              # noqa: BLE001
            diag["homeHoudiniDirectory_error"] = repr(e)
        _emit("  !! DID NOT LOAD TO REPO - diagnostics:")
        _emit("     %s" % json.dumps(diag, ensure_ascii=False))
    result["pass"] = passed
    _emit("  T1 verdict              : %s" % ("PASS" if passed else "FAIL"))
    _emit()
    return result


# --------------------------------------------------------------------------- #
# T2 - resources resolve via hou.findFile, into the repo                       #
# --------------------------------------------------------------------------- #
def probe_resources(hou, expect_root):
    syn_root = os.environ.get("SYNAPSE_ROOT", "") or expect_root
    icons_dir = os.path.join(syn_root, "houdini", "config", "Icons")
    disk_icons = sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(icons_dir, "SYNAPSE_*.png"))
    )
    icon_count = len(disk_icons)

    # HOUDINI_PATH-relative lookups: findFile searches every HOUDINI_PATH root.
    rel_targets = ["toolbar/synapse.shelf"] + ["config/Icons/" + n for n in disk_icons]
    checks = []
    for rel in rel_targets:
        entry = {"rel": rel, "resolved_raw": None, "resolved": None,
                 "inside_repo": False, "error": None}
        try:
            raw = hou.findFile(rel)                          # exact hou.findFile stdout
            entry["resolved_raw"] = raw
            entry["resolved"] = _n(raw)
        except Exception as e:                              # noqa: BLE001
            entry["error"] = repr(e)
        entry["inside_repo"] = _inside(entry["resolved"], syn_root)
        checks.append(entry)

    count_ok = icon_count == EXPECT_ICON_COUNT
    has_synapse_icon = "SYNAPSE_synapse.png" in disk_icons
    all_resolved = all(c["resolved"] for c in checks)
    all_inside = all(c["inside_repo"] for c in checks)
    passed = count_ok and has_synapse_icon and all_resolved and all_inside

    result = {
        "icons_dir": _n(icons_dir),
        "icon_count": icon_count,
        "icon_count_expected": EXPECT_ICON_COUNT,
        "icon_count_ok": count_ok,
        "has_SYNAPSE_synapse_png": has_synapse_icon,
        "disk_icons": disk_icons,
        "findfile_checks": checks,
        "all_resolved": all_resolved,
        "all_inside_repo": all_inside,
        "pass": passed,
    }
    _emit("== T2  resources via hou.findFile (into the repo) ==")
    _emit("  icons on disk           : %d (expected %d)  ok=%s"
          % (icon_count, EXPECT_ICON_COUNT, count_ok))
    _emit("  SYNAPSE_synapse.png     : %s" % has_synapse_icon)
    for c in checks:
        if c["resolved"]:
            _emit("  findFile('%s')" % c["rel"])
            _emit("      -> %s%s" % (c["resolved_raw"], "" if c["inside_repo"] else "   !! OUTSIDE REPO"))
        else:
            _emit("  findFile('%s')  -> UNRESOLVED  %s" % (c["rel"], c["error"]))
    _emit("  T2 verdict              : %s" % ("PASS" if passed else "FAIL"))
    _emit()
    return result


# --------------------------------------------------------------------------- #
# T3 - shadow-install sweep, order proven with indices                         #
# --------------------------------------------------------------------------- #
def probe_shadow_sweep(expect_root):
    import importlib.util
    try:
        import site
        site_dirs = list(site.getsitepackages()) if hasattr(site, "getsitepackages") else []
        if hasattr(site, "getusersitepackages"):
            site_dirs.append(site.getusersitepackages())
    except Exception:                                       # noqa: BLE001
        site_dirs = []

    repo_python = os.path.join(expect_root, "python")

    # Walk every sys.path entry (which subsumes site-packages) for a `synapse`
    # top-level provider. Also fold in site dirs not already on sys.path.
    scan = list(enumerate(sys.path))
    seen = {_n(e or os.getcwd()) for _, e in scan}
    for sd in site_dirs:
        if _n(sd) not in seen:
            scan.append((None, sd))
            seen.add(_n(sd))

    # Detect EVERY `synapse`-named entry, incl. namespace-style dirs with no
    # __init__.py. A namespace-portion dir is NOT an importable provider on its
    # own (a regular package elsewhere on the path terminates the namespace
    # search and wins), but it IS a lower-index candidate we must count so the
    # "order proven with indices" claim is honest, not just find_spec-lucky.
    providers = []
    for idx, entry in scan:
        base = entry if entry else os.getcwd()
        syn_dir = os.path.join(base, "synapse")
        cand_pkg = os.path.join(syn_dir, "__init__.py")
        cand_mod = os.path.join(base, "synapse.py")
        prov = None
        if os.path.isfile(cand_pkg):
            prov = (_n(cand_pkg), "regular_package", True)   # importable, provides code
        elif os.path.isfile(cand_mod):
            prov = (_n(cand_mod), "module", True)            # importable, provides code
        elif os.path.isdir(syn_dir):
            prov = (_n(syn_dir), "namespace_portion", False)  # dir, no __init__.py
        if prov:
            providers.append({
                "sys_path_index": idx,
                "entry": _n(base),
                "provider": prov[0],
                "kind": prov[1],
                "importable": prov[2],
                "is_repo_python": _inside(prov[0], repo_python),
            })

    importable = [p for p in providers if p["importable"]]
    namespace_portions = [p for p in providers if not p["importable"]]

    # winner = the lowest-real-index IMPORTABLE provider (what `import synapse`
    # actually binds to). None indexes are site-only extras, ranked last.
    def _rank(p):
        return (p["sys_path_index"] is None, p["sys_path_index"] if p["sys_path_index"] is not None else 1 << 30)
    winner = sorted(importable, key=_rank)[0] if importable else None

    # repo/python index in sys.path
    repo_python_index = None
    for idx, entry in enumerate(sys.path):
        if _n(entry or os.getcwd()) == _n(repo_python):
            repo_python_index = idx
            break

    # A shadow is a competing IMPORTABLE provider outside repo/python. Namespace
    # portions at a lower index are recorded (below) but are non-providers.
    shadows = [p for p in importable if not p["is_repo_python"]]
    lower_index_namespace = [
        p for p in namespace_portions
        if repo_python_index is not None
        and p["sys_path_index"] is not None
        and p["sys_path_index"] < repo_python_index
    ]

    # where does `import synapse` actually resolve (without executing it)?
    spec_origin = None
    try:
        spec = importlib.util.find_spec("synapse")
        spec_origin = _n(spec.origin) if spec and spec.origin else (
            _n(spec.submodule_search_locations[0]) if spec and spec.submodule_search_locations else None
        )
    except Exception as e:                                  # noqa: BLE001
        spec_origin = "ERROR: %r" % e
    spec_is_repo = isinstance(spec_origin, str) and _inside(spec_origin, repo_python)

    # importlib.metadata distributions that provide/are named `synapse`
    dist_hits = []
    try:
        from importlib import metadata as ilmd
        for d in ilmd.distributions():
            try:
                name = (d.metadata.get("Name") or "").strip()
            except Exception:                               # noqa: BLE001
                name = ""
            tops = []
            try:
                tl = d.read_text("top_level.txt") or ""
                tops = [t.strip() for t in tl.splitlines() if t.strip()]
            except Exception:                               # noqa: BLE001
                tops = []
            if name.lower() == "synapse" or "synapse" in [t.lower() for t in tops]:
                loc = ""
                try:
                    loc = _n(str(d.locate_file("")))
                except Exception:                           # noqa: BLE001
                    loc = ""
                # A dist-info whose files live INSIDE repo/python is the repo's
                # OWN editable-install metadata, not a competing (shadow)
                # provider of code. Only OUTSIDE-repo metadata is a shadow.
                dist_hits.append({"name": name, "version": getattr(d, "version", "?"),
                                  "top_level": tops, "location": loc,
                                  "inside_repo_python": _inside(loc, repo_python) if loc else False})
    except Exception as e:                                  # noqa: BLE001
        dist_hits = [{"error": repr(e)}]

    dist_shadows = [d for d in dist_hits if ("error" not in d) and not d.get("inside_repo_python")]
    dist_repo_own = [d for d in dist_hits if ("error" not in d) and d.get("inside_repo_python")]

    winner_is_repo = bool(winner) and winner["is_repo_python"]
    # order proof: repo/python is the lowest-index IMPORTABLE provider, i.e. no
    # importable synapse sits earlier on sys.path. (Lower-index namespace dirs do
    # not provide the package and are reported separately.)
    order_ok = (
        repo_python_index is not None
        and winner_is_repo
        and all(
            (p["sys_path_index"] is None) or (repo_python_index <= p["sys_path_index"])
            for p in importable
        )
    )
    shadow_count = len(shadows)
    dist_shadow_count = len(dist_shadows)
    passed = (shadow_count == 0) and winner_is_repo and spec_is_repo and order_ok and (dist_shadow_count == 0)

    result = {
        "repo_python": _n(repo_python),
        "repo_python_sys_path_index": repo_python_index,
        "providers": providers,
        "provider_count": len(providers),
        "importable_provider_count": len(importable),
        "namespace_portions": namespace_portions,
        "lower_index_namespace_dirs": lower_index_namespace,
        "winner": winner,
        "winner_is_repo_python": winner_is_repo,
        "order_ok_repo_first": order_ok,
        "shadows": shadows,
        "shadow_count": shadow_count,
        "find_spec_origin": spec_origin,
        "find_spec_is_repo": spec_is_repo,
        "metadata_synapse_distributions": dist_hits,
        "metadata_repo_own": dist_repo_own,
        "metadata_shadows": dist_shadows,
        "metadata_shadow_count": dist_shadow_count,
        "sys_path": [_n(e or os.getcwd()) for e in sys.path],
        "pass": passed,
    }
    _emit("== T3  shadow-install sweep (order proven with indices) ==")
    _emit("  repo/python             : %s" % _n(repo_python))
    _emit("  repo/python sys.path idx: %s  (lowest-index IMPORTABLE provider)" % repo_python_index)
    _emit("  `synapse`-named entries : %d (%d importable, %d namespace-portion)"
          % (len(providers), len(importable), len(namespace_portions)))
    for p in providers:
        if p["importable"]:
            tag = "   <== repo (importable)" if p["is_repo_python"] else "   !! SHADOW (importable)"
        else:
            tag = "   namespace-portion (no __init__.py; NOT a provider)"
        _emit("      [idx %s] %s  (%s)%s"
              % (p["sys_path_index"], p["provider"], p["kind"], tag))
    if lower_index_namespace:
        _emit("  note: %d lower-index namespace dir(s) exist but provide no importable"
              % len(lower_index_namespace))
        _emit("        `synapse` - a regular package at idx %s wins the import (proven by find_spec)"
              % repo_python_index)
    _emit("  import synapse resolves : %s  (repo=%s)" % (spec_origin, spec_is_repo))
    _emit("  order repo-first        : %s  (no importable synapse earlier on sys.path)" % order_ok)
    _emit("  metadata dists (synapse): %d total = %d repo-own + %d shadow"
          % (len(dist_repo_own) + len(dist_shadows), len(dist_repo_own), dist_shadow_count))
    for d in dist_repo_own:
        _emit("      repo-own: %s %s @ %s" % (d["name"], d["version"], d["location"]))
    for d in dist_shadows:
        _emit("      !! SHADOW dist: %s %s @ %s" % (d["name"], d["version"], d["location"]))
    _emit("  SHADOW COUNT (code+dist): %d" % (shadow_count + dist_shadow_count))
    _emit("  T3 verdict              : %s" % ("PASS" if passed else "FAIL"))
    _emit()
    return result


# --------------------------------------------------------------------------- #
# T4 - multi-build audit (which GUI build == honest UNKNOWN)                    #
# --------------------------------------------------------------------------- #
def probe_multibuild(hou, prefs_dir):
    builds = sorted(glob.glob(SEF_DIR + "/Houdini *"))
    info = []
    for b in builds:
        name = os.path.basename(b)
        ver = name.split(" ", 1)[1] if " " in name else ""
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", ver)
        if m:
            major, minor = m.group(1), m.group(2)
            info.append({"build": ver, "path": _n(b),
                         "prefs_dir_name": "houdini%s.%s" % (major, minor)})
        else:
            info.append({"build": None, "path": _n(b), "label": name})
    h22 = [x for x in info if (x.get("build") or "").startswith("22.")]
    prefs_names = sorted({x["prefs_dir_name"] for x in h22})

    running = None
    try:
        running = ".".join(str(x) for x in hou.applicationVersion())
    except Exception:                                       # noqa: BLE001
        try:
            running = hou.applicationVersionString()
        except Exception as e:                              # noqa: BLE001
            running = "ERROR: %r" % e

    # Look for ANY artifact that binds a GUI launch to a specific 22.0.x build.
    # None is expected: all 22.0.x share the houdini22.0 prefs dir and overwrite
    # it. We record what we inspected; we do NOT guess.
    artifacts = []
    if prefs_dir:
        for cand in ("logs", "houdini.log", "hversion", "version"):
            p = os.path.join(prefs_dir, cand)
            if os.path.exists(p):
                artifacts.append(_n(p))
    gui_build = "UNKNOWN"
    gui_evidence = ("no prefs/log artifact binds the GUI launch to a specific "
                    "22.0.x build; all 22.0.x map to the single houdini22.0 prefs "
                    "dir and overwrite it on launch")

    # Enumerate the live seat's package dir: which files Houdini would scan
    # (*.json) vs stale sidecars it ignores. This is first-hand seat evidence.
    prefs_packages = []
    synapse_json_scanned = []
    synapse_sidecars_ignored = []
    if prefs_dir:
        for p in sorted(glob.glob(os.path.join(prefs_dir, "packages", "*"))):
            if not os.path.isfile(p):
                continue
            base = os.path.basename(p)
            prefs_packages.append(base)
            if base.lower().startswith("synapse"):
                (synapse_json_scanned if base.lower().endswith(".json")
                 else synapse_sidecars_ignored).append(base)

    result = {
        "installed_builds": info,
        "count_22x": len(h22),
        "prefs_dir_names_for_22x": prefs_names,
        "single_prefs_dir_for_all_22x": prefs_names == ["houdini22.0"],
        "probe_ran_under_build": running,      # proven: this hython
        "gui_launch_build": gui_build,         # UNKNOWN unless artifact proves it
        "gui_launch_evidence": gui_evidence,
        "artifacts_inspected": artifacts,
        "prefs_packages_listing": prefs_packages,
        "seat_synapse_json_scanned": synapse_json_scanned,       # *.json Houdini loads
        "seat_synapse_sidecars_ignored": synapse_sidecars_ignored,  # non-json, not loaded
    }
    _emit("== T4  multi-build audit ==")
    _emit("  installed 22.x builds   : %d" % len(h22))
    for x in h22:
        _emit("      %-10s -> prefs %s   %s" % (x["build"], x["prefs_dir_name"], x["path"]))
    _emit("  all 22.x -> one prefs   : %s (%s)" % (result["single_prefs_dir_for_all_22x"], prefs_names))
    _emit("  probe ran under build   : %s  (proven: this hython)" % running)
    _emit("  Joe's GUI launch build  : UNKNOWN  (%s)" % gui_evidence)
    _emit("  seat synapse *.json     : %s  (Houdini scans these)" % (synapse_json_scanned or "(none)"))
    _emit("  seat synapse sidecars   : %s  (non-json, NOT loaded)" % (synapse_sidecars_ignored or "(none)"))
    _emit()
    return result


# --------------------------------------------------------------------------- #
# T5 - pypanel hot-flush pin                                                    #
# --------------------------------------------------------------------------- #
def probe_pypanel_flush(hou, expect_root):
    syn_root = os.environ.get("SYNAPSE_ROOT", "") or expect_root
    rel = "python_panels/synapse_panel.pypanel"

    # Resolve the pypanel Houdini ACTUALLY loads via HOUDINI_PATH (authoritative,
    # like T2) - not a hard-coded repo path - then assert it lives in the repo.
    resolved_raw, resolve_err = None, None
    try:
        resolved_raw = hou.findFile(rel)
    except Exception as e:                                  # noqa: BLE001
        resolve_err = repr(e)
    resolved = _n(resolved_raw) if resolved_raw else None
    inside_repo = _inside(resolved, syn_root)

    # Shadow-pypanel sweep: any OTHER synapse_panel.pypanel on HOUDINI_PATH.
    shadow_pypanels = []
    try:
        for p in hou.houdiniPath():
            cand = os.path.join(p, "python_panels", "synapse_panel.pypanel")
            if os.path.isfile(cand) and _n(cand) != resolved:
                shadow_pypanels.append(_n(cand))
    except Exception:                                       # noqa: BLE001
        pass

    read_path = resolved_raw or os.path.join(
        syn_root, "houdini", "python_panels", "synapse_panel.pypanel")
    result = {"rel": rel, "resolved_raw": resolved_raw, "resolved": resolved,
              "inside_repo": inside_repo, "resolve_error": resolve_err,
              "read_path": _n(read_path), "exists": os.path.isfile(read_path),
              "shadow_pypanels": shadow_pypanels,
              "flush_loop_line": None, "flush_pop_line": None, "matched_lines": [],
              "pass": False}
    has_loop = has_pop = False
    if result["exists"]:
        lines = open(read_path, encoding="utf-8").read().splitlines()
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if "del sys.modules[" in s:
                result["flush_loop_line"] = i
                result["matched_lines"].append({"line": i, "text": s})
            if re.search(r"sys\.modules\.pop\(\s*['\"]synapse['\"]", s):
                result["flush_pop_line"] = i
                result["matched_lines"].append({"line": i, "text": s})
        text = "\n".join(lines)
        # require: a del over the synapse.* modules AND the pop("synapse")
        has_loop = ("del sys.modules[" in text
                    and re.search(r"startswith\(\s*['\"]synapse\.['\"]", text) is not None)
        has_pop = re.search(r"sys\.modules\.pop\(\s*['\"]synapse['\"]", text) is not None
    result["pass"] = bool(result["exists"] and has_loop and has_pop
                          and inside_repo and not shadow_pypanels)

    _emit("== T5  pypanel hot-flush pin ==")
    if resolved:
        _emit("  findFile('%s')" % rel)
        _emit("      -> %s%s" % (resolved_raw, "" if inside_repo else "   !! OUTSIDE REPO"))
    else:
        _emit("  findFile('%s') -> UNRESOLVED  %s" % (rel, resolve_err))
    _emit("  shadow pypanels on HPATH: %d %s" % (len(shadow_pypanels), shadow_pypanels or ""))
    for m in result["matched_lines"]:
        _emit("      L%d: %s" % (m["line"], m["text"]))
    _emit("  T5 verdict              : %s" % ("PASS" if result["pass"] else "FAIL"))
    _emit()
    return result


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description="W5-SEAT seat-resolution probe")
    ap.add_argument("--expect-root", default=EXPECT_ROOT_DEFAULT,
                    help="the repo the live seat must resolve to")
    ap.add_argument("--out", default=None, help="write results JSON here")
    args = ap.parse_args(argv)

    expect_root = args.expect_root
    prefs_dir = os.environ.get("HOUDINI_USER_PREF_DIR", "")

    _emit("################################################################")
    _emit("# W5-SEAT seat-resolution probe (first-hand, live hython)")
    _emit("#   python     : %s" % sys.version.split()[0])
    _emit("#   executable : %s" % _n(sys.executable))
    _emit("#   prefs dir  : %s" % (prefs_dir or "(unset)"))
    _emit("#   expect repo: %s" % _n(expect_root))
    _emit("################################################################")
    _emit()

    try:
        import hou
    except Exception as e:                                  # noqa: BLE001
        _emit("!! `import hou` FAILED - not running under hython: %r" % e)
        _emit("   Cannot make first-hand seat claims. Recording UNKNOWN.")
        results = {"leg": "W5-SEAT", "error": "hou unavailable", "detail": repr(e),
                   "verdict": "blocked"}
        if args.out:
            open(args.out, "w", encoding="utf-8").write(json.dumps(results, indent=2))
        return 2

    t1 = probe_package_hpath(hou, expect_root, prefs_dir)
    t2 = probe_resources(hou, expect_root)
    t3 = probe_shadow_sweep(expect_root)
    t4 = probe_multibuild(hou, prefs_dir)
    t5 = probe_pypanel_flush(hou, expect_root)

    # Acceptance predicates (the leg's bar).
    acceptance = [
        {"predicate": "package + hpath resolve to the repo under hython with the live prefs dir, first-hand",
         "verdict": "pass" if t1["pass"] else "fail",
         "evidence": "T1: SYNAPSE_ROOT=%s ; <repo>/houdini on HOUDINI_PATH=%s"
                     % (t1["SYNAPSE_ROOT_env"] or "(unset)", t1["hpath_contains_repo"])},
        {"predicate": "all 7 icons + shelf file resolve via hou.findFile into the repo; count asserted",
         "verdict": "pass" if t2["pass"] else "fail",
         "evidence": "T2: icon_count=%d(==%d? %s), all resolved=%s, all inside repo=%s"
                     % (t2["icon_count"], t2["icon_count_expected"], t2["icon_count_ok"],
                        t2["all_resolved"], t2["all_inside_repo"])},
        {"predicate": "zero shadow synapse installs; sys.path order proven with indices",
         "verdict": "pass" if t3["pass"] else "fail",
         "evidence": "T3: shadow_count=%d, repo/python idx=%s (lowest importable), winner_is_repo=%s, "
                     "order_ok=%s, find_spec_is_repo=%s, metadata_shadows=%d"
                     % (t3["shadow_count"], t3["repo_python_sys_path_index"],
                        t3["winner_is_repo_python"], t3["order_ok_repo_first"],
                        t3["find_spec_is_repo"], t3["metadata_shadow_count"])},
    ]
    all_pass = all(a["verdict"] == "pass" for a in acceptance)
    # T5 (pypanel flush) is mission target 5, not one of the 3 formal acceptance
    # predicates - but it must still gate the leg: a flush-block regression makes
    # the verdict blocked, never a silent green.
    gate_pass = all_pass and bool(t5["pass"])

    # T4's mandated UNKNOWN + any stale-sidecar note are honest findings, not
    # failures: green_with_findings when acceptance passes, blocked otherwise.
    findings = [
        {"claim": "multi-build: which 22.0.x build Joe's GUI launched is UNKNOWN",
         "detail": "%d installed 22.x builds share the one houdini22.0 prefs dir; %s"
                   % (t4["count_22x"], t4["gui_launch_evidence"]),
         "anchor": "probe_seat.py::probe_multibuild"},
    ]
    repo_own = t3.get("metadata_repo_own", [])
    if len(repo_own) > 1:
        findings.append({
            "claim": "hygiene: %d duplicate editable-install dist-info in repo/python both provide top-level `synapse`"
                     % len(repo_own),
            "detail": ", ".join("%s %s" % (d["name"], d["version"]) for d in repo_own)
                      + " - both INSIDE repo/python, so NOT shadow installs (T3 shadow_count=0); stale metadata worth a cleanup pass",
            "anchor": "probe_seat.py::probe_shadow_sweep (metadata_repo_own)"})
    sidecars = t4.get("seat_synapse_sidecars_ignored", [])
    if sidecars:
        findings.append({
            "claim": "hygiene: %d stale non-json synapse sidecar(s) in the seat packages dir" % len(sidecars),
            "detail": ", ".join(sidecars) + " - not *.json, so Houdini does NOT load them (no shadow); safe to prune",
            "anchor": "probe_seat.py::probe_multibuild (seat_synapse_sidecars_ignored)"})
    ns = t3.get("lower_index_namespace_dirs", [])
    if ns:
        findings.append({
            "claim": "note: %d lower-index `synapse/` namespace dir(s) on sys.path (no __init__.py)" % len(ns),
            "detail": "; ".join("idx %s %s" % (p["sys_path_index"], p["provider"]) for p in ns)
                      + " - non-importable namespace portions; the repo/python regular package wins the import "
                      "(proven by find_spec), so these are NOT shadows, but they mean repo/python is the lowest "
                      "IMPORTABLE index, not the lowest synapse-named index",
            "anchor": "probe_seat.py::probe_shadow_sweep (lower_index_namespace_dirs)"})
    verdict = "green_with_findings" if gate_pass else "blocked"

    results = {
        "leg": "W5-SEAT",
        "probe": "harness/probes/parity_seat/probe_seat.py",
        "ran_under": {
            "hython": _n(sys.executable),
            "houdini_build": t4["probe_ran_under_build"],
            "prefs_dir": _n(prefs_dir) if prefs_dir else None,
            "python": sys.version.split()[0],
        },
        "expect_root": _n(expect_root),
        "targets": {"T1_package_hpath": t1, "T2_resources": t2,
                    "T3_shadow_sweep": t3, "T4_multibuild": t4,
                    "T5_pypanel_flush": t5},
        "acceptance": acceptance,
        "findings": findings,
        "verdict": verdict,
    }

    _emit("== ACCEPTANCE ==")
    for a in acceptance:
        _emit("  [%s] %s" % (a["verdict"].upper(), a["predicate"]))
    _emit("  T5 pypanel flush (mission target): %s" % ("PASS" if t5["pass"] else "FAIL"))
    _emit("== VERDICT: %s ==" % verdict)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(results, indent=2, ensure_ascii=False))
        _emit("wrote %s" % _n(args.out))

    return 0 if gate_pass else 2


if __name__ == "__main__":
    sys.exit(main())
