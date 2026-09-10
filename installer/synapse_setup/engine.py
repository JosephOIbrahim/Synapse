"""Manifest-based install/upgrade/uninstall. Never imports SYNAPSE or user keys."""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile

from . import discovery
from .registration import installed_package, UI_CORE
from .safety import (SetupError, atomic_write, change, check_writable, current, decode,
                     digest, encode, file_hash, inside, json_bytes, maintenance_lock,
                     member_path, no_links, read_json, recover, transact)

STATE = "installation.json"
JOURNAL = ".transaction.json"
MANIFEST = "payload-manifest.json"


def load_manifest(archive):
    try:
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            if len(names) != len(set(n.lower() for n in names)):
                raise SetupError("Payload contains duplicate Windows file names.")
            data = json.loads(package.read(MANIFEST))
            if data.get("schema") != "synapse-payload-1" or not re.fullmatch(r"\d+\.\d+\.\d+", data.get("version", "")):
                raise SetupError("Invalid SYNAPSE payload manifest/version.")
            if set(names) != set(data["files"]) | {MANIFEST}:
                raise SetupError("Payload members do not match the manifest.")
            for name, expected in data["files"].items():
                member_path(Path.cwd() / "payload-validation", name)
                info = package.getinfo(name)
                if info.file_size > 256 * 1024 * 1024 or info.is_dir():
                    raise SetupError(f"Invalid payload member size/type: {name}")
                if digest(package.read(name)) != expected:
                    raise SetupError(f"Payload checksum failed: {name}")
            if sum(x.file_size for x in package.infolist()) > 1024 * 1024 * 1024:
                raise SetupError("Payload exceeds the 1 GiB installer limit.")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise SetupError(f"Cannot read complete installation payload: {exc}") from exc
    required = {
        "VERSION", "python/synapse/__init__.py", "shared/__init__.py",
        "houdini/python_panels/synapse_panel.pypanel", "houdini/toolbar/synapse.shelf",
        "houdini/scripts/python/synapse_shelf.py", "houdini/scripts/python/tokens.py",
        "houdini/scripts/python/synapse_styles.py", "houdini/config/Icons/SYNAPSE_synapse.svg",
        "python/synapse/_vendor/pydantic_core/_pydantic_core.cp313-win_amd64.pyd",
        "python/synapse/_vendor/jiter/jiter.cp313-win_amd64.pyd",
    }
    for name in ("anthropic", "httpx", "httpcore", "anyio", "pydantic", "idna", "sniffio"):
        required.add(f"python/synapse/_vendor/{name}/__init__.py")
    if data.get("moneta"):
        required.update({"dependencies/moneta/src/moneta/__init__.py", "dependencies/moneta/schema/plugInfo.json", "dependencies/moneta/schema/generatedSchema.usda", "dependencies/moneta/schema/MonetaSchema.usda"})
    missing = required - set(data["files"])
    if missing:
        raise SetupError("Required runtime dependencies are missing: " + ", ".join(sorted(missing)))
    data["payload_id"] = data["version"] + "-" + digest(json_bytes(data))[:16]
    return data


def verify_runtime(root, manifest):
    failures = [name for name, expected in manifest["files"].items()
                if file_hash(member_path(root, name)) != expected]
    if failures:
        raise SetupError("Installed file check failed: " + ", ".join(failures[:10]))
    for name in ("houdini/python_panels/synapse_panel.pypanel", "houdini/toolbar/synapse.shelf"):
        try:
            ET.parse(root / name)
        except ET.ParseError as exc:
            raise SetupError(f"Invalid Houdini interface XML: {name}: {exc}") from exc
    if (root / "VERSION").read_text().strip() != manifest["version"]:
        raise SetupError("Runtime version disagrees with payload version.")
    return {"status": "PASS", "files_checked": len(manifest["files"]), "xml": "PASS"}


def state_for(app):
    state = read_json(app / STATE)
    if state is not None and (state.get("schema") != "synapse-install-1" or state.get("app") != str(app)):
        raise SetupError(f"Installation receipt does not belong to this folder: {app}")
    return state


def check_maintenance(app, *, allow_missing=False):
    """Inno owns helper deletion: block it if a recorded helper was edited."""
    base = no_links(app / "maintenance")
    if not base.exists():
        return
    manifest = read_json(base / "maintenance-manifest.json")
    if not manifest or manifest.get("schema") != "synapse-maintenance-1":
        raise SetupError("Maintenance manifest is missing. Preserve this folder and use a new application folder, or restore the matching manifest before maintenance.")
    for name, expected in manifest["files"].items():
        path = member_path(base, name)
        if allow_missing and not path.exists():
            continue
        if file_hash(path) != expected:
            raise SetupError(f"A maintenance file was changed or removed: {path}. Save your edit elsewhere and restore the original before upgrading or uninstalling. No files were removed.")


def completed_uninstall(app, *, sandbox=None):
    """Recognize the last safe boundary before Inno removes Windows integration."""
    archive = read_json(app / "uninstall-receipt.json")
    if not archive:
        return None
    if (archive.get("schema") != "synapse-uninstall-1" or archive.get("app") != str(app)
            or archive.get("status") != "PASS"
            or read_json(app / ".setup-owned.json") != {"schema": "synapse-directory-1", "app": str(app)}):
        raise SetupError("Completed uninstall receipt does not belong to this application folder.")
    if archive.get("former_installation"):
        former = archive["former_installation"]
        if former.get("schema") != "synapse-install-1" or former.get("app") != str(app):
            raise SetupError("Completed uninstall has an invalid former installation.")
        validate_receipt(app, former, sandbox)
    else:
        context = archive.get("recovery_context", {})
        if not context.get("homes") or not context.get("preferences"):
            raise SetupError("Completed uninstall is missing its recovery context.")
        for home in context["homes"]:
            guard_paths(app, list(map(Path, context["preferences"])), Path(home), sandbox)
    return {"status": "PASS", "removed": "Runtime uninstall already completed; Windows cleanup may resume.",
            "receipt": str(app / "uninstall-receipt.json")}


def validate_receipt(app, state, sandbox=None):
    """Receipts and journals are input, never unrestricted filesystem authority."""
    home = no_links(state["user_home"])
    prefs = [no_links(x["pref"]) for x in state["registrations"]]
    guard_paths(app, prefs, home, sandbox)
    for entry in state["registrations"]:
        if no_links(entry["path"]) != no_links(Path(entry["pref"]) / "packages/synapse.json"):
            raise SetupError("Receipt contains an unexpected registration destination.")
    if no_links(state["stamp"]["path"]) != home / ".synapse/install_stamp.json":
        raise SetupError("Receipt contains an unexpected diagnostic stamp destination.")
    for backup in state["backups"]:
        path = no_links(backup["path"])
        if not any(authorized_pref_file(path, pref) for pref in prefs):
            raise SetupError(f"Receipt backup destination is outside its Houdini preferences: {path}")
    for root, manifest in state["runtimes"].items():
        runtime = inside(root, app / "versions")
        if runtime.parent != app / "versions":
            raise SetupError("Invalid runtime directory in receipt.")
        for name in manifest["files"]:
            member_path(runtime, name)
    if state["active"] not in state["runtimes"]:
        raise SetupError("Active runtime is absent from the receipt.")
    return prefs, home


def authorized_pref_file(path, pref):
    if path.is_relative_to(pref / "packages") and path.suffix.lower() == ".json":
        return True
    if path in {pref / "toolbar/synapse.shelf", pref / "python_panels/synapse_panel.pypanel", pref / "scripts/python/synapse_shelf.py"}:
        return True
    return path.parent == pref / "config/Icons" and path.name.startswith("SYNAPSE_") and path.suffix.lower() in {".png", ".svg"}


def recover_install(app, prefs=(), home=None, sandbox=None, *, perform=True, keep_journal=False):
    journal = read_json(app / JOURNAL)
    if not journal:
        return False
    if journal.get("schema") != "synapse-transaction-1":
        raise SetupError("Unrecognized installation recovery journal.")
    candidates = []
    existing = state_for(app)
    if existing:
        candidates.append(existing)
    for op in journal.get("changes", []):
        if no_links(op["path"]) == app / STATE:
            for key in ("before", "after"):
                if op.get(key):
                    candidate = json.loads(decode(op[key]))
                    if candidate.get("schema") != "synapse-install-1" or candidate.get("app") != str(app):
                        raise SetupError("Recovery state does not belong to this installation.")
                    candidates.append(candidate)
    all_prefs = list(prefs)
    homes = [no_links(home)] if home else []
    for candidate in candidates:
        stored_prefs, stored_home = validate_receipt(app, candidate, sandbox)
        all_prefs.extend(stored_prefs)
        homes.append(stored_home)
    if not homes:
        raise SetupError("Recovery journal has no valid installation context; no files were changed.")
    for stored_home in homes:
        guard_paths(app, all_prefs, stored_home, sandbox)
    allowed = {app / STATE, *(h / ".synapse/install_stamp.json" for h in homes)}
    for candidate in candidates:
        allowed.update(no_links(entry["path"]) for entry in candidate["registrations"])
        allowed.update(no_links(entry["path"]) for entry in candidate["backups"])
    for op in journal.get("changes", []):
        path = no_links(op["path"])
        if sandbox:
            inside(path, sandbox)
        if path not in allowed:
            raise SetupError(f"Recovery target is outside the installation's authority: {path}")
        if not journal.get("committed") and current(path) not in (decode(op["before"]), decode(op["after"])):
            raise SetupError(f"Recovery stopped to preserve an externally changed file: {path}.")
    if not perform:
        return {"homes": list(map(str, homes)), "preferences": list(map(str, all_prefs))}
    return recover(app / JOURNAL, keep_journal=keep_journal)


def is_synapse(data, filename=""):
    if not isinstance(data, dict):
        return False
    return (str(data.get("name", "")).lower() == "synapse"
            or "synapse" in filename.lower()
            or any(isinstance(e, dict) and (e.get("var") == "SYNAPSE_ROOT" or "SYNAPSE_ROOT" in e) for e in data.get("env", []) if isinstance(data.get("env"), list)))


def registrations(directory, environ=None):
    found, pending, seen = [], [directory], set()
    env = dict(os.environ if environ is None else environ)
    while pending:
        folder = no_links(pending.pop(0))
        if folder in seen or not folder.is_dir():
            continue
        seen.add(folder)
        if len(seen) > 128:
            raise SetupError("Too many linked package directories to check safely.")
        # Match Houdini: only immediate files, then explicit package_path links.
        for path in sorted(folder.glob("*.json")):
            no_links(path)
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, OSError):
                if "synapse" in path.name.lower():
                    raise SetupError(f"Unreadable SYNAPSE package: {path}. Repair or move it before installing.")
                continue
            if not isinstance(data, dict) or data.get("enable", True) is False:
                continue
            if is_synapse(data, path.name):
                found.append(path)
            links = data.get("package_path", [])
            if isinstance(links, str):
                links = [links]
            if not isinstance(links, list) or any(not isinstance(link, str) for link in links):
                raise SetupError(f"Cannot resolve conditional package_path in {path}. Use a launch configuration with explicit package paths before setup.")
            for link in links:
                expanded = re.sub(r"\$\{([A-Za-z_][A-Za-z_0-9]*)\}|\$([A-Za-z_][A-Za-z_0-9]*)|%([A-Za-z_][A-Za-z_0-9]*)%",
                                  lambda m: env.get(next(x for x in m.groups() if x), m.group(0)), link)
                if "$" in expanded or "%" in expanded or not Path(expanded).is_absolute():
                    raise SetupError(f"Cannot safely resolve package_path '{link}' in {path}. Set an explicit launch path before setup.")
                pending.append(Path(expanded))
    return list(dict.fromkeys(found))


def guard_paths(app, prefs, home, sandbox=None):
    app, home = no_links(app), no_links(home)
    prefs = [no_links(p) for p in prefs]
    if app == app.anchor or len(app.parts) < 3:
        raise SetupError("Choose a dedicated SYNAPSE application folder.")
    for pref in prefs:
        if app == pref or app.is_relative_to(pref) or pref.is_relative_to(app):
            raise SetupError("The application and Houdini preference folders must be separate.")
        if pref == home or pref in home.parents:
            raise SetupError("Select a Houdini preference folder, not your home or a drive root.")
    if app == home or home.is_relative_to(app):
        raise SetupError("The application folder must not contain your user home.")
    if sandbox:
        sandbox = no_links(sandbox)
        for path in [app, home, *prefs]:
            inside(path, sandbox)
        if sandbox == Path.home() or Path.home().is_relative_to(sandbox):
            raise SetupError("Test root cannot contain the real user home.")
    else:
        active = discovery.running_houdini()
        if active:
            raise SetupError("Houdini is running (" + ", ".join(x["name"] + " PID " + str(x["pid"]) for x in active) + "). Save your work and close Houdini, then retry. Setup never closes it.")
    return app, prefs, home


def preflight(app, prefs, home, *, archive=None, hfs=None, allow_unverified=False,
              migrate=False, sandbox=None, uninstall=False):
    app, prefs, home = guard_paths(app, prefs, home, sandbox)
    check_maintenance(app, allow_missing=not uninstall)
    state = state_for(app)
    if state:
        validate_receipt(app, state, sandbox)
        if state.get("unregistered") and not uninstall:
            raise SetupError("An uninstall was interrupted. Run uninstall again before installing; retained data is preserved.")
    target = None
    if not uninstall:
        if not prefs:
            raise SetupError("Choose at least one Houdini preference folder.")
        if not hfs:
            raise SetupError("Choose the Houdini application folder.")
        target = discovery.validate_houdini(hfs)
        if not target["tested"] and not allow_unverified:
            raise SetupError(f"Houdini {target['version']} / Python {target['python']} compatibility is unverified. Acknowledge this in the wizard to continue.")
    manifest = load_manifest(archive) if archive else None
    if state and manifest and tuple(map(int, manifest["version"].split("."))) < tuple(map(int, state["version"].split("."))):
        raise SetupError(f"This is a downgrade from {state['version']} to {manifest['version']}. Keep the newer setup or uninstall first. User data is preserved.")
    if not state and app.exists():
        allowed = {".maintenance.lock", "maintenance", "unins000.exe", "unins000.dat", "unins000.msg"}
        if read_json(app / ".setup-owned.json") == {"schema": "synapse-directory-1", "app": str(app)}:
            allowed.update({"versions", ".setup-owned.json", "uninstall-receipt.json"})
        if any(p.name not in allowed for p in app.iterdir()):
            raise SetupError(f"The application folder contains an unrecognized installation or other files: {app}. Choose a new empty folder.")
    check_writable(app)
    for pref in prefs:
        check_writable(pref / "packages")
    check_writable(home / ".synapse")
    if state and not state.get("unregistered"):
        for owned in state["registrations"]:
            if file_hash(no_links(owned["path"])) != owned["sha256"]:
                raise SetupError(f"A registered package was changed or removed outside Setup: {owned['path']}. Restore the recorded file before maintenance; user edits are preserved.")
    owned_paths = {x["path"] for x in state["registrations"]} if state else set()
    conflicts = []
    for pref in prefs:
        scan_env = dict(os.environ, HOUDINI_USER_PREF_DIR=str(pref), HFS=str(hfs or ""))
        for path in registrations(pref / "packages", scan_env):
            if str(path) in owned_paths:
                continue
            if path.parent != pref / "packages":
                raise SetupError(f"External SYNAPSE package is loaded through package_path: {path}. Change the launcher/studio configuration; Setup will not migrate external files.")
            conflicts.append(path)
        target_file = pref / "packages/synapse.json"
        if target_file.exists() and target_file not in conflicts and str(target_file) not in owned_paths:
            raise SetupError(f"The package filename is already owned by another configuration: {target_file}")
        for rel in ("toolbar/synapse.shelf", "python_panels/synapse_panel.pypanel", "scripts/python/synapse_shelf.py"):
            if (pref / rel).exists():
                conflicts.append(pref / rel)
        conflicts.extend((pref / "config/Icons").glob("SYNAPSE_*.svg"))
        conflicts.extend((pref / "config/Icons").glob("SYNAPSE_*.png"))
    conflicts = list(dict.fromkeys(conflicts))
    if conflicts and not migrate and not uninstall:
        raise SetupError("Existing SYNAPSE registration or interface files found. Select 'Back up and replace existing SYNAPSE registration' to migrate:\n" + "\n".join(map(str, conflicts)))
    if not sandbox and not uninstall:
        selected = {str(p / "packages") for p in prefs}
        for directory in discovery.external_package_dirs(hfs):
            if str(no_links(directory)) in selected:
                continue
            dup = registrations(directory, dict(os.environ, HFS=str(hfs or "")))
            if dup:
                raise SetupError("External/studio SYNAPSE registration also loads for this Houdini. Remove it from the launch configuration before setup; no external files were changed:\n" + "\n".join(map(str, dup)))
    return {"app": str(app), "preferences": list(map(str, prefs)), "houdini": target,
            "conflicts": list(map(str, conflicts)), "version": manifest["version"] if manifest else None,
            "status": "PASS"}


def install(app, prefs, home, *, archive, hfs, allow_unverified=False, migrate=False, sandbox=None):
    app, prefs, home = guard_paths(app, prefs, home, sandbox)
    # Validate payload and target BEFORE creating application files.
    manifest = load_manifest(archive)
    if not (app / JOURNAL).exists():
        preflight(app, prefs, home, archive=archive, hfs=hfs, allow_unverified=allow_unverified, migrate=migrate, sandbox=sandbox)
    with maintenance_lock(app):
        recovered = recover_install(app, prefs, home, sandbox)
        atomic_write(app / ".setup-owned.json", json_bytes({"schema": "synapse-directory-1", "app": str(app)}))
        prior = state_for(app)
        # Upgrade all registrations managed by this installation, plus new targets.
        all_prefs = list(dict.fromkeys([*(Path(x["pref"]) for x in prior["registrations"])] + prefs)) if prior else prefs
        plan = preflight(app, all_prefs, home, archive=archive, hfs=hfs,
                         allow_unverified=allow_unverified, migrate=migrate, sandbox=sandbox)
        runtime = inside(app / "versions" / manifest["payload_id"], app)
        if not runtime.exists():
            runtime.mkdir(parents=True)
            # New content-addressed folder never overwrites a running/old runtime.
            with zipfile.ZipFile(archive) as bundle:
                for name in manifest["files"]:
                    atomic_write(member_path(runtime, name), bundle.read(name))
            atomic_write(runtime / MANIFEST, json_bytes(manifest))
        else:
            # Recover an interrupted extraction only when every existing byte is
            # recognized. A user-modified file must never be silently repaired.
            with zipfile.ZipFile(archive) as bundle:
                for name, expected in manifest["files"].items():
                    path = member_path(runtime, name)
                    if path.exists() and file_hash(path) != expected:
                        raise SetupError(f"Runtime file was modified: {path}. Choose a new application folder to preserve it.")
                    if not path.exists():
                        atomic_write(path, bundle.read(name))
            atomic_write(runtime / MANIFEST, json_bytes(manifest))
        checks = verify_runtime(runtime, manifest)
        state = copy.deepcopy(prior) if prior else {"schema": "synapse-install-1", "app": str(app), "id": uuid.uuid4().hex, "registrations": [], "backups": [], "runtimes": {}, "user_home": str(home)}
        if state["user_home"] != str(home):
            raise SetupError("This installation belongs to a different user-home path.")
        state.update(version=manifest["version"], active=str(runtime), houdini=plan["houdini"])
        state["runtimes"][str(runtime)] = manifest
        changes = []
        backup_paths = {x["path"] for x in state["backups"]}
        for name in plan["conflicts"]:
            if name in backup_paths:
                raise SetupError(f"A previously migrated file has been recreated: {name}. Keep it or move it before retrying; the original backup is preserved.")
            if name not in backup_paths:
                original = current(name)
                state["backups"].append({"path": name, "original": encode(original)})
                backup_paths.add(name)
            # The canonical filename is overwritten once below, not deleted first.
            if name not in {str(p / "packages/synapse.json") for p in all_prefs}:
                changes.append(change(name, None))
        package = installed_package(runtime, manifest, home)
        package["synapse_setup_owner"] = state["id"]
        package_data = json_bytes(package)
        state["registrations"] = []
        for pref in all_prefs:
            path = pref / "packages/synapse.json"
            changes.append(change(path, package_data))
            state["registrations"].append({"pref": str(pref), "path": str(path), "sha256": digest(package_data)})
        stamp = home / ".synapse/install_stamp.json"
        if "stamp" not in state:
            state["stamp"] = {"path": str(stamp), "original": encode(current(stamp))}
        elif file_hash(stamp) != state["stamp"]["sha256"]:
            raise SetupError(f"Another installer changed the diagnostic stamp: {stamp}. Existing content is preserved.")
        stamp_data = json_bytes({"schema": "synapse_install_stamp/v1", "synapse_version": manifest["version"],
                                 "repo_root": runtime.as_posix(), "installed_at": datetime.now(timezone.utc).isoformat(),
                                 "targets": [x["path"] for x in state["registrations"]]})
        changes.append(change(stamp, stamp_data))
        state["stamp"]["sha256"] = digest(stamp_data)
        state["checks"] = checks
        changes.append(change(app / STATE, json_bytes(state)))
        # Repeat the process guard at the last possible point before activation.
        guard_paths(app, all_prefs, home, sandbox)
        transact(app / JOURNAL, changes)
        try:
            report = verify(app)
        except Exception:
            # Readback failure restores the former registration/state; payload
            # remains staged and is never represented as a successful install.
            inverse = [{"path": op["path"], "before": op["after"], "after": op["before"]} for op in reversed(changes)]
            transact(app / JOURNAL, inverse)
            raise
        report["recovered_interrupted_transaction"] = recovered
        return report


def verify(app):
    app = no_links(app)
    check_maintenance(app)
    if (app / JOURNAL).exists():
        raise SetupError("Installation has an interrupted transaction. Run Setup again to recover it.")
    state = state_for(app)
    if not state:
        raise SetupError("No completed SYNAPSE installation receipt was found.")
    root = inside(state["active"], app / "versions")
    checks = verify_runtime(root, state["runtimes"][str(root)])
    for entry in state["registrations"]:
        if file_hash(no_links(entry["path"])) != entry["sha256"]:
            raise SetupError(f"Package registration verification failed: {entry['path']}")
        package = read_json(entry["path"])
        if package["hpath"] != (root / "houdini").as_posix():
            raise SetupError("Package runtime path disagrees with installation receipt.")
    if file_hash(no_links(state["stamp"]["path"])) != state["stamp"]["sha256"]:
        raise SetupError("Diagnostic installation stamp differs from the installed receipt.")
    return {"status": "PASS", "version": state["version"], "runtime": str(root),
            "checks": checks, "registrations_checked": len(state["registrations"]),
            "memory": "Moneta bundled" if state["runtimes"][str(root)].get("moneta") else "JSONL; Moneta not bundled",
            "manual": ["Launch Houdini to verify package loading and open New Pane Tab > Synapse.",
                       "Use Doctor for live components and USD schema diagnostics.",
                       "Connect models is a separate step; no model or credentials were tested."]}


def uninstall(app, *, sandbox=None):
    app = no_links(app)
    check_maintenance(app)
    recovered = False
    recovery_context = None
    if (app / JOURNAL).exists():
        with maintenance_lock(app):
            recovery_context = recover_install(app, sandbox=sandbox, perform=False)
            # Keep the only recovery authority durable until a receipt below
            # records completion (or an older installation receipt survives).
            recovered = recover_install(app, sandbox=sandbox, keep_journal=True)
            if state_for(app):
                (app / JOURNAL).unlink()
    state = state_for(app)
    if not state:
        if recovered:
            atomic_write(app / "uninstall-receipt.json", json_bytes({"schema": "synapse-uninstall-1", "app": str(app),
                         "status": "PASS", "recovery_context": recovery_context}))
            (app / JOURNAL).unlink(missing_ok=True)
            return {"status": "PASS", "recovered": "Interrupted first installation rolled back; unregistered staged files retained for review."}
        completed = completed_uninstall(app, sandbox=sandbox)
        if completed:
            return completed
        raise SetupError("No installation receipt. Refusing to guess which files to remove.")
    prefs, home = validate_receipt(app, state, sandbox)
    guard_paths(app, prefs, home, sandbox)
    with maintenance_lock(app):
        recover_install(app, prefs, home, sandbox)
        state = state_for(app)
        preflight(app, prefs, home, sandbox=sandbox, uninstall=True)
        changes, restored, preserved = [], [], []
        backups = {x["path"]: decode(x["original"]) for x in state["backups"]}
        if not state.get("unregistered"):
            for entry in state["registrations"]:
                changes.append(change(entry["path"], backups.pop(entry["path"], None)))
            for path, original in backups.items():
                if current(path) is not None:
                    raise SetupError(f"Cannot restore a legacy backup over a new file: {path}. Your files are preserved.")
                changes.append(change(path, original))
                restored.append(path)
        stamp = state["stamp"]
        if not state.get("unregistered") and file_hash(stamp["path"]) == stamp["sha256"]:
            changes.append(change(stamp["path"], decode(stamp["original"])))
        elif not state.get("unregistered"):
            preserved.append(stamp["path"])
        # First deactivate/restore registrations. No runtime can be left active
        # pointing at files removed by a failed uninstall.
        uninstall_receipt = copy.deepcopy(state)
        uninstall_receipt["unregistered"] = True
        changes.append(change(app / STATE, json_bytes(uninstall_receipt)))
        transact(app / JOURNAL, changes)
        for name, manifest in state["runtimes"].items():
            root = inside(name, app / "versions")
            for relative, expected in manifest["files"].items():
                path = member_path(root, relative)
                if path.exists():
                    if file_hash(path) == expected:
                        path.unlink()
                    else:
                        preserved.append(str(path))
            metadata = root / MANIFEST
            if metadata.exists() and read_json(metadata) == manifest:
                metadata.unlink()
            # Only attempt to remove empty, known parent directories. No glob
            # deletes: user projects, credentials and runtime state always survive.
            parents = {p for rel in manifest["files"] for p in member_path(root, rel).parents if p.is_relative_to(root)}
            for path in sorted(parents, key=lambda p: len(p.parts), reverse=True):
                no_links(path)
                try:
                    path.rmdir()
                except OSError:
                    pass
            if root.exists():
                preserved.append(str(root) + " (additional or modified files retained)")
        # Preserve backup provenance for recovery without deleting user contents.
        archive = app / "uninstall-receipt.json"
        atomic_write(archive, json_bytes({"schema": "synapse-uninstall-1", "app": str(app), "status": "PASS", "restored": restored, "preserved": preserved,
                                       "former_installation": state}))
        (app / STATE).unlink()
        return {"status": "PASS", "removed": "Manifest-owned unchanged files and registration", "preserved": preserved,
                "restored": restored, "receipt": str(archive)}
