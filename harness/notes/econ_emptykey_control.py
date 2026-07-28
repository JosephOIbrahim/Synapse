"""Control for R164 - an empty env var must not shadow the repo .env.

V3-F6, measured with a paired control on the same repo root and the same .env:

    ANTHROPIC_API_KEY=''   -> get_anthropic_api_key() returns None
    variable absent        -> returns the key

`_load_dotenv` used os.environ.setdefault, and setdefault is a NO-OP when the
key exists. An empty string exists. So any shell that exports the variable blank
- or any launcher that BLANKS rather than UNSETS - permanently shadowed the .env,
and the product reported itself unconfigured while holding a valid key.

A user who has just funded an account and sees "unconfigured" concludes the
funding failed.

Asserts BOTH directions, because a fix that always overwrites would be worse:
a real key exported in the environment must still win over the .env.
"""
import importlib, os, sys

sys.path.insert(0, "python")


def resolve(env_value):
    """Fresh import with ANTHROPIC_API_KEY set as given (None = absent)."""
    for k in ("ANTHROPIC_API_KEY", "SYNAPSE_ANTHROPIC_KEY"):
        os.environ.pop(k, None)
    if env_value is not None:
        os.environ["ANTHROPIC_API_KEY"] = env_value
    for m in [m for m in sys.modules if m.startswith("synapse.host.auth")]:
        del sys.modules[m]
    auth = importlib.import_module("synapse.host.auth")
    got = auth.get_anthropic_api_key()
    return bool(got), (got or "")


print("scenario                          resolves?  note")
print("-" * 62)

absent_ok, absent_key = resolve(None)
print("%-33s %-10s %s" % ("variable ABSENT", absent_ok, "reads .env"))

empty_ok, empty_key = resolve("")
print("%-33s %-10s %s" % ("variable EMPTY ''", empty_ok, "must ALSO read .env (R164)"))

real_ok, real_key = resolve("sk-test-explicit-override")
print("%-33s %-10s %s" % ("variable SET to a real value", real_ok,
                          "must WIN over .env"))

print()
ok_absent = absent_ok
ok_empty = empty_ok and empty_key == absent_key
ok_override = real_ok and real_key == "sk-test-explicit-override"

print("absent resolves from .env       :", ok_absent)
print("EMPTY also resolves from .env   :", ok_empty, " <- the fix")
print("explicit value still overrides  :", ok_override, " <- not broken by the fix")

allok = ok_absent and ok_empty and ok_override
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
