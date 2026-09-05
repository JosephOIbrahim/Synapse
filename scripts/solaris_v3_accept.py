#!/usr/bin/env python3
"""One acceptance command for Solaris v3; also its in-process pytest plugin.

Suite results and product rows are separate. Exact reviewed bindings plus fresh
path evidence are required to promote rows; an empty binding map is intentional
until the integrator has actual tests to bind. No GUI operations are performed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
GATES_PATH = Path("harness/solaris_v3/GATES.json")
RUNS_PATH = Path("harness/solaris_v3/runs")
TIERS = ("pure", "hython", "gui")
PURE_GLOBS = ("tests/test_recipe_*.py", "tests/test_worker_policy_demo*.py",
              "tests/test_solaris_v3_*.py")
PINNED_BUILD = "22.0.400"
ROW_IDS = {f"G{i}" for i in range(7)} | {f"T{i}" for i in range(1, 13)}
STATUSES = {"PASS", "FAIL", "UNKNOWN", "NOT_RUN"}
EVIDENCE_KEYS = {"receipt_id", "commit", "build", "runner_command", "log_path", "artifact_hashes"}
CONTEXT_ENV = "SYNAPSE_SOLARIS_ACCEPTANCE_CONTEXT"


class BindingError(ValueError):
    """The process did not exercise the checkout/build it claims to exercise."""


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=15)
    if result.returncode:
        raise BindingError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def checkout_identity(root, module_file):
    """Check an already imported module, not the intended PYTHONPATH."""
    root, module = Path(root).resolve(), Path(module_file).resolve()
    if not inside(module, root / "python" / "synapse"):
        raise BindingError(f"wrong checkout: loaded synapse at {module}; expected {root / 'python' / 'synapse'}")
    imported_root = Path(git(module.parent, "rev-parse", "--show-toplevel")).resolve()
    if imported_root != root:
        raise BindingError(f"imported git checkout {imported_root} differs from launch checkout {root}")
    # Commit is read from the checkout containing the imported module.
    source_paths = ("python/synapse", "scripts", "tests", "fixtures",
                    "harness/solaris_v3/bench.py", str(GATES_PATH).replace("\\", "/"))
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "--", *source_paths).splitlines()
    untracked_hashes = {path: sha256(root / path) for path in untracked if (root / path).is_file()}
    return {"checkout": str(root), "module_path": str(module),
            "commit": git(imported_root, "rev-parse", "HEAD"),
            "dirty": bool(untracked_hashes) or bool(git(root, "status", "--porcelain", "--untracked-files=no")),
            "untracked_source_hashes": untracked_hashes,
            "diff_sha256": hashlib.sha256(git(root, "diff", "HEAD", "--binary").encode("utf-8")).hexdigest()}


def bind_test_source(root, collected_path, module_file, expected_hashes):
    root, source = Path(root).resolve(), Path(collected_path).resolve()
    if not module_file or not inside(source, root) or Path(module_file).resolve() != source:
        raise BindingError(f"wrong test module: collected {source}, loaded {module_file}")
    relative = source.relative_to(root).as_posix()
    digest = sha256(source)
    if expected_hashes and expected_hashes.get(relative) != digest:
        raise BindingError(f"collected test does not match selected source: {relative}")
    return str(source), digest


def loaded_identity(root, tier):
    import synapse
    identity = checkout_identity(root, synapse.__file__)
    identity.update(build="UNAVAILABLE: pure Python (no host qualification)", hou_module_path=None)
    if tier == "hython":
        import hou
        if getattr(hou, "__synapse_canonical__", False) or not getattr(hou, "__file__", None):
            raise BindingError("hython requires the real hou module, not a test double")
        from synapse.server.main_thread import run_on_main
        # Confirmed in h22_symbol_table.json; absent from rulebook/phantoms.json.
        identity["build"] = run_on_main(hou.applicationVersionString)
        identity["hou_module_path"] = str(Path(hou.__file__).resolve())
        if identity["build"] != PINNED_BUILD:
            raise BindingError(f"wrong Houdini build: {identity['build']}; required {PINNED_BUILD}")
    return identity


def validate_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("timestamp must include a timezone")


def validate_evidence(evidence, tier):
    if not isinstance(evidence, dict) or not EVIDENCE_KEYS <= evidence.keys():
        raise ValueError("missing evidence")
    for key in ("receipt_id", "commit", "build", "log_path", "module_path"):
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            raise ValueError(f"empty or invalid evidence: {key}")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", evidence["commit"]):
        raise ValueError("commit must be a complete git object ID")
    if tier == "hython" and evidence["build"] != PINNED_BUILD:
        raise ValueError("hython evidence requires the pinned build")
    command = evidence["runner_command"]
    if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
        raise ValueError("runner_command must be a nonempty argument vector")
    hashes = evidence["artifact_hashes"]
    if not isinstance(hashes, dict) or not hashes or not all(
        isinstance(path, str) and path and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest) for path, digest in hashes.items()
    ):
        raise ValueError("artifact_hashes must contain paths and SHA-256 digests")
    if evidence["log_path"] not in hashes:
        raise ValueError("log_path must have an artifact hash")


def validate_gates(data):
    if data.get("schema_version") != 1:
        raise ValueError("unsupported gate schema")
    rows = data.get("rows", [])
    if len(rows) != len(ROW_IDS) or {r.get("id") for r in rows} != ROW_IDS:
        raise ValueError("GATES must contain G0-G6 and T1-T12 exactly once")
    for row in rows:
        if not {"id", "goalpost", "status", "evidence", "tier", "last_run"} <= row.keys():
            raise ValueError("gate row missing required fields")
        if not isinstance(row["goalpost"], str) or not row["goalpost"].strip():
            raise ValueError("gate goalpost must be nonempty")
        if row["tier"] not in TIERS or row["status"] not in STATUSES:
            raise ValueError("invalid tier/status")
        if row["status"] in {"PASS", "FAIL"}:
            validate_evidence(row["evidence"], row["tier"])
            validate_timestamp(row["last_run"])
        elif row["evidence"] is not None:
            raise ValueError("unmeasured gate cannot carry a promotion receipt")
        elif row["last_run"] is not None:
            validate_timestamp(row["last_run"])
    rule = data.get("promotion_rule", {})
    if not EVIDENCE_KEYS <= set(rule.get("required_evidence", [])) or not rule.get("rule"):
        raise ValueError("promotion rule missing required evidence")
    bindings = rule.get("bindings")
    if not isinstance(bindings, dict) or not set(bindings) <= ROW_IDS:
        raise ValueError("invalid row bindings")
    for specs in bindings.values():
        if not isinstance(specs, list) or not specs:
            raise ValueError("bindings must be nonempty lists")
        seen = set()
        for spec in specs:
            nodeid, path = spec.get("nodeid", ""), spec.get("intended_path", "")
            file = Path(nodeid.split("::")[0])
            if (not nodeid.startswith("tests/") or "::" not in nodeid or ".." in file.parts
                    or file.suffix != ".py" or nodeid in seen or not isinstance(path, str) or not path.strip()):
                raise ValueError("bindings need unique exact test nodeids and intended_path")
            seen.add(nodeid)
    return data


def discover(root, patterns=PURE_GLOBS):
    files, missing = set(), []
    for pattern in patterns:
        matches = [p for p in Path(root).glob(pattern) if p.is_file()]
        if not matches:
            missing.append(f"NOT_RUN: no tests collected for {pattern}")
        for match in matches:
            if not inside(match, root):
                raise BindingError(f"test path escapes checkout: {match}")
            files.add(match.relative_to(root).as_posix())
    return sorted(files), missing


def hython_candidates(root, environ=None):
    environ = os.environ if environ is None else environ
    explicit = environ.get("SYNAPSE_HYTHON")
    if explicit:
        return [explicit]  # A bad explicit pin never falls back to another build.
    shim = Path(root) / ".synapse/hytest.py"
    if not shim.is_file():
        return []
    spec = importlib.util.spec_from_file_location("_solaris_hytest", shim)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Reuse the repo shim's discovery, but never its newest-first selection or
    # GUI/PySide probe. Candidate paths must carry the pin; the process proves it.
    return list(dict.fromkeys(str(p) for p in module._candidates()
                             if re.search(r"(?<!\d)22\.0\.400(?!\d)", str(p))))


def subprocess_env(root):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root / "python"), str(root), env.get("PYTHONPATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["QT_QPA_PLATFORM"] = "offscreen"
    # Do not let a parent's selection/filter/plugin flags silently shrink proof.
    env.pop("PYTEST_ADDOPTS", None)
    env.pop(CONTEXT_ENV, None)
    return env


def run_logged(command, root, env, log, timeout):
    """Bounded child; logs remain evidence even when execution cannot finish."""
    try:
        with Path(log).open("w", encoding="utf-8") as output:
            proc = subprocess.run(command, cwd=root, env=env, stdout=output,
                                  stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return proc.returncode, None
    except subprocess.TimeoutExpired:
        return 124, "runner timeout; child terminated; no terminal product proof"
    except OSError as exc:
        Path(log).write_text(str(exc), encoding="utf-8")
        return 127, f"runner unavailable: {exc}"


def probe_host(candidate, root, directory, index):
    identity_file = directory / f"hython-probe-{index}.json"
    log = directory / f"hython-probe-{index}.log"
    command = [candidate, str(root / "scripts/solaris_v3_accept.py"),
               "--probe", str(identity_file)]
    code, reason = run_logged(command, root, subprocess_env(root), log, 45)
    record = {"runner_command": command, "log_path": str(log), "exit_code": code,
              "artifact_hashes": {str(log): sha256(log)}}
    if not code and identity_file.is_file():
        identity = read_json(identity_file)
        record["identity"] = identity
        record["artifact_hashes"][str(identity_file)] = sha256(identity_file)
        return identity, record
    record["reason"] = reason or "hython binding/pytest unavailable; see probe log"
    return None, record


def run_tier(tier, executable, selectors, root, directory, gates, timeout):
    result_file, log = directory / f"{tier}-observations.json", directory / f"{tier}.log"
    context_file = directory / f"{tier}-context.json"
    evidence_dir = directory / tier / "evidence"
    evidence_dir.mkdir(parents=True)
    command = [executable, "-m", "pytest", *selectors, "-q", "-p", "no:cacheprovider",
               "-p", "scripts.solaris_v3_accept", "--basetemp", str(directory / tier / "tmp")]
    context = {"run_id": directory.name, "root": str(root), "tier": tier,
               "runner_command": command, "result_file": str(result_file),
               "log_path": str(log), "evidence_dir": str(evidence_dir),
               "test_source_hashes": {selector.split("::")[0]: sha256(root / selector.split("::")[0])
                                      for selector in selectors if (root / selector.split("::")[0]).is_file()}}
    write_json(context_file, context)
    env = subprocess_env(root)
    env[CONTEXT_ENV] = str(context_file)
    code, error = run_logged(command, root, env, log, timeout)
    observation = read_json(result_file) if result_file.is_file() else {}
    ran = (bool(observation.get("identity")) and not observation.get("binding_error")
           and code != 5 and any(t.get("reports") for t in observation.get("tests", {}).values()))
    result = {"tier": tier, "ran": ran, "status": "NOT_RUN", "exit_code": code,
              "reason": error or observation.get("binding_error") or "",
              "runner_command": command, "log_path": str(log),
              "observation": observation, "artifact_hashes": {str(log): sha256(log),
              str(context_file): sha256(context_file)}}
    if result_file.is_file():
        result["artifact_hashes"][str(result_file)] = sha256(result_file)
    if not ran:
        result["reason"] = result["reason"] or ("NOT_RUN: no tests collected" if code == 5
                                                 else "pytest did not establish binding and execute tests; see log")
    elif code:
        result["status"] = "FAIL"
        result["reason"] = result["reason"] or f"pytest exited {code}"
    else:
        tests = observation.get("tests", {})
        outcomes = [phase_status(t) for t in tests.values()]
        result["status"] = "FAIL" if "FAIL" in outcomes else "PASS" if "PASS" in outcomes else "NOT_RUN"
        if result["status"] == "NOT_RUN":
            result["reason"] = "no test completed without skip/xfail"
    return result


def phase_status(test):
    reports = test.get("reports", [])
    if any(r.get("outcome") == "failed" for r in reports):
        return "FAIL"
    if any(r.get("outcome") == "skipped" or r.get("wasxfail") for r in reports):
        return "NOT_RUN"
    # Repeats/retries cannot mask a failure or omitted setup/teardown.
    if len(reports) == 3 and {r.get("when") for r in reports} == {"setup", "call", "teardown"}:
        if all(r.get("outcome") == "passed" for r in reports):
            return "PASS"
    return "UNKNOWN"


def assess_row(row, specs, tier_result, run_id):
    measured = copy.deepcopy(row)
    measured.update(status="NOT_RUN", evidence=None, last_run=None, reason="tier not selected")
    if not tier_result or not tier_result["ran"]:
        if tier_result:
            measured["reason"] = tier_result["reason"]
        return measured
    if not specs:
        measured["reason"] = "no reviewed exact test binding; suite results do not promote product gates"
        return measured
    observation = tier_result["observation"]
    tests, receipts, statuses = observation.get("tests", {}), [], []
    for spec in specs:
        test = tests.get(spec["nodeid"])
        if test is None:
            statuses.append("NOT_RUN")
            continue
        status = phase_status(test)
        if status == "PASS":
            matches = [e for e in test.get("evidence", []) if e.get("row_id") == row["id"]
                       and e.get("intended_path") == spec["intended_path"]]
            if len(matches) != 1 or not matches[0].get("artifact_hashes"):
                status = "UNKNOWN"
            else:
                evidence = matches[0]
                try:
                    if any(sha256(p) != digest for p, digest in evidence["artifact_hashes"].items()):
                        status = "UNKNOWN"
                    else:
                        receipts.append(evidence)
                except OSError:
                    status = "UNKNOWN"
        statuses.append(status)
    # A failing exercised check must not disappear behind another missing check.
    status = ("FAIL" if "FAIL" in statuses else "NOT_RUN" if "NOT_RUN" in statuses
              else "UNKNOWN" if "UNKNOWN" in statuses else "PASS")
    if tier_result["exit_code"] not in (0, 1) and status == "PASS":
        status = "UNKNOWN"
    measured.update(status=status, last_run=now(),
                    reason="all bound controls and fresh path receipts passed" if status == "PASS"
                    else "bound control failed, was missing/skipped, or lacked fresh intended-path evidence")
    if status in {"PASS", "FAIL"}:
        identity = observation["identity"]
        hashes = dict(tier_result["artifact_hashes"])
        for receipt in receipts:
            hashes.update(receipt["artifact_hashes"])
        measured["evidence"] = {"receipt_id": f"{run_id}:{row['id']}", "commit": identity["commit"],
                                "build": identity["build"], "module_path": identity["module_path"],
                                "runner_command": tier_result["runner_command"],
                                "log_path": tier_result["log_path"], "artifact_hashes": hashes,
                                "checks": receipts, "test_nodeids": [s["nodeid"] for s in specs]}
    return measured


def update_gates(gates, rows, tiers):
    """Unrun tiers retain history in GATES; this run's ledger never inherits it."""
    updated = copy.deepcopy(gates)
    actual = {r["tier"] for r in tiers if r["ran"]}
    current = {r["id"]: r for r in rows}
    for i, previous in enumerate(updated["rows"]):
        if previous["tier"] in actual:
            updated["rows"][i] = current[previous["id"]]
    return updated


def exit_code(tiers, rows):
    if any(r["status"] == "FAIL" for r in rows) or any(t["status"] == "FAIL" for t in tiers):
        return 1
    if any(t.get("exit_code") not in (None, 0, 5) for t in tiers):
        return 2
    return 0


def validate_ledger(ledger):
    if ledger.get("schema_version") != 1 or not ledger.get("run_id") or not ledger.get("runner_command"):
        raise ValueError("invalid ledger header")
    if {r.get("id") for r in ledger.get("rows", [])} != ROW_IDS or len(ledger["rows"]) != len(ROW_IDS):
        raise ValueError("invalid ledger rows")
    tiers = {t["tier"]: t for t in ledger["tiers"]}
    for row in ledger["rows"]:
        if row["status"] not in STATUSES or row["tier"] not in TIERS or not row.get("reason"):
            raise ValueError("invalid ledger status/reason")
        if row["status"] in {"PASS", "FAIL"}:
            tier = tiers[row["tier"]]
            if not tier["ran"] or not tier["observation"].get("identity"):
                raise ValueError("unbound or unrun tier cannot promote")
            validate_evidence(row["evidence"], row["tier"])
            validate_timestamp(row["last_run"])
        elif row["evidence"] is not None:
            raise ValueError("unmeasured gate cannot carry a promotion receipt")
    if ledger["exit_code"] != exit_code(ledger["tiers"], ledger["rows"]):
        raise ValueError("inconsistent exit code")
    return ledger


def execute(root, selected, timeout):
    root = Path(root).resolve()
    if root != Path(git(root, "rev-parse", "--show-toplevel")).resolve():
        raise BindingError("launch from the checkout root")
    if root != ROOT:
        raise BindingError(f"runner belongs to {ROOT}; launched from {root}")
    directory = root / RUNS_PATH / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid4().hex[:8])
    directory.mkdir(parents=True)
    # Prevent concurrent acceptance writers without assuming other swarm streams
    # are conductors of this board. O_EXCL also fails closed on a stale lock.
    lock = root / RUNS_PATH / ".acceptance.lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "run_id": directory.name}, sort_keys=True))
    try:
        gates = validate_gates(read_json(root / GATES_PATH))
        gate_definition_hash = sha256(root / GATES_PATH)
        files, missing = discover(root)
        tiers, probes = [], []
        bindings = gates["promotion_rule"]["bindings"]
        for tier in TIERS:
            item = {"tier": tier, "ran": False, "status": "NOT_RUN", "exit_code": None,
                    "reason": "tier not selected", "runner_command": [], "log_path": None,
                    "observation": {}, "artifact_hashes": {}}
            if tier == "gui":
                item["reason"] = "artist walk, undo and panel freshness are human GUI steps; this command never runs them"
            elif tier in selected:
                selectors = files if tier == "pure" else sorted({s["nodeid"] for row in gates["rows"]
                    if row["tier"] == "hython" for s in bindings.get(row["id"], [])})
                executable = sys.executable
                if tier == "hython":
                    executable = None
                    for index, candidate in enumerate(hython_candidates(root)):
                        identity, probe = probe_host(candidate, root, directory, index)
                        probes.append(probe)
                        if identity:
                            executable = candidate
                            break
                if not executable:
                    item["reason"] = "NOT_RUN: no bound hython with pytest on 22.0.400; see host probes"
                elif not selectors:
                    item["reason"] = "NOT_RUN: no reviewed hython test bindings" if tier == "hython" else "NOT_RUN: no tests collected"
                else:
                    item = run_tier(tier, executable, selectors, root, directory, gates, timeout)
            tiers.append(item)
        rows = [assess_row(row, bindings.get(row["id"], []), next(t for t in tiers if t["tier"] == row["tier"]), directory.name)
                for row in gates["rows"]]
        ledger = {"schema_version": 1, "run_id": directory.name, "created_at": now(),
                  "checkout": str(root), "runner_command": [sys.executable, *sys.argv],
                  "requested_tiers": list(selected), "tiers": tiers, "rows": rows,
                  "host_probes": probes, "missing_globs": missing,
                  "gate_definition_hash": gate_definition_hash,
                  "runner_hash": sha256(root / "scripts/solaris_v3_accept.py"),
                  "exit_code": exit_code(tiers, rows),
                  "could_not_verify": [r["id"] + ": " + r["reason"] for r in rows if r["status"] in {"NOT_RUN", "UNKNOWN"}]}
        validate_ledger(ledger)
        write_json(directory / "ledger.json", ledger)
        # Wrong-checkout refusal cannot overwrite any product status.
        if sha256(root / GATES_PATH) != gate_definition_hash:
            raise BindingError("gate definitions changed during this run; ledger retained, update refused")
        if not any(t["observation"].get("binding_error") for t in tiers):
            updated = update_gates(gates, rows, tiers)
            validate_gates(updated)
            if updated != gates:
                write_json(root / GATES_PATH, updated)
        print("ID    TIER     STATUS")
        for row in rows:
            print(f"{row['id']:<5} {row['tier']:<8} {row['status']}")
        for tier in tiers:
            print(f"{tier['tier']}: {tier['status']} {tier['reason']}")
        for reason in missing:
            print(reason)
        print(f"Ledger: {directory / 'ledger.json'}")
        print("Exit 0 means no executed check failed; it does not mean ship-ready.")
        return ledger["exit_code"]
    finally:
        lock.unlink()


class AcceptancePlugin:
    """Evidence captured in the actual pytest interpreter, after pythonpath setup."""
    def __init__(self, context):
        self.context = context
        self.output = {"identity": None, "binding_error": None, "tests": {}, "test_source_hashes": {}}

    def pytest_sessionstart(self, session):
        import pytest
        try:
            if Path(__file__).resolve() != Path(self.context["root"]).resolve() / "scripts/solaris_v3_accept.py":
                raise BindingError("wrong checkout: loaded acceptance plugin is outside the launch checkout")
            self.output["identity"] = loaded_identity(self.context["root"], self.context["tier"])
        except Exception as exc:
            self.output["binding_error"] = f"binding refused: {type(exc).__name__}: {exc}"
            write_json(self.context["result_file"], self.output)
            pytest.exit(self.output["binding_error"], returncode=4)

    def pytest_collection_modifyitems(self, session, config, items):
        import pytest
        try:
            for item in items:
                source, digest = bind_test_source(
                    self.context["root"], item.path, getattr(item.module, "__file__", None),
                    self.context.get("test_source_hashes", {}))
                self.output["test_source_hashes"][source] = digest
        except Exception as exc:
            self.output["binding_error"] = f"binding refused: {type(exc).__name__}: {exc}"
            write_json(self.context["result_file"], self.output)
            pytest.exit(self.output["binding_error"], returncode=4)

    def pytest_runtest_logreport(self, report):
        test = self.output["tests"].setdefault(report.nodeid, {"reports": [], "evidence": []})
        test["reports"].append({"when": report.when, "outcome": report.outcome,
                                "wasxfail": hasattr(report, "wasxfail"),
                                "reason": str(report.longrepr) if report.longrepr else ""})

    def emit(self, nodeid, row_id, intended_path, artifacts):
        if row_id not in ROW_IDS or not intended_path or not artifacts:
            raise ValueError("receipt requires row, intended path and fresh artifacts")
        hashes = {}
        for path in artifacts:
            path = Path(path).resolve()
            if not inside(path, self.context["evidence_dir"]) or not path.is_file():
                raise ValueError("artifact must be produced inside this run's evidence directory")
            hashes[str(path)] = sha256(path)
        receipt = {"row_id": row_id, "receipt_id": f"{self.context['run_id']}:{uuid4().hex}",
                   "intended_path": intended_path, "artifact_hashes": hashes,
                   "created_at": now(), "nodeid": nodeid}
        self.output["tests"].setdefault(nodeid, {"reports": [], "evidence": []})["evidence"].append(receipt)
        return receipt

    def pytest_sessionfinish(self, session, exitstatus):
        try:
            final = loaded_identity(self.context["root"], self.context["tier"])
            initial = self.output["identity"]
            if initial != final:
                raise BindingError("checkout/commit/build changed while tests ran")
            for path, digest in self.context.get("test_source_hashes", {}).items():
                if sha256(Path(self.context["root"]) / path) != digest:
                    raise BindingError(f"test source changed while tests ran: {path}")
            for path, digest in self.output["test_source_hashes"].items():
                if sha256(path) != digest:
                    raise BindingError(f"loaded test source changed while tests ran: {path}")
            loaded = {}
            for name, module in list(sys.modules.items()):
                if name == "synapse" or name.startswith("synapse."):
                    path = getattr(module, "__file__", None)
                    if path:
                        if not inside(path, Path(self.context["root"]) / "python" / "synapse"):
                            raise BindingError(f"mixed checkout module: {name} at {path}")
                        loaded[str(Path(path).resolve())] = sha256(path)
            self.output["loaded_module_hashes"] = loaded
        except Exception as exc:
            self.output["binding_error"] = f"binding refused: {type(exc).__name__}: {exc}"
            session.exitstatus = 4
        self.output["exit_code"] = int(session.exitstatus)
        write_json(self.context["result_file"], self.output)


def pytest_configure(config):
    context_path = os.environ.get(CONTEXT_ENV)
    if context_path:
        import pytest
        plugin = AcceptancePlugin(read_json(context_path))
        config.pluginmanager.register(plugin, "solaris-acceptance-recorder")

        class Fixtures:
            @pytest.fixture
            def solaris_acceptance_evidence(self, request):
                def emit(row_id, intended_path, artifacts):
                    return plugin.emit(request.node.nodeid, row_id, intended_path, artifacts)
                emit.directory = Path(plugin.context["evidence_dir"])
                return emit
        config.pluginmanager.register(Fixtures(), "solaris-acceptance-fixtures")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", action="append", choices=(*TIERS, "all"), help="repeatable; default pure")
    parser.add_argument("--timeout", type=float, default=600, help="finite per-tier wall-clock bound in seconds")
    parser.add_argument("--probe", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.probe:
            import pytest  # Availability check, without importing test conftest.
            if not inside(args.probe, ROOT / RUNS_PATH):
                raise BindingError("probe output must stay inside checkout runs")
            write_json(args.probe, loaded_identity(ROOT, "hython"))
            return 0
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        selected = args.tier or ["pure"]
        return execute(Path.cwd(), TIERS if "all" in selected else selected, args.timeout)
    except (OSError, ValueError, ImportError, subprocess.SubprocessError) as exc:
        print(f"ACCEPTANCE REFUSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
