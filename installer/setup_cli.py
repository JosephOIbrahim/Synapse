"""Machine-readable maintenance front door used by Inno and local diagnostics."""
import argparse
import configparser
import ctypes
import json
from pathlib import Path
import sys

from synapse_setup import discovery, engine
from synapse_setup.safety import SetupError, atomic_write, json_bytes, read_json, maintenance_lock, no_links


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["discover", "preflight", "install", "verify", "uninstall", "uninstall-check"])
    parser.add_argument("--app", type=Path)
    parser.add_argument("--pref", action="append", type=Path, default=[])
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--hfs", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--allow-unverified", action="store_true")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--sandbox", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--ini", type=Path)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "discover":
            result = discovery.discover()
            if args.ini:
                config = configparser.ConfigParser(interpolation=None)
                config["discovery"] = {"count": str(len(result["installations"]))}
                for i, entry in enumerate(result["installations"]):
                    prefs = entry["preferences"]
                    config[str(i)] = {"hfs": entry["hfs"], "version": entry["version"], "python": entry["python"], "tested": str(int(entry["tested"])),
                                      "pref": prefs[0]["path"] if prefs else "", "source": prefs[0]["source"] if prefs else "Custom",
                                      "pref_count": str(len(prefs))}
                    for j, pref in enumerate(prefs):
                        config[str(i)]["pref_" + str(j)] = pref["path"]
                        config[str(i)]["source_" + str(j)] = pref["source"]
                with args.ini.open("w", encoding="utf-16") as stream:
                    config.write(stream)
        elif args.action in {"install", "preflight"}:
            if not args.app:
                raise SetupError("An application directory is required.")
            if args.action == "preflight" and (args.app / engine.JOURNAL).exists():
                app = no_links(args.app)
                engine.guard_paths(app, args.pref, args.home, args.sandbox)
                with maintenance_lock(app):
                    engine.recover_install(app, args.pref, args.home, args.sandbox)
            result = getattr(engine, args.action)(args.app, args.pref, args.home, archive=args.payload,
                        hfs=args.hfs, allow_unverified=args.allow_unverified, migrate=args.migrate, sandbox=args.sandbox)
        elif args.action == "uninstall-check":
            engine.check_maintenance(args.app)
            state = engine.state_for(args.app)
            if (args.app / engine.JOURNAL).exists():
                engine.recover_install(no_links(args.app), sandbox=args.sandbox, perform=False)
                result = {"status": "PASS", "recovery": "Pending transaction will be recovered on uninstall."}
            elif state:
                prefs, home = engine.validate_receipt(args.app, state, args.sandbox)
                result = engine.preflight(args.app, prefs, home, sandbox=args.sandbox, uninstall=True)
            elif engine.completed_uninstall(args.app, sandbox=args.sandbox):
                result = {"status": "PASS", "recovery": "Runtime uninstall completed; Windows cleanup may resume."}
            else:
                raise SetupError("No installation receipt; no runtime files will be removed.")
        elif args.action == "uninstall":
            result = engine.uninstall(args.app, sandbox=args.sandbox)
        else:
            result = engine.verify(args.app)
        code = 0
    except Exception as exc:
        result, code = {"status": "FAIL", "error": str(exc), "exception": type(exc).__name__}, 1
    if code:
        message = result.get("error") or "SYNAPSE could not complete its checks. See the setup log."
    else:
        heading = "SYNAPSE" + (" " + str(result["version"]) if result.get("version") else "")
        message = heading + " checks passed.\n\n" + "\n".join(result.get("manual") or [])
    if args.report:
        atomic_write(args.report, json_bytes(result))
        atomic_write(args.report.with_suffix(".txt"), message.encode("utf-8"))
    if args.show and sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, message, "SYNAPSE installation check", 0x10 if code else 0x40)
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
