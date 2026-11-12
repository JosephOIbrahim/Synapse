# jev_release.py - JEV-RELEASE guard: two judgments the release ritual made by hand on 2026-09-20.
#   notes  : each claim in docs/releases/v<tag>.md against the diff stat + commit subjects since the
#            previous tag (citation-check shape). Output: one line per claim, SUPPORTED/PARTIAL/UNSUPPORTED.
#            This is the third leg of the triple-check; the other two (GitHub state, CI) stay exact code.
#   triage : a failing test's assertion text + the recent history of the file it reads -> a class.
#            Whether the failure PRE-EXISTS stays exact (run the test on the prior commit); Jev only
#            says what KIND of failure it is, so the operator knows which fix shape to reach for.
# Fail closed: no answer -> every claim REFEREE (read it yourself), every failure 'unknown'.
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = jc.REPO


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def _claims(notes: str) -> list[str]:
    body = notes.split("\n## ", 1)[1] if "\n## " in notes else notes
    out = []
    for para in re.split(r"\n\s*\n|\n(?=- )", body):
        p = " ".join(para.split())
        if len(p) > 40 and not p.startswith("#"):
            out.append(p[:600])
    return out[:20]


# A path-like token: something with a directory separator and a short extension.
# Bare filenames are deliberately NOT matched -- a claim saying "decide.py" is
# naming a thing, not asserting a location, and demanding it exist at the repo root
# would manufacture false defects in the other direction.
_PATH_TOKEN = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_][A-Za-z0-9_./-]*/"
                         r"[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,6})\b")


def claim_paths(claim: str) -> list:
    """Repo-relative paths a claim names. Templates and absolutes are not asserted."""
    out = []
    for m in _PATH_TOKEN.finditer(str(claim)):
        tok = m.group(1).strip(".,;:()")
        if "<" in tok or ">" in tok or tok.startswith(("/", "\\")):
            continue
        if re.match(r"^[A-Za-z]:", tok):
            continue
        out.append(tok)
    return out


def missing_paths(claim: str, root=None) -> list:
    """Every path the claim names that does not exist under ``root``.

    The release guard judges claims against a diff stat and commit subjects. Neither
    can see whether a path a claim names is in the tree being judged: a note claiming
    a module ships scored 0.84 supported and 0.79 confidence while that module was
    absent from master. A stronger threshold would not have caught it -- the model was
    answering the question it was asked. This is the question it was not asked.
    """
    base = Path(root) if root is not None else REPO
    return [tok for tok in claim_paths(claim) if not (base / tok).exists()]


def final_verdict(claim, choice, confidence, probabilities, policy, root=None):
    """The claim's verdict, with existence outranking the model.

    Returns (verdict, missing). A claim naming a path that is not in the tree is
    UNSUPPORTED whatever the model scored: the evidence contradicts it, and that is
    a fact rather than a judgment.
    """
    verdict = classify_claim(choice, confidence, probabilities, policy)
    missing = missing_paths(claim, root)
    if missing:
        return "UNSUPPORTED", missing
    return verdict, []


def classify_claim(choice, confidence, probabilities, policy) -> str:
    """The one release verdict. Code owns the thresholds; the model supplies a distribution.

    THE MODEL'S ARGMAX IS NOT THE VERDICT. A claim the model labelled `unsupported`
    but placed only 0.35 probability on is a PARTIAL, not an UNSUPPORTED: the
    distribution says it is not confident enough to condemn the claim. Reading the
    label as the verdict turned four partials into four false defects on 2026-11-11,
    which is why this lives in one function that every caller reaches.

    Returns UNSUPPORTED, SUPPORTED or PARTIAL. A caller with no answer at all is
    REFEREE, and that decision belongs to the caller because it is about a missing
    answer rather than about this one.
    """
    p = probabilities or {}
    if p.get("unsupported", 0) >= policy["unsupported_min"]:
        return "UNSUPPORTED"
    if choice == "supported" and (confidence or 0) >= policy["supported_min"]:
        return "SUPPORTED"
    return "PARTIAL"


def notes(tag: str, prev: str) -> int:
    path = REPO / "docs" / "releases" / f"{tag}.md"
    text = path.read_text(encoding="utf-8")
    claims = _claims(text)
    evidence = {
        "files_changed": _git("diff", "--stat", f"{prev}..{tag}").strip()[-6000:],
        "commit_subjects": _git("log", "--format=%s", f"{prev}..{tag}").strip()[:3000],
        "new_files": _git("diff", "--name-only", "--diff-filter=A", f"{prev}..{tag}").strip()[:3000],
    }
    g = jc.load_questions()["guards"]["release"]["questions"]["claim"]
    spec, state = {}, {"claims": claims, "evidence": evidence}
    for i in range(len(claims)):
        spec[f"c{i}"] = {"type": "choice",
                         "instructions": json.loads(json.dumps(g["instructions"]).replace("{i}", str(i))),
                         "criteria": g["criteria"]}
    a = jc.ask(state, spec, wave=tag, guard="release.notes", leg=tag)
    pol = jc.load_questions()["guards"]["release"]["policy"]
    bad = 0
    for i, c in enumerate(claims):
        r = (a or {}).get("choices", {}).get(f"c{i}")
        if r is None:
            v, _missing = "REFEREE", []
        else:
            v, _missing = final_verdict(c, r.get("choice"), r.get("confidence"),
                                        r.get("probabilities"), pol)
        bad += v in ("UNSUPPORTED", "REFEREE")
        note = f"  [missing: {', '.join(_missing)}]" if _missing else ""
        print(f"{v:11} {c[:96]}{note}")
    print(f"-- {len(claims)} claims, {bad} need a human read; ledger harness/jev/ledger/{tag}.release.notes.jsonl")
    return 1 if bad else 0


def triage(test: str, assertion: str, reads: str) -> int:
    hist = _git("log", "-4", "--format=%h %ad %s", "--date=short", "--", reads).strip()
    state = {"test": test, "assertion": assertion[:1500], "file_read_by_test": reads, "file_recent_commits": hist}
    g = jc.load_questions()["guards"]["release"]["questions"]["failure_kind"]
    a = jc.ask(state, {"kind": {"type": "choice", "instructions": g["instructions"], "criteria": g["criteria"]}},
               wave="triage", guard="release.triage", leg=test)
    r = (a or {}).get("choices", {}).get("kind")
    if r is None:
        print(f"unknown     {test}  (fallback)")
        return 1
    top = sorted(r["probabilities"].items(), key=lambda kv: -kv[1])[:2]
    print(f"{r['choice']:22} {test}  " + "  ".join(f"{k}={v:.2f}" for k, v in top))
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("notes"); n.add_argument("--tag", required=True); n.add_argument("--prev", required=True)
    t = sub.add_parser("triage"); t.add_argument("--test", required=True); t.add_argument("--assertion", required=True)
    t.add_argument("--reads", required=True, help="repo path the test reads")
    a = ap.parse_args()
    sys.exit(notes(a.tag, a.prev) if a.cmd == "notes" else triage(a.test, a.assertion, a.reads))
