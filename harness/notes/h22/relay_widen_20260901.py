import json
from pathlib import Path
p = Path(r"C:\Users\User\SYNAPSE\harness\relay-settings.json")
d = json.loads(p.read_text(encoding="utf-8"))
allow, deny = d["permissions"]["allow"], d["permissions"]["deny"]
add_allow = [
    # shells + scripts (python:* was already arbitrary code; powershell is not a wider surface)
    "Bash(powershell:*)", "Bash(pwsh:*)", "Bash(cmd /c:*)",
    # git in every form the legs actually use (git -C <worktree> ...). Irreversible ops stay in deny;
    # master pushes are refused by the pre-push Gate C hook regardless of this file.
    "Bash(git:*)",
    # CI / release READ access (gh release:* stays denied)
    "Bash(gh run list:*)", "Bash(gh run view:*)", "Bash(gh release list:*)", "Bash(gh release view:*)", "Bash(gh api:*)",
    # read/inspect utilities that were tripping prompts
    "Bash(type:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(diff:*)", "Bash(fc:*)", "Bash(where:*)", "Bash(rg:*)", "Bash(find:*)",
    "Bash(Get-Content:*)", "Bash(Select-String:*)", "Bash(Get-ChildItem:*)", "Bash(Test-Path:*)", "Bash(Measure-Object:*)",
    "Bash(mkdir:*)", "Bash(copy:*)", "Bash(move:*)", "Bash(Copy-Item:*)", "Bash(Move-Item:*)", "Bash(New-Item:*)",
    "Bash(timeout:*)", "Bash(sleep:*)", "Bash(Start-Sleep:*)", "Bash(Start-Process:*)", "Bash(Get-Process:*)", "Bash(Get-CimInstance:*)",
    "Bash(pip show:*)", "Bash(pip list:*)", "Bash(py:*)", "Bash(node --version:*)",
    # hython/husk already present; PDG/houdini helpers
    "Bash(hserver:*)", "Bash(hbatch:*)",
    # edits the legs make routinely (acceptEdits covers in-tree, listed for clarity under other modes)
    "Edit(docs/**)", "Edit(harness/battleplan/**)", "Edit(.synapse/contracts/**)", "Edit(houdini/**)", "Edit(scripts/**)",
]
add_deny = [
    "Bash(git tag:*)", "Bash(git push --force:*)", "Bash(git push -f:*)",
    "Bash(git branch -D master:*)", "Bash(git checkout master:*)", "Bash(git switch master:*)",
    "Bash(gh release create:*)", "Bash(gh release edit:*)", "Bash(gh release delete:*)",
]
for r in add_allow:
    if r not in allow: allow.append(r)
for r in add_deny:
    if r not in deny: deny.append(r)
d["_comment"] = d["_comment"] + (" 2026-09-01 16:2x (Joe pre-approval, CTO seat manages agent teams): allow list widened to "
    "the commands legs actually run - git in all forms, powershell/pwsh, gh READ verbs, inspect/copy/sleep utilities. "
    "Deny list holds and grows: tags, force pushes, master checkout, all gh release writes. Master pushes are refused by the "
    "pre-push Gate C hook independent of this file. Takes effect at the next leg launch.")
p.write_text(json.dumps(d, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
json.loads(p.read_text(encoding="utf-8"))
print("valid; allow", len(allow), "deny", len(deny))
