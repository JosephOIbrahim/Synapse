#!/usr/bin/env python
"""Local executor: run one rope task through an Ollama model (zero API tokens).

Same contract as the claude executor: read the task, edit the files, exit.
The harness's accepts + commits stay identical -- the judge doesn't care who
edited. Protocol: the model must answer ONLY with full-file blocks:

<<<FILE path/relative/to/repo
...entire new file content...
>>>END

Files not echoed back are left untouched. Honest scope (L1): good for small
files (docs, manifests, qss, tests). 2000-line surgery waits for a big model.
"""
import argparse, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROPE = os.path.join(ROOT, "harness", "rope")
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    st = json.load(open(os.path.join(ROPE, "STATE.json"), encoding="utf-8"))
    t = next(x for x in st["tasks"] if x["id"] == args.task)

    parts = ["You are a precise code editor. Task card:", json.dumps(
        {k: t[k] for k in ("id", "title", "change", "files")}, indent=1),
        "\nCurrent file contents:"]
    for f in t.get("files", []):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            try:
                parts.append("\n=== %s ===\n%s" % (f, open(p, encoding="utf-8").read()))
            except OSError:
                parts.append("\n=== %s === (unreadable)" % f)
        else:
            parts.append("\n=== %s === (does not exist yet -- create it)" % f)
    parts.append(
        "\nRespond ONLY with one or more blocks, nothing else:\n"
        "<<<FILE relative/path\n<entire new file content>\n>>>END\n"
        "Echo a file ONLY if you change or create it. Full content, no diffs.")
    prompt = "\n".join(parts)

    req = urllib.request.Request(
        OLLAMA + "/api/chat", method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"model": args.model, "stream": False,
                         "options": {"num_ctx": 32768, "temperature": 0.2},
                         "messages": [{"role": "user", "content": prompt}]}).encode())
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.load(r)["message"]["content"]

    print(out[:2000])   # into last_run.log via the runner's redirect
    wrote = 0
    pos = 0
    while True:
        a = out.find("<<<FILE", pos)
        if a < 0:
            break
        nl = out.find("\n", a)
        b = out.find(">>>END", nl)
        if nl < 0 or b < 0:
            break
        rel = out[a + 7:nl].strip().replace("\\", "/")
        body = out[nl + 1:b]
        if body.endswith("\n") is False:
            body += "\n"
        # safety: only files the task declared may be written
        if rel not in [x.replace("\\", "/") for x in t.get("files", [])]:
            print("REFUSED out-of-scope write: %s" % rel)
            pos = b + 6
            continue
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8", newline="\n").write(body)
        wrote += 1
        print("wrote %s (%d bytes)" % (rel, len(body)))
        pos = b + 6
    print("files written: %d" % wrote)
    sys.exit(0 if wrote else 3)

if __name__ == "__main__":
    main()
