#!/usr/bin/env python
"""rope graph -- a capped, clocked work graph over the repo's own import graph.

runner.py walks one list, one session at a time, in the tree Houdini serves.
This walks a graph in a worktree of its own: one read-only scout per area of
the code, a route over what the scouts found, one fixer per kept candidate,
a referee over what was kept, and the same binary gate rope already trusts.

    python harness/rope/graph.py map
    python harness/rope/graph.py init   --run DIR --slots DIR [--cap 50] [--minutes 60]
    python harness/rope/graph.py tick   --run DIR [--kinds scout,fix,review] [--loop 15]
    python harness/rope/graph.py route  --run DIR      scout results -> jev_sweep -> fix_items.json
    python harness/rope/graph.py add    --run DIR fix_items.json
    python harness/rope/graph.py review --run DIR      one referee item per batch of kept commits
    python harness/rope/graph.py status --run DIR

It owns the order, the cap, the clock, the fences and the verdict. It does not
own the model: an executor is whatever rope's claude_cmd() returns, so the
engine and the model swap in one place, exactly as they do for rope.

Laws kept from program.md: L2 it frays visibly, L6 it never climbs for you.
Three of its own:
  1. The cap is counted here and nowhere else. A session is counted before it starts.
  2. A fix may only declare files outside the fences and outside the exam.
  3. The loop never edits its own exam. Existing tests, fixtures, the catalog and
     this harness are read-only to every worker; keep or discard is decided by
     checks, never by a model.
"""
from __future__ import annotations

import argparse
import ast
import glob
import importlib.util
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time

ROPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(ROPE))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# check / verdict / revert / claude_cmd are rope's, imported, never copied.
rope = _load("_rope_runner_for_graph", os.path.join(ROPE, "runner.py"))


def _sh(args, timeout=None, stdin=None, stdout=None):
    """rope.sh with decoding that cannot raise on a stray byte in test output."""
    return subprocess.run(args, cwd=rope.ROOT, timeout=timeout, stdin=stdin,
                          stdout=stdout or subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=(stdout is None), encoding="utf-8", errors="replace")


rope.sh = _sh

FENCES = ("python/synapse/server/handlers_tops/", "python/synapse/_vendor/")
EXAM = ("harness/", "tests/fixtures/", "rag/catalog/", ".github/")
# Not the exam and not quarantined, but not a worker's to change: release files, what Houdini
# loads at startup, and the sessions' own agent configuration.
OWNER_ONLY = (".claude/", "packages/", "installer/", "VERSION", "pyproject.toml", "install.py")
RATCHETS = ("tests/test_harden_catalog_conformance.py",
            "tests/test_b4_recipe_strings_conformance.py",
            "tests/test_d_track.py",
            "tests/test_except_ratchet.py")
# Areas outside python/synapse. Globs are relative to the repo root.
OUTER = {
    "mcp_stdio": ["mcp_server.py", "mcp_tools_*.py"],
    "shared": ["shared/**/*.py"],
    "agent": ["agent/**/*.py"],
    "host_pkg": ["host/**/*.py"],
    "scripts": ["scripts/*.py"],
    "docs_help": ["docs/help/*.html", "docs/help/*.md"],
}
TIER = {"scout": "mechanical", "fix": "reasoning", "review": "referee"}
TIMEOUT = {"scout": 780, "fix": 960, "review": 780}
TURNS = {"scout": 45, "fix": 50, "review": 30}
READ_ONLY_DENY = "Edit,Write,NotebookEdit,Bash,WebFetch,WebSearch"
FIX_ALLOW = "Read,Grep,Glob,Edit,Write,Bash(python -m pytest:*)"
FIX_DENY = "NotebookEdit,WebFetch,WebSearch"
QUOTA = ("session limit", "usage limit", "rate limit")
OPEN = ("pending", "running")
NOT_HOUDINI = '-m "not needs_houdini"'
STALE_INDEX = "semantic index stale: run scripts/refresh_knowledge.py"


def posix(p):
    p = p.replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def git(*a, cwd=None, timeout=180):
    return subprocess.run(["git", *a], cwd=cwd or ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


# --------------------------------------------------------------- the code graph

def _lines(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _area_files():
    files = {}
    pkg = os.path.join(ROOT, "python", "synapse")
    for d, dirs, names in os.walk(pkg):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for n in sorted(names):
            if not n.endswith(".py"):
                continue
            rel = posix(os.path.relpath(os.path.join(d, n), ROOT))
            if rel.startswith(FENCES):
                continue
            parts = rel.split("/")
            files.setdefault(parts[2] if len(parts) > 3 else "_top", []).append(rel)
    for area, pats in OUTER.items():
        got = set()
        for pat in pats:
            for p in glob.glob(os.path.join(ROOT, pat), recursive=True):
                rel = posix(os.path.relpath(p, ROOT))
                if "__pycache__" not in rel and os.path.isfile(p):
                    got.add(rel)
        if got:
            files[area] = sorted(got)
    return files


def _imports(rel, tree, areas, outer_root):
    """The areas this file imports."""
    out = set()
    parts = rel.split("/")
    pkg = parts[1:-1] if parts[0] == "python" else []
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: max(0, len(pkg) - (node.level - 1))]
                if node.module:
                    mods = [".".join(base + node.module.split("."))]
                else:
                    mods = [".".join(base + [a.name]) for a in node.names]
            elif node.module == "synapse":
                mods = ["synapse." + a.name for a in node.names]
            elif node.module:
                mods = [node.module]
        for m in mods:
            p = m.split(".")
            if p[0] == "synapse":
                a = p[1] if len(p) > 1 and p[1] in areas else "_top"
            else:
                a = outer_root.get(p[0])
            if a and a in areas:
                out.add(a)
    return out


def code_graph():
    """Areas, who imports whom, and how far a change in each one reaches."""
    files = _area_files()
    outer_root = {}
    for area in OUTER:
        for rel in files.get(area, []):
            if rel.endswith(".py"):
                outer_root[rel.split("/")[0].replace(".py", "")] = area
    areas = {a: {"files": [[f, _lines(f)] for f in fs], "imports": set()} for a, fs in files.items()}
    for a, fs in files.items():
        for rel in fs:
            if not rel.endswith(".py"):
                continue
            try:
                with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as f:
                    tree = ast.parse(f.read())
            except (SyntaxError, ValueError, OSError):
                continue
            areas[a]["imports"] |= _imports(rel, tree, areas, outer_root) - {a}
    for a in areas:
        areas[a]["imported_by"] = sorted(b for b in areas if a in areas[b]["imports"])
    for a in areas:
        seen, todo = set(), list(areas[a]["imported_by"])
        while todo:
            b = todo.pop()
            if b not in seen and b != a:
                seen.add(b)
                todo += areas[b]["imported_by"]
        areas[a]["blast"] = len(seen)                     # transitive: who could feel a change
        areas[a]["direct"] = len(areas[a]["imported_by"])  # direct: who imports it by name
        areas[a]["imports"] = sorted(areas[a]["imports"])
        areas[a]["lines"] = sum(n for _, n in areas[a]["files"])
    return areas


def plan_scouts(areas, n):
    """Pack the areas into n scout items, smallest reach first, by line count."""
    order = sorted(areas, key=lambda a: (areas[a]["direct"], areas[a]["blast"], a))
    total = sum(areas[a]["lines"] for a in order)
    target = max(1, total // max(1, n))
    bins, cur, size = [], [], 0
    for a in order:
        for f, ln in areas[a]["files"]:
            if cur and size + ln > target * 1.15 and len(bins) < n - 1:
                bins.append(cur)
                cur, size = [], 0
            cur.append((a, f, ln))
            size += ln
    if cur:
        bins.append(cur)
    items = []
    for i, b in enumerate(bins, 1):
        ars = sorted({a for a, _, _ in b}, key=order.index)
        items.append({"id": "S%02d" % i, "kind": "scout", "title": "scout " + ", ".join(ars),
                      "areas": ars, "files": [f for _, f, _ in b],
                      "lines": sum(ln for _, _, ln in b), "deps": [],
                      "status": "pending", "attempts": 0})
    return items


# --------------------------------------------------------------------- state

def state_path(run):
    return os.path.join(run, "GRAPH.json")


def load(run):
    with open(state_path(run), encoding="utf-8") as f:
        return json.load(f)


def save(st):
    tmp = state_path(st["run"]) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, state_path(st["run"]))


def ledger(st, tid, model, verdict, attempts, dur, tokens, note):
    """rope's results.tsv columns, with the token count rope could not see."""
    p = os.path.join(st["run"], "results.tsv")
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("ts\ttask\tmodel\tverdict\tattempts\tdur_s\ttokens\tnote\n")
        f.write("%s\t%s\t%s\t%s\t%d\t%.0f\t%s\t%s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), tid, model, verdict, attempts, dur, tokens,
            str(note).replace("\t", " ").replace("\n", " ")[:300]))


def by_id(st, iid):
    for it in st["items"]:
        if it["id"] == iid:
            return it
    raise KeyError(iid)


def rails_model(tier):
    try:
        with open(os.path.join(ROOT, "harness", "rails_exec.json"), encoding="utf-8") as f:
            table = json.load(f)
        return table.get("tiers", table)[tier]["model"]
    except (OSError, KeyError, ValueError):
        return ""


def model_for(st, it):
    """A tier name in, a model string out. The table is rails_exec.json; a run may override a tier."""
    tier = it.get("tier") or TIER[it["kind"]]
    return st.get("models", {}).get(tier) or rails_model(tier) or rails_model("reasoning")


def minutes_left(st):
    if not st.get("started"):
        return float(st["minutes"])
    return st["minutes"] - (time.time() - st["started"]) / 60.0


def refuse_session(st):
    """Why no new session may start, or '' when one may."""
    if st.get("stop"):
        return st["stop"]
    if st["sessions"] >= st["cap"]:
        return "cap reached: %d of %d sessions" % (st["sessions"], st["cap"])
    if minutes_left(st) <= 0:
        return "clock ran out: %d minutes" % st["minutes"]
    return ""


def refuse_item(st, it):
    """Why a fix item may not enter the graph, or ''. Code decides this, never a model."""
    if it.get("kind") != "fix":
        return ""
    files = [posix(f) for f in it.get("files", [])]
    if not files:
        return "declares no files"
    owned = {posix(f): o["id"] for o in st["items"]
             if o.get("kind") == "fix" and o["status"] in OPEN and o["id"] != it.get("id")
             for f in o.get("files", [])}
    for f in files:
        if f.startswith("/") or ".." in f.split("/") or re.match(r"^[A-Za-z]:", f):
            return "path leaves the tree: " + f
        if f.startswith(FENCES):
            return "fenced: " + f
        if f.startswith(EXAM):
            return "the exam is read-only: " + f
        if f.startswith(OWNER_ONLY):
            return "owner-only: " + f
        if f.startswith("tests/") and git("ls-files", "--error-unmatch", "--", f).returncode == 0:
            return "an existing test is the exam: " + f
        if f in owned:
            return "file already owned by %s: %s" % (owned[f], f)
    return ""


def held(st):
    """Why no fixer may start, from the last preflight, or ''. Reads the state; runs nothing."""
    pf = st.get("preflight") or {}
    if pf.get("ok", True):
        return ""
    return "fixes held, ratchets red on the base tree: " + "; ".join(pf.get("failing") or ["?"])


def preflight(st):
    """Run the ratchets against the base tree once, before any fixer, and record the verdict.

    Every fix's acceptance runs the ratchets in the root. A ratchet that is red before any
    fixer starts (a stale local master ref turned tests/test_d_track.py red) discards every
    fix, and nothing said why. A red that names no test is still red: a crash, a timeout or
    a collection error must never read as green. Code decides; no model is asked.
    """
    ratchets = [t for t in RATCHETS if os.path.exists(os.path.join(ROOT, t))]
    failing = []
    if ratchets:
        env_before = os.environ.get("PYTEST_ADDOPTS")
        os.environ["PYTEST_ADDOPTS"] = NOT_HOUDINI      # the same tests the gate will run
        try:
            r = rope.sh([sys.executable, "-m", "pytest", *ratchets, "-q", "-p", "no:cacheprovider",
                         "-rfE", "--tb=no"], timeout=1800)
            out = r.stdout or ""
            failing = re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M)
            if r.returncode != 0 and not failing:     # the gate keeps only rc 0; 5 (none ran) is red
                failing = ["pytest exit %s: %s" % (r.returncode, _norm(out[-200:]))]
        except subprocess.TimeoutExpired:
            failing = ["the ratchets timed out on the base tree"]
        except OSError as e:
            failing = ["the ratchets could not run: %s" % e]
        finally:
            if env_before is None:
                os.environ.pop("PYTEST_ADDOPTS", None)
            else:
                os.environ["PYTEST_ADDOPTS"] = env_before
    st["preflight"] = {"ok": not failing, "failing": failing, "ratchets": ratchets,
                       "head": git("rev-parse", "HEAD").stdout.strip()}
    if failing:
        ledger(st, "PREFLIGHT", "-", "ratchets-red", 0, 0, "-", "; ".join(failing))
    return held(st)


def add_items(st, items):
    """Returns [(id, reason)] for the ones refused. Refusals are loud, never silent."""
    refused, ids = [], {i["id"] for i in st["items"]}
    for it in items:
        why = "duplicate id" if it["id"] in ids else refuse_item(st, it)
        if why:
            refused.append((it["id"], why))
            ledger(st, it["id"], "-", "refused", 0, 0, "-", why)
            continue
        it.setdefault("deps", [])
        it.setdefault("status", "pending")
        it.setdefault("attempts", 0)
        it["files"] = [posix(f) for f in it.get("files", [])]
        st["items"].append(it)
        ids.add(it["id"])
    return refused


# ------------------------------------------------------------------ executors

def worker_cmd(st, it):
    cmd = rope.claude_cmd(model_for(st, it))
    if os.environ.get("SYNAPSE_ROPE_ENGINE", "claude") != "claude":
        return cmd
    k = it["kind"]
    cmd += ["--settings", "harness/rope/graph-worker.json", "--output-format", "json",
            "--max-turns", str(TURNS[k])]
    if k == "fix":
        cmd += ["--allowedTools", FIX_ALLOW, "--disallowedTools", FIX_DENY]
    else:
        cmd += ["--disallowedTools", READ_ONLY_DENY]
    return cmd


def _program():
    try:
        with open(os.path.join(ROPE, "program.md"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def build_prompt(st, it):
    k = it["kind"]
    if k == "scout":
        blast = max([st["areas"][a].get("direct", 0) for a in it["areas"]] or [0])
        listing = "\n".join("  " + f for f in it["files"])
        return SCOUT % {"id": it["id"], "areas": ", ".join(it["areas"]), "blast": blast,
                        "n": len(it["files"]), "lines": it.get("lines", 0), "files": listing,
                        "turns": TURNS["scout"], "git": GIT_RULES,
                        "brief": ("YOUR BRIEF (it narrows the search; the reply format does not change):\n%s\n"
                                  % it["brief"]) if it.get("brief") else ""}
    if k == "fix":
        card = {x: it[x] for x in ("id", "title", "files", "change", "accept") if x in it}
        return _program() + FIX % {"card": json.dumps(card, indent=1), "id": it["id"], "git": GIT_RULES}
    blocks = []
    for sha, fid in it["commits"]:
        f = by_id(st, fid)
        show = git("show", "--stat", "--patch", "--format=%h %s", sha).stdout
        blocks.append("--- %s : %s\nCARD: %s\n%s" % (fid, f["title"], f.get("change", ""), show[:14000]))
    return REVIEW % {"id": it["id"], "git": GIT_RULES, "blocks": "\n\n".join(blocks)}


def _exec(run, iid):
    """Child process: run ONE session, write <id>.exit when it ends. Never writes the state."""
    st = load(run)
    it = by_id(st, iid)
    base = os.path.join(run, iid)
    env = dict(os.environ)
    for k in ("USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH"):
        real = env.pop("ROPE_GRAPH_REAL_" + k, None)
        if real:
            env[k] = real          # the model CLI signs in with the real profile;
        elif real == "":           # any Python it starts is sent back to scratch by the guard
            env.pop(k, None)
    t0, rc, note = time.time(), None, ""
    kw = {"creationflags": 0x08000000} if os.name == "nt" else {"start_new_session": True}
    try:
        with open(base + ".prompt.txt", encoding="utf-8") as fin, \
                open(base + ".out", "w", encoding="utf-8") as fo, \
                open(base + ".err", "w", encoding="utf-8") as fe:
            p = subprocess.Popen(worker_cmd(st, it), cwd=it.get("slot") or st["root"],
                                 stdin=fin, stdout=fo, stderr=fe, env=env, **kw)
            try:
                rc = p.wait(timeout=TIMEOUT[it["kind"]])
            except subprocess.TimeoutExpired:
                note = "timeout"
                if os.name == "nt":
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                else:
                    import signal
                    os.killpg(p.pid, signal.SIGKILL)
                p.wait(timeout=30)
    except OSError as e:
        rc, note = -1, "spawn failed: %s" % e
    with open(base + ".exit.tmp", "w", encoding="utf-8") as f:
        json.dump({"rc": rc, "dur": time.time() - t0, "note": note}, f)
    os.replace(base + ".exit.tmp", base + ".exit")


def spawn(st, it):
    kw = ({"creationflags": 0x08000000 | 0x00000200} if os.name == "nt"
          else {"start_new_session": True})
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "_exec", "--run", st["run"],
                      "--id", it["id"]], cwd=st["root"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)


def read_out(st, iid):
    """(reply text, usage dict, is_error) from a finished session's output."""
    base = os.path.join(st["run"], iid)
    try:
        with open(base + ".out", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError:
        return "", {}, True
    try:
        j = json.loads(raw)
    except ValueError:
        return raw, {}, False
    if not isinstance(j, dict):
        return raw, {}, False
    return str(j.get("result") or ""), j, bool(j.get("is_error"))


def tokens_of(j):
    u = j.get("usage") or {}
    n = sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                         "cache_creation_input_tokens", "cache_read_input_tokens"))
    return str(n) if n else "unavailable"


def json_in(text):
    """The last JSON object in a worker's reply, or None."""
    for m in reversed(list(re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S))):
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    i, j = text.find("{"), text.rfind("}")
    while 0 <= i < j:
        try:
            return json.loads(text[i:j + 1])
        except ValueError:
            i = text.find("{", i + 1)
    return None


# ------------------------------------------------------------------- the gate

def stales_index(rel):
    """True when a committed path feeds the embedding digest, so a kept edit leaves
    rag/semantic_index/manifest.json stale. Mirrors the inputs of
    harness/verify/checks.py::check_semantic_index_fresh exactly: the top-level *.md of
    rag/skills/houdini21-reference/ (a glob, not a walk) and the topic metadata file.
    Nothing else under rag/skills is read by that digest, so nothing else is flagged."""
    rel = posix(rel)
    head, _, name = rel.rpartition("/")
    return ((head == "rag/skills/houdini21-reference" and name.endswith(".md"))
            or rel == "rag/documentation/_metadata/semantic_index.json")



NEW = ("??", "!!")      # untracked, or untracked AND gitignored: no HEAD side either way


def _changed(tree, declared=()):
    """What a worker changed. A NEW file under a gitignored path ('/.synapse/') is invisible
    to plain `git status`, so the gate kept the rest of the card and shipped half a split
    while local tests stayed green (post-demo loop 1). Declared paths are asked about with
    --ignored and come back as '!!'; undeclared ignored files (caches) stay out of view."""
    out = []
    for ln in git("status", "--porcelain", "-uall", cwd=tree).stdout.splitlines():
        code, rel = ln[:2], ln[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        out.append((code, posix(rel.strip('"'))))
    if declared:
        seen = {rel for _, rel in out}
        r = git("status", "--porcelain", "-uall", "--ignored", "--", *declared, cwd=tree)
        for ln in r.stdout.splitlines():
            rel = posix(ln[3:].strip().strip('"'))
            if ln[:2] == "!!" and rel not in seen:
                out.append(("!!", rel))
    return out


def _free_slot(st, slot_path, changed):
    """Hand a slot back clean, or retire it out loud. Scoped: only what the worker changed."""
    slot = next(s for s in st["slots"] if s["path"] == slot_path)
    slot["busy"] = ""
    for code, rel in changed:
        p = os.path.join(slot_path, rel)
        if code.strip() in NEW:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        else:
            git("checkout", "HEAD", "--", rel, cwd=slot_path)
    if git("status", "--porcelain", cwd=slot_path).stdout.strip():
        slot["retired"] = "left dirty after scoped restore"


LOG_CALL = re.compile(r"\b(?:_?log(?:ger)?|logging|LOG)\.(?:debug|info|warning|warn|error|exception|critical)\(")
_FIRST_LITERAL = re.compile(r"(['\"])(.+?)\1")


def _dropped_logging(slot, changed, card_text):
    """Logger calls a fix removed and neither moved nor named in its card. Code decides, never a model.

    A removed line is flagged when it is a logger call and
      (i)  no added line in any declared file equals it after whitespace is normalised
           (a move or a re-indent is allowed; a new file's lines all count as added), and
      (ii) the first string literal inside the call does not appear verbatim in the card
           (a card that quotes the line asked for its removal).
    There is no waiver for the word "log" in the card: "Keep the existing logging" (K03)
    must not excuse a dropped line. `print(` is out of scope on purpose.
    Known gap: a call that spans several lines, with its literal on a continuation line,
    is not matched, because the diff is read one line at a time.
    """
    removed, added = [], set()
    for code, rel in changed:
        if code.strip() in NEW:                       # new file: no HEAD side to lose,
            try:                                      # but every line in it is an added line
                with open(os.path.join(slot, rel), encoding="utf-8", errors="replace") as f:
                    added.update(_norm(x) for x in f.read().splitlines())
            except OSError:
                pass
            continue
        out = git("diff", "HEAD", "--unified=0", "--", rel, cwd=slot).stdout
        for ln in out.splitlines():
            if ln.startswith("---") or ln.startswith("+++"):
                continue
            if ln.startswith("-"):
                removed.append((rel, ln[1:]))
            elif ln.startswith("+"):
                added.add(_norm(ln[1:]))
    lost = []
    for rel, ln in removed:
        m = LOG_CALL.search(ln)
        if not m:
            continue
        if _norm(ln) in added:
            continue
        lit = _FIRST_LITERAL.search(ln, m.end())
        if lit and lit.group(2) in card_text:
            continue
        lost.append("%s: %s" % (rel, ln.strip()[:100]))
    return lost


def _force_tracked_dir(tree, rel):
    """True when rel's own directory (not the root, not a parent) holds a tracked file that is
    also gitignored: the only precedent under which the gate may `git add -f` a new ignored file."""
    d = posixpath.dirname(rel)
    if not d:
        return False
    r = git("ls-files", "-z", "-ci", "--exclude-standard", "--", d, cwd=tree)
    return any(posixpath.dirname(posix(e)) == d for e in r.stdout.split("\0") if e)


def gate(st, it):
    """Judge one finished fix. Returns (verdict, note). Checks decide; no model is asked."""
    slot, root = it["slot"], st["root"]
    changed = _changed(slot, it["files"])
    declared = set(it["files"])
    paths = [rel for _, rel in changed]
    try:
        if not paths:
            return "no_change", "worker changed nothing"
        strays = [p for p in paths if p not in declared]
        if strays:
            return "stray", "edited outside its card: " + ", ".join(strays[:4])
        gone = [rel for code, rel in changed if "D" in code]
        if gone:
            return "deletion", "a fix may not delete a file: " + ", ".join(gone)
        for p in paths:
            if p.endswith(".py"):
                try:
                    with open(os.path.join(slot, p), encoding="utf-8") as f:
                        ast.parse(f.read())
                except (SyntaxError, ValueError, OSError) as e:
                    return "syntax", "%s does not parse: %s" % (p, e)
        lost = _dropped_logging(slot, changed, "%s %s" % (it.get("change", ""), it.get("title", "")))
        if lost:
            return "dropped_log", "a fix removed logging its card never mentioned: " + "; ".join(lost[:3])
        # `add -f` below may only follow a precedent: a new ignored file joins a directory that
        # ALREADY holds a force-tracked file, i.e. a tracked file in that same directory which is
        # itself ignored (.synapse/contracts/). A tracked sibling that is not ignored is no
        # precedent (pkg/a.py does not license pkg/secret.key), and an ignored file at the repo
        # root (.env) is refused outright. Anything else is the owner's call, not a fix's: origin
        # is public and auto-pushed.
        no_precedent = [rel for code, rel in changed if code == "!!" and not _force_tracked_dir(slot, rel)]
        if no_precedent:
            return "ignored", "new gitignored file with no force-tracked sibling in its directory: " \
                + ", ".join(no_precedent[:4])
        existed ={p: os.path.exists(os.path.join(root, p)) for p in paths}
        for p in paths:
            os.makedirs(os.path.dirname(os.path.join(root, p)) or root, exist_ok=True)
            shutil.copyfile(os.path.join(slot, p), os.path.join(root, p))
        task = {"files": paths, "accept": it.get("accept", [])}
        env_before = os.environ.get("PYTEST_ADDOPTS")
        os.environ["PYTEST_ADDOPTS"] = NOT_HOUDINI
        try:
            ok, manual, fails = rope.verdict(task)
        finally:
            if env_before is None:
                os.environ.pop("PYTEST_ADDOPTS", None)
            else:
                os.environ["PYTEST_ADDOPTS"] = env_before
        if not ok:
            rope.revert(task, existed)
            return "fail", "; ".join(fails)[:240]
        # Never `add -A`: only the named paths, every one of them declared (strays were refused
        # above). `-f` because a declared file under a gitignored path is force-tracked the way
        # .synapse/contracts/ is: a plain add refuses a new one (exit 1, which nobody checked)
        # and exits 1 even while it stages an edit to a tracked one. So the exit is checked now.
        a = git("add", "-f", "--", *paths)
        if a.returncode != 0:
            git("reset", "-q", "--", *paths)
            rope.revert(task, existed)
            return "fail", "git add refused: " + (a.stdout + a.stderr).strip()[:160]
        msg = "rope:%s %s [%s]" % (it["id"], it["title"][:72], it.get("law", "sweep"))
        if st.get("trailer"):
            msg += "\n\n" + st["trailer"]
        c = git("commit", "-q", "-m", msg, "--", *paths)
        if c.returncode != 0:
            git("reset", "-q", "--", *paths)
            rope.revert(task, existed)
            return "fail", "commit refused: " + (c.stdout + c.stderr).strip()[:160]
        it["sha"] = git("rev-parse", "--short", "HEAD").stdout.strip()
        note = it["sha"]
        if any(stales_index(p) for p in paths):   # only the full gate sees this; say it here,
            it["stale_index"] = True              # before the manual list, which the ledger
            note += "; " + STALE_INDEX            # (300) and `status` (110) may truncate
        return "kept", note + (" manual: " + "; ".join(manual) if manual else "")
    finally:
        _free_slot(st, slot, changed)


# ------------------------------------------------------------------- the tick

def _finish(st, it):
    base = os.path.join(st["run"], it["id"])
    with open(base + ".exit", encoding="utf-8") as f:
        ex = json.load(f)
    text, j, is_err = read_out(st, it["id"])
    model, toks, dur = model_for(st, it), tokens_of(j), ex.get("dur") or 0
    low = text.lower()
    if (is_err or ex.get("rc") not in (0, None)) and any(k in low for k in QUOTA):
        st["stop"] = "quota: a session hit a usage limit; the loop stops and is never retried"
        it["status"] = "pending"
        if it.get("slot"):
            _free_slot(st, it["slot"], _changed(it["slot"], it.get("files", ())))
        ledger(st, it["id"], model, "quota-pause", it["attempts"], dur, toks, "usage limit hit; task unharmed")
        return
    if it["kind"] == "fix":
        reply = json_in(text) or {}
        v, note = gate(st, it)
        it["status"] = "kept" if v == "kept" else "discarded"
        if v == "no_change" and reply.get("outcome"):
            note = "%s: %s" % (reply["outcome"], reply.get("summary", ""))
        it["verdict"], it["note"] = v, note
        ledger(st, it["id"], model, v, it["attempts"], dur, toks, note)
        return
    res = json_in(text)
    if res is None or ex.get("note"):
        it["status"] = "failed"
        why = "ran out of turns before replying" if j.get("subtype") == "error_max_turns" else ""
        ledger(st, it["id"], model, "failed", it["attempts"], dur, toks,
               ex.get("note") or why or "reply was not JSON: " + text[-120:])
        return
    with open(base + ".result.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    it["status"] = "done"
    if it["kind"] == "review":
        for v in res.get("verdicts", []):
            if str(v.get("verdict")).lower() != "drop":
                continue
            try:
                f = by_id(st, v.get("id"))
            except KeyError:
                continue
            if f.get("status") != "kept" or not f.get("sha"):
                continue
            r = git("revert", "--no-edit", f["sha"])
            f["status"] = "dropped" if r.returncode == 0 else "kept"
            f["review"] = str(v.get("why", ""))[:240]
            ledger(st, f["id"], model, "dropped" if r.returncode == 0 else "drop-failed",
                   f["attempts"], 0, "-", "referee: " + f["review"])
    n = len(res.get("candidates", res.get("verdicts", [])))
    ledger(st, it["id"], model, "done", it["attempts"], dur, toks, "%d returned" % n)


def _ready(st, kinds):
    done = {i["id"] for i in st["items"] if i["status"] not in OPEN}
    cands = [i for i in st["items"] if i["status"] == "pending" and i["kind"] in kinds
             and all(d in done for d in i.get("deps", []))]
    if held(st):
        cands = [i for i in cands if i["kind"] != "fix"]
    cands.sort(key=lambda i: (-float(i.get("priority", 0)), i["id"]))
    return cands


def tick(st, kinds, parallel):
    """One pass: reap what finished (gating fixes one at a time), then start what may start."""
    for it in [i for i in st["items"] if i["status"] == "running"]:
        base = os.path.join(st["run"], it["id"])
        if os.path.exists(base + ".exit"):
            _finish(st, it)
        elif time.time() - it.get("launched", 0) > TIMEOUT[it["kind"]] + 180:
            it["status"] = "failed"
            if it.get("slot"):
                next(s for s in st["slots"] if s["path"] == it["slot"])["retired"] = "session lost"
            ledger(st, it["id"], model_for(st, it), "lost", it["attempts"], 0, "-", "no exit file")
        save(st)
    running = sum(1 for i in st["items"] if i["status"] == "running")
    if ("preflight" not in st and "fix" in kinds and not refuse_session(st)
            and any(i["kind"] == "fix" for i in _ready(st, kinds))):
        preflight(st)               # once per run, before the first fixer, never per tick
        save(st)
    for it in _ready(st, kinds):
        if running >= parallel or refuse_session(st):
            break
        if it["kind"] == "fix":
            slot = next((s for s in st["slots"] if not s["busy"] and not s["retired"]), None)
            if slot is None:
                continue
            head = git("rev-parse", "HEAD").stdout.strip()
            if git("checkout", "-q", "--detach", head, cwd=slot["path"]).returncode != 0:
                slot["retired"] = "could not move to the integration head"
                continue
            slot["busy"], it["slot"] = it["id"], slot["path"]
        for ext in (".exit", ".out", ".err", ".result.json"):
            if os.path.exists(os.path.join(st["run"], it["id"] + ext)):
                os.remove(os.path.join(st["run"], it["id"] + ext))
        with open(os.path.join(st["run"], it["id"] + ".prompt.txt"), "w", encoding="utf-8") as f:
            f.write(build_prompt(st, it))
        if not st.get("started"):
            st["started"] = time.time()
        st["sessions"] += 1
        it["status"], it["launched"] = "running", time.time()
        it["attempts"] += 1
        save(st)                    # counted before it starts: a crash cannot beat the cap
        spawn(st, it)
        running += 1
    save(st)
    return running


def status_line(st):
    tally = {}
    for i in st["items"]:
        tally.setdefault(i["kind"], {}).setdefault(i["status"], 0)
        tally[i["kind"]][i["status"]] += 1
    parts = ["%s %s" % (k, " ".join("%d %s" % (n, s) for s, n in sorted(v.items())))
             for k, v in sorted(tally.items())]
    why, hold = refuse_session(st), held(st)
    # One batched refresh for the run, not one per lane. A dropped fix was reverted: not counted.
    stale = [i["id"] for i in st["items"]
             if i["kind"] == "fix" and i["status"] == "kept" and i.get("stale_index")]
    return "%s  sessions %d/%d  clock %.0fm left  |  %s%s%s%s" % (
        time.strftime("%H:%M:%S"), st["sessions"], st["cap"], max(0.0, minutes_left(st)),
        "  |  ".join(parts), ("  |  STOP: " + why) if why else "",
        ("  |  " + hold) if hold else "",
        ("  |  %s (%s)" % (STALE_INDEX, ", ".join(stale))) if stale else "")


# ------------------------------------------------------------------ the route

def _tests_index():
    idx = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "tests", "test_*.py"))):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                idx[posix(os.path.relpath(p, ROOT))] = f.read()
        except OSError:
            pass
    return idx


def tests_for(rel, idx, limit=5):
    """The existing tests that name this module: the ones that can judge a change to it."""
    stem = os.path.basename(rel)
    if stem.endswith(".py"):
        stem = stem[:-3]
    if stem == "__init__":
        stem = rel.split("/")[-2]
    pat = re.compile(r"\b%s\b" % re.escape(stem))
    hits = sorted(((len(pat.findall(s)), t) for t, s in idx.items() if pat.search(s)), reverse=True)
    return [t for _, t in hits[:limit]]


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


_FILE_LINE = re.compile(r"^\S+\.\w+:\d+(?::\d+)?\s*")
# A quote that directly follows a file:line cite -- the compound shape -- never a literal in code.
_SPAN = re.compile(r'[\w./\\-]+\.[A-Za-z]\w*:\d+\s*(?:`([^`]{6,})`|"((?:[^"\\]|\\.){6,})")')
# One word, bare or quoted ("claude", `running`, running): never a line.
_WORD = re.compile(r"""^["'`]?\w+["'`]?$""")


def _evidence_spans(raw):
    """The ways one evidence string can name a line, most literal first.

    Seeds and scouts often send compound evidence: a.py:12 "quote"; b.py:4 `quote`.
    The whole string comes first, then the string with a file:line prefix removed, so a clean
    line is never cut down to a quoted token inside it; then each quoted span in reading order.
    A span counts only when it directly follows a file:line cite: a string literal inside a code
    line ("running", "claude") never does, so a line gone from the file stays vetoed rather
    than passing on a word quoted inside it. Nor does one word on its own, bare or quoted, cited
    or not: it is a substring of every line that holds it, so it anchors none, and the veto
    would move the seed to whichever line held it first.
    """
    raw = str(raw)
    out = [raw, _FILE_LINE.sub("", raw.strip(), count=1)]
    for m in _SPAN.finditer(raw):
        out.append(m.group(1) if m.group(1) is not None else m.group(2).replace('\\"', '"'))
    seen, spans = set(), []
    for s in out:
        n = _norm(s)
        if len(n) >= 6 and n not in seen and not _WORD.match(n):
            seen.add(n)
            spans.append(n)
    return spans


def veto(c):
    """Deterministic reasons a candidate never reaches a fixer. Checked before any model."""
    f = posix(str(c.get("file", "")))
    if re.match(r"(?:[A-Za-z]:)?/", f) or ".." in f.split("/"):
        return "outside the repo"  # join() would drop ROOT and read, then fix, the host's file
    if not f or not os.path.isfile(os.path.join(ROOT, f)):
        return "no such file"
    if f.startswith(FENCES):
        return "fenced"
    if f.startswith(EXAM) or f.startswith("tests/"):
        return "the exam is read-only"
    if f.startswith(OWNER_ONLY):
        return "owner-only"
    spans = _evidence_spans(c.get("evidence", ""))
    if not spans:
        return "no evidence line"
    with open(os.path.join(ROOT, f), encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    try:
        ln = int(c.get("line") or 0)
    except (TypeError, ValueError):
        ln = 0
    near = _norm(" ".join(lines[max(0, ln - 9): ln + 8]))
    for n, ev in enumerate(spans):
        hit = ev in near
        if not hit:
            for i, text in enumerate(lines, 1):
                if ev in _norm(text):
                    c["line"] = i      # the quote is real, the line number was off
                    hit = True
                    break
        if hit:
            if n:                      # compound evidence: keep the one span this file holds
                c["evidence"] = ev
            return ""
    return "evidence not found in the file"


def collect(st):
    """Every scout candidate plus any seeds, each with its veto and its area's reach."""
    out = []
    seeds = os.path.join(st["run"], "seeds.json")
    groups = []
    if os.path.exists(seeds):
        with open(seeds, encoding="utf-8") as f:
            groups.append(("SEED", json.load(f)))
    for it in st["items"]:
        p = os.path.join(st["run"], it["id"] + ".result.json")
        if it["kind"] == "scout" and it["status"] == "done" and os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                groups.append((it["id"], json.load(f).get("candidates", [])))
    file_area = {f: a for a, d in st["areas"].items() for f, _ in d["files"]}
    for src, cands in groups:
        for n, c in enumerate(cands if isinstance(cands, list) else [], 1):
            if not isinstance(c, dict):
                continue
            c = dict(c)
            c["id"] = "%s-%d" % (src, n)
            c["file"] = posix(str(c.get("file", "")))
            c["veto"] = veto(c)
            c["area"] = file_area.get(c["file"], "")
            c["blast"] = st["areas"].get(c["area"], {}).get("direct", 0)   # direct importers
            out.append(c)
    return out


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def new_test_path(st, cid, claimed=()):
    """A new test path no earlier run owns. Code decides, from the tree.

    Seeds reuse ids run to run (SEED-1 again), so the id alone collided with a committed
    test and refuse_item turned the item away as "an existing test is the exam". The run
    folder's name tags the path; a numeric suffix then walks until the path is free by the
    same check refuse_item uses (tracked in git) and on disk (an untracked leftover would
    let the `exists` acceptance pass without the fixer writing anything).
    """
    tag, cid = _slug(os.path.basename(os.path.normpath(st["run"]))), _slug(cid) or "item"
    stem = "tests/test_graph_%s_%s" % (tag, cid) if tag else "tests/test_graph_%s" % cid
    n = 1
    while True:
        p = stem + (".py" if n == 1 else "_%d.py" % n)
        if (p not in claimed and not os.path.exists(os.path.join(st["root"], p))
                and git("ls-files", "--error-unmatch", "--", p).returncode != 0):
            return p
        n += 1


def route(st):
    """Scout candidates -> veto -> jev_sweep -> proposed fix items. Writes two files, adds nothing."""
    sys.path.insert(0, os.path.join(ROOT, "harness", "jev"))
    import jev_sweep
    cands = collect(st)
    jev_sweep.resolve_many([c for c in cands if not c["veto"]], wave="graph")
    for c in cands:
        if c["veto"]:
            c["decision"] = {"route": "vetoed", "tier": None, "priority": 0.0,
                             "reason": "rule: " + c["veto"], "jev": None}
    idx = _tests_index()
    claimed = set()
    groups = {}
    for c in cands:
        if c["decision"]["route"] == "fix_now":
            groups.setdefault(c["file"], []).append(c)
    items = []
    for f, cs in groups.items():
        cs.sort(key=lambda c: -c["decision"]["priority"])
        tests = [t for t in tests_for(f, idx)]
        new_test = new_test_path(st, cs[0]["id"], claimed)
        claimed.add(new_test)
        files = [f] + ([new_test] if f.endswith(".py") else [])
        run = [t for t in RATCHETS if os.path.exists(os.path.join(ROOT, t))] + tests
        accept = [{"kind": "pytest", "args": " ".join(run) + " -q -p no:cacheprovider"}] if run else []
        if f.endswith(".py"):
            accept.insert(0, {"kind": "exists", "path": new_test})
            accept.append({"kind": "pytest", "args": new_test + " -q -p no:cacheprovider"})
        change = "\n".join("- line %s: %s\n  evidence: %s\n  smallest fix: %s\n  proof: %s" % (
            c.get("line"), c.get("claim"), c.get("evidence"), c.get("fix"), c.get("check")) for c in cs)
        tier = "reasoning" if any(c["decision"]["tier"] != "mechanical" for c in cs) else "mechanical"
        items.append({"kind": "fix", "title": _norm(cs[0].get("claim", f))[:90], "files": files,
                      "change": change, "accept": accept, "tier": tier, "law": "sweep",
                      "priority": max(c["decision"]["priority"] for c in cs),
                      "blast": cs[0]["blast"], "from": [c["id"] for c in cs]})
    items.sort(key=lambda i: (-i["priority"], i["blast"], i["files"][0]))
    for n, it in enumerate(items, 1):
        it["id"] = "F%02d" % n
    with open(os.path.join(st["run"], "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(cands, f, indent=1)
    with open(os.path.join(st["run"], "fix_items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=1)
    return cands, items


def add_reviews(st, per=5):
    """One referee item per batch of kept commits that no referee has seen yet."""
    seen = {fid for i in st["items"] if i["kind"] == "review" for _, fid in i["commits"]}
    kept = [(i["sha"], i["id"]) for i in st["items"]
            if i["kind"] == "fix" and i["status"] == "kept" and i["id"] not in seen]
    n = sum(1 for i in st["items"] if i["kind"] == "review")
    new = []
    for k in range(0, len(kept), per):
        n += 1
        new.append({"id": "R%02d" % n, "kind": "review", "title": "referee %d kept commits" % len(kept[k:k + per]),
                    "commits": kept[k:k + per], "deps": [], "status": "pending", "attempts": 0})
    st["items"] += new
    return new


# --------------------------------------------------------------------- prompts

# Every session hears this, whatever its tools. Stash refs live in the shared .git, so one
# worktree's `git stash pop` can take another's stash: two lanes swapped patches on 2026-10-07.
GIT_RULES = """GIT: Never run git stash. Stash refs are shared by every worktree of this repo, so another
session can pop your stash and you can pop theirs. To see a test fail on the old code, run it before
you edit. If old code is ever needed as files, the only safe copy is
git archive <rev> python | tar -x -C <scratch> with PYTHONPATH pointed at the scratch copy;
a plain git show <rev>:<path> breaks package imports.
"""

SCOUT = """You are a read-only scout for SYNAPSE, an AI assistant that runs inside SideFX Houdini.
You are node %(id)s of a work graph. You read. You never edit a file, never run code, never start a subagent.

YOUR AREA: %(areas)s   (%(blast)s other areas import it)
YOUR FILES (%(n)s files, %(lines)s lines):
%(files)s

WHAT TO LOOK FOR: defects that a program can judge. Nothing else.
 1. error_path  - a path that cannot work as written: an undefined name, the wrong variable, a format
                  string whose arguments do not match it, an except branch that raises instead of falling back.
 2. false_text  - text that states something the code beside it does not do: a tooltip, a label, an error
                  message, a docstring or a help line naming the wrong file, path, command, count or behaviour.
 3. disagrees   - a value that disagrees with its own source of truth inside this repo: a duplicated constant,
                  a version string, a tool or argument name that differs between where it is defined and used.
 4. bad_call    - a call that cannot succeed and needs no Houdini to say so: wrong argument count, a misspelled
                  attribute on a plain Python object defined in this repo.

NOT WANTED: style, naming taste, refactors, missing features, performance guesses, type hints, TODOs.
If judging it needs Houdini itself (a node type, a parameter name, a cook, a render, a viewport), report it
with needs_houdini true. It will be listed for the owner. It will not be fixed here.

FENCES: never report inside python/synapse/server/handlers_tops/, python/synapse/_vendor/, harness/,
tests/fixtures/ or rag/catalog/. Existing tests are the exam: read them to learn what is expected,
never propose changing one.

%(git)s
METHOD: Grep first, then Read around each hit. Open the real file and confirm every claim before you
report it. A wrong report costs a whole session downstream, so five true ones beat fifteen guesses.
Stop at 6 candidates. You may read any file in the repo to check a claim.
You have about %(turns)s tool calls. Spend at most three quarters of them reading, then write your
reply. A scout that runs out of calls before replying has reported nothing.
%(brief)s

REPLY with one JSON object and nothing after it:
{"scout":"%(id)s","read_files":0,"candidates":[{
 "file":"<repo path>","line":0,
 "kind":"error_path|false_text|disagrees|bad_call",
 "claim":"<one sentence: what is wrong>",
 "evidence":"<ONE line copied exactly from that file at that line>",
 "fix":"<the smallest change, in words, naming the exact new text or name>",
 "check":"<how a program proves the fix: an existing test file to run, or what a new ten-line test asserts>",
 "needs_houdini":false}]}
An empty candidates list is a good answer when the area is clean.
"""

FIX = """

=== YOUR CARD (one card, surgical) ===
%(card)s

Rules for this graph run:
- Edit only the files listed in "files". A listed path under tests/ that does not exist yet is a new test
  for you to create. No other test, fixture or harness file may change: they are the exam.
- First open the file and confirm the finding. If it is not a real defect, change nothing and answer
  "not-a-bug". If the right fix needs Houdini to judge, change nothing and answer "needs-houdini".
  If it needs more than about 30 changed lines, change nothing and answer "too-big".
- Make the smallest change that fixes it. In the new test file, write a short test that fails before
  your change and passes after it, without Houdini.
- The only command you may run is: python -m pytest <test files named in the card> -q -m "not needs_houdini"
- Do not commit. Do not start a subagent. The gate decides what is kept.
%(git)s- Reply with one JSON object and nothing after it:
  {"id":"%(id)s","outcome":"changed|not-a-bug|needs-houdini|too-big","summary":"<two sentences>"}
"""

REVIEW = """You are the referee for a work graph run on SYNAPSE, an AI assistant inside SideFX Houdini.
You are node %(id)s. You read. You never edit a file, never run code, never start a subagent.

Each block below is one commit a fixer made and a test gate kept. The gate only proves that tests
pass. You decide whether the change deserves to stay. You may Read and Grep the tree for context.

DROP a commit when any of these is true:
- it does more than its card says;
- it changes what an artist would see or how a scene is built, beyond correcting the stated defect;
- its new test cannot fail: it would pass with the fix removed;
- the fix is wrong, or the original code was right.
Otherwise KEEP it. When unsure, drop: a dropped fix is a line in a report, a wrong one ships.

%(git)s
%(blocks)s

Reply with one JSON object and nothing after it:
{"verdicts":[{"id":"<card id>","verdict":"keep|drop","why":"<one sentence>"}]}
"""


# ------------------------------------------------------------------------- cli

def _houdini_alive():
    if os.name != "nt":
        return False
    tl = subprocess.run(["tasklist"], capture_output=True, text=True, errors="replace").stdout.lower()
    return any(k in tl for k in ("houdini", "hindie"))


def cmd_init(a):
    os.makedirs(a.run, exist_ok=True)
    if os.path.exists(state_path(a.run)):
        sys.exit("a graph run already lives in %s" % a.run)
    alive = _houdini_alive()
    if alive and not a.live_seat_ok:
        sys.exit("a Houdini process is running. rope refuses here because it edits the tree Houdini "
                 "serves. If this graph runs in a worktree of its own, pass --live-seat-ok \"<why it "
                 "is safe>\"; the reason is written to the ledger.")
    slots = []
    for n in range(1, a.nslots + 1):
        p = os.path.join(a.slots, "s%d" % n)
        if not os.path.exists(p):
            r = git("worktree", "add", "-q", "--detach", p, "HEAD", timeout=600)
            if r.returncode != 0:
                sys.exit("could not create slot %s: %s" % (p, r.stderr.strip()))
        slots.append({"path": p, "busy": "", "retired": ""})
    areas = code_graph()
    models = dict(kv.split("=", 1) for kv in a.models.split(",") if "=" in kv)
    st = {"version": "rope-graph/1", "root": ROOT, "run": os.path.abspath(a.run),
          "base": git("rev-parse", "HEAD").stdout.strip(),
          "branch": git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
          "cap": a.cap, "sessions": 0, "minutes": a.minutes, "started": None, "stop": "",
          "parallel": a.parallel, "models": models, "trailer": a.trailer, "slots": slots,
          "areas": areas, "items": plan_scouts(areas, a.scouts)}
    hold = preflight(st)
    save(st)
    if alive:
        ledger(st, "INIT", "-", "live-seat-override", 0, 0, "-", a.live_seat_ok)
    print("graph ready: %d areas, %d scout items, cap %d, %d minutes, %d slots"
          % (len(areas), len(st["items"]), a.cap, a.minutes, len(slots)))
    if hold:
        print("WARNING " + hold + "\n  scouts may run; every fix item waits until the base is green "
              "and `tick` is run again.")


def cmd_tick(a):
    kinds = tuple(k for k in a.kinds.split(",") if k)
    st = load(a.run)
    if "fix" in kinds and held(st):  # a red base is re-checked once per `tick` command: the repair
        del st["preflight"]         # (a refreshed master ref) need not move HEAD
        save(st)
    while True:
        st = load(a.run)
        running = tick(st, kinds, a.parallel or st["parallel"])
        print(status_line(st), flush=True)
        if not a.loop:
            return
        if not running and (refuse_session(st) or not _ready(st, kinds)):
            print("nothing running and nothing may start: this stage is over.", flush=True)
            return
        time.sleep(a.loop)


def cmd_route(a):
    st = load(a.run)
    cands, items = route(st)
    tally = {}
    for c in cands:
        tally[c["decision"]["route"]] = tally.get(c["decision"]["route"], 0) + 1
    print("candidates %d: %s" % (len(cands), ", ".join("%s %d" % kv for kv in sorted(tally.items()))))
    print("proposed fix items: %d  ->  %s" % (len(items), os.path.join(a.run, "fix_items.json")))


def cmd_add(a):
    st = load(a.run)
    with open(a.items, encoding="utf-8") as f:
        items = json.load(f)
    refused = add_items(st, items)
    save(st)
    print("added %d, refused %d" % (len(items) - len(refused), len(refused)))
    for iid, why in refused:
        print("  refused %s: %s" % (iid, why))


def cmd_review(a):
    st = load(a.run)
    new = add_reviews(st, a.per)
    save(st)
    print("referee items added: %d" % len(new))


def cmd_status(a):
    st = load(a.run)
    print(status_line(st))
    for it in st["items"]:
        if it["kind"] != "scout":
            print("  %-4s %-9s %s  %s" % (it["id"], it["status"], it.get("sha", "       "),
                                           it.get("note", it["title"])[:110]))


def cmd_map(a):
    areas = code_graph()
    for name in sorted(areas, key=lambda n: (areas[n]["direct"], areas[n]["blast"], n)):
        d = areas[name]
        print("%-14s imported by %2d directly, %2d in all  files %3d  lines %6d  imports: %s"
              % (name, d["direct"], d["blast"], len(d["files"]), d["lines"], ", ".join(d["imports"]) or "-"))


def main():
    ap = argparse.ArgumentParser(description="rope graph: a capped, clocked work graph")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("map").set_defaults(fn=cmd_map)
    p = sub.add_parser("init")
    p.add_argument("--run", required=True)
    p.add_argument("--slots", required=True)
    p.add_argument("--nslots", type=int, default=6)
    p.add_argument("--cap", type=int, default=50)
    p.add_argument("--minutes", type=int, default=60)
    p.add_argument("--scouts", type=int, default=22)
    p.add_argument("--parallel", type=int, default=6)
    p.add_argument("--models", default="", help="tier=model,... overrides rails_exec.json for this run")
    p.add_argument("--trailer", default="", help="appended to every commit message of this run")
    p.add_argument("--live-seat-ok", default="", metavar="WHY")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("tick")
    p.add_argument("--run", required=True)
    p.add_argument("--kinds", default="scout,fix,review")
    p.add_argument("--parallel", type=int, default=0)
    p.add_argument("--loop", type=int, default=0, metavar="SECONDS")
    p.set_defaults(fn=cmd_tick)
    for name, fn in (("route", cmd_route), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        p.set_defaults(fn=fn)
    p = sub.add_parser("add")
    p.add_argument("--run", required=True)
    p.add_argument("items")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("review")
    p.add_argument("--run", required=True)
    p.add_argument("--per", type=int, default=5)
    p.set_defaults(fn=cmd_review)
    p = sub.add_parser("_exec")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.set_defaults(fn=lambda a: _exec(a.run, a.id))
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
