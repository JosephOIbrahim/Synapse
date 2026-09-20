# adds the 'release' guard to harness/jev/questions.json (idempotent)
import json
from pathlib import Path
p = Path(r"C:\Users\User\SYNAPSE\harness\jev\questions.json")
q = json.loads(p.read_text(encoding="utf-8"))
q["guards"]["release"] = {
    "edge": "release ritual: docs/releases notes -> tree (triple-check leg 3); failing CI test -> failure kind",
    "questions": {
        "claim": {
            "type": "choice",
            "_comment": "instantiated once per claim as c<i>",
            "instructions": {
                "task": "Read `claims[{i}]`, one paragraph or bullet from the release notes. Using only `evidence` (files changed since the previous tag, commit subjects, newly added files), is the claim supported?",
                "rules": [
                    "A claim naming a file, directory, test count, or script that appears in the evidence is supported.",
                    "A claim about behaviour that the evidence cannot show either way (a measured number, a runtime effect) is partial, not unsupported.",
                    "Text that describes what is NOT in the release, or explains history, is not_a_claim.",
                    "A claim naming something the evidence contradicts (a file that does not appear, a component the diff never touched) is unsupported."
                ]
            },
            "criteria": {
                "supported": "The evidence names the files or commits the claim describes.",
                "partial": "On topic, but the diff stat cannot show the specific effect claimed.",
                "unsupported": "The evidence contradicts the claim or shows nothing related.",
                "not_a_claim": "Scope notes, history, caveats: nothing to verify against the tree."
            }
        },
        "failure_kind": {
            "type": "choice",
            "instructions": "A CI test failed. From `assertion` (the pytest failure text), `file_read_by_test`, and `file_recent_commits`, what kind of failure is this? Whether it pre-exists is decided elsewhere; judge only the kind.",
            "criteria": {
                "phrasing_drift": {"what": "The test pins a literal sentence from a doc, and the doc was rewritten while the fact it stated survives.", "examples": ["assert 'synced by X' in CLAUDE.md after a docs rewrite commit"]},
                "claim_drift": {"what": "A doc or banner carries a version, count, or tag that a bump elsewhere did not propagate.", "examples": ["README 'v5.75.2 is Latest' vs VERSION 5.76.0"]},
                "behavior_regression": {"what": "Code under test returns a different value or raises; the assertion is about runtime behaviour, not text."},
                "environment": {"what": "Import error, missing binary, path or platform difference, timeout."},
                "unknown": "The assertion text does not say enough to classify."
            }
        }
    },
    "policy": {"supported_min": 0.75, "unsupported_min": 0.60}
}
p.write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("release guard:", "release" in q["guards"])
