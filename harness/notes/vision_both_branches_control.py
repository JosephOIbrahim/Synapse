"""Both branches of _execute_tool_block must attach. Not one.

THE DEFECT THIS PINS, and it cost two restarts to find.

`_execute_tool_block` has two paths: MCP first, then a Qt-signal fallback to the
main-thread executor. The first version of the vision attach wired ONLY the MCP
branch. So whether a viewport capture reached the model depended on which route
its tool happened to take - which is not a decision anyone made.

Measured live: Fable 5, vision-capable, on a session that HAD the code, answered
"the capture tool gives me the image file, but it doesn't stream the pixels back
to me." It was exactly right. The attach was sitting on the branch its tool did
not take.

That is 'built and connected to nothing' with the connection HALF made - harder
to spot than not making it at all, because the code is present, the tests pass,
and it works on whichever path you happen to test.

A source-level assertion rather than a behavioural one, deliberately: the two
branches differ only in where the result came from, and mocking the Qt executor
to prove it would test the mock. What matters is that neither branch can return
a tool_result without passing through the attach.
"""
import ast
import sys

SRC = "python/synapse/panel/claude_worker.py"
src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)

ok = {}
ok["module parses"] = True

# Find _execute_tool_block and walk ITS returns only.
fn = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_execute_tool_block":
        fn = node
        break
ok["_execute_tool_block found"] = fn is not None

if fn is not None:
    # Every `return` that yields a NON-ERROR tool_result must be a bare name
    # that the attach has already rewritten - not a dict literal built inline.
    inline_success_dicts = 0
    returns_result_name = 0
    for node in ast.walk(fn):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        v = node.value
        if isinstance(v, ast.Dict):
            keys = [k.value for k in v.keys if isinstance(k, ast.Constant)]
            vals = dict(zip(keys, v.values))
            err = vals.get("is_error")
            is_err = isinstance(err, ast.Constant) and err.value is True
            if "type" in keys and not is_err:
                inline_success_dicts += 1
        elif isinstance(v, ast.Name) and v.id == "result":
            returns_success_name = True
            returns_result_name += 1

    ok["no inline SUCCESS dict escapes the attach"] = inline_success_dicts == 0
    ok["both branches return the attached name"] = returns_result_name >= 2

    calls = sum(1 for n in ast.walk(fn)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "attach_image")
    ok["attach_image called on both branches"] = calls == 2

print("%-44s %s" % ("ASSERTION", "RESULT"))
print("-" * 56)
for k, v in ok.items():
    print("%-44s %s" % (k, v))

allok = all(ok.values())
print()
print("RESULT:", "PASS" if allok else "FAIL - a branch can return a capture with no image")
sys.exit(0 if allok else 1)
